"""P251: exact shared research profile in the real structural replay."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase

from mfx_research.p216_structural_sim_fold import run_structural_sim_fold
from mfx_research.p249_b2s2_sim_profile import read_shared_sim_profile
from mfx_research.p251_shared_structural_fold import (
    run_shared_structural_fold, verify_shared_structural_fold,
)
import test_mfx_p216_structural_sim_fold as fixture216


class P251Tests(TestCase):
    def setUp(self):
        f = fixture216.P216StructuralReplayTests()
        f.setUp()
        self.p = read_shared_sim_profile()
        self.snaps = (f.a, f.b)
        self.inputs = tuple(replace(fixture216.quote_input(s), max_quote_age=self.p.max_quote_age)
                            for s in self.snaps)
        self.plan = f.plan
        self.now = f.b.decision_utc+timedelta(hours=2)

    def run_shared(self, inputs=None):
        return run_shared_structural_fold(
            self.snaps, self.inputs if inputs is None else inputs, ((), ()),
            fold_plan=self.plan, evaluation_utc=self.now,
        )

    def test_exact_shared_profile_matches_existing_engine(self):
        r = self.run_shared()
        direct = run_structural_sim_fold(
            self.snaps, self.inputs, ((), ()), structural_policy=self.p.structural,
            fold_plan=self.plan, evaluation_utc=self.now,
        )
        self.assertEqual(r.receipt, direct)
        self.assertTrue(verify_shared_structural_fold(r))
        self.assertEqual(r.profile_sha256, self.p.fingerprint)

    def test_no_quotes_do_not_impute_exits(self):
        r = self.run_shared((None, None))
        self.assertEqual(r.public_summary()["structural_plans_accepted"], 0)
        self.assertEqual(r.receipt.structural, (None, None))

    def test_caller_cannot_change_quote_age(self):
        for age in (timedelta(seconds=1), timedelta(seconds=31)):
            with self.assertRaisesRegex(ValueError, "QUOTE_AGE"):
                self.run_shared((replace(self.inputs[0], max_quote_age=age), self.inputs[1]))

    def test_forged_profile_or_policy_rejected(self):
        r = self.run_shared()
        for v in (replace(r, profile_sha256="0"*64),
                  replace(r, receipt=replace(r.receipt, structural_policy=replace(
                      r.receipt.structural_policy, min_net_r=self.p.structural.min_net_r+1)))):
            with self.assertRaisesRegex(ValueError, "PROFILE_OR_STRUCTURAL"):
                verify_shared_structural_fold(v)

    def test_receipt_tamper_rejected(self):
        r = self.run_shared()
        v = replace(r, receipt=replace(r.receipt, structural=(None, None)))
        with self.assertRaisesRegex(ValueError, "RECEIPT_DRIFT"):
            verify_shared_structural_fold(v)

    def test_summary_not_performance_or_production(self):
        d = self.run_shared().public_summary()
        for key in ("historical_oos_qualified", "performance_computed",
                    "actual_fills_verified", "may_publish_buy_sell", "may_trade",
                    "real_quote_or_cost_inferred"):
            self.assertFalse(d[key])
        self.assertEqual(d["action"], "NO_SIGNAL")
