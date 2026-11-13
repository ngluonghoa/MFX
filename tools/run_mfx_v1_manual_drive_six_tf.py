"""Owner-gated MFX 1.0: manual GitHub Actions GET-only Drive six-TF evidence.

Never a scheduled writer, vendor price caller, execution interface, or market
signal. This is an integration *capability*, not proof a real run occurred.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import re
from typing import Any
from urllib.parse import urlsplit

from mfx_research.six_tf_sealed_archive_consumer import (
    ReadOnlyObjectStore, SealedArchiveSixTFReceipt,
    consume_sealed_archives_for_six_tf,
)
from mfx_research.hourly_source_freshness import diagnose_hourly_m5_freshness
from mfx_research.signal_only_six_tf_response import (
    build_signal_only_research_response,
)
from mfx_research.ohlc_first_optional_bidask_policy import (
    classify_ohlc_first_mode,
)
from mfx_research.six_tf_private_candle_geometry import (
    compute_private_six_tf_candle_geometry,
)
from mfx_research.sealed_multibar_private_features import (
    PrivateMultiBarReceipt, VERSION as MULTIBAR_VERSION,
)
from mfx_research.sealed_private_pivot_sensitivity import (
    PrivatePivotSensitivityReceipt, VERSION as PRIVATE_PIVOT_VERSION,
    POLICY_WINDOWS,
)
from mfx_research.b2_s2_source_computation_crosswalk import (
    reconcile_b2s2_source_to_computation,
)
from mfx_research.sealed_private_m15_microbreak import (
    PrivateMicroBreakReceipt, compute_private_sealed_m15_microbreak,
)
from tools.run_a04_p45_cloud_twelve_data_cache import (
    CHUNK_FOLDER, MANIFEST_FOLDER, _drive_auth_info,
    _require_oauth_cache_folders, _session,
)
from tools.run_a04_p46_cloud_batch_cache import PrivateDriveBatchStore
from tools.mfx_native_htf_drive_seal import PrivateNativeDriveStore

VERSION = "MFX_V1_MANUAL_PRIVATE_DRIVE_GET_ONLY_SIX_TF_V1"
CONFIRMATION = "READ_ONLY_NO_SIGNAL"
READ_APPROVAL = "MFX_V1_SIX_TF_MANUAL_READONLY_APPROVED"
EXISTING_GATES = (
    "MFX_REAL_CACHE_ENABLED", "MFX_V2_BATCH_CACHE_ACCEPTED",
    "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED",
)
ALLOWED_PREFIXES = (
    "MFX_TD_EURUSD_M5_V2_", "MFX_TD_EURUSD_H4_NATIVE_V1_",
    "MFX_TD_EURUSD_D1_NATIVE_V1_",
)
DRIVE_API = "https://www.googleapis.com"
ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,160}$")
MAX_DRIVE_GETS = 8000


class GetOnlyDriveSession:
    """Narrow proxy: no POST/PATCH/PUT/DELETE/request, no vendor host."""

    __slots__ = ("__session", "get_count")

    def __init__(self, session: Any) -> None:
        if session is None or not callable(getattr(session, "get", None)):
            raise ValueError("MFX_V1_READONLY_INVALID_GET_SESSION")
        self.__session = session
        self.get_count = 0

    def get(self, url: str, *, params: dict[str, Any],
            timeout: int) -> Any:
        if (type(url) is not str or type(params) is not dict
                or type(timeout) is not int or not 1 <= timeout <= 60):
            raise ValueError("MFX_V1_READONLY_GET_ARGUMENTS_DENIED")
        u = urlsplit(url)
        if (u.scheme != "https" or u.netloc != "www.googleapis.com"
                or u.username is not None or u.password is not None
                or u.query or u.fragment):
            raise ValueError("MFX_V1_READONLY_GOOGLE_DRIVE_HOST_REQUIRED")
        if u.path == "/drive/v3/files":
            q = params.get("q")
            if (type(q) is not str
                    or not any(q.startswith(
                        f"'{folder}' in parents and name contains '"
                        ) for folder in (CHUNK_FOLDER, MANIFEST_FOLDER))
                    or not any(f"name contains '{prefix}" in q
                               for prefix in ALLOWED_PREFIXES)
                    or not q.endswith("and trashed = false")
                    or params.get("supportsAllDrives") != "true"
                    or params.get("includeItemsFromAllDrives") != "true"):
                raise ValueError("MFX_V1_READONLY_DRIVE_LIST_SCOPE_DENIED")
            allowed_keys = {
                "q", "pageSize", "fields", "supportsAllDrives",
                "includeItemsFromAllDrives", "pageToken",
            }
            if set(params) - allowed_keys:
                raise ValueError("MFX_V1_READONLY_LIST_EXTRA_ARGUMENT_DENIED")
        elif u.path.startswith("/drive/v3/files/"):
            file_id = u.path.rsplit("/", 1)[-1]
            if (ID_RE.fullmatch(file_id) is None
                    or params != {
                        "alt": "media", "supportsAllDrives": "true",
                    }):
                raise ValueError("MFX_V1_READONLY_FILE_SCOPE_DENIED")
        else:
            raise ValueError("MFX_V1_READONLY_NON_DRIVE_API_DENIED")

        if self.get_count >= MAX_DRIVE_GETS:
            raise ValueError("MFX_V1_READONLY_GET_REQUEST_LIMIT")
        self.get_count += 1
        return self.__session.get(url, params=params, timeout=timeout)


class ReadOnlyView:
    """Only list/read is reachable by the signal research consumer."""

    __slots__ = ("__store",)

    def __init__(self, store: Any) -> None:
        if (not callable(getattr(store, "list_names", None))
                or not callable(getattr(store, "read", None))):
            raise ValueError("MFX_V1_READONLY_STORE_CONTRACT_REQUIRED")
        self.__store = store

    def list_names(self, bucket: str) -> tuple[str, ...]:
        return self.__store.list_names(bucket)

    def read(self, bucket: str, name: str) -> dict[str, Any]:
        return self.__store.read(bucket, name)


def manual_dispatch_authorized(settings: dict[str, str]) -> bool:
    """Separate new owner flag; never inferred from legacy cache writers."""
    if type(settings) is not dict:
        return False
    return (settings.get(READ_APPROVAL) == "true"
            and settings.get("MFX_V1_READONLY_CONFIRMATION") == CONFIRMATION
            and all(settings.get(name) == "true" for name in EXISTING_GATES))


def private_get_only_probe(
    upstream_session: Any, *, asof_utc: datetime,
) -> tuple[SealedArchiveSixTFReceipt, int]:
    """Actual Drive access is supplied by GitHub OAuth, NEVER by this API.

    Fixed original source-reviewed M5 root/checkpoint pins are mandatory;
    synthetic fixture pin overrides are intentionally not an argument.
    """
    session = GetOnlyDriveSession(upstream_session)
    m5: ReadOnlyObjectStore = ReadOnlyView(PrivateDriveBatchStore(session))
    h4: ReadOnlyObjectStore = ReadOnlyView(
        PrivateNativeDriveStore(session, symbol="EUR/USD", interval="4h"))
    d1: ReadOnlyObjectStore = ReadOnlyView(
        PrivateNativeDriveStore(session, symbol="EUR/USD", interval="1day"))
    evidence = consume_sealed_archives_for_six_tf(
        m5, h4, d1, asof_utc=asof_utc)
    return evidence, session.get_count


def _safe_microbreak_public_history(status: str) -> str:
    """Never expose whether a private pivot or crossing was actually seen.

    Only input history sufficiency may cross into public GitHub logs; both
    'there is a known pivot' and 'there is no pivot' yield identical text.
    """
    if type(status) is not str:
        raise ValueError("MFX_V1_PRIVATE_M15_STATUS_TYPE_DENIED")
    if status in (
        "PRIVATE_PRIOR_CONFIRMED_M15_LEVEL_EVALUATED",
        "NO_PRIOR_RIGHT_CLOSED_M15_PIVOT",
    ):
        return "M15_CLOSED_HISTORY_ONLY_PRIVATE_EVENT_REDACTED"
    if status in (
        "M15_MISSING_OR_STALE",
        "INSUFFICIENT_CLOSED_M15_HISTORY",
    ):
        return status
    raise ValueError("MFX_V1_PRIVATE_M15_UNKNOWN_STATUS_DENIED")


def safe_summary(
    evidence: SealedArchiveSixTFReceipt, *, drive_gets: int,
) -> dict[str, Any]:
    """Only SHA/count/time/status metadata, NEVER raw OHLC/keys/Drive IDs."""
    if (type(evidence) is not SealedArchiveSixTFReceipt
            or type(drive_gets) is not int or not 0 <= drive_gets <= MAX_DRIVE_GETS
            or evidence.technical.action != "NO_SIGNAL"
            or evidence.technical.stage != "UNVERIFIED"
            or evidence.may_publish_buy_sell or evidence.may_trade
            or not evidence.github_reviewed_m5_anchors_checked):
        raise ValueError("MFX_V1_READONLY_UNSAFE_OR_UNVERIFIED_RECEIPT")
    full = (
        evidence.m5_sha_audit_mode == "FULL_BOUNDED_ALL_RAW_SHA"
        and evidence.all_three_bounded_sha_chains_verified
        and evidence.m5_full_historical_raw_sha_verified
        and evidence.m5_historical_raw_chunks_not_reread == 0
        and evidence.m5_total_archived_manifest_pairs ==
            evidence.m5_manifest_pairs_full_sha
        and evidence.m5_total_manifest_parent_chain_verified ==
            evidence.m5_total_archived_manifest_pairs
        and evidence.m5_recent_raw_sha_verified
    )
    rolling = (
        evidence.m5_sha_audit_mode ==
            "ROOT_PINNED_ALL_MANIFESTS_LATEST_256_CHUNKS"
        and not evidence.all_three_bounded_sha_chains_verified
        and not evidence.m5_full_historical_raw_sha_verified
        and evidence.m5_recent_raw_sha_verified
        and evidence.m5_manifest_pairs_full_sha == 256
        and evidence.m5_historical_raw_chunks_not_reread > 0
        and evidence.m5_total_manifest_parent_chain_verified ==
            evidence.m5_total_archived_manifest_pairs
        and evidence.m5_total_archived_manifest_pairs ==
            evidence.m5_historical_raw_chunks_not_reread + 256
    )
    if not (full or rolling):
        raise ValueError("MFX_V1_READONLY_UNSAFE_SHA_SCOPE_NOT_ESTABLISHED")
    technical = evidence.technical
    freshness = diagnose_hourly_m5_freshness(
        m5_latest_hour_utc=evidence.m5_latest_source_hour_utc,
        asof_utc=datetime.fromisoformat(technical.asof_utc),
    )
    if ((freshness["closed_source_slot_gaps"]["M5"] == 0)
            != ("M5" not in technical.missing_or_stale_frames)
            or (freshness["closed_source_slot_gaps"]["M15"] == 0)
            != ("M15" not in technical.missing_or_stale_frames)):
        raise ValueError("MFX_V1_READONLY_SOURCE_FRESHNESS_RECEIPT_DRIFT")
    # P0.149 presentation is now consumed by the ACTUAL existing optional
    # GitHub OAuth GET-only adapter, without making another Drive/vendor call.
    signal_only = build_signal_only_research_response(evidence)
    if (signal_only.action != "NO_SIGNAL"
            or signal_only.stage != "UNVERIFIED"
            or signal_only.quote_side != "MID"
            or signal_only.asof_utc != technical.asof_utc
            or signal_only.frames_present != tuple(
                f.frame for f in technical.frames)
            or signal_only.frames_missing_or_stale !=
                technical.missing_or_stale_frames
            or signal_only.may_publish_buy_sell or signal_only.may_trade):
        raise ValueError("MFX_V1_READONLY_SIGNAL_PRESENTATION_DRIFT")
    # Explicit owner-selected architecture: MID OHLC research does not need
    # a terminal or BID/ASK; live net-R:R does need separate licensed API data.
    # No additional Drive GET or quote request: classify the existing view.
    source_mode = classify_ohlc_first_mode(signal_only)
    # P0.154: the first REAL technical arithmetic over all PRESENT, sealed,
    # closed MID OHLC candles. Shapes remain private and in memory; do not
    # stringify prices, derived candle directions, body or wick calculations.
    private_geometry = compute_private_six_tf_candle_geometry(evidence)
    if (private_geometry.action != "NO_SIGNAL"
            or private_geometry.stage != "UNVERIFIED"
            or private_geometry.source_price_side != "MID"
            or private_geometry.may_publish_prices_or_derived_signals
            or private_geometry.may_trade
            or private_geometry.provider_requests
            or private_geometry.drive_price_cache_writes
            or private_geometry.broker_orders
            or len(private_geometry.shapes) != len(technical.frames)
            or private_geometry.frames_missing_or_stale !=
                technical.missing_or_stale_frames
            or private_geometry.source_fingerprint_sha256 !=
                signal_only.evidence_fingerprint_sha256):
        raise ValueError("MFX_V1_READONLY_PRIVATE_GEOMETRY_SOURCE_DRIFT")
    # P0.155: this is REAL history-based arithmetic computed *inside* the
    # existing source consumer from exactly the SAME SHA-validated buffers,
    # not an additional Drive read. Never log returns, TRs, derived highs,
    # lows, close direction, or the private input fingerprint.
    multibar = evidence.private_multibar
    if (type(multibar) is not PrivateMultiBarReceipt
            or multibar.version != MULTIBAR_VERSION
            or multibar.asof_utc != technical.asof_utc
            or multibar.action != "NO_SIGNAL"
            or multibar.stage != "UNVERIFIED"
            or multibar.source_price_side != "MID"
            or multibar.may_publish_prices_or_signals
            or multibar.may_trade or multibar.vendor_source_license_verified
            or multibar.first_known_publisher_verified
            or multibar.original_forex_numeric_source_approved
            or multibar.historical_asof_replay_proven
            or multibar.bidask_net_rr_available
            or multibar.confirmed_pivot_or_original_trend_inferred
            or multibar.provider_requests
            or multibar.drive_market_cache_writes
            or multibar.broker_orders
            or tuple(f.frame for f in multibar.frames) !=
                tuple(f.frame for f in technical.frames)
            or multibar.frames_missing_or_stale !=
                technical.missing_or_stale_frames
            or multibar.public_technical_context_complete !=
                technical.research_technical_context_complete):
        raise ValueError("MFX_V1_READONLY_MULTIBAR_PRIVATE_SCOPE_DRIFT")
    if any(
            (feature.observed_closed_candles < 1
             or feature.original_numeric_entry_source_approved
             or feature.data_rights_independently_verified
             or feature.provider_first_known_proven
             or feature.publishable_buy_sell
             or feature.latest_source_sha256_claim !=
                raw.evidence_sha256
             or feature.latest_source_label != raw.source_label)
            for feature, raw in zip(multibar.frames, technical.frames)):
        raise ValueError("MFX_V1_READONLY_MULTIBAR_SOURCE_DRIFT")
    # P0.156: strict right-candle closure research on the SAME source
    # buffers; no new Drive GET or price logs. These two exploratory pivot
    # window policies must NEVER become source-owner approved thresholds.
    pivot = evidence.private_pivot_sensitivity
    if (type(pivot) is not PrivatePivotSensitivityReceipt
            or pivot.version != PRIVATE_PIVOT_VERSION
            or pivot.asof_utc != technical.asof_utc
            or pivot.action != "NO_SIGNAL" or pivot.stage != "UNVERIFIED"
            or pivot.source_private_multibar_digest_sha256 !=
                multibar.private_input_digest_sha256
            or pivot.frames_missing_or_stale !=
                technical.missing_or_stale_frames
            or pivot.source_price_side != "MID"
            or pivot.original_forex_numeric_pivot_policy_approved
            or pivot.real_historical_first_known_verified
            or pivot.data_license_and_redistribution_verified
            or pivot.chronological_oos_acceptance
            or pivot.real_d1_session_continuity_qualified
            or pivot.net_bidask_rr_available
            or pivot.may_publish_price_derived_values_or_signals
            or pivot.may_trade or pivot.provider_requests
            or pivot.drive_cache_writes or pivot.broker_orders
            or len(pivot.studied) != len(POLICY_WINDOWS)*len(technical.frames)):
        raise ValueError("MFX_V1_READONLY_PIVOT_SENSITIVITY_AUTHORITY_DRIFT")
    for index, (left,right) in enumerate(POLICY_WINDOWS):
        batch=pivot.studied[
            index*len(technical.frames):(index+1)*len(technical.frames)]
        if (tuple(r.frame for r in batch) !=
                tuple(r.frame for r in technical.frames)
                or any(r.left_bars != left or r.right_bars != right
                       or r.source_price_side != "MID"
                       or r.real_data_rights_verified
                       or r.source_numeric_policy_verified
                       or r.may_publish_buy_sell
                       or any(p.independently_proven_first_known
                              or p.source_owner_numeric_rule_approved
                              or p.may_publish_buy_sell
                              for p in r.pivots)
                       or (r.frame == "D1" and
                           (r.status !=
                            "D1_SOURCE_SESSION_CALENDAR_UNVERIFIED"
                            or r.pivots))
                       for r in batch)):
            raise ValueError("MFX_V1_READONLY_PIVOT_SOURCE_POLICY_DRIFT")
    # P0.157: reconcile the EXACT 36 pinned B2/S2 owner obligations
    # against current private technical capability, NOT the source approval.
    # This re-checks local Git blob pins, not extra vendor/Drive GETs.
    source_crosswalk = reconcile_b2s2_source_to_computation(evidence)
    if (len(source_crosswalk.rows) != 36
            or source_crosswalk.original_b2s2_numeric_approvals
            or source_crosswalk.original_source_numeric_decisions_pending != 36
            or source_crosswalk.independently_authenticated_source_owner_formula
            or source_crosswalk.authorized_real_bidask_net_rr
            or source_crosswalk.original_forex_parity_proven
            or source_crosswalk.historical_oos_qualified
            or source_crosswalk.live_signal_release_approved
            or source_crosswalk.action != "NO_SIGNAL"
            or source_crosswalk.stage != "UNVERIFIED"
            or source_crosswalk.may_trade
            or source_crosswalk.provider_calls
            or source_crosswalk.drive_market_cache_writes
            or source_crosswalk.broker_orders):
        raise ValueError("MFX_V1_READONLY_SOURCE_COMPUTATION_36_NO_GO_DRIFT")
    # P0.158: independent re-check of the same private in-memory M15
    # computation. Never leak computed crossing direction or MID level.
    microbreak = evidence.private_m15_microbreak
    if (type(microbreak) is not PrivateMicroBreakReceipt
            or microbreak != compute_private_sealed_m15_microbreak(
                evidence.private_multibar, technical,
                evidence.private_pivot_sensitivity,
            )
            or microbreak.action != "NO_SIGNAL"
            or microbreak.stage != "UNVERIFIED"
            or microbreak.may_publish_prices_or_signals
            or microbreak.may_trade
            or microbreak.provider_requests
            or microbreak.drive_gets_added
            or microbreak.drive_writes
            or microbreak.broker_orders):
        raise ValueError("MFX_V1_READONLY_PRIVATE_M15_MICROBREAK_DRIFT")
    if (source_mode.publishable_buy_sell
            or source_mode.broker_order_integration
            or source_mode.requires_mt4_or_mt5_terminal
            or source_mode.bidask_quote_observed_and_licensed
            or source_mode.source_data_account_rights_verified):
        raise ValueError("MFX_V1_READONLY_OHLC_MODE_AUTHORITY_DRIFT")
    return {
        "schema": VERSION,
        "status": "MANUAL_AUTHENTICATED_DRIVE_GET_SOURCE_RESEARCH_ONLY",
        "action": "NO_SIGNAL",
        "stage": "UNVERIFIED",
        "asof_utc": technical.asof_utc,
        "sha_verified_source_freshness_timing": freshness,
        "frames_present": [f.frame for f in technical.frames],
        "frames_missing_or_stale": list(technical.missing_or_stale_frames),
        "technical_six_frame_ready": technical.research_technical_context_complete,
        "m5_manifest_chunk_pairs_full_sha": evidence.m5_manifest_pairs_full_sha,
        "m5_sha_audit_mode": evidence.m5_sha_audit_mode,
        "m5_full_historical_raw_sha_verified":
            evidence.m5_full_historical_raw_sha_verified,
        "m5_total_manifest_parent_chain_verified":
            evidence.m5_total_manifest_parent_chain_verified,
        "m5_total_archived_manifest_pairs":
            evidence.m5_total_archived_manifest_pairs,
        "m5_historical_raw_chunks_not_reread":
            evidence.m5_historical_raw_chunks_not_reread,
        "h4_manifest_chunk_pairs_full_sha": evidence.h4_manifest_pairs_full_sha,
        "d1_manifest_chunk_pairs_full_sha": evidence.d1_manifest_pairs_full_sha,
        "m5_tip_sha256": evidence.m5_manifest_tip_sha256,
        "h4_tip_sha256": evidence.h4_manifest_tip_sha256,
        "d1_tip_sha256": evidence.d1_manifest_tip_sha256,
        "reviewed_m5_source_pins_matched": True,
        "source_account_license_verified": False,
        "source_first_known_verified": False,
        "independent_external_witness_verified": False,
        "numeric_buy_sell_rules_approved": False,
        "bid_ask_cost_sl_tp_net_rr_approved": False,
        "historical_replay_oos_proven": False,
        "may_publish_buy_sell": False,
        "provider_price_requests": 0,
        "drive_reads": drive_gets,
        "drive_writes": 0,
        "broker_orders": 0,
        "raw_price_logged": False,
        "b2_s2_source_computation_crosswalk": {
            "status": "36_PINNED_OWNER_DECISIONS_PENDING_RESEARCH_ONLY",
            "source_locked_doc_id": source_crosswalk.source_locked_doc_id,
            "original_numeric_approvals":
                source_crosswalk.original_b2s2_numeric_approvals,
            "remaining_numeric_owner_decisions":
                source_crosswalk.original_source_numeric_decisions_pending,
            "original_forex_1to1_parity_proven": False,
            "licensed_real_bidask_net_rr": False,
            "first_known_verified": False,
            "historical_oos_approved": False,
            "public_signal_action": "NO_SIGNAL",
            "rows": [
                {
                    "rule_id": row.rule_id,
                    "requirement_id": row.source_requirement_id,
                    "phase": row.phase,
                    "original_source_paragraph_index":
                        row.original_source_paragraph_index,
                    "private_computation_state":
                        row.observed_research_state,
                    "original_numeric_owner_approved": False,
                } for row in source_crosswalk.rows
            ],
            "published_ohlc_or_private_pivot_price": False,
            "provider_requests_added": 0,
            "drive_gets_added": 0,
            "drive_writes": 0,
            "broker_orders": 0,
        },
        "private_m15_microbreak": {
            "status": "PRIVATE_CLOSED_M15_PREKNOWN_PIVOT_RESEARCH_ONLY",
            "profile_history_availability": [
                _safe_microbreak_public_history(x.status)
                for x in microbreak.profiles
            ],
            "profiles": ["SIM_1_LEFT_1_RIGHT", "SIM_2_LEFT_2_RIGHT"],
            "m15_missing_or_stale":
                "M15" in microbreak.frames_missing_or_stale,
            "experimental_cross_direction_or_prices_published": False,
            "numeric_source_owner_approved": False,
            "publisher_first_known_verified": False,
            "real_bidask_risk_approved": False,
            "source_d1_revision_hold_cleared": False,
            "action": "NO_SIGNAL",
            "stage": "UNVERIFIED",
            "provider_requests_added": 0,
            "drive_gets_added": 0,
            "drive_writes": 0,
            "broker_orders": 0,
        },
        "private_pivot_sensitivity": {
            "status": "TWO_SIM_ONLY_RESEARCH_POLICIES_NO_SIGNAL",
            "sim_research_only_profiles": [
                "SIM_1_LEFT_1_RIGHT", "SIM_2_LEFT_2_RIGHT"
            ],
            "frames_studied": list(f.frame for f in technical.frames),
            "frames_with_enough_contiguous_closed_history_by_profile": [
                [r.frame for r in pivot.studied[
                    i*len(technical.frames):(i+1)*len(technical.frames)]
                 if r.status ==
                    "PRIVATE_RESEARCH_RIGHT_BARS_CLOSED_NO_FIRST_KNOWN_PROOF"]
                for i in range(len(POLICY_WINDOWS))
            ],
            "frames_missing_or_stale": list(pivot.frames_missing_or_stale),
            "source_right_confirmed_only_after_candle_close": True,
            "publisher_first_known_verified": False,
            "sydney_d1_session_calendar_verified": False,
            "original_forex_numeric_pivot_policy_approved": False,
            "reported_pivot_prices_or_directions": False,
            "bidask_net_rr_available": False,
            "action": "NO_SIGNAL",
            "stage": "UNVERIFIED",
            "drive_reads_added": 0,
            "provider_requests": 0,
            "broker_orders": 0,
        },
        "private_multibar_research": {
            "status": "MULTIBAR_COMPUTED_PRIVATE_NO_VALUES_PUBLISHED",
            "frames_processed": len(multibar.frames),
            "frames_with_two_or_more_closed_candles": [
                f.frame for f in multibar.frames
                if f.observed_closed_candles >= 2
            ],
            "frames_with_insufficient_closed_history": [
                f.frame for f in multibar.frames
                if f.observed_closed_candles < 2
            ],
            "missing_or_stale_frames": list(
                multibar.frames_missing_or_stale),
            "sydney_d1_session_continuity_independently_proven": False,
            "published_raw_or_derived_price_values": False,
            "publisher_first_known_verified": False,
            "original_source_numeric_rules_approved": False,
            "source_licence_for_derived_market_values_verified": False,
            "confirmed_trend_or_pivot_proven": False,
            "bidask_net_rr_available": False,
            "action": "NO_SIGNAL",
            "stage": "UNVERIFIED",
            "provider_requests": 0,
            "drive_market_cache_writes": 0,
            "broker_orders": 0,
        },
        "private_ohlc_geometry": {
            "status": "COMPUTED_IN_MEMORY_NEVER_PUBLISHED",
            "source_side": "MID",
            "frames_computed": len(private_geometry.shapes),
            "frames_missing_or_stale": list(
                private_geometry.frames_missing_or_stale),
            "six_frame_technical_complete":
                private_geometry.technical_six_frame_complete,
            "single_candle_not_trend_or_confirmed_pivot": True,
            "prices_and_derived_values_published": False,
            "external_derived_data_rights_verified": False,
            "original_strategy_numeric_rules_approved": False,
            "source_first_known_proven": False,
            "bidask_execution_net_rr_available": False,
            "action": "NO_SIGNAL",
            "stage": "UNVERIFIED",
            "provider_requests": 0,
            "drive_price_cache_writes": 0,
            "broker_orders": 0,
        },
        "analysis_mode_decision": {
            "schema_version": source_mode.schema_version,
            "analysis_lane": source_mode.analysis_lane,
            "market_quote_mode": source_mode.market_quote_mode,
            "technical_status": source_mode.technical_status,
            "frames_missing_or_stale": list(
                source_mode.frames_missing_or_stale),
            "ohlc_research_implementation_may_proceed_offline":
                source_mode.ohlc_research_implementation_may_proceed_offline,
            "sealed_six_frame_context_complete":
                source_mode.sealed_six_frame_context_complete,
            "requires_bidask_for_closed_ohlc_pattern_research":
                source_mode.requires_bidask_for_closed_ohlc_pattern_research,
            "requires_bidask_for_executable_net_rr":
                source_mode.requires_bidask_for_executable_net_rr,
            "requires_mt4_or_mt5_terminal":
                source_mode.requires_mt4_or_mt5_terminal,
            "future_bidask_route": source_mode.future_bidask_route,
            "future_broker_connection_required":
                source_mode.future_broker_connection_required,
            "source_data_account_rights_verified":
                source_mode.source_data_account_rights_verified,
            "bidask_quote_observed_and_licensed":
                source_mode.bidask_quote_observed_and_licensed,
            "original_numeric_rules_approved":
                source_mode.original_numeric_rules_approved,
            "net_rr_status": source_mode.net_rr_status,
            "publishable_buy_sell": source_mode.publishable_buy_sell,
            "broker_order_integration": source_mode.broker_order_integration,
            "provider_requests": source_mode.provider_requests,
            "drive_price_cache_writes": source_mode.drive_price_cache_writes,
            "broker_orders": source_mode.broker_orders,
        },
        # This child report is an allowlisted safe projection: never raw OHLC,
        # source Drive IDs, credentials, candidate trade prices or live alerts.
        "signal_only_output": {
            "schema_version": signal_only.schema_version,
            "action": signal_only.action,
            "stage": signal_only.stage,
            "technical_status": signal_only.technical_status,
            "quote_side": signal_only.quote_side,
            "frames_present": list(signal_only.frames_present),
            "frames_missing_or_stale": list(
                signal_only.frames_missing_or_stale),
            "reason_codes": list(signal_only.reason_codes),
            "evidence_fingerprint_sha256":
                signal_only.evidence_fingerprint_sha256,
            "zone_label": None,
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "net_risk_reward": None,
            "publisher_first_known_utc": None,
            "source_numeric_rules_approved": False,
            "source_account_license_verified": False,
            "bid_ask_economics_approved": False,
            "historical_oos_approved": False,
            "may_publish_buy_sell": False,
            "may_trade": False,
        },
    }


def main() -> None:
    # No credentials loaded, no Drive access or network from denied dispatches.
    if not manual_dispatch_authorized(dict(os.environ)):
        print("MFX_V1_MANUAL_DRIVE_GET_ONLY_DISABLED_OWNER_GATE")
        return
    try:
        auth = _drive_auth_info()
        _require_oauth_cache_folders(auth)
        actual = _session(auth)
        receipt, gets = private_get_only_probe(
            actual, asof_utc=datetime.now(timezone.utc))
        # Never print PASS before all source/authority validation and JSON
        # encoding have succeeded. A failure must emit ONLY the FAIL marker.
        payload = safe_summary(receipt, drive_gets=gets)
        encoded = json.dumps(payload, sort_keys=True)
        print("MFX_V1_MANUAL_DRIVE_GET_ONLY_TECHNICAL_AUDIT_PASS")
        print(encoded)
    except Exception:
        # Never leak private Drive object IDs, OAuth errors, URLs or raw prices
        # in Actions stderr. Failure must be nonzero, never a fake PASS.
        print("MFX_V1_MANUAL_DRIVE_GET_ONLY_FAILED_FAIL_CLOSED")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
