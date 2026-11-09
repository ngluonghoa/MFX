"""P0.18 synthetic-only parameterized B2/S2 pullback numeric RESEARCH pilots.

These are *experimentally specified* price predicates: original Forex 03
provides qualitative B2/S2 but NO approved numerical near/anti-chase/
pivot thresholds. Numeric parameters are required, have no defaults, and
can only have SIM: versions. They do NOT constitute original 1:1 detectors.
No provider or broker access, position actions, cache writes or release.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from forex_trading.market_data import (
    BarSide, MarketBar, Timeframe, evaluate_closed_bar,
)
from forex_trading.model import SignalStage
from forex_trading.quotes import ensure_utc

from mfx_research.offline_ema_signals import CandidateAction


class StructuralTrend(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


def _positive_decimal(value: Decimal, name: str, *, bound: Decimal | None = None) -> None:
    if (not isinstance(value, Decimal) or not value.is_finite() or value <= 0
            or (bound is not None and value > bound)):
        raise ValueError("P018_INVALID_" + name)


def _sim_id(value: str, name: str) -> None:
    if (not isinstance(value, str) or not value.startswith("SIM:")
            or len(value) > 128 or len(value) <= 4
            or any(ch.isspace() for ch in value)):
        raise ValueError("P018_ONLY_SYNTHETIC_" + name)


@dataclass(frozen=True, slots=True)
class UnapprovedResearchParameters:
    version: str
    near_zone_atr_multiple: Decimal
    max_chase_atr_multiple: Decimal

    def __post_init__(self) -> None:
        _sim_id(self.version, "PARAM_VERSION")
        # 20x is an input safety upper bound, NOT any accepted Forex threshold.
        _positive_decimal(self.near_zone_atr_multiple, "NEAR_MULTIPLE",
                          bound=Decimal("20"))
        _positive_decimal(self.max_chase_atr_multiple, "CHASE_MULTIPLE",
                          bound=Decimal("20"))


@dataclass(frozen=True, slots=True)
class ClaimedStructuralContext:
    rule_id: str
    instrument_version: str
    origin_event_id: str
    d1_trend: StructuralTrend
    h4_trend: StructuralTrend
    h1_zone_low: Decimal
    h1_zone_high: Decimal
    known_micro_level: Decimal
    known_atr: Decimal
    context_first_known_utc: datetime
    structure_invalidated: bool = False

    def __post_init__(self) -> None:
        if self.rule_id not in ("B2", "S2"):
            raise ValueError("P018_ONLY_B2_S2_PILOTS")
        _sim_id(self.instrument_version, "INSTRUMENT")
        _sim_id(self.origin_event_id, "ORIGIN_EVENT")
        if (not isinstance(self.d1_trend, StructuralTrend)
                or not isinstance(self.h4_trend, StructuralTrend)):
            raise TypeError("P018_TYPED_D1_H4_TREND_REQUIRED")
        for name in ("h1_zone_low", "h1_zone_high", "known_micro_level",
                     "known_atr"):
            _positive_decimal(getattr(self, name), name.upper())
        if self.h1_zone_high < self.h1_zone_low:
            raise ValueError("P018_INVERTED_KNOWN_H1_ZONE")
        if type(self.structure_invalidated) is not bool:
            raise TypeError("P018_INVALIDATION_BOOL_REQUIRED")
        ensure_utc(self.context_first_known_utc, "context_first_known_utc")


@dataclass(frozen=True, slots=True)
class ResearchPullbackResult:
    action: CandidateAction
    rule_id: str
    instrument_version: str
    origin_event_id: str
    parameter_version: str
    reason: str
    first_known_utc: datetime
    decision_utc: datetime
    stage: SignalStage = SignalStage.UNVERIFIED
    original_forex_numerical_parity: bool = False
    source_verified_for_market: bool = False
    may_send_confirmed_signal: bool = False
    can_trade: bool = False
    provider_requests: int = 0
    drive_market_cache_writes: int = 0

    def as_record(self) -> dict[str, str | bool | int]:
        return {
            "action": self.action.value,
            "rule_id": self.rule_id,
            "instrument_version": self.instrument_version,
            "origin_event_id": self.origin_event_id,
            "parameter_version": self.parameter_version,
            "reason": self.reason,
            "first_known_utc": self.first_known_utc.isoformat(),
            "decision_utc": self.decision_utc.isoformat(),
            "stage": self.stage.value,
            "original_forex_numerical_parity": self.original_forex_numerical_parity,
            "source_verified_for_market": self.source_verified_for_market,
            "may_send_confirmed_signal": self.may_send_confirmed_signal,
            "can_trade": self.can_trade,
            "provider_requests": self.provider_requests,
            "drive_market_cache_writes": self.drive_market_cache_writes,
        }


def evaluate_unapproved_b2_s2(
    bars: tuple[MarketBar, MarketBar],
    context: ClaimedStructuralContext,
    parameters: UnapprovedResearchParameters,
    decision_utc: datetime,
) -> ResearchPullbackResult:
    """Real numeric two-M15 closed-bar trigger with externally supplied claims.

    Claims for H4/D1 trend, H1 zone, ATR and micro level are NOT independently
    derived; they are fabricated for fixture testing. A successful predicate
    is an UNVERIFIED research observation, never Forex source-confirmed BUY/SELL.
    """
    ensure_utc(decision_utc, "decision_utc")
    if not isinstance(context, ClaimedStructuralContext):
        raise TypeError("P018_TYPED_STRUCTURE_REQUIRED")
    if not isinstance(parameters, UnapprovedResearchParameters):
        raise TypeError("P018_TYPED_UNAPPROVED_PARAMETERS_REQUIRED")
    if (not isinstance(bars, tuple) or len(bars) != 2
            or not all(isinstance(b, MarketBar) for b in bars)):
        raise ValueError("P018_EXACTLY_TWO_TYPED_M15_BARS_REQUIRED")
    first, last = bars
    if (first.key.timeframe is not Timeframe.M15
            or first.key.side is not BarSide.MID):
        raise ValueError("P018_M15_MID_TECHNICAL_ONLY")
    identity = (
        first.key.instrument_version, first.key.timeframe,
        first.key.side, first.key.calendar_version,
        first.key.aggregation_version, first.observation.provider_id,
        first.observation.stream_id,
    )
    if context.instrument_version != first.key.instrument_version:
        raise ValueError("P018_CONTEXT_PAIR_MISMATCH")
    if (context.context_first_known_utc > first.key.bar_start_utc):
        raise ValueError("P018_CONTEXT_WAS_NOT_KNOWN_BEFORE_EVALUATION_WINDOW")
    for bar in bars:
        this = (
            bar.key.instrument_version, bar.key.timeframe,
            bar.key.side, bar.key.calendar_version,
            bar.key.aggregation_version, bar.observation.provider_id,
            bar.observation.stream_id,
        )
        if this != identity:
            raise ValueError("P018_MIXED_INSTRUMENT_STREAM_OR_SIDE")
        if (not bar.key.instrument_version.startswith("SIM:")
                or not bar.observation.provider_id.startswith("SIM:")
                or not bar.observation.stream_id.startswith("SIM:")
                or bar.observation.license_scope_claim != "SYNTHETIC_ONLY"
                or bar.revision_number != 1):
            raise ValueError("P018_REJECT_REAL_SOURCE_OR_REVISED_MARKET_BAR")
        if (bar.key.bar_end_utc > decision_utc
                or bar.observation.retrieved_at_utc > decision_utc):
            raise ValueError("P018_FUTURE_BAR_OR_RETRIEVAL")
        gate = evaluate_closed_bar(bar, decision_utc)
        if (not gate.usable_for_technical_features
                or gate.confirmed_phase_authorized or gate.permission_to_trade):
            raise ValueError("P018_CLOSED_BAR_SOURCE_GATE:" + gate.reason)
    if first.key.bar_end_utc != last.key.bar_start_utc:
        raise ValueError("P018_NONCONTIGUOUS_M15_BARS")

    def result(action: CandidateAction, reason: str) -> ResearchPullbackResult:
        return ResearchPullbackResult(
            action=action, rule_id=context.rule_id,
            instrument_version=context.instrument_version,
            origin_event_id=context.origin_event_id,
            parameter_version=parameters.version, reason=reason,
            first_known_utc=last.first_known_utc,
            decision_utc=decision_utc,
        )

    expected_trend = (
        StructuralTrend.UP if context.rule_id == "B2" else StructuralTrend.DOWN
    )
    if (context.d1_trend is not expected_trend
            or context.h4_trend is not expected_trend):
        return result(CandidateAction.NO_SIGNAL, "P018_TREND_NOT_SUPPORTED")
    if context.structure_invalidated:
        return result(CandidateAction.NO_SIGNAL, "P018_STRUCTURE_INVALIDATED")

    tolerance = context.known_atr * parameters.near_zone_atr_multiple
    chase = context.known_atr * parameters.max_chase_atr_multiple
    if context.rule_id == "B2":
        # Prior M15 *observes* a known H1 support neighborhood, then latest
        # M15 closes above a micro-high known before the two-bar window.
        near = (first.low <= context.h1_zone_high + tolerance
                and first.high >= context.h1_zone_low - tolerance)
        triggered = (
            first.close <= context.known_micro_level
            and last.close > context.known_micro_level
        )
        anti_chase = last.close - context.known_micro_level <= chase
        candidate = CandidateAction.BUY
    else:
        # Mirrored bearish retracement: known resistance and micro-low.
        near = (first.high >= context.h1_zone_low - tolerance
                and first.low <= context.h1_zone_high + tolerance)
        triggered = (
            first.close >= context.known_micro_level
            and last.close < context.known_micro_level
        )
        anti_chase = context.known_micro_level - last.close <= chase
        candidate = CandidateAction.SELL
    if not near:
        return result(CandidateAction.NO_SIGNAL, "P018_PRIOR_M15_NOT_NEAR_H1_ZONE")
    if not triggered:
        return result(CandidateAction.NO_SIGNAL, "P018_NO_LATEST_MICRO_BREAK")
    if not anti_chase:
        return result(CandidateAction.NO_SIGNAL, "P018_SYNTHETIC_ANTI_CHASE_LIMIT")
    return result(candidate, "P018_SYNTHETIC_PARAMETRIC_PATTERN_UNVERIFIED")
