"""Research-only offline EMA CROSS BUY/SELL candidates from synthetic M15 bars.

This MFX-owned module deliberately lives OUTSIDE the locked src/forex_trading
package and the release wheel. It reuses unchanged Forex typed bar/EMA gates.
It is an EXPERIMENTAL indicator, NOT the frozen Forex 18-zone detector or a
financially qualified signal. No data provider, files, cache or broker I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from forex_trading.cache_indicators import ema_full
from forex_trading.market_data import (
    BarSide, MarketBar, Timeframe, evaluate_closed_bar,
)
from forex_trading.model import SignalStage
from forex_trading.quotes import ensure_utc


class CandidateAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NO_SIGNAL = "NO_SIGNAL"


STRATEGY = "EXPERIMENTAL_EMA_CROSS_NOT_FOREX_1_TO_1"
MAX_BARS = 512


@dataclass(frozen=True, slots=True)
class OfflineResearchSignal:
    action: CandidateAction
    stage: SignalStage
    direction: str
    instrument: str
    timeframe: Timeframe
    latest_bar_end_utc: datetime
    first_known_utc: datetime
    decision_utc: datetime
    reason: str
    source_verified: bool = False
    economic_parity_proven: bool = False
    can_trade: bool = False
    provider_requests: int = 0
    drive_market_cache_writes: int = 0

    def as_record(self) -> dict[str, str | bool | int]:
        return {
            "action": self.action.value,
            "stage": self.stage.value,
            "direction": self.direction,
            "instrument": self.instrument,
            "timeframe": self.timeframe.value,
            "latest_bar_end_utc": self.latest_bar_end_utc.isoformat(),
            "first_known_utc": self.first_known_utc.isoformat(),
            "decision_utc": self.decision_utc.isoformat(),
            "reason": self.reason,
            "strategy": STRATEGY,
            "source_verified": self.source_verified,
            "economic_parity_proven": self.economic_parity_proven,
            "can_trade": self.can_trade,
            "provider_requests": self.provider_requests,
            "drive_market_cache_writes": self.drive_market_cache_writes,
        }


def research_only_ema_signal(
    bars: tuple[MarketBar, ...],
    decision_utc: datetime,
    *,
    fast_period: int = 2,
    slow_period: int = 3,
) -> OfflineResearchSignal:
    """Causal latest-closed M15 crossover; never emits CONFIRMED_SIGNAL.

    Inputs are *only* fabricated SIM provenance. Existing source's technical
    CLOSED bar gate is necessary but not vendor entitlement or signal proof.
    Rejects partial, stale-revision, future-known, noncontiguous, mixed stream
    and side changes; never treats MID as executable ASK/BID.
    """
    ensure_utc(decision_utc, "decision_utc")
    if (type(fast_period) is not int or type(slow_period) is not int
            or fast_period < 2 or slow_period <= fast_period
            or slow_period > 200):
        raise ValueError("RESEARCH_INVALID_EMA_PERIOD_POLICY")
    if (not isinstance(bars, tuple) or len(bars) < slow_period + 2
            or len(bars) > MAX_BARS):
        raise ValueError("RESEARCH_INSUFFICIENT_OR_UNBOUNDED_CLOSED_BARS")
    first = bars[0]
    if not isinstance(first, MarketBar):
        raise TypeError("RESEARCH_EXPECTS_TYPED_MARKET_BARS")
    identity = (
        first.key.instrument_version, first.key.timeframe,
        first.key.calendar_version, first.key.aggregation_version,
        first.key.side, first.observation.provider_id,
        first.observation.stream_id,
    )
    if (first.key.timeframe is not Timeframe.M15
            or first.key.side is not BarSide.MID):
        raise ValueError("RESEARCH_ONLY_CLOSED_M15_MID_TECHNICAL_REFERENCE")
    if (not first.key.instrument_version.startswith("SIM:")
            or not first.observation.provider_id.startswith("SIM:")
            or not first.observation.stream_id.startswith("SIM:")):
        raise ValueError("RESEARCH_NO_LIVE_PROVIDER_OR_REAL_INSTRUMENT")
    closes = []
    previous_end: datetime | None = None
    for bar in bars:
        if not isinstance(bar, MarketBar):
            raise TypeError("RESEARCH_EXPECTS_TYPED_MARKET_BARS")
        here = (
            bar.key.instrument_version, bar.key.timeframe,
            bar.key.calendar_version, bar.key.aggregation_version,
            bar.key.side, bar.observation.provider_id,
            bar.observation.stream_id,
        )
        if here != identity:
            raise ValueError("RESEARCH_MIXED_INSTRUMENT_SOURCE_OR_PRICE_SIDE")
        if (bar.observation.license_scope_claim != "SYNTHETIC_ONLY"
                or bar.revision_number != 1):
            raise ValueError("RESEARCH_NOT_SYNTHETIC_FIRST_REVISION")
        if (bar.observation.retrieved_at_utc > decision_utc
                or bar.key.bar_end_utc > decision_utc):
            raise ValueError("RESEARCH_FUTURE_BAR_OR_RETRIEVAL")
        if previous_end is not None and bar.key.bar_start_utc != previous_end:
            raise ValueError("RESEARCH_GAP_DUPLICATE_OR_REORDERED_BAR")
        gate = evaluate_closed_bar(bar, decision_utc)
        if not gate.usable_for_technical_features:
            raise ValueError("RESEARCH_SOURCE_CLOSED_BAR_GATE:" + gate.reason)
        if gate.confirmed_phase_authorized or gate.permission_to_trade:
            raise ValueError("RESEARCH_UNEXPECTED_EXECUTION_AUTHORITY")
        previous_end = bar.key.bar_end_utc
        closes.append(bar.close)
    fast = ema_full(tuple(closes), fast_period)
    slow = ema_full(tuple(closes), slow_period)
    action = CandidateAction.NO_SIGNAL
    if fast[-2] <= slow[-2] and fast[-1] > slow[-1]:
        action = CandidateAction.BUY
    elif fast[-2] >= slow[-2] and fast[-1] < slow[-1]:
        action = CandidateAction.SELL
    return OfflineResearchSignal(
        action=action,
        stage=SignalStage.UNVERIFIED,
        direction=("LONG" if action is CandidateAction.BUY
                   else "SHORT" if action is CandidateAction.SELL else "NONE"),
        instrument=first.key.instrument_version,
        timeframe=Timeframe.M15,
        latest_bar_end_utc=bars[-1].key.bar_end_utc,
        first_known_utc=bars[-1].first_known_utc,
        decision_utc=decision_utc,
        reason=("RESEARCH_ONLY_SYNTHETIC_EMA_CROSS_NOT_ORIGINAL_FOREX"
                if action is not CandidateAction.NO_SIGNAL
                else "NO_LATEST_CLOSED_M15_EMA_CROSS"),
    )
