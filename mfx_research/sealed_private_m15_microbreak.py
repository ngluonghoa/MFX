"""P0.158: private M15 closed-bar crossings of PREVIOUSLY confirmed pivots.

Actual calculations reuse the P0.155 SHA-audited in-memory six-TF
source and P0.156 right-closed SIM pivot profiles. They never infer source
first-known, source-owner thresholds, BID/ASK fills, an actual trade, or a
BUY/SELL signal. Latest M15 candle CLOSE is tested against a level that
was already right-bar-confirmed BEFORE that candle opened.

No additional provider/Drive calls, writable store or broker interface.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from mfx_research.sealed_multibar_private_features import (
    PrivateMultiBarReceipt, _number, _ts, WIDTHS,
)
from mfx_research.sealed_private_pivot_sensitivity import (
    POLICY_WINDOWS, PrivatePivotPoint, PrivatePivotSensitivityReceipt,
    scan_private_sealed_pivot_sensitivity,
)
from mfx_research.six_tf_readonly_context import SixTimeframeResearchReceipt

VERSION = "MFX_V1_P158_SEALED_PRIVATE_CAUSAL_M15_MICROBREAK_V1"


@dataclass(frozen=True, slots=True, repr=False)
class PrivateMicroBreakProfile:
    left_bars: int
    right_bars: int
    status: str
    source_m15_closed_history: int
    prior_right_closed_high_available: bool
    prior_right_closed_low_available: bool
    # These event and price details are PRIVATE, not an allowed output field.
    experimental_cross: str
    referenced_mid_pivot: Decimal | None
    latest_closed_mid_price: Decimal | None
    latest_candle_closed_utc: str | None
    source_price_side: str = "MID"
    source_numeric_rule_approved: bool = False
    publisher_first_known_attested: bool = False
    may_publish_signal: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class PrivateMicroBreakReceipt:
    version: str
    asof_utc: str
    source_private_multibar_digest_sha256: str
    profiles: tuple[PrivateMicroBreakProfile, ...]
    frames_missing_or_stale: tuple[str, ...]
    source_price_side: str = "MID"
    original_b2_s2_approved: bool = False
    independently_licensed_provider_data: bool = False
    publisher_first_known_verified: bool = False
    source_d1_session_or_revision_qualified: bool = False
    real_bidask_sl_tp_net_rr_approved: bool = False
    historical_oos_accepted: bool = False
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    may_publish_prices_or_signals: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_gets_added: int = 0
    drive_writes: int = 0
    broker_orders: int = 0


def _last_known(
    pivots: tuple[PrivatePivotPoint, ...],
    kind: str,
    latest_open_utc: datetime,
) -> PrivatePivotPoint | None:
    eligible = (
        p for p in pivots
        if p.kind == kind
        # A pivot confirmed by a later still-OPEN candle is never known.
        and datetime.fromisoformat(p.right_candle_closed_utc)
            <= latest_open_utc
    )
    return next(iter(reversed(tuple(eligible))), None)


def _one_profile(
    rows: tuple[object, ...] | None,
    pivot: PrivatePivotSensitivityReceipt,
    left: int,
    right: int,
) -> PrivateMicroBreakProfile:
    if rows is None:
        return PrivateMicroBreakProfile(
            left, right, "M15_MISSING_OR_STALE", 0, False, False,
            "NO_RESEARCH_EVENT", None, None, None,
        )
    if len(rows) < left + right + 3:
        return PrivateMicroBreakProfile(
            left, right, "INSUFFICIENT_CLOSED_M15_HISTORY", len(rows),
            False, False, "NO_RESEARCH_EVENT", None, None, None,
        )
    studies = tuple(
        s for s in pivot.studied
        if (s.frame, s.left_bars, s.right_bars) == ("M15", left, right)
    )
    if (len(studies) != 1
            or studies[0].status !=
            "PRIVATE_RESEARCH_RIGHT_BARS_CLOSED_NO_FIRST_KNOWN_PROOF"):
        raise ValueError("P158_UNQUALIFIED_M15_PIVOT_RESEARCH")
    study = studies[0]
    latest_open = _ts(rows[-1].label, "M15")
    latest_close = latest_open + timedelta(minutes=WIDTHS["M15"])
    high = _last_known(study.pivots, "HIGH", latest_open)
    low = _last_known(study.pivots, "LOW", latest_open)
    prev_close = _number(rows[-2].close)
    now_close = _number(rows[-1].close)
    cross = "NO_RESEARCH_EVENT"
    level: Decimal | None = None
    if high is not None and prev_close <= high.candidate_mid_price < now_close:
        cross, level = "EXPERIMENTAL_UP_CROSS", high.candidate_mid_price
    elif low is not None and prev_close >= low.candidate_mid_price > now_close:
        cross, level = "EXPERIMENTAL_DOWN_CROSS", low.candidate_mid_price
    return PrivateMicroBreakProfile(
        left, right,
        ("PRIVATE_PRIOR_CONFIRMED_M15_LEVEL_EVALUATED"
         if (high is not None or low is not None)
         else "NO_PRIOR_RIGHT_CLOSED_M15_PIVOT"),
        len(rows), high is not None, low is not None,
        cross, level, now_close, latest_close.isoformat(),
    )


def compute_private_sealed_m15_microbreak(
    multi: PrivateMultiBarReceipt,
    technical: SixTimeframeResearchReceipt,
    pivots: PrivatePivotSensitivityReceipt,
) -> PrivateMicroBreakReceipt:
    """Cross closed M15 only against earlier right-closed private SIM levels.

    Even a positive experimental crossing remains NO_SIGNAL: the original
    source rule, legal rights, publisher first-known, D1 and economics are
    unqualified. Tampered existing source/pivot receipts fail closed.
    """
    if (type(multi) is not PrivateMultiBarReceipt
            or type(technical) is not SixTimeframeResearchReceipt
            or type(pivots) is not PrivatePivotSensitivityReceipt):
        raise TypeError("P158_EXACT_SEALED_TYPED_INPUTS_REQUIRED")
    if (multi.action, multi.stage, pivots.action, pivots.stage,
            technical.action, technical.stage) != (
            "NO_SIGNAL", "UNVERIFIED", "NO_SIGNAL", "UNVERIFIED",
            "NO_SIGNAL", "UNVERIFIED"):
        raise ValueError("P158_NUMERIC_OR_SIGNAL_AUTHORITY_DRIFT")
    if (multi.source_price_side != "MID"
            or pivots.source_price_side != "MID"
            or multi.asof_utc != technical.asof_utc
            or multi.asof_utc != pivots.asof_utc
            or multi.original_forex_numeric_source_approved
            or pivots.original_forex_numeric_pivot_policy_approved
            or multi.vendor_source_license_verified
            or pivots.data_license_and_redistribution_verified
            or multi.first_known_publisher_verified
            or pivots.real_historical_first_known_verified
            or multi.historical_asof_replay_proven
            or pivots.chronological_oos_acceptance
            or multi.may_publish_prices_or_signals or multi.may_trade
            or pivots.may_publish_price_derived_values_or_signals
            or pivots.may_trade or technical.may_trade
            or technical.may_publish_verified_buy_sell
            or multi.provider_requests or multi.drive_market_cache_writes
            or multi.broker_orders or pivots.provider_requests
            or pivots.drive_cache_writes or pivots.broker_orders):
        raise ValueError("P158_SOURCE_RIGHTS_OR_EXECUTION_DRIFT")
    # P0.156 independently rechecks the actual SHA-bound private histories
    # and every source-closed timestamp before producing any pivot result.
    if pivots != scan_private_sealed_pivot_sensitivity(multi, technical):
        raise ValueError("P158_PIVOT_RESULT_OR_PRIVATE_SOURCE_TAMPER")
    if (pivots.source_private_multibar_digest_sha256 !=
            multi.private_input_digest_sha256
            or pivots.frames_missing_or_stale !=
            multi.frames_missing_or_stale):
        raise ValueError("P158_PRIVATE_SOURCE_CHAIN_DRIFT")
    histories = dict(multi.private_closed_histories)
    m15 = histories.get("M15")
    if (("M15" in technical.missing_or_stale_frames) != (m15 is None)):
        raise ValueError("P158_M15_FRESHNESS_OR_HISTORY_DRIFT")
    profiles = tuple(_one_profile(m15, pivots, left, right)
                     for left, right in POLICY_WINDOWS)
    return PrivateMicroBreakReceipt(
        version=VERSION, asof_utc=multi.asof_utc,
        source_private_multibar_digest_sha256=
            multi.private_input_digest_sha256,
        profiles=profiles, frames_missing_or_stale=
            multi.frames_missing_or_stale,
    )
