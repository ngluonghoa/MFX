"""P278 active-vintage stability and ordinal capacity are not D1 authority."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from mfx_cache.native_fx_htf import NativeFXBar
from mfx_research.p278_d1_vintage_research import study_native_vintages
from tools.audit_mfx_p209_d1_private_cache import PrivateSnapshot

BASE = datetime(2026, 11, 26, tzinfo=timezone.utc)
H = timedelta(hours=1)


def row(day, high="11", low="9"):
    return NativeFXBar("EUR/USD", "1day", f"2026-11-{day:02}",
                       "EXCHANGE_LOCAL_SESSION_DATE", "Australia/Sydney",
                       "10", high, low, "10")


def snap(clock, rows):
    return PrivateSnapshot(clock, tuple(rows), clock.isoformat())


class P278Tests(TestCase):
    def test_revision_and_append_are_separate(self):
        a = snap(BASE, (row(18), row(19)))
        b = snap(BASE+H, (replace(a.rows[0], high="12"), row(19), row(20)))
        r = study_native_vintages(((BASE, a), (BASE+H, b)), cutoff=BASE+H)
        self.assertEqual((r.overlap_comparisons, r.changed_overlap_rows,
                          r.added_rows, r.removed_rows), (2, 1, 1, 0))
        self.assertEqual(r.distinct_active_vintages, 2)
        self.assertFalse(r.public_summary()["native_d1_calendar_qualified"])

    def test_late_old_snapshot_does_not_replace_active(self):
        old = snap(BASE, (row(18),))
        new = snap(BASE+H, (row(18), row(19)))
        r = study_native_vintages(((BASE+2*H, old), (BASE+H, new)), cutoff=BASE+2*H)
        self.assertEqual((r.visible_snapshots, r.distinct_active_vintages,
                          r.removed_rows), (2, 1, 0))

    def test_future_archive_not_visible(self):
        a = snap(BASE, (row(18),))
        r = study_native_vintages(((BASE+H, a),), cutoff=BASE)
        self.assertEqual((r.visible_snapshots, r.distinct_active_vintages), (0, 0))
        self.assertFalse(r.latest_one_one_capacity)

    def test_short_latest_not_fallback(self):
        a = snap(BASE, (row(18), row(19)))
        b = snap(BASE+H, (row(18),))
        r = study_native_vintages(((BASE, a), (BASE+H, b)), cutoff=BASE+H)
        self.assertEqual((r.added_rows, r.removed_rows), (0, 1))

    def test_ordinal_capacity_with_two_distinct_highs_and_lows(self):
        rows = (row(18), row(19, high="12"), row(20, low="8"),
                row(21, high="13"), row(22, low="7"), row(23))
        r = study_native_vintages(((BASE, snap(BASE, rows)),), cutoff=BASE)
        self.assertTrue(r.latest_one_one_capacity)
        self.assertFalse(r.latest_two_two_capacity)
        self.assertEqual(r.public_summary()["action"], "NO_SIGNAL")

    def test_reordered_labels_rejected(self):
        a = snap(BASE, (row(19), row(18)))
        with self.assertRaisesRegex(ValueError, "ORDERED"):
            study_native_vintages(((BASE, a),), cutoff=BASE)
