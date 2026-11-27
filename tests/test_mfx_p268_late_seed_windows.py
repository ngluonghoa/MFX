"""P268 observed arrival windows for late-only EMA seeds, without promotion."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase

from mfx_research.p232_delayed_middle_pairs import replay_delayed_middle_pairs
from mfx_research.p263_private_ema_watch import late_seed_window
from test_mfx_p263_private_ema_watch import fixture, observe


def late_fixture(minutes):
    raw, clocks = fixture()
    end = clocks[-2][1]
    clocks = clocks[:-2] + ((end+timedelta(minutes=minutes), end),) + clocks[-1:]
    return raw, clocks


class P268Tests(TestCase):
    def test_first_probe_inclusive(self):
        raw, clocks = late_fixture(30)
        result = observe(raw, clocks)
        self.assertEqual(result.status, "HISTORY_UNAVAILABLE")
        self.assertEqual(late_seed_window(result, result.cutoff_utc, clocks[-1][0]),
                         "BY_FIRST_PROBE_CLOSE")

    def test_pair_close_inclusive(self):
        raw, clocks = late_fixture(45)
        result = observe(raw, clocks)
        self.assertEqual(late_seed_window(result, result.cutoff_utc, clocks[-1][0]),
                         "BY_PAIR_CLOSE")

    def test_after_pair_close(self):
        raw, clocks = late_fixture(46)
        result = observe(raw, clocks)
        self.assertEqual(late_seed_window(result, result.cutoff_utc, clocks[-1][0]),
                         "AFTER_PAIR_CLOSE")

    def test_complete_and_missing_not_reclassified(self):
        for hours in (50, 51):
            raw, clocks = fixture(hours)
            result = observe(raw, clocks)
            self.assertIsNone(late_seed_window(result, result.cutoff_utc, clocks[-1][0]))

    def test_forged_clock_rejected(self):
        raw, clocks = late_fixture(30)
        result = observe(raw, clocks)
        for value in (None, result.cutoff_utc, clocks[-1][0]+timedelta(seconds=1)):
            with self.assertRaisesRegex(ValueError, "P268_LATE_SEED_CLOCK_DRIFT"):
                late_seed_window(replace(result, late_seed_ready_utc=value),
                                 result.cutoff_utc, clocks[-1][0])

    def test_public_partition_and_no_private_timestamp(self):
        raw, clocks = late_fixture(31)
        replay = replay_delayed_middle_pairs(raw, clocks, (), ())
        result = replay.samples[-1].ema_watch
        s = replay.public_summary()
        self.assertEqual(s["ema_late_seed_by_pair_close"], 1)
        self.assertEqual(sum(v for k, v in s.items() if k.startswith("ema_late_seed_")),
                         s["ema_seed_clock_late_hour"])
        self.assertNotIn("late_seed_ready_utc", str(s))
        self.assertEqual(result.status, "HISTORY_UNAVAILABLE")
        self.assertEqual(s["action"], "NO_SIGNAL")
