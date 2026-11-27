"""P250: actual shared profile across P189/P214/P215 arithmetic."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from forex_trading.market_data import Timeframe
from mfx_research.p250_shared_sim_mirror import verify_shared_sim_mirror
from test_mfx_p165_option_b_v2_chronological_replay import snapshot
from test_mfx_p166_option_b_v2_bidask_replay_bridge import bundle
from test_mfx_p214_sim_htf_invalidation import later, levels
from test_mfx_p215_sim_structural_tp1 import wide_targets


def run(s, **kwargs):
    b = bundle(s)
    args = dict(quote=b.quote, costs=b.costs, h1_path=(), h4_path=(),
                evaluation_utc=s.decision_utc+timedelta(minutes=1),
                anchor=D("1.15"))
    args.update(kwargs)
    return verify_shared_sim_mirror(s, **args)


class P250MirrorTests(TestCase):
    def test_both_directions_block_near_obstacle_symmetrically(self):
        for rule in ("B2", "S2"):
            r = run(snapshot(rule))
            self.assertFalse(r.exits_compared)
            self.assertEqual(r.invalidation_frames_compared, 2)

    def test_wide_target_economics_mirror(self):
        for rule in ("B2", "S2"):
            r = run(wide_targets(snapshot(rule)))
            self.assertTrue(r.economics_compared)
            self.assertTrue(r.public_summary()["structural_disposition_mirror_verified"])

    def test_shared_buffer_strict_boundary_and_breach(self):
        for rule in ("B2", "S2"):
            s = snapshot(rule)
            sign = -1 if rule == "B2" else 1
            for distance in (D("0.00005"), D("0.00006")):
                b = later(s, Timeframe.H1, levels(s)[0]+sign*distance)
                r = run(s, h1_path=(b,), evaluation_utc=b.first_known_utc)
                self.assertEqual(r.invalidation_frames_compared, 2)

    def test_no_setup_mirrors_without_invalidation_path(self):
        s = snapshot()
        s = replace(s, bars=replace(s.bars, daily=s.bars.daily[:4]))
        r = run(s)
        self.assertFalse(r.economics_compared)
        self.assertEqual(r.invalidation_frames_compared, 0)

    def test_future_known_path_rejected(self):
        s = snapshot()
        b = later(s, Timeframe.H1, levels(s)[0])
        with self.assertRaises(ValueError):
            run(s, h1_path=(b,), evaluation_utc=b.first_known_utc-timedelta(seconds=1))

    def test_non_sim_quote_rejected(self):
        s = snapshot()
        q = replace(bundle(s).quote, provider="REAL")
        with self.assertRaises(ValueError):
            run(s, quote=q)

    def test_no_signal_or_source_promotion(self):
        r = run(wide_targets(snapshot()))
        d = r.public_summary()
        self.assertEqual(d["action"], "NO_SIGNAL")
        self.assertFalse(d["may_publish_buy_sell"])
        self.assertFalse(d["original_forex_numeric_parity_verified"])
        self.assertFalse(d["actual_market_economics_verified"])
        self.assertNotIn("1.10", repr(r))
