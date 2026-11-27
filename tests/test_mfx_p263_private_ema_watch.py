"""P263 fixed visible seed and private-only EMA observation."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_engine import derive_intraday
from mfx_research.p263_private_ema_watch import (
    _observe_archive_ema, ema_observation_available,
)
from mfx_research.p232_delayed_middle_pairs import replay_delayed_middle_pairs
from test_mfx_p227_pretrigger_h1 import START, HOUR, M5


def fixture(hours=51):
    raw = tuple(ClosedM5Bar((START+i*M5).isoformat(), "1.1", "1.2", "1.0", "1.1")
                for i in range(12*hours))
    clocks = tuple((START+(i+1)*HOUR+timedelta(minutes=7), START+(i+1)*HOUR)
                   for i in range(hours))
    return raw, clocks


def observe(raw, clocks):
    known, end = clocks[-1]
    cutoff = end - timedelta(minutes=45)
    probe = derive_intraday(raw[-9:-6], "M15", asof_utc=known).candles[0]
    return _observe_archive_ema(raw, clocks, probe, cutoff=cutoff, decision=known)


class P263Tests(TestCase):
    def test_exact_visible_seed_and_both_sides(self):
        raw, clocks = fixture()
        result = observe(raw, clocks)
        self.assertTrue(ema_observation_available(result, result.cutoff_utc))
        self.assertTrue(all(x.near20 and x.near50 for x in result.observations))

    def test_short_or_late_history_not_filled(self):
        raw, clocks = fixture(50)
        self.assertEqual(observe(raw, clocks).status, "HISTORY_UNAVAILABLE")
        raw, clocks = fixture()
        late = clocks[:-2]+((clocks[-2][1]+timedelta(minutes=16), clocks[-2][1]),)+clocks[-1:]
        self.assertEqual(observe(raw, late).status, "HISTORY_UNAVAILABLE")

    def test_after_probe_mutation_does_not_change_observation(self):
        raw, clocks = fixture()
        a = observe(raw, clocks)
        changed = raw[:-6]+tuple(replace(x, high="1.9") for x in raw[-6:])
        self.assertEqual(a, observe(changed, clocks))

    def test_redacted_actual_replay_integration(self):
        raw, clocks = fixture()
        receipt = replay_delayed_middle_pairs(raw, clocks, (), ())
        summary = receipt.public_summary()
        self.assertEqual(summary["pretrigger_ema50_seeded_observation_coverage"], 1)
        self.assertNotIn("near20", str(summary))
        self.assertNotIn("near50", str(summary))
        self.assertEqual(summary["action"], "NO_SIGNAL")
        self.assertTrue(ema_observation_available(receipt.samples[-1].ema_watch,
                                                  receipt.samples[-1].h1.cutoff_utc))

    def test_bad_receipt_cannot_report_coverage(self):
        raw, clocks = fixture()
        a = observe(raw, clocks)
        with self.assertRaisesRegex(ValueError, "P263_EMA_PAIR"):
            ema_observation_available(replace(a, observations=()), a.cutoff_utc)
