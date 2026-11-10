"""A04/P0.44: actual synthetic H1/M15 B3/S4 range-rejection research.

A self-contained, configurable NEW research hypothesis, not the original
Forex 1:1 numerically approved detector. Strict SIM-only, CLOSED MID candles.
Only a computed experimental pattern can reach the P031 22-zone router, and
its externally actionable output remains NO_SIGNAL. No real provider access,
Drive raw quote cache, live alerts, broker interface or publication.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from re import fullmatch

from forex_trading.market_data import (
    BarSide, MarketBar, Timeframe,
)
from forex_trading.model import SignalStage
from forex_trading.quotes import ensure_utc

from mfx_research.causal_multitf_context import _validate_closed_synthetic
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p031_sim_22_zone_router import (
    ResearchZoneReport, SimZoneLabelClaim, route_sim_22_zone_labels,
)
from mfx_research.p043_remaining_entry_source_gaps import (
    read_remaining_entry_gap_report,
)

VERSION = "MFX_A04_P44_COMPUTED_SIM_RANGE_B3_S4_RESEARCH_V1"
ROLES = {"B3": CandidateAction.BUY, "S4": CandidateAction.SELL}


def _id(value: str, field: str) -> None:
    if type(value) is not str or fullmatch(r"SIM:[A-Za-z0-9_.:-]{1,124}", value) is None:
        raise ValueError("P044_SIM_ONLY_IDENTIFIER:" + field)


def _multiple(value: Decimal, field: str) -> None:
    if (type(value) is not Decimal or not value.is_finite()
            or value <= 0 or value > Decimal("20")):
        raise ValueError("P044_EXPLICIT_UNAPPROVED_PARAMETER:" + field)


@dataclass(frozen=True, slots=True)
class SimRangeResearchParameters:
    version: str
    h1_lookback: int
    min_edge_touches: int
    touch_tolerance_true_range_multiple: Decimal
    max_sweep_true_range_multiple: Decimal
    reclaim_margin_true_range_multiple: Decimal

    def __post_init__(self) -> None:
        _id(self.version, "parameter_version")
        if type(self.h1_lookback) is not int or not 4 <= self.h1_lookback <= 24:
            raise ValueError("P044_EXPLICIT_H1_LOOKBACK_4_TO_24_REQUIRED")
        if (type(self.min_edge_touches) is not int
                or not 2 <= self.min_edge_touches <= self.h1_lookback):
            raise ValueError("P044_EXPLICIT_BOUNDARY_TOUCH_COUNT_REQUIRED")
        for field in (
            "touch_tolerance_true_range_multiple",
            "max_sweep_true_range_multiple",
            "reclaim_margin_true_range_multiple",
        ):
            _multiple(getattr(self, field), field)


@dataclass(frozen=True, slots=True)
class SimRangeResearchBars:
    """Prior H1 history and next two CLOSED M15 bars; never market feed."""
    hourly: tuple[MarketBar, ...]
    trigger_m15: tuple[MarketBar, MarketBar]


@dataclass(frozen=True, slots=True)
class SimRangeResearchReceipt:
    version: str
    rule_id: str
    experimental_pattern: CandidateAction
    research_reason: str
    observed_h1_range_low: Decimal
    observed_h1_range_high: Decimal
    h1_mean_true_range: Decimal
    lower_boundary_touches: int
    upper_boundary_touches: int
    origin_event_id: str
    input_fingerprint_sha256: str
    first_known_utc: datetime
    decision_utc: datetime
    classified_output: ResearchZoneReport
    stage: SignalStage = SignalStage.UNVERIFIED
    source_price_side: BarSide = BarSide.MID
    source_numeric_approved: bool = False
    original_forex_numeric_parity: bool = False
    original_h4_range_validation_proven: bool = False
    actual_confirmed_signals: int = 0
    real_provider_calls: int = 0
    drive_real_quote_cache_writes: int = 0
    broker_orders: int = 0
    publish_alerts: bool = False
    release_ready: bool = False
    action: str = "NO_SIGNAL"


def _origin(first: MarketBar, last: MarketBar) -> str:
    identity = (
        first.key.instrument_version, first.key.calendar_version,
        first.observation.provider_id, first.observation.stream_id,
        first.key.bar_start_utc.isoformat(), last.key.bar_end_utc.isoformat(),
    )
    raw = json.dumps(identity, ensure_ascii=True, separators=(",", ":"))
    return "SIM:P044-" + sha256(raw.encode("utf-8")).hexdigest()[:32]


def _fingerprint(
    rule: str, data: SimRangeResearchBars, policy: SimRangeResearchParameters,
) -> str:
    records: list[dict[str, object]] = []
    for bar in (*data.hourly, *data.trigger_m15):
        records.append({
            "tf": bar.key.timeframe.value, "side": bar.key.side.value,
            "start": bar.key.bar_start_utc.isoformat(),
            "end": bar.key.bar_end_utc.isoformat(),
            "instrument": bar.key.instrument_version,
            "calendar": bar.key.calendar_version,
            "aggregation": bar.key.aggregation_version,
            "provider": bar.observation.provider_id,
            "stream": bar.observation.stream_id,
            "revision": bar.revision_number,
            "known": bar.first_known_utc.isoformat(),
            "retrieved": bar.observation.retrieved_at_utc.isoformat(),
            "raw_sha256": bar.observation.raw_sha256,
            "ohlc": list(map(str, (bar.open, bar.high, bar.low, bar.close))),
        })
    document = {
        "v": VERSION, "rule": rule, "policy": {
            "v": policy.version, "lookback": policy.h1_lookback,
            "touches": policy.min_edge_touches,
            "tolerance": str(policy.touch_tolerance_true_range_multiple),
            "sweep": str(policy.max_sweep_true_range_multiple),
            "reclaim": str(policy.reclaim_margin_true_range_multiple),
        }, "bars": records,
    }
    return sha256(json.dumps(
        document, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def compute_sim_b3_s4_range_rejection(
    rule_id: str,
    data: SimRangeResearchBars,
    policy: SimRangeResearchParameters,
    decision_utc: datetime,
) -> SimRangeResearchReceipt:
    """Compute causal test-pattern BUY/SELL from bars, not labels/claims.

    H1 range is only a SIM study proxy: does NOT validate a real source-
    approved H4/H1 range, numeric touch count, spread, SL/TP or profitability.
    """
    ensure_utc(decision_utc, "decision_utc")
    if type(rule_id) is not str or rule_id not in ROLES:
        raise ValueError("P044_ONLY_B3_S4_EXPERIMENTAL_RESEARCH")
    if not isinstance(data, SimRangeResearchBars):
        raise TypeError("P044_TYPED_SIM_RANGE_BARS_REQUIRED")
    if not isinstance(policy, SimRangeResearchParameters):
        raise TypeError("P044_TYPED_SIM_RANGE_POLICY_REQUIRED")
    if (not isinstance(data.hourly, tuple)
            or len(data.hourly) != policy.h1_lookback + 1
            or not isinstance(data.trigger_m15, tuple)
            or len(data.trigger_m15) != 2):
        raise ValueError("P044_EXACT_H1_LOOKBACK_PLUS_PRIOR_CLOSE_AND_TWO_M15")
    first, last = data.trigger_m15
    if not isinstance(first, MarketBar) or not isinstance(last, MarketBar):
        raise TypeError("P044_TYPED_SIM_TRIGGER_BARS_REQUIRED")
    cutoff = first.key.bar_start_utc
    pair, provider, calendar = (
        first.key.instrument_version, first.observation.provider_id,
        first.key.calendar_version,
    )
    for field, val in (("pair", pair), ("provider", provider), ("calendar", calendar)):
        _id(val, field)
    # Validates *each* H1 & M15 bar as CLOSED, COMPLETE, VERIFIED, MID, rev 1,
    # known and retrieved at the right cutoff, with no missing/duplicate bars.
    _validate_closed_synthetic(
        data.hourly, Timeframe.H1, cutoff, pair, provider, calendar,
    )
    _validate_closed_synthetic(
        data.trigger_m15, Timeframe.M15, decision_utc, pair, provider, calendar,
    )
    if (data.hourly[-1].key.bar_end_utc != cutoff
            or first.key.bar_end_utc != last.key.bar_start_utc):
        raise ValueError("P044_PREKNOWN_H1_RANGE_OR_CONTIGUOUS_M15_REQUIRED")
    if (first.observation.stream_id != last.observation.stream_id
            or first.key.aggregation_version != last.key.aggregation_version
            or first.key.side is not BarSide.MID
            or last.key.side is not BarSide.MID):
        raise ValueError("P044_SINGLE_SIM_M15_MID_STREAM_REQUIRED")
    if data.hourly[-1].first_known_utc > cutoff:
        raise ValueError("P044_H1_RANGE_NOT_KNOWN_BEFORE_SWEEP")

    # Mean true range is a research volatility proxy, NOT an accepted ATR gate.
    ranges: list[Decimal] = []
    for prior, current in zip(data.hourly, data.hourly[1:]):
        ranges.append(max(
            current.high - current.low,
            abs(current.high - prior.close),
            abs(current.low - prior.close),
        ))
    mean_tr = sum(ranges, Decimal("0")) / Decimal(len(ranges))
    if not mean_tr.is_finite() or mean_tr <= 0:
        raise ValueError("P044_NONPOSITIVE_SIM_H1_TRUE_RANGE")
    past = data.hourly[1:]
    lower = min(b.low for b in past)
    upper = max(b.high for b in past)
    if lower >= upper:
        raise ValueError("P044_DEGENERATE_H1_RANGE")
    tolerance = mean_tr * policy.touch_tolerance_true_range_multiple
    n_lower = sum(abs(b.low - lower) <= tolerance for b in past)
    n_upper = sum(abs(b.high - upper) <= tolerance for b in past)
    sweep_limit = mean_tr * policy.max_sweep_true_range_multiple
    margin = mean_tr * policy.reclaim_margin_true_range_multiple

    pattern = CandidateAction.NO_SIGNAL
    reason = "SIM_P044_NO_RANGE_EDGE_REJECTION_PATTERN"
    if (n_lower < policy.min_edge_touches
            or n_upper < policy.min_edge_touches):
        reason = "SIM_P044_PRIOR_H1_RANGE_TOUCH_COUNT_NOT_MET"
    elif rule_id == "B3":
        if (first.close < lower and first.low < lower
                and last.close > lower + margin
                and last.close <= upper
                and last.close > first.high
                and lower - first.low <= sweep_limit):
            pattern = CandidateAction.BUY
            reason = "SIM_P044_B3_LOWER_RANGE_SWEEP_AND_CLOSED_RECLAIM"
    elif (first.close > upper and first.high > upper
          and last.close < upper - margin
          and last.close >= lower
          and last.close < first.low
          and first.high - upper <= sweep_limit):
        pattern = CandidateAction.SELL
        reason = "SIM_P044_S4_UPPER_RANGE_SWEEP_AND_CLOSED_REJECTION"

    inventory = read_remaining_entry_gap_report()
    selected = [z for z in inventory.rules if z.label == rule_id]
    if (len(selected) != 1 or selected[0].pair_id != "E03"
            or selected[0].source_numeric_approval
            or selected[0].eligible_for_confirmed_signal):
        raise ValueError("P044_UNAPPROVED_SOURCE_E03_RESEARCH_ROLE_GATE")
    origin = _origin(first, last)
    claims: tuple[SimZoneLabelClaim, ...] = ()
    if pattern is not CandidateAction.NO_SIGNAL:
        claims = (SimZoneLabelClaim(
            instrument_version=last.key.instrument_version,
            calendar_version=last.key.calendar_version,
            origin_event_id=origin,
            provider_id=last.observation.provider_id,
            stream_id=last.observation.stream_id,
            label=rule_id,
            closed_candle_end_utc=last.key.bar_end_utc,
            first_known_utc=last.first_known_utc,
            retrieved_at_utc=last.observation.retrieved_at_utc,
        ),)
    grouped = route_sim_22_zone_labels(claims, decision_utc)
    if (len(grouped.classified) != len(claims)
            or len(grouped.events) != len(claims)
            or grouped.numeric_entry_predicates_approved != 0
            or grouped.confirmed_buy_sell_signals != 0
            or grouped.may_send_live_alerts or grouped.may_trade
            or grouped.release_ready or grouped.broker_orders):
        raise ValueError("P044_NO_NUMERIC_OR_LIVE_SIGNAL_PROMOTION")
    if claims:
        row, event = grouped.classified[0], grouped.events[0]
        if (row.label != rule_id or row.action != "NO_SIGNAL"
                or event.action != "NO_SIGNAL"
                or (event.entry_long_labels != ("B3",)
                    if rule_id == "B3" else
                    event.entry_short_labels != ("S4",))):
            raise ValueError("P044_COMPUTED_SOURCE_TO_ROUTER_ROLE_MISMATCH")

    return SimRangeResearchReceipt(
        version=VERSION, rule_id=rule_id,
        experimental_pattern=pattern, research_reason=reason,
        observed_h1_range_low=lower, observed_h1_range_high=upper,
        h1_mean_true_range=mean_tr,
        lower_boundary_touches=n_lower, upper_boundary_touches=n_upper,
        origin_event_id=origin,
        input_fingerprint_sha256=_fingerprint(rule_id, data, policy),
        first_known_utc=last.first_known_utc,
        decision_utc=decision_utc, classified_output=grouped,
    )
