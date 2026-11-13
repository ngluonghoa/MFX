"""MFX 1.0: fail-closed signal-only presentation over sealed six-TF research.

Offline, read-only, typed rendering only. A sealed cache hash and a six-frame
technical receipt cannot authorize original-source numeric BUY/SELL, BID/ASK
economics, live first-known custody or trading. No provider/Drive/broker I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
import re

from mfx_cache.td_m5_codec import PROVIDER, SYMBOL
from mfx_research.six_tf_readonly_context import (
    FRAMES, VERSION as TECH_VERSION, ReadonlyTimeframeEvidence,
    SixTimeframeResearchReceipt,
)
from mfx_research.six_tf_sealed_archive_consumer import (
    VERSION as SEALED_VERSION, SealedArchiveSixTFReceipt,
)

VERSION = "MFX_V1_SIGNAL_ONLY_SIX_TF_PRESENTATION_RESEARCH_V1"
SEALED_STATUS = "SEALED_READONLY_CACHE_TECHNICAL_RESEARCH_ONLY_NO_SIGNAL"
FULL_MODE = "FULL_BOUNDED_ALL_RAW_SHA"
ROLLING_MODE = "ROOT_PINNED_ALL_MANIFESTS_LATEST_256_CHUNKS"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_STATIC_BLOCKERS = (
    "ORIGINAL_SOURCE_NUMERIC_RULES_UNAPPROVED",
    "ACCOUNT_SPECIFIC_DATA_RIGHTS_UNVERIFIED",
    "PUBLISHER_FIRST_KNOWN_UNVERIFIED",
    "BID_ASK_SPREAD_COST_SL_TP_NET_RR_UNVERIFIED",
    "CAUSAL_OOS_AND_RELEASE_NOT_ACCEPTED",
)


@dataclass(frozen=True, slots=True)
class SignalOnlyResearchResponse:
    schema_version: str
    instrument: str
    asof_utc: str
    action: str
    stage: str
    technical_status: str
    quote_side: str
    source_provider: str
    frames_present: tuple[str, ...]
    frames_missing_or_stale: tuple[str, ...]
    reason_codes: tuple[str, ...]
    source_manifest_tips: tuple[tuple[str, str], ...]
    evidence_fingerprint_sha256: str
    # These are intentionally absent, not numeric zeroes or MID-derived prices.
    zone_label: None = None
    entry_price: None = None
    stop_loss: None = None
    take_profit: None = None
    net_risk_reward: None = None
    publisher_first_known_utc: None = None
    verified_original_numeric_rules: bool = False
    account_data_rights_verified: bool = False
    bidask_execution_costs_verified: bool = False
    historical_oos_verified: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_cache_writes: int = 0
    broker_orders: int = 0


def _sha(value: str, field: str) -> None:
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise ValueError("V1_SIGNAL_ONLY_INVALID_SOURCE_SHA:" + field)


def _require_unprivileged(receipt: SealedArchiveSixTFReceipt) -> None:
    t = receipt.technical
    if type(receipt) is not SealedArchiveSixTFReceipt or type(t) is not SixTimeframeResearchReceipt:
        raise TypeError("V1_SIGNAL_ONLY_TYPED_SEALED_RECEIPT_REQUIRED")
    if (receipt.version != SEALED_VERSION or receipt.status != SEALED_STATUS
            or t.version != TECH_VERSION or t.instrument != SYMBOL
            or t.source_provider != PROVIDER
            or t.action != "NO_SIGNAL" or t.stage != "UNVERIFIED"
            or receipt.may_publish_buy_sell or receipt.may_trade
            or receipt.provider_account_data_rights_verified
            or receipt.source_first_known_time_proven
            or receipt.independent_monotonic_witness_verified
            or receipt.storage_reader_identity_independently_attested
            or receipt.historical_asof_replay_proven
            or receipt.source_numeric_entry_rules_approved
            or receipt.bidask_costs_and_sl_tp_net_rr_approved
            or receipt.provider_price_calls != 0
            or receipt.drive_cache_writes != 0 or receipt.broker_orders != 0
            or t.may_publish_verified_buy_sell or t.may_trade
            or t.source_feed_subscription_verified
            or t.archive_sha_independently_verified
            or t.historical_asof_replay_proven
            or t.forex_1to1_numerical_parity_verified
            or t.entry_sl_tp_net_rr_approved
            or t.provider_requests != 0
            or t.drive_market_cache_writes != 0 or t.broker_orders != 0):
        raise ValueError("V1_SIGNAL_ONLY_FORGED_SOURCE_OR_SIGNAL_AUTHORITY")
    try:
        stamp = datetime.fromisoformat(t.asof_utc)
    except (TypeError, ValueError) as exc:
        raise ValueError("V1_SIGNAL_ONLY_INVALID_ASOF") from exc
    if (stamp.tzinfo is None or stamp.utcoffset() != timedelta(0)
            or not t.asof_utc.endswith("+00:00")):
        raise ValueError("V1_SIGNAL_ONLY_EXACT_UTC_ASOF_REQUIRED")
    present = tuple(e.frame for e in t.frames)
    missing = t.missing_or_stale_frames
    if (type(t.frames) is not tuple or type(missing) is not tuple
            or present != tuple(f for f in FRAMES if f in present)
            or len(set(present)) != len(present)
            or missing != tuple(f for f in FRAMES if f not in present)
            or t.total_frames != len(present)
            or t.research_technical_context_complete != (len(present) == 6)
            or t.status != ("SIX_TF_TECHNICAL_RESEARCH_READY_NO_SIGNAL"
                            if len(present) == 6 else "SIX_TF_MISSING_OR_STALE_NO_SIGNAL")):
        raise ValueError("V1_SIGNAL_ONLY_SIX_FRAME_COVERAGE_DRIFT")
    for e in t.frames:
        if (type(e) is not ReadonlyTimeframeEvidence
                or e.source_provider != PROVIDER or e.source_price_side != "MID"
                or e.verified_feed_subscription
                or e.independently_verified_archive_custody
                or e.source_numeric_strategy_approved):
            raise ValueError("V1_SIGNAL_ONLY_FRAME_AUTHORITY_OR_SIDE_DRIFT")
        _sha(e.evidence_sha256, "frame_" + e.frame)
    _sha(t.input_m5_sha256, "technical_m5")
    for name, value in (("m5", receipt.m5_manifest_tip_sha256),
                        ("h4", receipt.h4_manifest_tip_sha256),
                        ("d1", receipt.d1_manifest_tip_sha256)):
        _sha(value, name)
    if (receipt.m5_manifest_pairs_full_sha < 1
            or receipt.h4_manifest_pairs_full_sha < 1
            or receipt.d1_manifest_pairs_full_sha < 1
            or receipt.m5_sha_audit_mode not in (FULL_MODE, ROLLING_MODE)
            or receipt.m5_total_archived_manifest_pairs < receipt.m5_manifest_pairs_full_sha
            or receipt.m5_total_manifest_parent_chain_verified != receipt.m5_total_archived_manifest_pairs):
        raise ValueError("V1_SIGNAL_ONLY_INVALID_SEALED_CHAIN_COUNTS")
    if receipt.m5_sha_audit_mode == FULL_MODE and (
            not receipt.m5_full_historical_raw_sha_verified
            or not receipt.all_three_bounded_sha_chains_verified
            or receipt.m5_historical_raw_chunks_not_reread != 0):
        raise ValueError("V1_SIGNAL_ONLY_FORGED_FULL_SHA_MODE")
    if receipt.m5_sha_audit_mode == ROLLING_MODE and (
            receipt.m5_full_historical_raw_sha_verified
            or receipt.all_three_bounded_sha_chains_verified
            or receipt.m5_historical_raw_chunks_not_reread < 1
            or not receipt.m5_recent_raw_sha_verified):
        raise ValueError("V1_SIGNAL_ONLY_FORGED_ROLLING_SHA_MODE")


def build_signal_only_research_response(
    receipt: SealedArchiveSixTFReceipt,
) -> SignalOnlyResearchResponse:
    """Render technical cache evidence without ever promoting a market action."""
    _require_unprivileged(receipt)
    technical = receipt.technical
    present = tuple(frame.frame for frame in technical.frames)
    missing = technical.missing_or_stale_frames
    reasons: list[str] = []
    if missing:
        reasons.extend("FRAME_MISSING_OR_STALE_" + frame for frame in missing)
    if receipt.m5_sha_audit_mode == ROLLING_MODE:
        reasons.append("OLDER_M5_RAW_CHUNKS_NOT_REREAD")
    if not receipt.github_reviewed_m5_anchors_checked:
        reasons.append("M5_SOURCE_ANCHORS_SYNTHETIC_OR_UNREVIEWED")
    reasons.extend(_STATIC_BLOCKERS)
    tips = (
        ("M5", receipt.m5_manifest_tip_sha256),
        ("H4", receipt.h4_manifest_tip_sha256),
        ("D1", receipt.d1_manifest_tip_sha256),
    )
    payload = {
        "schema": VERSION, "asof": technical.asof_utc, "instrument": SYMBOL,
        "tips": tips, "m5_typed_sha": technical.input_m5_sha256,
        "frames": [(e.frame, e.source_label, e.evidence_sha256)
                   for e in technical.frames],
        "missing": missing, "reasons": reasons,
    }
    fingerprint = sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")).hexdigest()
    return SignalOnlyResearchResponse(
        schema_version=VERSION, instrument=SYMBOL, asof_utc=technical.asof_utc,
        action="NO_SIGNAL", stage="UNVERIFIED",
        technical_status=("SIX_TF_COMPLETE_RESEARCH_ONLY"
                          if not missing else "SIX_TF_INCOMPLETE_RESEARCH_ONLY"),
        quote_side="MID", source_provider=PROVIDER,
        frames_present=present, frames_missing_or_stale=missing,
        reason_codes=tuple(reasons), source_manifest_tips=tips,
        evidence_fingerprint_sha256=fingerprint,
    )
