"""P213 strictly chronological synthetic split; no real OOS claim."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase

from mfx_research.option_b_v2_exit_touch_audit import audit_option_b_v2_sim_exit_touches
from mfx_research.p213_purged_sim_fold import SimFoldPlan, split_verified_sim_exit_audit
from test_mfx_p165_option_b_v2_chronological_replay import future, snapshot
from test_mfx_p166_option_b_v2_bidask_replay_bridge import bundle, price
from test_mfx_p167_option_b_v2_exit_touch_audit import make_bar


class P213PurgedFoldTests(TestCase):
    def setUp(self):
        self.a = snapshot("B2")
        self.b = future(snapshot("S2"), days=60)
        self.plan = SimFoldPlan(
            train_end=self.a.decision_utc + timedelta(days=1),
            test_start=self.a.decision_utc + timedelta(days=2),
            test_end=self.b.decision_utc + timedelta(days=1),
            embargo=timedelta(days=1), outcome_horizon=timedelta(hours=1),
        )

    def audit(self, snapshots=None, paths=None):
        s = (self.a, self.b) if snapshots is None else snapshots
        p = tuple((make_bar(x, "target"),) for x in s) if paths is None else paths
        return audit_option_b_v2_sim_exit_touches(
            price(s, tuple(bundle(x) for x in s)), p,
            evaluation_utc=s[-1].decision_utc + timedelta(hours=2),
        )

    def test_01_separated_train_test(self):
        r = split_verified_sim_exit_audit(self.audit(), plan=self.plan)
        self.assertEqual(r.training_indices, (0,))
        self.assertEqual(r.test_indices, (1,))
        self.assertTrue(r.public_summary()["nonempty_train_and_test"])
        self.assertFalse(r.public_summary()["historical_oos_qualified"])

    def test_02_purge_overlapping_feature_history(self):
        b = future(snapshot("S2"), days=3)
        r = split_verified_sim_exit_audit(self.audit((self.a, b)), plan=self.plan)
        self.assertEqual(r.purged_indices, (1,))
        self.assertEqual(r.test_indices, ())

    def test_03_purge_unmatured_training_horizon(self):
        plan = replace(self.plan, train_end=self.a.decision_utc + timedelta(minutes=10))
        r = split_verified_sim_exit_audit(self.audit(), plan=plan)
        self.assertEqual(r.purged_indices, (0,))
        self.assertEqual(r.training_indices, ())

    def test_04_horizon_mismatch_denied(self):
        plan = replace(self.plan, outcome_horizon=timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "EXCEEDS_FIXED_HORIZON"):
            split_verified_sim_exit_audit(self.audit(), plan=plan)

    def test_05_membership_not_selected_by_exit_touch(self):
        a = self.audit()
        b = self.audit(paths=((make_bar(self.a, "stop"),),
                              (make_bar(self.b, "both"),)))
        r = split_verified_sim_exit_audit(a, plan=self.plan)
        s = split_verified_sim_exit_audit(b, plan=self.plan)
        self.assertEqual(r.training_indices, s.training_indices)
        self.assertEqual(r.test_indices, s.test_indices)
        self.assertNotEqual(r.audited_chain, s.audited_chain)

    def test_06_invalid_embargo_denied(self):
        with self.assertRaisesRegex(ValueError, "INVALID_EXPLICIT"):
            replace(self.plan, embargo=timedelta(days=3))

    def test_07_tampered_exit_receipt_denied(self):
        a = replace(self.audit(), actual_fill_or_order_known=True)
        with self.assertRaises(ValueError):
            split_verified_sim_exit_audit(a, plan=self.plan)

    def test_08_maturity_after_test_end_purged(self):
        plan = replace(self.plan, test_end=self.b.decision_utc + timedelta(minutes=10))
        r = split_verified_sim_exit_audit(self.audit(), plan=plan)
        self.assertEqual(r.purged_indices, (1,))
        self.assertFalse(r.public_summary()["performance_computed"])
