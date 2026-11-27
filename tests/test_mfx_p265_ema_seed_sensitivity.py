"""P265 paired EMA warm-up sensitivity, private agreement only."""
from dataclasses import replace
from unittest import TestCase

from mfx_research.p232_delayed_middle_pairs import replay_delayed_middle_pairs
from mfx_research.p263_private_ema_watch import ema_seed_comparison_available
from test_mfx_p263_private_ema_watch import fixture, observe


class P265Tests(TestCase):
    def test_complete_same_probe_and_short_seed_suffix(self):
        raw, clocks = fixture(101)
        a = observe(raw, clocks)
        self.assertTrue(ema_seed_comparison_available(a, a.cutoff_utc))
        self.assertEqual(a.comparison.agreement, ((True, True), (True, True)))

    def test_short_observation_retained_when_long_missing(self):
        raw, clocks = fixture(51)
        a = observe(raw, clocks)
        self.assertEqual(a.status, "OBSERVED")
        self.assertEqual(a.long_seed_clock_state, "OUTSIDE_TAIL")
        self.assertFalse(ema_seed_comparison_available(a, a.cutoff_utc))

    def test_seed_length_can_change_watch_not_a_policy_selection(self):
        raw, clocks = fixture(101)
        raw = tuple(replace(x, open="1.4", high="1.401", low="1.399", close="1.4")
                    if i < 600 else replace(x, high="1.101", low="1.099")
                    for i, x in enumerate(raw))
        a = observe(raw, clocks)
        self.assertTrue(ema_seed_comparison_available(a, a.cutoff_utc))
        self.assertTrue(all(x.near50 for x in a.observations))
        self.assertTrue(all(not pair[1] for pair in a.comparison.agreement))

    def test_earlier_gap_blocks_long_only_and_future_price_ignored(self):
        raw, clocks = fixture(101)
        a = observe(raw, clocks)
        changed = raw[:-6]+tuple(replace(x, high="1.9") for x in raw[-6:])
        self.assertEqual(a, observe(changed, clocks))
        b = observe(raw[:12]+raw[24:], clocks[:1]+clocks[2:])
        self.assertEqual(a.observations, b.observations)
        self.assertEqual(b.long_seed_clock_state, "MISSING_HOUR")
        self.assertFalse(ema_seed_comparison_available(b, b.cutoff_utc))

    def test_tamper_and_public_redaction(self):
        raw, clocks = fixture(101)
        a = observe(raw, clocks)
        bad = replace(a, comparison=replace(a.comparison, agreement=((False, False),)*2))
        with self.assertRaisesRegex(ValueError, "P265_COMPARISON_PAIR_DRIFT"):
            ema_seed_comparison_available(bad, a.cutoff_utc)
        s = replay_delayed_middle_pairs(raw, clocks, (), ()).public_summary()
        self.assertEqual(s["ema_paired_50_100_seed_coverage"], 1)
        self.assertNotIn("agreement", str(s))
        self.assertNotIn("near50", str(s))
        self.assertEqual(s["action"], "NO_SIGNAL")
