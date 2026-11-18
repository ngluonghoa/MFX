"""P0.189 -- executable B2/S2 closed-OHLC counterfactual mirror witness.

This is an OFFLINE, SYNTHETIC-only adversarial regression of the *actual*
P0.161 Option-B-v2 D1/H4/H1/M15 calculations, not merely role-label mapping.
Reflect every closed OHLC and a preconfirmed M15 pivot history about a
positive Decimal price anchor. Equal bars stay equal, highs become lows,
TR and zone widths stay unchanged; BUY/S2 and SELL/B2 must invert exactly.

NEVER feed real provider data here, infer source publisher first-known, grant
original Forex numeric approval, quote or publish prices, or place orders.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, MarketBar, SourceQuality,
)
from mfx_research.causal_multitf_context import SyntheticMultiTfBars
from mfx_research.confirmed_swings import (
    PivotKind, SwingScanReceipt,
)
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    MfxB2S2V2ClosedResearch, MfxConfirmedB2S2V2Policy,
    compute_mfx_b2s2_v2_closed_candidate,
)
from mfx_research.offline_ema_signals import CandidateAction

VERSION = "MFX_P189_B2S2_EXECUTABLE_CLOSED_OHLC_MIRROR_SIM_ONLY_V1"
SIDES = {"B2": "S2", "S2": "B2"}
ACTIONS = {
    CandidateAction.BUY: CandidateAction.SELL,
    CandidateAction.SELL: CandidateAction.BUY,
    CandidateAction.NO_SIGNAL: CandidateAction.NO_SIGNAL,
}
TRENDS = {"UP": "DOWN", "DOWN": "UP", "UNKNOWN": "UNKNOWN"}
PIVOTS = {PivotKind.HIGH: PivotKind.LOW, PivotKind.LOW: PivotKind.HIGH}


def _sim_bar(bar: MarketBar) -> None:
    if type(bar) is not MarketBar:
        raise TypeError("P189_EXACT_SYNTHETIC_MARKETBAR_REQUIRED")
    if (not bar.key.instrument_version.startswith("SIM:")
            or not bar.key.calendar_version.startswith("SIM:")
            or not bar.observation.provider_id.startswith("SIM:")
            or not bar.observation.stream_id.startswith("SIM:")
            or bar.observation.license_scope_claim != "SYNTHETIC_ONLY"
            or bar.key.side is not BarSide.MID
            or bar.lifecycle is not BarLifecycle.CLOSED
            or bar.coverage is not BarCoverage.COMPLETE
            or bar.quality is not SourceQuality.VERIFIED
            or bar.revision_number != 1):
        raise ValueError("P189_REAL_UNVERIFIED_OR_REVISED_SOURCE_DENIED")


def _anchor(value: Decimal) -> Decimal:
    if type(value) is not Decimal or not value.is_finite() or value <= 0:
        raise ValueError("P189_POSITIVE_DECIMAL_MIRROR_ANCHOR_REQUIRED")
    return value


def reflect_sim_closed_ohlc(bar: MarketBar, *, anchor: Decimal) -> MarketBar:
    """Reflect price only; preserve exact source time, identity and provenance.

    This helper explicitly rejects real market data and mutated/partial bars.
    It is NOT an as-of validation replacement; the original P161 evaluator
    independently enforces those requirements on both original and reflection.
    """
    _sim_bar(bar)
    a = _anchor(anchor) * 2
    return replace(bar,
                   open=a-bar.open, high=a-bar.low,
                   low=a-bar.high, close=a-bar.close)


def reflect_sim_b2s2_packet(
    bars: SyntheticMultiTfBars,
    confirmed_m15_history: tuple[MarketBar, ...],
    *, anchor: Decimal,
) -> tuple[SyntheticMultiTfBars, tuple[MarketBar, ...]]:
    """Mirror D1/H4/H1/M15 input AND right-confirmed M15 witness together."""
    if type(bars) is not SyntheticMultiTfBars:
        raise TypeError("P189_EXACT_SYNTHETIC_4TF_PACKET_REQUIRED")
    if (type(confirmed_m15_history) is not tuple
            or not confirmed_m15_history
            or type(bars.trigger_m15) is not tuple
            or len(bars.trigger_m15) != 2
            or not all(type(x) is MarketBar for x in confirmed_m15_history)
            or confirmed_m15_history[-1] != bars.micro_seed_m15[-1]):
        raise ValueError("P189_EXACT_PRETRIGGER_CONFIRMED_M15_SEED_REQUIRED")
    _anchor(anchor)

    def rows(data: tuple[MarketBar, ...]) -> tuple[MarketBar, ...]:
        if type(data) is not tuple or not data:
            raise ValueError("P189_NONEMPTY_EXACT_SIM_CLOSED_TUPLES_REQUIRED")
        return tuple(reflect_sim_closed_ohlc(b, anchor=anchor) for b in data)

    reflected = SyntheticMultiTfBars(
        daily=rows(bars.daily),
        four_hour=rows(bars.four_hour),
        hourly=rows(bars.hourly),
        micro_seed_m15=rows(bars.micro_seed_m15),
        trigger_m15=rows(bars.trigger_m15),
    )
    history = rows(confirmed_m15_history)
    if history[-1] != reflected.micro_seed_m15[-1]:
        raise ValueError("P189_REFLECTED_PRIOR_M15_IDENTITY_DRIFT")
    return reflected, history


def _mirror_pivots(
    original: SwingScanReceipt,
    opposite: SwingScanReceipt,
    anchor: Decimal,
) -> None:
    if (original.timeframe is not opposite.timeframe
            or original.asof_utc != opposite.asof_utc
            or original.last_input_bar_end_utc != opposite.last_input_bar_end_utc
            or len(original.pivots) != len(opposite.pivots)):
        raise ValueError("P189_PIVOT_COUNT_OR_CAUSAL_CUTOFF_ASYMMETRY")
    for a, b in zip(original.pivots, opposite.pivots):
        if (b.kind is not PIVOTS[a.kind]
                or b.price != 2*anchor-a.price
                or a.candidate_index != b.candidate_index
                or a.confirmation_index != b.confirmation_index
                or a.candidate_bar_end_utc != b.candidate_bar_end_utc
                or a.confirmed_first_known_utc != b.confirmed_first_known_utc
                or b.source_verified or a.source_verified):
            raise ValueError("P189_PIVOT_PRICE_OR_RIGHT_CONFIRMATION_ASYMMETRY")


def _assert_research_only(r: MfxB2S2V2ClosedResearch) -> None:
    if (type(r) is not MfxB2S2V2ClosedResearch
            or r.public_action != "NO_SIGNAL"
            or r.stage != "UNVERIFIED"
            or r.independent_numeric_rule_approved
            or r.original_forex_numeric_1to1
            or r.source_market_rights_verified
            or r.native_d1_revision_hold_cleared
            or r.true_historical_oos_qualified
            or r.live_buy_sell_allowed
            or r.may_trade or r.new_provider_requests
            or r.new_drive_market_writes or r.broker_orders
            or r.source.may_send_confirmed_signal
            or r.source.can_trade):
        raise ValueError("P189_SIM_MIRROR_CANNOT_PROMOTE_SOURCE_AUTHORITY")


@dataclass(frozen=True, slots=True)
class SimB2S2MirrorWitness:
    """Private source values never appear in public logs or repr."""
    version: str
    input_rule: str
    mirrored_rule: str
    original: MfxB2S2V2ClosedResearch = field(repr=False)
    reflected: MfxB2S2V2ClosedResearch = field(repr=False)
    paired_executable_arithmetic_verified: bool = True
    original_forex_1to1_approved: bool = False
    original_numeric_approvals: int = 0
    original_numeric_pending: int = 36
    source_account_license_verified: bool = False
    publisher_first_known_verified: bool = False
    live_buy_sell_authorized: bool = False
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    broker_orders: int = 0

    def as_safe_summary(self) -> dict[str, str | bool | int]:
        return {
            "version": self.version,
            "mode": "SYNTHETIC_OFFLINE_ONLY",
            "mirrored_roles": "B2_S2",
            "actual_p161_arithmetic_mirrored": True,
            "original_numeric_approvals": 0,
            "original_numeric_pending": 36,
            "licensed_vendor_quote_data": False,
            "publisher_first_known_verified": False,
            "action": "NO_SIGNAL", "stage": "UNVERIFIED",
            "may_trade": False, "broker_orders": 0,
            "vendor_requests": 0, "drive_writes": 0,
        }


def verify_executable_b2s2_sim_mirror(
    rule_id: str,
    bars: SyntheticMultiTfBars,
    confirmed_m15_history: tuple[MarketBar, ...],
    policy: MfxConfirmedB2S2V2Policy,
    decision_utc: datetime,
    *,
    anchor: Decimal,
) -> SimB2S2MirrorWitness:
    """Recompute TWO real P161 candidate paths on reflected synthetic OHLC.

    The witness proves only mathematical B2/S2 inversion for this fixture
    and EXACT versioned experiment, never original Forex source parity.
    """
    if type(rule_id) is not str or rule_id not in SIDES:
        raise ValueError("P189_ONLY_B2_S2_MIRROR_PAIR")
    if type(policy) is not MfxConfirmedB2S2V2Policy:
        raise TypeError("P189_PINNED_P161_POLICY_REQUIRED")
    synthetic, mirrored_history = reflect_sim_b2s2_packet(
        bars, confirmed_m15_history, anchor=anchor,
    )
    original = compute_mfx_b2s2_v2_closed_candidate(
        rule_id, bars, confirmed_m15_history, policy, decision_utc,
    )
    opposite = compute_mfx_b2s2_v2_closed_candidate(
        SIDES[rule_id], synthetic, mirrored_history, policy, decision_utc,
    )
    _assert_research_only(original)
    _assert_research_only(opposite)
    if (original.experimental_action not in ACTIONS
            or opposite.experimental_action is not ACTIONS[
                original.experimental_action]
            or original.source.daily_trend.value not in TRENDS
            or original.source.four_hour_trend.value not in TRENDS
            or opposite.source.daily_trend.value !=
                TRENDS[original.source.daily_trend.value]
            or opposite.source.four_hour_trend.value !=
                TRENDS[original.source.four_hour_trend.value]
            or len(original.routed.classified) != len(opposite.routed.classified)
            or original.policy_fingerprint_sha256 !=
                opposite.policy_fingerprint_sha256):
        raise ValueError("P189_EXECUTABLE_B2_S2_ACTION_OR_TREND_ASYMMETRY")
    for a, b in (
        (original.source.daily, opposite.source.daily),
        (original.source.four_hour, opposite.source.four_hour),
    ):
        _mirror_pivots(a, b, anchor)
    if (original.source.m15_confirmed_pivots is None
            or opposite.source.m15_confirmed_pivots is None):
        raise ValueError("P189_PRETRIGGER_M15_PIVOTS_REQUIRED")
    _mirror_pivots(original.source.m15_confirmed_pivots,
                   opposite.source.m15_confirmed_pivots, anchor)
    a, b = original.source.derived_context, opposite.source.derived_context
    if (b.h1_zone_low != 2*anchor-a.h1_zone_high
            or b.h1_zone_high != 2*anchor-a.h1_zone_low
            or b.known_micro_level != 2*anchor-a.known_micro_level
            or b.known_atr != a.known_atr
            or a.context_first_known_utc != b.context_first_known_utc
            or original.source.signal.first_known_utc !=
                opposite.source.signal.first_known_utc
            or original.source.signal.decision_utc !=
                opposite.source.signal.decision_utc):
        raise ValueError("P189_H1_ZONE_TR_MICRO_OR_ASOF_ASYMMETRY")
    if any(x.label != expected for x, expected in (
        [(x, rule_id) for x in original.routed.classified]
        + [(x, SIDES[rule_id]) for x in opposite.routed.classified]
    )):
        raise ValueError("P189_ROUTER_ROLE_MIRROR_ASYMMETRY")
    return SimB2S2MirrorWitness(
        version=VERSION, input_rule=rule_id,
        mirrored_rule=SIDES[rule_id],
        original=original, reflected=opposite,
    )
