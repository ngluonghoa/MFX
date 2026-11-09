"""P0.19: independent causal synthetic D1/H4/H1/M15 context derivation.

RESEARCH ONLY. Computes simple 2-bar HTF extrema trend proxies, ATR-like
H1 true-range mean, H1 recent low/high and a prior M15 micro-level directly
from synthetic CLOSED OHLC. No source-approved Forex pivot/trend parameter
exists; this is NOT a Forex 1:1 numerical detector or production alert.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from forex_trading.market_data import (
    BarSide, MarketBar, Timeframe, evaluate_closed_bar,
)
from forex_trading.quotes import ensure_utc

from mfx_research.pullback_pilot import (
    ClaimedStructuralContext, ResearchPullbackResult, StructuralTrend,
    UnapprovedResearchParameters, evaluate_unapproved_b2_s2,
)


@dataclass(frozen=True, slots=True)
class SyntheticDerivationParameters:
    version: str
    atr_h1_periods: int
    h1_zone_lookback: int
    zone_width_atr_multiple: Decimal

    def __post_init__(self) -> None:
        if (not isinstance(self.version, str) or
                not self.version.startswith("SIM:") or
                len(self.version) <= 4 or len(self.version) > 128 or
                any(ch.isspace() for ch in self.version)):
            raise ValueError("P019_SIM_ONLY_PARAMETER_VERSION")
        for name in ("atr_h1_periods", "h1_zone_lookback"):
            value = getattr(self, name)
            if type(value) is not int or not 2 <= value <= 24:
                raise ValueError("P019_UNAPPROVED_H1_PERIOD_BOUNDS:" + name)
        width = self.zone_width_atr_multiple
        if (not isinstance(width, Decimal) or
                not width.is_finite() or width <= 0 or width > Decimal("20")):
            raise ValueError("P019_UNAPPROVED_ZONE_WIDTH")
        # Bounds 2..24 / 20 only contain abuse; NOT production thresholds.


@dataclass(frozen=True, slots=True)
class SyntheticMultiTfBars:
    daily: tuple[MarketBar, ...]
    four_hour: tuple[MarketBar, ...]
    hourly: tuple[MarketBar, ...]
    micro_seed_m15: tuple[MarketBar, ...]
    trigger_m15: tuple[MarketBar, MarketBar]


@dataclass(frozen=True, slots=True)
class DerivedResearchReceipt:
    derived_context: ClaimedStructuralContext
    signal: ResearchPullbackResult
    derivation_version: str
    h1_true_range_atr: Decimal
    known_at_start_utc: datetime
    structural_calibration_approved: bool = False
    original_forex_source_signal_parity: bool = False
    source_verified_for_market: bool = False
    may_send_confirmed_signal: bool = False
    can_trade: bool = False
    provider_requests: int = 0
    drive_market_cache_writes: int = 0


_DURATIONS = {
    Timeframe.D1: timedelta(days=1),
    Timeframe.H4: timedelta(hours=4),
    Timeframe.H1: timedelta(hours=1),
    Timeframe.M15: timedelta(minutes=15),
}


def _validate_closed_synthetic(
    series: tuple[MarketBar, ...], tf: Timeframe,
    known_at: datetime, pair: str, provider: str, calendar: str,
) -> None:
    if not isinstance(series, tuple) or not series:
        raise ValueError("P019_MISSING_OR_MUTABLE_TIMEFRAME_INPUT:" + tf.value)
    previous: MarketBar | None = None
    original_stream: str | None = None
    original_aggregation: str | None = None
    for bar in series:
        if not isinstance(bar, MarketBar):
            raise TypeError("P019_TYPED_OHLC_BAR_REQUIRED")
        if (not bar.key.instrument_version.startswith("SIM:")
                or not bar.observation.provider_id.startswith("SIM:")
                or not bar.observation.stream_id.startswith("SIM:")
                or bar.observation.license_scope_claim != "SYNTHETIC_ONLY"
                or bar.revision_number != 1):
            raise ValueError("P019_REJECT_REAL_MARKET_SOURCE_OR_REVISIONS")
        if (bar.key.instrument_version != pair or
                bar.observation.provider_id != provider or
                bar.key.calendar_version != calendar):
            raise ValueError("P019_CROSS_TIMEFRAME_IDENTITY_CONFLICT")
        if bar.key.timeframe is not tf or bar.key.side is not BarSide.MID:
            raise ValueError("P019_CROSS_TIMEFRAME_OR_SIDE_MISMATCH")
        if bar.key.bar_end_utc - bar.key.bar_start_utc != _DURATIONS[tf]:
            raise ValueError("P019_SIM_UTC_TIMEFRAME_DURATION_MISMATCH")
        if bar.key.bar_end_utc > known_at:
            raise ValueError("P019_FUTURE_PRICE_BAR_NOT_CLOSED_AT_CONTEXT_CUTOFF")
        if (bar.first_known_utc > known_at or
                bar.observation.retrieved_at_utc > known_at):
            raise ValueError("P019_FUTURE_KNOWN_OR_RETRIEVED_PRICE_DATA")
        gate = evaluate_closed_bar(bar, known_at)
        if (not gate.usable_for_technical_features
                or gate.confirmed_phase_authorized or gate.permission_to_trade):
            raise ValueError("P019_CLOSED_QUALITY_STOP:" + gate.reason)
        if previous is not None:
            if bar.key.bar_start_utc != previous.key.bar_end_utc:
                raise ValueError("P019_MISSING_REORDERED_OR_DUPLICATE_BAR")
            if bar.first_known_utc < previous.first_known_utc:
                raise ValueError("P019_NONCAUSAL_OBSERVATION_ORDER")
        if original_stream is None:
            original_stream = bar.observation.stream_id
            original_aggregation = bar.key.aggregation_version
        if (bar.observation.stream_id != original_stream or
                bar.key.aggregation_version != original_aggregation):
            raise ValueError("P019_INTRA_TIMEFRAME_STREAM_MISMATCH")
        previous = bar


def _extrema_proxy(series: tuple[MarketBar, ...]) -> StructuralTrend:
    old, new = series
    if new.high > old.high and new.low > old.low:
        return StructuralTrend.UP
    if new.high < old.high and new.low < old.low:
        return StructuralTrend.DOWN
    return StructuralTrend.UNKNOWN


def derive_and_evaluate_b2_s2(
    rule_id: str,
    bars: SyntheticMultiTfBars,
    derivation: SyntheticDerivationParameters,
    trigger_parameters: UnapprovedResearchParameters,
    decision_utc: datetime,
    *,
    origin_event_id: str,
) -> DerivedResearchReceipt:
    """Build full synthetic as-of context before latest M15, then research BUY/SELL.

    A two-HTF-bar HH/HL (or LH/LL) proxy is NOT confirmed causal pivots.
    Explicitly reject partial bar, future-known zone, broken chronology,
    edited market history, invalid pseudo-calendar and mixed quote basis.
    """
    ensure_utc(decision_utc, "decision_utc")
    if rule_id not in ("B2", "S2"):
        raise ValueError("P019_ONLY_ORIGINAL_CATALOG_B2_S2_IDS")
    if (not isinstance(bars, SyntheticMultiTfBars) or
            not isinstance(derivation, SyntheticDerivationParameters) or
            not isinstance(trigger_parameters, UnapprovedResearchParameters)):
        raise TypeError("P019_TYPED_SYNTHETIC_CONTEXT_AND_PARAMETERS_REQUIRED")
    if (not isinstance(origin_event_id, str) or
            not origin_event_id.startswith("SIM:") or
            len(origin_event_id) <= 4 or len(origin_event_id) > 128):
        raise ValueError("P019_SYNTHETIC_ORIGIN_ID_REQUIRED")
    m15 = bars.trigger_m15
    if (not isinstance(m15, tuple) or len(m15) != 2 or
            not isinstance(m15[0], MarketBar)):
        raise ValueError("P019_TWO_TRIGGER_M15_BARS_REQUIRED")
    first = m15[0]
    cutoff = first.key.bar_start_utc
    if len(bars.daily) != 2 or len(bars.four_hour) != 2:
        raise ValueError("P019_TWO_HTF_BARS_PER_TREND_PROXY_REQUIRED")
    if len(bars.hourly) != max(derivation.atr_h1_periods + 1,
                               derivation.h1_zone_lookback):
        raise ValueError("P019_COMPLETE_H1_ATR_AND_ZONE_HISTORY_REQUIRED")
    if len(bars.micro_seed_m15) != 1:
        raise ValueError("P019_ONE_PREKNOWN_MICRO_SEED_REQUIRED")

    pair = first.key.instrument_version
    provider = first.observation.provider_id
    calendar = first.key.calendar_version
    if (not pair.startswith("SIM:") or not provider.startswith("SIM:")
            or not calendar.startswith("SIM:")):
        raise ValueError("P019_NO_REAL_OR_UNKNOWN_CALENDAR")
    for seq, tf, asof in (
        (bars.daily, Timeframe.D1, cutoff),
        (bars.four_hour, Timeframe.H4, cutoff),
        (bars.hourly, Timeframe.H1, cutoff),
        (bars.micro_seed_m15, Timeframe.M15, cutoff),
        (m15, Timeframe.M15, decision_utc),
    ):
        _validate_closed_synthetic(seq, tf, asof, pair, provider, calendar)
    seed = bars.micro_seed_m15[-1]
    if (seed.key.bar_end_utc != cutoff or
            seed.first_known_utc > cutoff or
            seed.observation.retrieved_at_utc > cutoff):
        raise ValueError("P019_MICRO_PIVOT_NOT_CAUSALLY_KNOWN_AT_START")
    if m15[0].key.bar_end_utc != m15[1].key.bar_start_utc:
        raise ValueError("P019_M15_TRIGGER_DISCONTINUITY")

    h1 = bars.hourly
    atr_periods = derivation.atr_h1_periods
    tr_values: list[Decimal] = []
    # Previous H1 close is known; unlike high-low-only proxy this handles
    # H1 interbar gaps, but NOT broker ticks, spread or execution costs.
    for i in range(len(h1) - atr_periods, len(h1)):
        current, prior = h1[i], h1[i - 1]
        tr_values.append(max(
            current.high - current.low,
            abs(current.high - prior.close),
            abs(current.low - prior.close),
        ))
    atr = sum(tr_values, Decimal("0")) / Decimal(atr_periods)
    if not atr.is_finite() or atr <= 0:
        raise ValueError("P019_NO_POSITIVE_H1_TRUE_RANGE")
    zone_bars = h1[-derivation.h1_zone_lookback:]
    width = atr * derivation.zone_width_atr_multiple
    if rule_id == "B2":
        anchor = min(x.low for x in zone_bars)
        zone_low, zone_high = anchor, anchor + width
        micro = seed.high
    else:
        anchor = max(x.high for x in zone_bars)
        zone_low, zone_high = anchor - width, anchor
        micro = seed.low
    if zone_low <= 0:
        raise ValueError("P019_DERIVED_ZONE_NOT_POSITIVE")
    first_known = max(
        *(x.first_known_utc for x in (
            bars.daily + bars.four_hour + bars.hourly + bars.micro_seed_m15
        )),
    )
    if first_known > cutoff:
        raise ValueError("P019_DERIVED_STRUCTURE_FUTURE_KNOWN")
    ctx = ClaimedStructuralContext(
        rule_id=rule_id, instrument_version=pair,
        origin_event_id=origin_event_id,
        d1_trend=_extrema_proxy(bars.daily),
        h4_trend=_extrema_proxy(bars.four_hour),
        h1_zone_low=zone_low, h1_zone_high=zone_high,
        known_micro_level=micro, known_atr=atr,
        context_first_known_utc=first_known,
    )
    result = evaluate_unapproved_b2_s2(m15, ctx, trigger_parameters, decision_utc)
    return DerivedResearchReceipt(
        derived_context=ctx, signal=result,
        derivation_version=derivation.version,
        h1_true_range_atr=atr, known_at_start_utc=first_known,
    )
