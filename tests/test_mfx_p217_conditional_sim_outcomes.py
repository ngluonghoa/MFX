"""P217 scenario bounds with structural P216 plans and exact SIM M5 slots."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from mfx_research.p217_conditional_sim_outcomes import evaluate_conditional_sim_outcomes
import test_mfx_p216_structural_sim_fold as fixture216
from test_mfx_p167_option_b_v2_exit_touch_audit import make_bar
from test_mfx_p215_sim_structural_tp1 import run


def scenario_bar(s, kind, *, offset=0):
    exits = run(s).planned_exits
    b = make_bar(s, offset=offset)
    low, high = sorted((exits.stop_price, exits.target_price))
    if kind == "both":
        return replace(b, low=low, high=high)
    if kind == "stop":
        return replace(b, low=low if s.rule_id == "B2" else b.low,
                       high=high if s.rule_id == "S2" else b.high)
    if kind == "target":
        return replace(b, low=low if s.rule_id == "S2" else b.low,
                       high=high if s.rule_id == "B2" else b.high)
    if kind == "open_stop":
        return replace(b, open=exits.stop_price, low=min(b.low, exits.stop_price),
                       high=max(b.high, exits.stop_price))
    return b


class P217OutcomeTests(TestCase):
    def setUp(self):
        self.fixture = fixture216.P216StructuralReplayTests()
        self.fixture.setUp()
        self.a, self.b = self.fixture.a, self.fixture.b

    def report(self, a_kind, b_kind):
        paths = tuple(() if kind is None else (scenario_bar(s, kind),)
                      for s, kind in ((self.a, a_kind), (self.b, b_kind)))
        return evaluate_conditional_sim_outcomes(self.fixture.run_fold(paths=paths))

    def test_ambiguous_both_directions_not_assumed_wins(self):
        r = self.report("both", "both")
        for fold in (r.train, r.test):
            self.assertEqual(fold.ambiguous_events, 1)
            self.assertEqual(fold.private_scored_subset_lower_sum_r, D("-1"))
            self.assertGreater(fold.private_scored_subset_upper_sum_r, D("0"))
            self.assertTrue(fold.outcomes[0].entry_fragment_unobserved)
        self.assertFalse(r.public_summary()["actual_fill_verified"])
        self.assertFalse(r.public_summary()["unconditional_outcome_bounds_verified"])

    def test_stop_and_target_use_net_r_once(self):
        r = self.report("stop", "target")
        self.assertEqual(r.train.private_scored_subset_lower_sum_r, D("-1"))
        self.assertEqual(r.train.private_scored_subset_upper_sum_r, D("-1"))
        rr = r.source.audit.prior.steps[1].economics.experimental_net_risk_reward
        self.assertEqual(r.test.private_scored_subset_lower_sum_r, rr)
        self.assertEqual(r.test.private_scored_subset_upper_sum_r, rr)

    def test_no_path_and_no_touch_not_zero_returns(self):
        r = self.report(None, "none")
        for fold in (r.train, r.test):
            self.assertEqual(fold.planned_events, 1)
            self.assertEqual(fold.scored_events, 0)
            self.assertEqual(fold.unresolved_events, 1)
            self.assertIsNone(fold.private_scored_subset_lower_sum_r)
            self.assertIsNone(fold.private_scored_subset_upper_sum_r)

    def test_open_breach_unresolved(self):
        r = self.report("open_stop", "open_stop")
        for fold in (r.train, r.test):
            self.assertEqual(fold.outcomes[0].state, "UNRESOLVED_OPEN_BREACH")
            self.assertEqual(fold.unresolved_events, 1)

    def test_late_start_cannot_be_scored(self):
        source = self.fixture.run_fold(paths=((scenario_bar(self.a, "both", offset=1),), ()))
        r = evaluate_conditional_sim_outcomes(source)
        self.assertEqual(r.train.outcomes[0].state, "UNRESOLVED_LATE_OR_OFF_GRID_START")
        self.assertEqual(r.train.scored_events, 0)

    def test_purged_event_not_scored(self):
        self.fixture.plan = replace(self.fixture.plan,
                                    train_end=self.a.decision_utc+timedelta(minutes=10))
        source = self.fixture.run_fold(paths=((scenario_bar(self.a, "both"),), ()))
        r = evaluate_conditional_sim_outcomes(source)
        self.assertEqual(r.train.planned_events, 0)
        self.assertEqual(r.train.outcomes, ())

    def test_blocked_plan_not_an_unresolved_trade(self):
        source = self.fixture.run_fold(inputs=(None, None))
        r = evaluate_conditional_sim_outcomes(source)
        for fold in (r.train, r.test):
            self.assertEqual(fold.planned_events, 0)
            self.assertEqual(fold.unresolved_events, 0)

    def test_revised_path_rejected_for_scoring(self):
        b = replace(scenario_bar(self.a, "both"), revision_number=2)
        source = self.fixture.run_fold(paths=((b,), ()))
        with self.assertRaisesRegex(ValueError, "EXACT_INITIAL_SIM_M5_GRID"):
            evaluate_conditional_sim_outcomes(source)

    def test_tampered_fold_and_private_numbers_not_published(self):
        import json
        r = self.report("both", "target")
        source = replace(r.source, fold=replace(r.source.fold, test_indices=()))
        with self.assertRaises(ValueError):
            evaluate_conditional_sim_outcomes(source)
        public = json.dumps(r.public_summary())
        self.assertNotIn("private_scored_subset", public)
        self.assertNotIn("conditional_lower_r", public)
        self.assertEqual(r.public_summary()["action"], "NO_SIGNAL")
