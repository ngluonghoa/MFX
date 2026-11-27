"""P255: cost stress preserves target and cannot claim market calibration."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

import test_mfx_p216_structural_sim_fold as f216
from mfx_research.p249_b2s2_sim_profile import read_shared_sim_profile
from mfx_research.p251_shared_structural_fold import run_shared_structural_fold
from mfx_research.p218_sim_monitoring_lifecycle import SimHTFPath
from mfx_research.p252_shared_sim_lifecycle import run_shared_sim_lifecycle
from mfx_research.p255_shared_cost_stress import (
    stress_fixed_targets, verify_fixed_target_stress,
)


class P255Tests(TestCase):
    def setUp(self):
        f = f216.P216StructuralReplayTests()
        f.setUp()
        snaps = (f.a, f.b)
        profile = read_shared_sim_profile()
        inputs = tuple(replace(f216.quote_input(s),
                               max_quote_age=profile.max_quote_age) for s in snaps)
        self.fold = run_shared_structural_fold(
            snaps, inputs, ((), ()), fold_plan=f.plan,
            evaluation_utc=f.b.decision_utc + timedelta(hours=2))
        self.life = run_shared_sim_lifecycle(self.fold, (SimHTFPath((), ()),)*2)
        self.grid = (D("0"), D("0.0001"), D("0.1"))

    def test_adverse_cost_cannot_improve_pass_count(self):
        r = stress_fixed_targets(self.life, self.grid)
        self.assertGreater(r.eligible_count, 0)
        self.assertEqual(r.pass_counts[0], r.eligible_count)
        self.assertEqual(r.pass_counts[-1], 0)
        self.assertEqual(tuple(sorted(r.pass_counts, reverse=True)), r.pass_counts)

    def test_receipt_recomputation(self):
        r = stress_fixed_targets(self.life, self.grid)
        self.assertTrue(verify_fixed_target_stress(r))
        with self.assertRaisesRegex(ValueError, "RECEIPT_DRIFT"):
            verify_fixed_target_stress(replace(r, eligible_count=r.eligible_count+1))

    def test_grid_rejects_optimistic_or_ambiguous_scenarios(self):
        for grid in ((D("0"), D("-1")), (D("1"), D("2")),
                     (D("0"), D("0")), (D("0"), D("NaN")), (D("0"), 1)):
            with self.assertRaisesRegex(ValueError, "ADVERSE_FEE_GRID"):
                stress_fixed_targets(self.life, grid)

    def test_public_scope(self):
        s = stress_fixed_targets(self.life, self.grid).public_summary()
        self.assertEqual(s["action"], "NO_SIGNAL")
        for k in ("calibrated", "historical_oos_qualified", "performance_computed",
                  "may_publish_buy_sell", "may_trade"):
            self.assertFalse(s[k])
