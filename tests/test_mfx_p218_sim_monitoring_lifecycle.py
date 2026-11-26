"""P218 chronology and fold coverage, using structural SIM fixtures."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from forex_trading.market_data import Timeframe
from mfx_research.p214_sim_htf_invalidation import SimInvalidationPolicy
from mfx_research.p218_sim_monitoring_lifecycle import (
    SimHTFPath, SimMonitoringPolicy, evaluate_sim_monitoring_lifecycle,
)
import test_mfx_p216_structural_sim_fold as fixture216
from test_mfx_p217_conditional_sim_outcomes import scenario_bar
from test_mfx_p214_sim_htf_invalidation import later, levels
from test_mfx_p165_option_b_v2_chronological_replay import shift_bar


def touch_at(s, offset):
    return tuple(scenario_bar(s, "none", offset=i) for i in range(offset)) + (
        scenario_bar(s, "both", offset=offset),)


def breach(s):
    sign = -1 if s.rule_id == "B2" else 1
    return later(s, Timeframe.H1, levels(s)[0]+sign*D("0.0001"))


class P218MonitoringTests(TestCase):
    def setUp(self):
        self.fixture = fixture216.P216StructuralReplayTests()
        self.fixture.setUp()
        self.a, self.b = self.fixture.a, self.fixture.b

    def report(self, offset=0, slots=4, htf=None, frames=(Timeframe.H1, Timeframe.H4)):
        s = self.fixture.run_fold(paths=(touch_at(self.a, offset),
                                         touch_at(self.b, offset)))
        p = (SimHTFPath((), ()),)*2 if htf is None else htf
        return evaluate_sim_monitoring_lifecycle(
            s, p, policy=SimMonitoringPolicy(
                SimInvalidationPolicy(frames, D("0")), slots),
        )

    def test_early_touch_retained_before_any_new_htf_close(self):
        r = self.report()
        for row in (r.train[0], r.test[0]):
            self.assertEqual(row.state, "TOUCH_STRICTLY_BEFORE_MONITORING_CUTOFF")
            self.assertEqual(row.lower_r, D("-1"))
            self.assertGreater(row.upper_r, D("0"))

    def test_expiry_before_later_touch_no_imputed_fill(self):
        r = self.report(offset=3, slots=1)
        for row in (r.train[0], r.test[0]):
            self.assertEqual(row.state, "EXPIRY_BEFORE_TOUCH")
            self.assertIsNone(row.lower_r)

    def test_expiry_touches_bar_boundary_is_unresolved(self):
        r = self.report(offset=1, slots=1)
        self.assertEqual(r.train[0].state, "UNRESOLVED_CUTOFF_OVERLAPS_TOUCH_BAR")
        self.assertIsNone(r.test[0].upper_r)

    def test_invalidation_prior_to_touch_both_sides(self):
        h = tuple(SimHTFPath((breach(s),), ()) for s in (self.a, self.b))
        r = self.report(offset=6, htf=h)
        for row in (r.train[0], r.test[0]):
            self.assertEqual(row.state, "INVALIDATION_BEFORE_TOUCH")
            self.assertIsNone(row.upper_r)

    def test_invalidation_within_touch_bar_is_unresolved(self):
        h = tuple(SimHTFPath((breach(s),), ()) for s in (self.a, self.b))
        r = self.report(offset=5, htf=h)
        self.assertEqual(r.train[0].state, "UNRESOLVED_CUTOFF_OVERLAPS_TOUCH_BAR")

    def test_future_invalidation_does_not_remove_prior_touch(self):
        h = tuple(SimHTFPath((breach(s),), ()) for s in (self.a, self.b))
        r = self.report(htf=h)
        self.assertIsNotNone(r.train[0].lower_r)
        self.assertIsNotNone(r.test[0].lower_r)

    def test_missing_due_htf_slot_is_not_assumed_intact(self):
        r = self.report(offset=6)
        self.assertEqual(r.train[0].state, "UNRESOLVED_HTF_COVERAGE")
        self.assertIsNone(r.test[0].upper_r)

    def test_late_retrieval_cannot_establish_prior_coverage(self):
        b = breach(self.a)
        b = replace(b, observation=replace(
            b.observation, retrieved_at_utc=b.first_known_utc+timedelta(minutes=20)))
        r = self.report(offset=6, htf=(SimHTFPath((b,), ()), SimHTFPath((), ())))
        self.assertEqual(r.train[0].state, "UNRESOLVED_HTF_COVERAGE")

    def test_htf_path_outside_fixed_horizon_rejected(self):
        b = shift_bar(breach(self.a), timedelta(hours=2))
        with self.assertRaisesRegex(ValueError, "CROSSES_FOLD_OR_HORIZON"):
            self.report(htf=(SimHTFPath((b,), ()), SimHTFPath((), ())))

    def test_explicit_policy_and_redacted_scope(self):
        for value in (0, 33, True):
            with self.assertRaises(ValueError):
                SimMonitoringPolicy(SimInvalidationPolicy((Timeframe.H1,), D("0")), value)
        d = self.report().public_summary()
        self.assertEqual(d["action"], "NO_SIGNAL")
        self.assertFalse(d["actual_fill_verified"])
        self.assertFalse(d["historical_oos_qualified"])
        self.assertTrue(d["expiry_is_candidate_monitoring_cutoff_only"])
        self.assertNotIn("lower_r", str(d))
