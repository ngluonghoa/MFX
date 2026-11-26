"""P215: first-obstacle structural SL/TP1 economic test on SIM B2/S2.

Point-level experimental universe, not complete source supply/demand zones.
MID-to-exit conversion is an explicit hypothetical offset, never a broker
price or permission to infer real historical executable levels.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from forex_trading.market_data import Timeframe
from forex_trading.model import ActionIntent
from forex_trading.quotes import PriceSide, Quote, indicative_price
from mfx_research.bidask_cost_aware_sim_risk import (
    CostAwareSimRiskReceipt, SimExitLevels, SimPerUnitCosts,
    evaluate_cost_aware_sim_risk,
)
from mfx_research.confirmed_swings import PivotKind
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    compute_mfx_b2s2_v2_closed_candidate, read_mfx_confirmed_b2s2_v2,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.option_b_v2_chronological_replay import OptionBReplaySnapshot
from mfx_research.p152_sim_signal_risk_vertical_slice import _join_quote

VERSION = "MFX_P215_SIM_STRUCTURAL_FIRST_OBSTACLE_NET_R_V1"


@dataclass(frozen=True, slots=True)
class SimStructuralTargetPolicy:
    stop_frame: Timeframe
    stop_buffer: Decimal
    target_buffer: Decimal
    mid_exit_offset: Decimal
    min_net_r: Decimal

    def __post_init__(self) -> None:
        if (type(self.stop_frame) is not Timeframe
                or self.stop_frame not in (Timeframe.H1, Timeframe.H4)):
            raise ValueError("P215_EXPLICIT_STOP_FRAME_REQUIRED")
        for value in (self.stop_buffer, self.target_buffer,
                      self.mid_exit_offset, self.min_net_r):
            if type(value) is not Decimal or not value.is_finite() or value < 0:
                raise ValueError("P215_EXPLICIT_FINITE_SIM_PARAMETERS_REQUIRED")
        if self.stop_buffer <= 0 or self.min_net_r <= 0:
            raise ValueError("P215_POSITIVE_STOP_BUFFER_AND_MIN_NET_R_REQUIRED")


@dataclass(frozen=True, slots=True, repr=False)
class SimStructuralTargetReceipt:
    status: str
    obstacle_count: int
    first_obstacle: Decimal | None = field(default=None, repr=False)
    next_contextual_obstacle: Decimal | None = field(default=None, repr=False)
    planned_exits: SimExitLevels | None = field(default=None, repr=False)
    economics: CostAwareSimRiskReceipt | None = field(default=None, repr=False)

    def public_summary(self) -> dict[str, str | int | bool]:
        return {
            "version": VERSION,
            "hypothetical_economics_calculated": self.economics is not None,
            "simulated_only": True,
            "actual_market_economics_verified": False,
            "numeric_source_approved": False,
            "historical_oos_qualified": False,
            "action": "NO_SIGNAL", "stage": "UNVERIFIED",
            "may_publish_buy_sell": False, "may_trade": False,
            "provider_requests": 0, "drive_writes": 0, "broker_orders": 0,
        }


def plan_sim_structural_tp1(
    snapshot: OptionBReplaySnapshot, policy: SimStructuralTargetPolicy,
    *, quote: Quote, costs: SimPerUnitCosts, max_quote_age: timedelta,
) -> SimStructuralTargetReceipt:
    """Never skip the nearest observed opposing level for better net R.

    Only pre-trigger source rows/pivots of the recomputed P161 candidate
    contribute levels; the trigger or later price path cannot add obstacles.
    TP2 is a contextual next level, never a second actionable target.
    """
    if type(snapshot) is not OptionBReplaySnapshot or type(policy) is not SimStructuralTargetPolicy:
        raise TypeError("P215_TYPED_SIM_SNAPSHOT_POLICY_REQUIRED")
    computed = compute_mfx_b2s2_v2_closed_candidate(
        snapshot.rule_id, snapshot.bars, snapshot.confirmed_m15_history,
        read_mfx_confirmed_b2s2_v2(), snapshot.decision_utc,
    )
    if computed.experimental_action is CandidateAction.NO_SIGNAL:
        return SimStructuralTargetReceipt("NO_SETUP", 0)
    if type(costs) is not SimPerUnitCosts:
        raise TypeError("P215_TYPED_SIM_COSTS_REQUIRED")
    long = snapshot.rule_id == "B2"
    intent = ActionIntent.ENTRY_LONG if long else ActionIntent.ENTRY_SHORT
    side = PriceSide.BID if long else PriceSide.ASK
    _join_quote(quote=quote, last_mid=snapshot.bars.trigger_m15[-1],
                decision_utc=snapshot.decision_utc)
    entry = indicative_price(quote, intent, snapshot.decision_utc, max_quote_age)
    source = computed.source
    context = source.derived_context
    stop_kind = PivotKind.LOW if long else PivotKind.HIGH
    opposing = PivotKind.HIGH if long else PivotKind.LOW
    h4_stops = tuple(p for p in source.four_hour.pivots if p.kind is stop_kind)
    if not h4_stops or source.m15_confirmed_pivots is None:
        raise ValueError("P215_PREKNOWN_SOURCE_PIVOTS_REQUIRED")
    anchor = (h4_stops[-1].price if policy.stop_frame is Timeframe.H4
              else context.h1_zone_low if long else context.h1_zone_high)
    sign = Decimal(1) if long else Decimal(-1)
    stop = anchor - sign * (policy.stop_buffer + policy.mid_exit_offset)
    visible_exit = quote.bid if long else quote.ask
    if stop <= 0 or sign * (visible_exit - stop) <= 0:
        return SimStructuralTargetReceipt("NO_VALID_STRUCTURAL_STOP", 0)
    cutoff = snapshot.bars.trigger_m15[0].key.bar_start_utc
    pivots = source.daily.pivots + source.four_hour.pivots + source.m15_confirmed_pivots.pivots
    if any(p.confirmed_first_known_utc > cutoff for p in pivots):
        raise ValueError("P215_FUTURE_PIVOT")
    if any(b.key.bar_end_utc > cutoff or b.first_known_utc > cutoff
           or b.observation.retrieved_at_utc > cutoff for b in snapshot.bars.hourly):
        raise ValueError("P215_FUTURE_H1_OBSTACLE")
    mid_levels = {p.price for p in pivots if p.kind is opposing}
    mid_levels.update(b.high if long else b.low for b in snapshot.bars.hourly)
    converted = {p - sign * policy.mid_exit_offset for p in mid_levels}
    if any(p <= 0 for p in converted):
        raise ValueError("P215_NONPOSITIVE_HYPOTHETICAL_SIDE_LEVEL")
    # Include obstacles at the executable exit quote or inside the spread.
    # Already passed levels behind it are not continuation objectives.
    obstacles = sorted((p for p in converted if sign * (p - visible_exit) >= 0),
                       reverse=not long)
    if not obstacles:
        return SimStructuralTargetReceipt("NO_PREKNOWN_OBSTACLE", 0)
    first = obstacles[0]
    target = first - sign * policy.target_buffer
    if target <= 0 or sign * (target - entry.value) <= 0:
        return SimStructuralTargetReceipt("FIRST_OBSTACLE_NO_ROOM", len(obstacles), first)
    exits = SimExitLevels("SIM:P215-STRUCTURAL-TP1", stop, target, side)
    economics = evaluate_cost_aware_sim_risk(
        quote=quote, intent=intent, decision_utc=snapshot.decision_utc,
        max_quote_age=max_quote_age, exits=exits, costs=costs, instrument="EUR/USD",
    )
    if economics.experimental_net_risk_reward < policy.min_net_r:
        return SimStructuralTargetReceipt(
            "FIRST_OBSTACLE_NET_R_INSUFFICIENT", len(obstacles), first,
            economics=economics,
        )
    return SimStructuralTargetReceipt(
        "SIM_FIRST_OBSTACLE_NET_R_PASS", len(obstacles), first,
        obstacles[1] if len(obstacles) > 1 else None, exits, economics,
    )
