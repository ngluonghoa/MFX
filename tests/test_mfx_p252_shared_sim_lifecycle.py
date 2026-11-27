"""P252: freeze actual structural risk and lifecycle to one profile."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase

from mfx_research.p218_sim_monitoring_lifecycle import (
    SimHTFPath, evaluate_sim_monitoring_lifecycle,
)
from mfx_research.p249_b2s2_sim_profile import read_shared_sim_profile
from mfx_research.p251_shared_structural_fold import run_shared_structural_fold
from mfx_research.p252_shared_sim_lifecycle import (
    run_shared_sim_lifecycle, verify_shared_sim_lifecycle,
)
import test_mfx_p216_structural_sim_fold as fixture216
from test_mfx_p167_option_b_v2_exit_touch_audit import make_bar


class P252Tests(TestCase):
    def setUp(self):
        f = fixture216.P216StructuralReplayTests()
        f.setUp()
        self.p = read_shared_sim_profile()
        self.snaps = (f.a, f.b)
        self.inputs = tuple(replace(fixture216.quote_input(s),
                                    max_quote_age=self.p.max_quote_age)
                            for s in self.snaps)
        self.plan = f.plan
        self.now = f.b.decision_utc+timedelta(hours=2)

    def fold(self, paths=((), ()), inputs=None):
        return run_shared_structural_fold(
            self.snaps, self.inputs if inputs is None else inputs, paths,
            fold_plan=self.plan, evaluation_utc=self.now,
        )

    def test_shared_lifecycle_matches_existing_engine(self):
        f = self.fold()
        paths = (SimHTFPath((), ()),)*2
        r = run_shared_sim_lifecycle(f, paths)
        self.assertEqual(r.monitoring, evaluate_sim_monitoring_lifecycle(
            f.receipt, paths, policy=self.p.monitoring))
        self.assertTrue(verify_shared_sim_lifecycle(r))

    def test_accepted_plans_use_trigger_close_plus_four_slots(self):
        f = self.fold()
        paths = []
        for s, p in zip(self.snaps, f.receipt.structural):
            self.assertIsNotNone(p.planned_exits)
            b = make_bar(s)
            e = p.planned_exits
            paths.append((replace(b, low=min(e.stop_price, e.target_price, b.low),
                                  high=max(e.stop_price, e.target_price, b.high)),))
        r = run_shared_sim_lifecycle(self.fold(tuple(paths)), (SimHTFPath((), ()),)*2)
        for row, s in zip(r.monitoring.train+r.monitoring.test, self.snaps):
            self.assertEqual(row.expiry_utc, s.bars.trigger_m15[-1].key.bar_end_utc+
                             timedelta(hours=1))
            self.assertEqual(row.state, "TOUCH_STRICTLY_BEFORE_MONITORING_CUTOFF")
            self.assertIsNotNone(row.lower_r)

    def test_missing_quotes_never_create_monitoring_scenario(self):
        r = run_shared_sim_lifecycle(self.fold(inputs=(None, None)),
                                     (SimHTFPath((), ()),)*2)
        self.assertTrue(all(x.state == "NO_ACCEPTED_PLAN"
                            for x in r.monitoring.train+r.monitoring.test))

    def test_forged_expiry_or_profile_rejected(self):
        r = run_shared_sim_lifecycle(self.fold(), (SimHTFPath((), ()),)*2)
        for v in (replace(r, profile_sha256="0"*64),
                  replace(r, monitoring=replace(r.monitoring, policy=replace(
                      r.monitoring.policy, expiry_m15_slots=3)))):
            with self.assertRaisesRegex(ValueError, "DRIFT"):
                verify_shared_sim_lifecycle(v)

    def test_tampered_monitoring_outcome_rejected(self):
        r = run_shared_sim_lifecycle(self.fold(), (SimHTFPath((), ()),)*2)
        with self.assertRaisesRegex(ValueError, "DRIFT"):
            verify_shared_sim_lifecycle(replace(
                r, monitoring=replace(r.monitoring, train=())))

    def test_no_performance_or_persistent_event_claim(self):
        r = run_shared_sim_lifecycle(self.fold(), (SimHTFPath((), ()),)*2)
        d = r.public_summary()
        self.assertEqual(d["expiry_m15_slots"], 4)
        self.assertEqual(d["action"], "NO_SIGNAL")
        for key in ("actual_fill_verified", "realized_profit_verified",
                    "historical_oos_qualified", "persistent_idempotence_verified",
                    "may_publish_buy_sell", "may_trade"):
            self.assertFalse(d[key])
