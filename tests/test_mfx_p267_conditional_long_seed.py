"""P267 conditional long-seed clock coverage on actual replay receipts."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase

from mfx_research.p232_delayed_middle_pairs import replay_delayed_middle_pairs
from test_mfx_p263_private_ema_watch import fixture, observe


def summary(raw, clocks):
    replay = replay_delayed_middle_pairs(raw, clocks, (), ())
    return replay._summary((replay.samples[-1],))


def counts(result):
    return {k.removeprefix("ema_long_seed_given_short_"): v
            for k, v in result.items() if k.startswith("ema_long_seed_given_short_")}


class P267Tests(TestCase):
    def test_complete_pair(self):
        raw, clocks = fixture(101)
        s = summary(raw, clocks)
        self.assertEqual(counts(s)["complete"], 1)
        self.assertEqual(sum(counts(s).values()), 1)

    def test_short_only_due_to_tail(self):
        raw, clocks = fixture(51)
        s = summary(raw, clocks)
        self.assertEqual(counts(s)["outside_tail"], 1)
        self.assertEqual(s["ema_paired_50_100_seed_coverage"], 0)

    def test_short_only_due_to_missing_earlier_hour(self):
        raw, clocks = fixture(101)
        s = summary(raw[:12]+raw[24:], clocks[:1]+clocks[2:])
        self.assertEqual(counts(s)["missing_hour"], 1)

    def test_short_only_due_to_late_earlier_hour(self):
        raw, clocks = fixture(101)
        # A late earlier hour cannot be admitted by the private EMA clock.
        a = observe(raw, clocks)
        late = clocks[:1]+((a.cutoff_utc+timedelta(minutes=1), clocks[1][1]),)+clocks[2:]
        self.assertEqual(observe(raw, late).long_seed_clock_state, "LATE_HOUR")

    def test_excludes_short_unavailable_and_price_flat(self):
        raw, clocks = fixture(50)
        self.assertEqual(sum(counts(summary(raw, clocks)).values()), 0)
        raw, clocks = fixture(101)
        flat = tuple(replace(x, high="1.1", low="1.1") for x in raw)
        self.assertEqual(sum(counts(summary(flat, clocks)).values()), 0)

    def test_cohort_partition_and_redaction(self):
        raw, clocks = fixture(101)
        s = replay_delayed_middle_pairs(raw, clocks, (), ()).public_summary()
        self.assertEqual(sum(counts(s).values()), s["pretrigger_ema50_seeded_observation_coverage"])
        self.assertEqual(counts(s)["complete"], s["ema_paired_50_100_seed_coverage"])
        self.assertNotIn("agreement", str(s))
        self.assertEqual(s["action"], "NO_SIGNAL")
