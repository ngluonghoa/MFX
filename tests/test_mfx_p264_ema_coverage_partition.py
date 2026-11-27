"""P264: actual archive EMA coverage partition, not direction or outcomes."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase

from mfx_research.p232_delayed_middle_pairs import replay_delayed_middle_pairs
from mfx_research.p263_private_ema_watch import ema_clock_state
from test_mfx_p263_private_ema_watch import fixture, observe


class P264Tests(TestCase):
    def test_tail_and_late_distinguished(self):
        raw, clocks = fixture(50)
        self.assertEqual(observe(raw, clocks).seed_clock_state, "OUTSIDE_TAIL")
        raw, clocks = fixture()
        late = clocks[:-2] + ((clocks[-2][1] + timedelta(minutes=16),
                               clocks[-2][1]),) + clocks[-1:]
        self.assertEqual(observe(raw, late).seed_clock_state, "LATE_HOUR")

    def test_interior_missing_and_mixed(self):
        raw, clocks = fixture()
        self.assertEqual(observe(raw[:12]+raw[24:], clocks[:1]+clocks[2:]).seed_clock_state,
                         "MISSING_HOUR")
        late = clocks[:-2] + ((clocks[-2][1] + timedelta(minutes=16),
                               clocks[-2][1]),) + clocks[-1:]
        self.assertEqual(observe(raw[:12]+raw[24:], late[:1]+late[2:]).seed_clock_state,
                         "MIXED")

    def test_clock_state_independent_of_prices_and_partition(self):
        raw, clocks = fixture()
        a = replay_delayed_middle_pairs(raw, clocks, (), ()).public_summary()
        b = replay_delayed_middle_pairs(tuple(replace(x, high="1.9") for x in raw),
                                        clocks, (), ()).public_summary()
        for k in a:
            if k.startswith("ema_seed_clock_"):
                self.assertEqual(a[k], b[k])
        self.assertEqual(sum(v for k, v in a.items() if k.startswith("ema_seed_clock_")), 32)
        self.assertEqual(a["ema_seed_clock_complete"], 1)
        self.assertEqual(a["ema_with_bound_context"], 0)
        self.assertEqual(a["ema_with_bound_context_decision_and_both_boundary_grids"], 0)

    def test_inconsistent_clock_state_rejected(self):
        raw, clocks = fixture()
        a = observe(raw, clocks)
        with self.assertRaisesRegex(ValueError, "P264_SEED_CLOCK_STATUS_DRIFT"):
            ema_clock_state(replace(a, seed_clock_state="LATE_HOUR"), a.cutoff_utc)

    def test_zero_tr_separate_from_clock_gap(self):
        raw, clocks = fixture()
        raw = tuple(replace(x, high="1.1", low="1.1") for x in raw)
        a = observe(raw, clocks)
        self.assertEqual(a.status, "ZERO_TR")
        self.assertEqual(ema_clock_state(a, a.cutoff_utc), "COMPLETE")
        summary = replay_delayed_middle_pairs(raw, clocks, (), ()).public_summary()
        self.assertEqual(summary["ema_seed_zero_tr"], 1)
        self.assertEqual(summary["pretrigger_ema50_seeded_observation_coverage"], 0)
