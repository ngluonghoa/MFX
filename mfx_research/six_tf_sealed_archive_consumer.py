"""MFX 1.0 signal-first: sealed, read-only M5/H4/D1 archive to six-TF research.

No OAuth/token handling, provider polling, Drive writes, broker, or public
BUY/SELL. Store objects are caller-injected GET/list-only; SHA integrity does
not establish the identity of a Drive reader, data rights, first-known time,
external anti-rollback witness, or trading strategy authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.td_m5_codec import digest
from mfx_cache.v2_batch_commit import _name, _validate_manifest
from mfx_research.six_tf_readonly_context import (
    SixTimeframeResearchReceipt, build_six_timeframe_readonly_context,
)
from mfx_research.sealed_multibar_private_features import (
    PrivateMultiBarReceipt, calculate_private_multibar_from_sealed_rows,
)
from mfx_research.sealed_private_pivot_sensitivity import (
    PrivatePivotSensitivityReceipt, scan_private_sealed_pivot_sensitivity,
)
from mfx_research.sealed_private_m15_microbreak import (
    PrivateMicroBreakReceipt, compute_private_sealed_m15_microbreak,
)
from tools.mfx_m5_full_sha_two_anchor_audit import (
    ROOT_UTC, ROOT_MANIFEST_SHA256, REVIEWED_CHECKPOINT_UTC,
    REVIEWED_CHECKPOINT_SHA256, REVIEWED_CHECKPOINT_PAIRS,
)
from tools.mfx_native_htf_drive_seal import (
    _batch_from_chunk, audit_native_archive,
)
from tools.run_mfx_m5_h4_live_parity_audit import _m5_archive
from tools.mfx_m5_rolling_manifest_audit import (
    MAX_ROOTED_MANIFESTS, ROLLING_HOURS, audit_rooted_rolling_m5,
)

VERSION = "MFX_V1_SEALED_READONLY_SIX_TF_RESEARCH_V1"
SYMBOL = "EUR/USD"
SYDNEY = "Australia/Sydney"
MAX_M5_PAIRS = 256
MAX_NATIVE_ROWS_FOR_CONTEXT = 120


class ReadOnlyObjectStore(Protocol):
    """Only the needed GET/list surface, never the writer protocol."""

    def list_names(self, bucket: str) -> tuple[str, ...]: ...
    def read(self, bucket: str, name: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class SyntheticFixturePins:
    """Test fixtures ONLY; never a reviewed GitHub source anchor."""

    root_hour_utc: str
    root_sha256: str
    checkpoint_hour_utc: str
    checkpoint_sha256: str
    checkpoint_pairs: int


@dataclass(frozen=True, slots=True)
class SealedArchiveSixTFReceipt:
    version: str
    status: str
    technical: SixTimeframeResearchReceipt
    m5_manifest_pairs_full_sha: int
    h4_manifest_pairs_full_sha: int
    d1_manifest_pairs_full_sha: int
    m5_manifest_tip_sha256: str
    h4_manifest_tip_sha256: str
    d1_manifest_tip_sha256: str
    all_three_bounded_sha_chains_verified: bool
    github_reviewed_m5_anchors_checked: bool
    m5_latest_source_hour_utc: str = ""
    m5_sha_audit_mode: str = "FULL_BOUNDED_ALL_RAW_SHA"
    m5_total_manifest_parent_chain_verified: int = 0
    m5_total_archived_manifest_pairs: int = 0
    m5_historical_raw_chunks_not_reread: int = 0
    m5_full_historical_raw_sha_verified: bool = True
    m5_recent_raw_sha_verified: bool = True
    storage_reader_identity_independently_attested: bool = False
    provider_account_data_rights_verified: bool = False
    source_first_known_time_proven: bool = False
    independent_monotonic_witness_verified: bool = False
    historical_asof_replay_proven: bool = False
    source_numeric_entry_rules_approved: bool = False
    bidask_costs_and_sl_tp_net_rr_approved: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    provider_price_calls: int = 0
    drive_cache_writes: int = 0
    broker_orders: int = 0
    # Actual decoded multi-candle analysis, derived from exactly the already
    # audited buffers: private and NEVER included in CI JSON / repr.
    private_multibar: PrivateMultiBarReceipt | None = field(
        default=None, repr=False,
    )
    private_pivot_sensitivity: PrivatePivotSensitivityReceipt | None = field(
        default=None, repr=False,
    )
    private_m15_microbreak: PrivateMicroBreakReceipt | None = field(
        default=None, repr=False,
    )


def _snapshot(store: ReadOnlyObjectStore) -> tuple[tuple[str, ...], tuple[str, ...]]:
    names = tuple(store.list_names("manifest"))
    chunks = tuple(store.list_names("chunk"))
    if (names != tuple(sorted(set(names)))
            or chunks != tuple(sorted(set(chunks)))):
        raise ValueError("V1_CACHE_DUPLICATE_OR_UNSORTED_LIST")
    return names, chunks


def _m5_pinned_rows(
    store: ReadOnlyObjectStore, *, asof_utc: datetime,
    fixture_pins: SyntheticFixturePins | None,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    # Real mode ALWAYS uses checked-in, independently reviewed root+checkpoint.
    if fixture_pins is None:
        root_hour, root_sha = ROOT_UTC, ROOT_MANIFEST_SHA256
        checkpoint_hour = REVIEWED_CHECKPOINT_UTC
        checkpoint_sha = REVIEWED_CHECKPOINT_SHA256
        checkpoint_count = REVIEWED_CHECKPOINT_PAIRS
    else:
        if type(fixture_pins) is not SyntheticFixturePins:
            raise ValueError("V1_CACHE_SYNTHETIC_PINS_TYPE")
        root_hour, root_sha = (
            fixture_pins.root_hour_utc, fixture_pins.root_sha256)
        checkpoint_hour, checkpoint_sha = (
            fixture_pins.checkpoint_hour_utc, fixture_pins.checkpoint_sha256)
        checkpoint_count = fixture_pins.checkpoint_pairs

    before = _snapshot(store)
    names, chunks = before
    if (type(checkpoint_count) is not int
            or not 1 <= checkpoint_count <= MAX_M5_PAIRS
            or len(names) < checkpoint_count
            or len(names) > MAX_ROOTED_MANIFESTS
            or len(names) != len(chunks)):
        raise ValueError("V1_CACHE_M5_ROLLBACK_OR_UNVERIFIABLE_BOUND")
    # No writer / price feed. <=256: P0.66 checks every raw chunk.
    # >256: P0.69 checks EVERY manifest SHA/parent and newest 256 raw
    # chunks, but explicitly cannot certify old raw chunks in this read.
    if (names[0] != _name("manifest", root_hour, root_sha)
            or names[checkpoint_count-1] != _name(
                "manifest", checkpoint_hour, checkpoint_sha)):
        raise ValueError("V1_CACHE_M5_SOURCE_REVIEWED_ANCHOR_MISMATCH")

    root = store.read("manifest", names[0])
    checkpoint = store.read("manifest", names[checkpoint_count-1])
    if (_validate_manifest(names[0], root) != root_hour
            or _validate_manifest(
                names[checkpoint_count-1], checkpoint) != checkpoint_hour
            or digest(root) != root_sha
            or digest(checkpoint) != checkpoint_sha
            or checkpoint["total_batches"] != checkpoint_count
            or checkpoint["total_closed_m5"] != 12*checkpoint_count):
        raise ValueError("V1_CACHE_M5_REVIEWED_CONTENT_MISMATCH")

    rolling = len(names) > MAX_M5_PAIRS
    if rolling:
        bars, evidence = audit_rooted_rolling_m5(
            store, now_utc=asof_utc,
            root_sha256=root_sha, root_hour_utc=root_hour,
        )
    else:
        bars, evidence = _m5_archive(store, now_utc=asof_utc)
    tip = store.read("manifest", names[-1])
    if (evidence["m5_full_bounded_chain_verified"] is not (not rolling)
            or evidence["m5_manifest_chunk_pairs_full_sha_verified"] != (
                ROLLING_HOURS if rolling else len(names))
            or (rolling and (
                evidence["m5_manifest_full_sha_parent_chain_verified"] != len(names)
                or evidence["m5_total_archived_manifest_chunk_pairs"] != len(names)
                or evidence["m5_historical_unread_chunks"] !=
                    len(names) - ROLLING_HOURS
                or evidence["m5_rolling_256_chunk_sha_verified"] is not True
                or evidence["m5_old_raw_chunks_not_reverified_this_run"] is not True
            ))
            or evidence["m5_closed_bars"] != len(bars)
            or evidence["m5_latest_manifest_sha256"] != digest(tip)
            or tip["total_batches"] != len(names)
            or digest(store.read("manifest", names[0])) != root_sha
            or digest(store.read(
                "manifest", names[checkpoint_count-1])) != checkpoint_sha
            or _snapshot(store) != before):
        raise ValueError("V1_CACHE_M5_READONLY_SNAPSHOT_DRIFT")
    return bars, evidence


def _native_pinned_rows(
    store: ReadOnlyObjectStore, *, interval: str,
) -> tuple[NativeFXBatch, int, str]:
    if interval not in ("4h", "1day"):
        raise ValueError("V1_CACHE_NATIVE_INTERVAL_DENIED")
    before = _snapshot(store)
    names, chunks = before
    # Reuse canonical P0.55 native SHA/parent-chain verifier.
    state = audit_native_archive(store, symbol=SYMBOL, interval=interval)
    if (state.last_manifest is None or state.manifest_count < 1
            or state.chunk_count != state.manifest_count
            or state.uncommitted_chunk_names
            or state.manifest_count != len(names)
            or state.chunk_count != len(chunks)):
        raise ValueError("V1_CACHE_NATIVE_INCOMPLETE_OR_UNCOMMITTED")

    rows: list[NativeFXBar] = []
    for name in names:
        manifest = store.read("manifest", name)
        if (type(manifest) is not dict
                or type(manifest.get("chunk_name")) is not str
                or manifest["chunk_name"] not in chunks):
            raise ValueError("V1_CACHE_NATIVE_MANIFEST_DRIFT")
        chunk = store.read("chunk", manifest["chunk_name"])
        if (digest(chunk) != manifest["chunk_sha256"]
                or (type(chunk) is not dict)
                or chunk.get("parent_manifest_sha256") !=
                manifest["parent_manifest_sha256"]):
            raise ValueError("V1_CACHE_NATIVE_CHUNK_DRIFT")
        decoded = _batch_from_chunk(chunk)
        if decoded.interval != interval or decoded.symbol != SYMBOL:
            raise ValueError("V1_CACHE_NATIVE_SCOPE_DRIFT")
        rows.extend(decoded.closed_bars)
    labels = tuple(row.native_open_label for row in rows)
    if (not rows
            or labels != tuple(sorted(set(labels)))
            or len(rows) != state.last_manifest["total_closed_native_bars"]
            or labels[-1] != state.last_manifest["last_native_open_label"]
            or digest(store.read("manifest", names[-1])) !=
            digest(state.last_manifest)
            or _snapshot(store) != before):
        raise ValueError("V1_CACHE_NATIVE_READONLY_SNAPSHOT_DRIFT")
    zone = state.last_manifest["exchange_timezone"]
    if zone != SYDNEY:
        raise ValueError("V1_CACHE_NATIVE_SYDNEY_SOURCE_REQUIRED")
    batch = NativeFXBatch(
        symbol=SYMBOL, interval=interval, exchange_timezone=zone,
        time_reference=state.last_manifest["time_reference"],
        closed_bars=tuple(rows[-MAX_NATIVE_ROWS_FOR_CONTEXT:]),
        incomplete_excluded=0,
    )
    return batch, state.manifest_count, digest(state.last_manifest)


def consume_sealed_archives_for_six_tf(
    m5_store: ReadOnlyObjectStore,
    h4_store: ReadOnlyObjectStore,
    d1_store: ReadOnlyObjectStore, *, asof_utc: datetime,
    fixture_pins: SyntheticFixturePins | None = None,
) -> SealedArchiveSixTFReceipt:
    """Read verified content-addressed archive context; NEVER authorize trades.

    The caller must arrange authenticated Drive access outside this pure
    function. Even actual OAuth GET + matching SHA cannot prove market licence,
    provider first-known or publisher-signed revisions. No live source run or
    independently authenticated Drive read is performed by this module.
    """
    if (type(asof_utc) is not datetime or asof_utc.tzinfo is None
            or asof_utc.utcoffset() != timedelta(0)):
        raise ValueError("V1_CACHE_EXACT_UTC_ASOF_REQUIRED")
    if fixture_pins is not None and type(fixture_pins) is not SyntheticFixturePins:
        raise ValueError("V1_CACHE_SYNTHETIC_PINS_TYPE")

    initial = (_snapshot(m5_store), _snapshot(h4_store),
               _snapshot(d1_store))
    m5_bars, m5_evidence = _m5_pinned_rows(
        m5_store, asof_utc=asof_utc, fixture_pins=fixture_pins)
    # The audited manifest hour MUST correspond to the latest closed
    # 12-bar M5 chunk, not just its SHA or one source label.
    last_source_hour = m5_evidence["m5_latest_hour_utc"]
    if (type(last_source_hour) is not str
            or m5_bars[-1].start_utc != (
                datetime.fromisoformat(last_source_hour)
                + timedelta(minutes=55)).isoformat()):
        raise ValueError("V1_CACHE_M5_SOURCE_TIP_HOUR_DRIFT")
    h4, h4_pairs, h4_tip = _native_pinned_rows(h4_store, interval="4h")
    d1, d1_pairs, d1_tip = _native_pinned_rows(d1_store, interval="1day")

    # The existing six-frame validator enforces latest CLOSED M5, exact
    # 3/6/12 M5 windows, source-native UTC H4 and Sydney-local D1. SHA
    # custody must never flip its separate unverified market permissions.
    technical = build_six_timeframe_readonly_context(
        tuple(m5_bars[-12:]), h4, d1, asof_utc=asof_utc)
    if ((_snapshot(m5_store), _snapshot(h4_store),
         _snapshot(d1_store)) != initial):
        raise ValueError("V1_CACHE_CROSS_ARCHIVE_CHANGED_DURING_READ")

    # No extra GET: use the SAME SHA-audited M5/H4/D1 buffers to calculate
    # per-frame true ranges and prior-close deltas. All values stay private.
    multi = calculate_private_multibar_from_sealed_rows(
        m5_bars, h4, d1, technical, asof_utc=asof_utc,
    )
    if (multi.action != "NO_SIGNAL" or multi.stage != "UNVERIFIED"
            or multi.source_price_side != "MID"
            or multi.may_publish_prices_or_signals or multi.may_trade
            or multi.provider_requests or multi.drive_market_cache_writes
            or multi.broker_orders or
            tuple(x.frame for x in multi.frames) !=
                tuple(x.frame for x in technical.frames)
            or multi.frames_missing_or_stale !=
                technical.missing_or_stale_frames):
        raise ValueError("V1_CACHE_PRIVATE_MULTIBAR_AUTHORITY_DRIFT")

    # Strict right-closed pivot research uses EXACT SAME private contiguous
    # histories and checks their local input digest; both 1/1 and 2/2 are
    # explicitly SIM stress profiles, never owner-approved Forex thresholds.
    private_pivots = scan_private_sealed_pivot_sensitivity(
        multi, technical,
    )
    if (private_pivots.action != "NO_SIGNAL"
            or private_pivots.stage != "UNVERIFIED"
            or private_pivots.may_publish_price_derived_values_or_signals
            or private_pivots.may_trade
            or private_pivots.original_forex_numeric_pivot_policy_approved
            or private_pivots.data_license_and_redistribution_verified
            or private_pivots.real_historical_first_known_verified
            or private_pivots.chronological_oos_acceptance
            or private_pivots.real_d1_session_continuity_qualified
            or private_pivots.provider_requests
            or private_pivots.drive_cache_writes
            or private_pivots.broker_orders
            or private_pivots.source_private_multibar_digest_sha256 !=
                multi.private_input_digest_sha256):
        raise ValueError("V1_CACHE_PIVOT_RESEARCH_AUTHORITY_DRIFT")

    # P0.158: evaluate latest closed M15 against levels independently
    # right-confirmed before that candle opened; NEVER emit private events.
    private_microbreak = compute_private_sealed_m15_microbreak(
        multi, technical, private_pivots,
    )
    if (private_microbreak.action != "NO_SIGNAL"
            or private_microbreak.stage != "UNVERIFIED"
            or private_microbreak.may_publish_prices_or_signals
            or private_microbreak.may_trade
            or private_microbreak.provider_requests
            or private_microbreak.drive_gets_added
            or private_microbreak.drive_writes
            or private_microbreak.broker_orders):
        raise ValueError("V1_CACHE_PRIVATE_M15_MICROBREAK_AUTHORITY_DRIFT")

    return SealedArchiveSixTFReceipt(
        version=VERSION,
        status="SEALED_READONLY_CACHE_TECHNICAL_RESEARCH_ONLY_NO_SIGNAL",
        technical=technical,
        m5_manifest_pairs_full_sha=(
            m5_evidence["m5_manifest_chunk_pairs_full_sha_verified"]),
        h4_manifest_pairs_full_sha=h4_pairs,
        d1_manifest_pairs_full_sha=d1_pairs,
        m5_manifest_tip_sha256=m5_evidence["m5_latest_manifest_sha256"],
        h4_manifest_tip_sha256=h4_tip,
        d1_manifest_tip_sha256=d1_tip,
        # False in rolling mode: all historic raw M5 chunks NOT re-read.
        all_three_bounded_sha_chains_verified=(
            m5_evidence["m5_full_bounded_chain_verified"]),
        github_reviewed_m5_anchors_checked=fixture_pins is None,
        m5_latest_source_hour_utc=last_source_hour,
        m5_sha_audit_mode=(
            "ROOT_PINNED_ALL_MANIFESTS_LATEST_256_CHUNKS"
            if "m5_rolling_256_chunk_sha_verified" in m5_evidence
            else "FULL_BOUNDED_ALL_RAW_SHA"),
        m5_total_manifest_parent_chain_verified=m5_evidence.get(
            "m5_manifest_full_sha_parent_chain_verified",
            m5_evidence["m5_manifest_chunk_pairs_full_sha_verified"]),
        m5_total_archived_manifest_pairs=m5_evidence.get(
            "m5_total_archived_manifest_chunk_pairs",
            m5_evidence["m5_manifest_chunk_pairs_full_sha_verified"]),
        m5_historical_raw_chunks_not_reread=m5_evidence.get(
            "m5_historical_unread_chunks", 0),
        m5_full_historical_raw_sha_verified=(
            m5_evidence["m5_full_bounded_chain_verified"]),
        m5_recent_raw_sha_verified=True,
        private_multibar=multi,
        private_pivot_sensitivity=private_pivots,
        private_m15_microbreak=private_microbreak,
    )
