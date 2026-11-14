"""A04/P0.20 — right-bar-confirmed causal swing research, NOT Forex 1:1.

No pivots may be used at the candidate candle's close: the configured
right bars must have closed, been first-known AND retrieved. Numeric
left/right and price rules have only SIM: experimental parameter authority.
Inputs are strictly synthetic and closed. No broker, cloud cache or feed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from forex_trading.market_data import MarketBar, Timeframe
from forex_trading.quotes import ensure_utc

from mfx_research.causal_multitf_context import (
    SyntheticDerivationParameters, SyntheticMultiTfBars,
    _validate_closed_synthetic,
)
from mfx_research.pullback_pilot import (
    ClaimedStructuralContext, ResearchPullbackResult, StructuralTrend,
    UnapprovedResearchParameters, evaluate_unapproved_b2_s2,
)


class PivotKind(str, Enum):
    HIGH = "HIGH"
    LOW = "LOW"


@dataclass(frozen=True, slots=True)
class SyntheticPivotParameters:
    version: str
    left_bars: int
    right_bars: int

    def __post_init__(self) -> None:
        if (not isinstance(self.version, str)
                or not self.version.startswith("SIM:")
                or len(self.version) <= 4 or len(self.version) > 128
                or any(ch.isspace() for ch in self.version)):
            raise ValueError("P020_SIM_ONLY_UNAPPROVED_PIVOT_POLICY")
        if (type(self.left_bars) is not int
                or type(self.right_bars) is not int
                or not 1 <= self.left_bars <= 3
                or not 1 <= self.right_bars <= 3):
            raise ValueError("P020_INVALID_EXPLICIT_LEFT_RIGHT_BARS")


@dataclass(frozen=True, slots=True)
class ConfirmedSwing:
    kind: PivotKind
    candidate_index: int
    confirmation_index: int
    price: Decimal
    candidate_bar_end_utc: datetime
    confirmed_first_known_utc: datetime
    timeframe: Timeframe
    origin_rule: str = "SIM:STRICT_EXTREMA_AFTER_RIGHT_BARS"
    source_verified: bool = False


@dataclass(frozen=True, slots=True)
class SwingScanReceipt:
    timeframe: Timeframe
    pivots: tuple[ConfirmedSwing, ...]
    asof_utc: datetime
    last_input_bar_end_utc: datetime
    original_forex_numeric_policy_approved: bool = False


@dataclass(frozen=True, slots=True)
class ConfirmedSwingResearchReceipt:
    daily: SwingScanReceipt
    four_hour: SwingScanReceipt
    daily_trend: StructuralTrend
    four_hour_trend: StructuralTrend
    derived_context: ClaimedStructuralContext
    signal: ResearchPullbackResult
    structural_pivot_policy: str
    m15_confirmed_pivots: SwingScanReceipt | None = None
    source_forex_1to1_numerical_parity: bool = False
    may_send_confirmed_signal: bool = False
    can_trade: bool = False
    market_provider_calls: int = 0
    drive_raw_market_cache_writes: int = 0


def detect_confirmed_swings(
    series: tuple[MarketBar, ...],
    timeframe: Timeframe,
    policy: SyntheticPivotParameters,
    asof_utc: datetime,
) -> SwingScanReceipt:
    """Strict left/right extrema, no ties; confirmation is first *observable*.

    A swing cannot be known on its candidate candle. It becomes eligible
    only after all right candles are closed, known and retrieved. Future
    history supplied to an as-of call is REJECTED rather than silently read.
    """
    ensure_utc(asof_utc, "asof_utc")
    if not isinstance(policy, SyntheticPivotParameters):
        raise TypeError("P020_TYPED_SIM_POLICY_REQUIRED")
    if (not isinstance(series, tuple) or
            len(series) < policy.left_bars + policy.right_bars + 1
            or len(series) > 512):
        raise ValueError("P020_INSUFFICIENT_OR_UNBOUNDED_PIVOT_HISTORY")
    first = series[0]
    if not isinstance(first, MarketBar):
        raise TypeError("P020_TYPED_SYNTHETIC_BARS_REQUIRED")
    if timeframe not in (Timeframe.D1, Timeframe.H4, Timeframe.M15):
        raise ValueError("P020_ONLY_D1_H4_M15_PIVOT_RESEARCH")
    pair = first.key.instrument_version
    provider = first.observation.provider_id
    calendar = first.key.calendar_version
    if (not pair.startswith("SIM:") or not provider.startswith("SIM:")
            or not calendar.startswith("SIM:")):
        raise ValueError("P020_REJECT_REAL_OR_UNPROVEN_CALENDAR")
    _validate_closed_synthetic(
        series, timeframe, asof_utc, pair, provider, calendar,
    )
    pivots: list[ConfirmedSwing] = []
    left, right = policy.left_bars, policy.right_bars
    for i in range(left, len(series) - right):
        sample = series[i]
        neighbors = series[i - left:i] + series[i + 1:i + right + 1]
        is_high = all(sample.high > n.high for n in neighbors)
        is_low = all(sample.low < n.low for n in neighbors)
        # Same-bar high+low extrema produce conflicting structural meaning.
        if is_high == is_low:
            continue
        complete_right = series[i + right]
        known = max(
            b.first_known_utc
            for b in series[i - left:i + right + 1]
        )
        retrieved = max(
            b.observation.retrieved_at_utc
            for b in series[i - left:i + right + 1]
        )
        confirmed = max(known, retrieved)
        if (confirmed > asof_utc
                or complete_right.key.bar_end_utc > asof_utc
                or complete_right.key.bar_end_utc <= sample.key.bar_end_utc):
            raise ValueError("P020_PIVOT_RIGHT_CONFIRMATION_NOT_CAUSAL")
        pivots.append(ConfirmedSwing(
            kind=PivotKind.HIGH if is_high else PivotKind.LOW,
            candidate_index=i, confirmation_index=i + right,
            price=sample.high if is_high else sample.low,
            candidate_bar_end_utc=sample.key.bar_end_utc,
            confirmed_first_known_utc=confirmed,
            timeframe=timeframe,
        ))
    return SwingScanReceipt(
        timeframe=timeframe, pivots=tuple(pivots),
        asof_utc=asof_utc,
        last_input_bar_end_utc=series[-1].key.bar_end_utc,
    )


def trend_from_confirmed_swings(
    receipt: SwingScanReceipt,
) -> StructuralTrend:
    """Two independently *confirmed* high pivots and low pivots per trend."""
    if not isinstance(receipt, SwingScanReceipt):
        raise TypeError("P020_TYPED_CONFIRMED_SWING_SCAN_REQUIRED")
    highs = [x.price for x in receipt.pivots if x.kind is PivotKind.HIGH]
    lows = [x.price for x in receipt.pivots if x.kind is PivotKind.LOW]
    if len(highs) < 2 or len(lows) < 2:
        return StructuralTrend.UNKNOWN
    if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
        return StructuralTrend.UP
    if highs[-1] < highs[-2] and lows[-1] < lows[-2]:
        return StructuralTrend.DOWN
    return StructuralTrend.UNKNOWN


def derive_swing_b2_s2_research(
    rule_id: str,
    bars: SyntheticMultiTfBars,
    swing_policy: SyntheticPivotParameters,
    zone_policy: SyntheticDerivationParameters,
    trigger_policy: UnapprovedResearchParameters,
    decision_utc: datetime,
    *,
    origin_event_id: str,
    confirmed_m15_history: tuple[MarketBar, ...] | None = None,
    confirmed_m15_policy: SyntheticPivotParameters | None = None,
) -> ConfirmedSwingResearchReceipt:
    """Actual confirmed-pivot context feeding B2/S2 *synthetic* evaluator.

    H1 ATR/zone and M15 micro seed continue original P0.19 proven formula;
    D1/H4 trend now uses confirmed swings rather than 2-candle extrema.
    """
    ensure_utc(decision_utc, "decision_utc")
    if rule_id not in ("B2", "S2"):
        raise ValueError("P020_ONLY_B2_S2_RESEARCH")
    if (not isinstance(bars, SyntheticMultiTfBars)
            or not isinstance(swing_policy, SyntheticPivotParameters)
            or not isinstance(zone_policy, SyntheticDerivationParameters)
            or not isinstance(trigger_policy, UnapprovedResearchParameters)):
        raise TypeError("P020_TYPED_FULL_CONTEXT_AND_POLICIES_REQUIRED")
    if (not isinstance(origin_event_id, str)
            or not origin_event_id.startswith("SIM:")
            or len(origin_event_id) <= 4 or len(origin_event_id) > 128
            or any(ch.isspace() for ch in origin_event_id)):
        raise ValueError("P020_REQUIRES_SYNTHETIC_ORIGIN_EVENT")
    if (confirmed_m15_history is None) != (confirmed_m15_policy is None):
        raise ValueError("P020_EXACT_COMPLETE_CONFIRMED_M15_POLICY_PAIR")
    m15 = bars.trigger_m15
    if (not isinstance(m15, tuple) or len(m15) != 2
            or not all(isinstance(x, MarketBar) for x in m15)):
        raise ValueError("P020_EXACTLY_TWO_M15_TRIGGER_BARS")
    first = m15[0]
    cutoff = first.key.bar_start_utc
    pair = first.key.instrument_version
    provider = first.observation.provider_id
    calendar = first.key.calendar_version
    if (not pair.startswith("SIM:") or not provider.startswith("SIM:")
            or not calendar.startswith("SIM:")):
        raise ValueError("P020_REJECT_REAL_OR_UNKNOWN_CALENDAR")
    daily = detect_confirmed_swings(
        bars.daily, Timeframe.D1, swing_policy, cutoff,
    )
    h4 = detect_confirmed_swings(
        bars.four_hour, Timeframe.H4, swing_policy, cutoff,
    )
    # Pivot scan validates internal identity. The cross-timeframe identity
    # is checked independently against the prospective M15 trigger source.
    for series in (bars.daily, bars.four_hour):
        sample = series[0]
        if (sample.key.instrument_version != pair
                or sample.observation.provider_id != provider
                or sample.key.calendar_version != calendar):
            raise ValueError("P020_CROSS_TIMEFRAME_PIVOT_IDENTITY")
    h1 = bars.hourly
    if (len(h1) != max(zone_policy.atr_h1_periods + 1,
                       zone_policy.h1_zone_lookback)
            or len(bars.micro_seed_m15) != 1):
        raise ValueError("P020_INCOMPLETE_H1_OR_PREKNOWN_MICRO_SEED")
    for series, timeframe, known_at in (
        (h1, Timeframe.H1, cutoff),
        (bars.micro_seed_m15, Timeframe.M15, cutoff),
        (m15, Timeframe.M15, decision_utc),
    ):
        _validate_closed_synthetic(
            series, timeframe, known_at, pair, provider, calendar,
        )
    seed = bars.micro_seed_m15[0]
    if (seed.key.bar_end_utc != cutoff
            or seed.first_known_utc > cutoff
            or seed.observation.retrieved_at_utc > cutoff):
        raise ValueError("P020_MICRO_SEED_NOT_KNOWN_BEFORE_TRIGGER")
    if first.key.bar_end_utc != m15[1].key.bar_start_utc:
        raise ValueError("P020_TRIGGER_GAP_OR_REORDER")
    micro_scan: SwingScanReceipt | None = None
    micro_level: Decimal | None = None
    if confirmed_m15_history is not None:
        if (type(confirmed_m15_history) is not tuple
                or type(confirmed_m15_policy) is not SyntheticPivotParameters
                or not confirmed_m15_history
                or confirmed_m15_history[-1] != seed):
            raise ValueError("P020_M15_HISTORY_MUST_END_WITH_EXACT_PRETRIGGER_SEED")
        for item in confirmed_m15_history:
            if (type(item) is not MarketBar
                    or item.key.instrument_version != pair
                    or item.key.calendar_version != calendar
                    or item.observation.provider_id != provider
                    or item.observation.stream_id != seed.observation.stream_id
                    or item.key.aggregation_version != seed.key.aggregation_version):
                raise ValueError("P020_M15_PIVOT_ORIGIN_STREAM_IDENTITY_MISMATCH")
        for trigger in m15:
            if (trigger.observation.stream_id != seed.observation.stream_id
                    or trigger.key.aggregation_version != seed.key.aggregation_version):
                raise ValueError("P020_M15_TRIGGER_STREAM_DRIFT")
        micro_scan = detect_confirmed_swings(
            confirmed_m15_history, Timeframe.M15,
            confirmed_m15_policy, cutoff,
        )
        kind = PivotKind.HIGH if rule_id == "B2" else PivotKind.LOW
        candidates = [pivot for pivot in micro_scan.pivots if pivot.kind is kind]
        if not candidates:
            raise ValueError("P020_NO_PRIOR_RIGHT_CONFIRMED_M15_LEVEL")
        latest_known = candidates[-1]
        if (latest_known.confirmed_first_known_utc > cutoff
                or confirmed_m15_history[
                    latest_known.confirmation_index].key.bar_end_utc > cutoff):
            raise ValueError("P020_M15_PIVOT_NOT_KNOWN_BEFORE_TRIGGER_OPEN")
        micro_level = latest_known.price
    tr: list[Decimal] = []
    for i in range(len(h1) - zone_policy.atr_h1_periods, len(h1)):
        x, previous = h1[i], h1[i - 1]
        tr.append(max(
            x.high - x.low,
            abs(x.high - previous.close),
            abs(x.low - previous.close),
        ))
    atr = sum(tr, Decimal("0")) / Decimal(zone_policy.atr_h1_periods)
    if atr <= 0 or not atr.is_finite():
        raise ValueError("P020_NO_H1_TRUE_RANGE_ATR")
    zone = h1[-zone_policy.h1_zone_lookback:]
    width = atr * zone_policy.zone_width_atr_multiple
    if rule_id == "B2":
        anchor = min(x.low for x in zone)
        zone_low, zone_high = anchor, anchor + width
        micro = seed.high
    else:
        anchor = max(x.high for x in zone)
        zone_low, zone_high = anchor - width, anchor
        micro = seed.low
    if micro_level is not None:
        micro = micro_level
    if zone_low <= 0:
        raise ValueError("P020_NONPOSITIVE_H1_ZONE")
    first_known = max(
        x.first_known_utc for x in (
            bars.daily + bars.four_hour + h1 + bars.micro_seed_m15
        )
    )
    if first_known > cutoff:
        raise ValueError("P020_CONTEXT_FUTURE_KNOWN")
    ctx = ClaimedStructuralContext(
        rule_id=rule_id, instrument_version=pair,
        origin_event_id=origin_event_id,
        d1_trend=trend_from_confirmed_swings(daily),
        h4_trend=trend_from_confirmed_swings(h4),
        h1_zone_low=zone_low, h1_zone_high=zone_high,
        known_micro_level=micro, known_atr=atr,
        context_first_known_utc=first_known,
    )
    signal = evaluate_unapproved_b2_s2(
        m15, ctx, trigger_policy, decision_utc,
    )
    return ConfirmedSwingResearchReceipt(
        daily=daily, four_hour=h4, daily_trend=ctx.d1_trend,
        four_hour_trend=ctx.h4_trend, derived_context=ctx,
        signal=signal, structural_pivot_policy=swing_policy.version,
        m15_confirmed_pivots=micro_scan,
    )
