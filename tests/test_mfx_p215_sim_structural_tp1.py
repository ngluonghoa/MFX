"""P215 tests: first-obstacle economics and mirrored quote-side semantics."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from forex_trading.market_data import Timeframe
from forex_trading.quotes import PriceSide
from mfx_research.p189_b2s2_executable_ohlc_mirror import reflect_sim_b2s2_packet
from mfx_research.p215_sim_structural_tp1 import (
    SimStructuralTargetPolicy, plan_sim_structural_tp1,
)
from test_mfx_p165_option_b_v2_chronological_replay import snapshot
from test_mfx_p166_option_b_v2_bidask_replay_bridge import bundle


def policy(**kw):
    values = dict(stop_frame=Timeframe.H1, stop_buffer=D("0.0001"),
                  target_buffer=D("0"), mid_exit_offset=D("0.0001"),
                  min_net_r=D("0.1"))
    values.update(kw)
    return SimStructuralTargetPolicy(**values)


def run(s, p=None, **kw):
    b = bundle(s)
    values = dict(quote=b.quote, costs=b.costs, max_quote_age=b.max_quote_age)
    values.update(kw)
    return plan_sim_structural_tp1(s, p or policy(), **values)


def wide_targets(s):
    rows = tuple(replace(b, high=D("1.107")) if s.rule_id == "B2"
                 else replace(b, low=D("1.190")) for b in s.bars.hourly)
    return replace(s, bars=replace(s.bars, hourly=rows))


class P215Tests(TestCase):
    def test_first_obstacle_in_spread_never_skipped(self):
        for rule in ("B2", "S2"):
            r = run(snapshot(rule))
            self.assertEqual(r.status, "FIRST_OBSTACLE_NO_ROOM")
            self.assertGreater(r.obstacle_count, 1)
            self.assertIsNone(r.planned_exits)
            self.assertIsNone(r.next_contextual_obstacle)

    def test_structural_stop_and_first_target_with_costs(self):
        for rule in ("B2", "S2"):
            s = wide_targets(snapshot(rule))
            r = run(s)
            self.assertEqual(r.status, "SIM_FIRST_OBSTACLE_NET_R_PASS")
            self.assertEqual(r.planned_exits.target_price, r.first_obstacle)
            self.assertEqual(r.planned_exits.exit_side,
                             PriceSide.BID if rule == "B2" else PriceSide.ASK)
            self.assertEqual(r.economics.entry_side,
                             PriceSide.ASK if rule == "B2" else PriceSide.BID)
            self.assertGreater(r.economics.experimental_net_risk_reward, D("0.1"))

    def test_high_minimum_never_hunts_far_target(self):
        s = wide_targets(snapshot())
        good = run(s)
        blocked = run(s, policy(min_net_r=D("1000")))
        self.assertEqual(blocked.first_obstacle, good.first_obstacle)
        self.assertEqual(blocked.status, "FIRST_OBSTACLE_NET_R_INSUFFICIENT")
        self.assertIsNone(blocked.planned_exits)
        self.assertIsNone(blocked.next_contextual_obstacle)

    def test_reflected_packet_and_quote_mirror_first_obstacle(self):
        s = wide_targets(snapshot())
        anchor = D("1.15")
        bars, hist = reflect_sim_b2s2_packet(
            s.bars, s.confirmed_m15_history, anchor=anchor,
        )
        reflected = replace(s, rule_id="S2", bars=bars, confirmed_m15_history=hist)
        q = bundle(s).quote
        opposite = replace(q, bid=2*anchor-q.ask, ask=2*anchor-q.bid)
        a = run(s)
        b = run(reflected, quote=opposite)
        self.assertEqual(a.status, b.status)
        self.assertEqual(b.first_obstacle, 2*anchor-a.first_obstacle)
        self.assertEqual(b.planned_exits.stop_price, 2*anchor-a.planned_exits.stop_price)
        self.assertEqual(b.economics.experimental_net_risk_reward,
                         a.economics.experimental_net_risk_reward)

    def test_target_buffer_cannot_skip_first_obstacle(self):
        s = wide_targets(snapshot())
        base = run(s)
        blocked = run(s, policy(target_buffer=D("0.1")))
        self.assertEqual(blocked.first_obstacle, base.first_obstacle)
        self.assertEqual(blocked.status, "FIRST_OBSTACLE_NO_ROOM")

    def test_stale_quote_rejected(self):
        with self.assertRaises(ValueError):
            run(snapshot(), max_quote_age=timedelta(microseconds=1))

    def test_invalid_policy_no_defaults(self):
        for kw in (dict(stop_frame=Timeframe.M15), dict(stop_buffer=D("0")),
                   dict(target_buffer=D("-0.01")), dict(min_net_r=D("0"))):
            with self.assertRaises(ValueError):
                policy(**kw)

    def test_summary_not_approved_or_price_bearing(self):
        import json
        r = run(wide_targets(snapshot()))
        d = r.public_summary()
        self.assertFalse(d["numeric_source_approved"])
        self.assertFalse(d["may_publish_buy_sell"])
        self.assertEqual(d["action"], "NO_SIGNAL")
        self.assertNotIn("first_obstacle", json.dumps(d))
        self.assertNotIn("planned_exits", json.dumps(d))
