"""P250: verify shared P249 entry, structural economics and invalidation mirrors.

Only synthetic inputs are accepted by the original P189/P214/P215 gates.
Recompute both directions independently; do not infer source parity or fills.
"""
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from forex_trading.quotes import PriceSide, Quote
from mfx_research.bidask_cost_aware_sim_risk import SimPerUnitCosts
from mfx_research.mfx_b2s2_confirmed_policy_v2 import read_mfx_confirmed_b2s2_v2
from mfx_research.option_b_v2_chronological_replay import OptionBReplaySnapshot
from mfx_research.p189_b2s2_executable_ohlc_mirror import (
    SIDES, reflect_sim_b2s2_packet, reflect_sim_closed_ohlc,
    verify_executable_b2s2_sim_mirror,
)
from mfx_research.p214_sim_htf_invalidation import check_sim_setup_invalidation
from mfx_research.p215_sim_structural_tp1 import plan_sim_structural_tp1
from mfx_research.p249_b2s2_sim_profile import read_shared_sim_profile

VERSION = "MFX_P250_SHARED_SIM_MIRROR_V1"


@dataclass(frozen=True, slots=True)
class SharedSimMirror:
    profile_sha256: str
    economics_compared: bool
    exits_compared: bool
    invalidation_frames_compared: int

    def public_summary(self):
        return {
            "version": VERSION, "entry_mirror_verified": True,
            "structural_disposition_mirror_verified": True,
            "economics_compared": self.economics_compared,
            "exits_compared": self.exits_compared,
            "invalidation_frames_compared": self.invalidation_frames_compared,
            "original_forex_numeric_parity_verified": False,
            "actual_market_economics_verified": False,
            "action": "NO_SIGNAL", "may_publish_buy_sell": False,
            "may_trade": False, "broker_orders": 0,
        }


def _equal(a, b):
    if a != b:
        raise ValueError("P250_SHARED_POLICY_MIRROR_DRIFT")


def _price(a, b, twice):
    if a is None or b is None:
        _equal(a, b)
    else:
        _equal(b, twice - a)


def verify_shared_sim_mirror(
    snapshot: OptionBReplaySnapshot, *, quote: Quote,
    costs: SimPerUnitCosts, h1_path: tuple, h4_path: tuple,
    evaluation_utc: datetime, anchor: Decimal,
) -> SharedSimMirror:
    if (type(snapshot) is not OptionBReplaySnapshot or type(quote) is not Quote
            or type(costs) is not SimPerUnitCosts):
        raise TypeError("P250_EXACT_TYPED_SIM_INPUT_REQUIRED")
    if (type(h1_path) is not tuple or type(h4_path) is not tuple
            or len(h1_path) > 96 or len(h4_path) > 96):
        raise ValueError("P250_BOUNDED_IMMUTABLE_PATH_REQUIRED")
    profile = read_shared_sim_profile()
    policy = read_mfx_confirmed_b2s2_v2()
    verify_executable_b2s2_sim_mirror(
        snapshot.rule_id, snapshot.bars, snapshot.confirmed_m15_history,
        policy, snapshot.decision_utc, anchor=anchor,
    )
    bars, history = reflect_sim_b2s2_packet(
        snapshot.bars, snapshot.confirmed_m15_history, anchor=anchor,
    )
    mirrored = replace(snapshot, rule_id=SIDES[snapshot.rule_id],
                       bars=bars, confirmed_m15_history=history)
    twice = 2 * anchor
    reflected_quote = replace(quote, bid=twice-quote.ask, ask=twice-quote.bid)
    if (not quote.provider.startswith("SIM:")
            or not quote.source_revision.startswith("SIM:")):
        raise ValueError("P250_SIM_QUOTE_REQUIRED")
    r = plan_sim_structural_tp1(snapshot, profile.structural, quote=quote,
                               costs=costs, max_quote_age=profile.max_quote_age)
    s = plan_sim_structural_tp1(mirrored, profile.structural, quote=reflected_quote,
                               costs=costs, max_quote_age=profile.max_quote_age)
    _equal((r.status, r.obstacle_count), (s.status, s.obstacle_count))
    for name in ("first_obstacle", "next_contextual_obstacle"):
        _price(getattr(r, name), getattr(s, name), twice)
    _equal(r.planned_exits is None, s.planned_exits is None)
    _equal(r.economics is None, s.economics is None)
    side = {PriceSide.BID: PriceSide.ASK, PriceSide.ASK: PriceSide.BID}
    if r.planned_exits is not None:
        a, b = r.planned_exits, s.planned_exits
        _price(a.stop_price, b.stop_price, twice)
        _price(a.target_price, b.target_price, twice)
        _equal(side[a.exit_side], b.exit_side)
    if r.economics is not None:
        a, b = r.economics, s.economics
        _equal(side[a.entry_side], b.entry_side)
        _equal(side[a.exit_side], b.exit_side)
        _price(a.reference_bid, b.reference_ask, twice)
        _price(a.reference_ask, b.reference_bid, twice)
        for name in ("entry_reference_price", "effective_entry_price",
                     "stop_exit_reference_price", "target_exit_reference_price",
                     "effective_stop_exit_price", "effective_target_exit_price"):
            _price(getattr(a, name), getattr(b, name), twice)
        for name in ("reference_spread", "explicit_roundtrip_fee_per_base_unit",
                     "net_risk_quote_currency_per_base_unit",
                     "net_reward_quote_currency_per_base_unit",
                     "experimental_net_risk_reward"):
            _equal(getattr(a, name), getattr(b, name))
    def check(snap, h1, h4):
        return check_sim_setup_invalidation(
            snap, profile.monitoring.invalidation, h1_path=h1, h4_path=h4,
            evaluation_utc=evaluation_utc,
        )
    a = check(snapshot, h1_path, h4_path)
    b = check(mirrored,
              tuple(reflect_sim_closed_ohlc(x, anchor=anchor) for x in h1_path),
              tuple(reflect_sim_closed_ohlc(x, anchor=anchor) for x in h4_path))
    _equal((a.status, len(a.frames)), (b.status, len(b.frames)))
    for x, y in zip(a.frames, b.frames):
        _equal((x.timeframe, x.status, x.inspected, x.first_breach_known_utc),
               (y.timeframe, y.status, y.inspected, y.first_breach_known_utc))
        _price(x.frozen_anchor, y.frozen_anchor, twice)
    return SharedSimMirror(profile.fingerprint, r.economics is not None,
                           r.planned_exits is not None, len(a.frames))
