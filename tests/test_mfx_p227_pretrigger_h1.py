"""P227: only previously archive-visible H1, never future source or public prices."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest import TestCase

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_research.p227_pretrigger_h1 import calculate_pretrigger_h1

START = datetime(2026, 11, 26, 8, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
M5 = timedelta(minutes=5)


def fixture():
    raw = tuple(ClosedM5Bar(
        (START + i*M5).isoformat(), "1.1", "1.2", "1.0", "1.1")
        for i in range(60))
    clocks = tuple((START + (i+1)*HOUR + timedelta(minutes=7),
                    START + (i+1)*HOUR) for i in range(5))
    return raw, clocks


def run(raw, clocks):
    return calculate_pretrigger_h1(
        raw, clocks, latest_m15_open=START + timedelta(hours=4, minutes=45),
        decision_utc=START + timedelta(hours=5, minutes=7))


class P227PretriggerH1Tests(TestCase):
    def test_four_prior_hours_compute_both_zones(self):
        raw, clocks = fixture()
        r = run(raw, clocks)
        self.assertEqual(r.status, "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED")
        self.assertEqual(r.visible_contiguous_h1_rows, 4)
        self.assertEqual(r.mean_tr, Decimal("0.2"))
        self.assertEqual(r.support_zone, (Decimal("1.0"), Decimal("1.06")))
        self.assertEqual(r.resistance_zone, (Decimal("1.14"), Decimal("1.2")))
        self.assertEqual(r.cutoff_utc, START + timedelta(hours=4, minutes=30))
        self.assertEqual(r.action, "NO_SIGNAL")
        self.assertFalse(r.publisher_first_known_verified)
        self.assertFalse(r.numeric_policy_approved)

    def test_trigger_hour_mutation_does_not_change_context(self):
        raw, clocks = fixture()
        changed = raw[:48] + tuple(replace(b, high="1.9") for b in raw[48:])
        self.assertEqual(run(raw, clocks), run(changed, clocks))

    def test_late_fourth_hour_excluded_even_if_visible_at_decision(self):
        raw, clocks = fixture()
        late = clocks[:3] + ((START+timedelta(hours=4, minutes=31), clocks[3][1]),) + clocks[4:]
        self.assertEqual(run(raw, late).status, "PRETRIGGER_H1_STALE")

    def test_equal_cutoff_commit_is_available(self):
        raw, clocks = fixture()
        on_cutoff = clocks[:3] + ((START+timedelta(hours=4, minutes=30), clocks[3][1]),) + clocks[4:]
        self.assertEqual(run(raw, on_cutoff).status, "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED")

    def test_gap_cannot_be_bridged(self):
        raw, clocks = fixture()
        r = run(raw[:12]+raw[24:], clocks[:1]+clocks[2:])
        self.assertEqual(r.status, "PRETRIGGER_H1_HISTORY_INSUFFICIENT")

    def test_no_prior_commit_no_zone(self):
        raw, clocks = fixture()
        delayed = tuple((START+timedelta(hours=5, minutes=7), end) for _, end in clocks)
        r = run(raw, delayed)
        self.assertEqual(r.status, "NO_PRETRIGGER_ARCHIVE_HOUR")
        self.assertIsNone(r.support_zone)

    def test_bad_metadata_rejected(self):
        raw, clocks = fixture()
        with self.assertRaises(ValueError):
            run(raw, clocks[:-1])
        with self.assertRaises(ValueError):
            run(raw, clocks[:2]+((clocks[2][0], clocks[1][1]),)+clocks[3:])
