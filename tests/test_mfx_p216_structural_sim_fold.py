"""P216 end-to-end SIM structure, pricing, touch and fold regression."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from mfx_research.p213_purged_sim_fold import SimFoldPlan
from mfx_research.p216_structural_sim_fold import (
    SimQuoteCostInput, run_structural_sim_fold, verify_structural_sim_fold,
)
from test_mfx_p165_option_b_v2_chronological_replay import future, snapshot
from test_mfx_p166_option_b_v2_bidask_replay_bridge import bundle
from test_mfx_p167_option_b_v2_exit_touch_audit import make_bar
from test_mfx_p215_sim_structural_tp1 import policy, wide_targets


def quote_input(s):
    b = bundle(s)
    return SimQuoteCostInput(b.quote, b.costs, b.max_quote_age)


class P216StructuralReplayTests(TestCase):
    def setUp(self):
        self.a = wide_targets(snapshot("B2"))
        self.b = future(wide_targets(snapshot("S2")), days=60)
        self.plan = SimFoldPlan(
            train_end=self.a.decision_utc + timedelta(days=1),
            test_start=self.a.decision_utc + timedelta(days=2),
            test_end=self.b.decision_utc + timedelta(days=1),
            embargo=timedelta(days=1), outcome_horizon=timedelta(hours=1),
        )

    def run_fold(self, snaps=None, inputs=None, paths=None, p=None):
        s = (self.a, self.b) if snaps is None else snaps
        q = tuple(quote_input(x) for x in s) if inputs is None else inputs
        return run_structural_sim_fold(
            s, q, tuple(() for _ in s) if paths is None else paths,
            structural_policy=p or policy(), fold_plan=self.plan,
            evaluation_utc=s[-1].decision_utc + timedelta(hours=2),
        )

    def test_actual_structural_exits_in_both_folds(self):
        r = self.run_fold()
        for p, b, step in zip(r.structural, r.audit.prior.bundles, r.audit.prior.steps):
            self.assertEqual(p.planned_exits, b.exits)
            self.assertEqual(p.economics, step.economics)
        self.assertEqual(r.public_summary()["train_structural_plans"], 1)
        self.assertEqual(r.public_summary()["test_structural_plans"], 1)
        self.assertTrue(verify_structural_sim_fold(r))

    def test_stop_and_target_touches_remain_not_fills(self):
        r = self.run_fold(paths=((make_bar(self.a, "stop"),),
                                 (make_bar(self.b, "target"),)))
        self.assertEqual(r.audit.stop_only, 1)
        self.assertFalse(r.audit.actual_fill_or_order_known)
        self.assertFalse(r.public_summary()["performance_computed"])

    def test_nearest_obstacle_blocked_not_priced(self):
        s = snapshot("B2")
        r = self.run_fold(snaps=(s,))
        self.assertEqual(r.structural[0].status, "FIRST_OBSTACLE_NO_ROOM")
        self.assertIsNone(r.audit.prior.bundles[0])
        self.assertEqual(r.public_summary()["structural_plans_accepted"], 0)

    def test_below_min_net_r_never_priced(self):
        r = self.run_fold(p=policy(min_net_r=D("1000")))
        self.assertTrue(all(s.economics is not None for s in r.structural))
        self.assertEqual(r.audit.prior.bundles, (None, None))

    def test_duplicate_same_quote_is_not_second_plan(self):
        repeat = replace(self.a, decision_utc=self.a.decision_utc + timedelta(seconds=1))
        q = quote_input(self.a)
        r = self.run_fold(snaps=(self.a, repeat, self.b),
                          inputs=(q, q, quote_input(self.b)))
        self.assertIsNone(r.structural[1])
        self.assertEqual(r.fold.duplicate_indices, (1,))
        self.assertEqual(r.public_summary()["structural_plans_accepted"], 2)

    def test_duplicate_quote_drift_rejected_even_if_blocked(self):
        s = snapshot()
        repeat = replace(s, decision_utc=s.decision_utc + timedelta(seconds=1))
        q = quote_input(s)
        other = replace(q, costs=replace(q.costs, entry_fee=D("0.1")))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_QUOTE_OR_COST_DRIFT"):
            self.run_fold(snaps=(s, repeat), inputs=(q, other))

    def test_future_exit_path_for_blocked_plan_rejected(self):
        s = snapshot()
        with self.assertRaises(ValueError):
            self.run_fold(snaps=(s,), paths=((make_bar(s, "stop"),),))

    def test_missing_quote_is_not_accepted_plan(self):
        r = self.run_fold(inputs=(None, quote_input(self.b)))
        self.assertIsNone(r.structural[0])
        self.assertEqual(r.public_summary()["train_structural_plans"], 0)

    def test_tamper_fold_and_authority_rejected(self):
        r = self.run_fold()
        with self.assertRaisesRegex(ValueError, "RECEIPT_DRIFT"):
            verify_structural_sim_fold(replace(r, fold=replace(r.fold, test_indices=())))
        self.assertEqual(r.public_summary()["action"], "NO_SIGNAL")
        self.assertFalse(r.public_summary()["historical_oos_qualified"])
