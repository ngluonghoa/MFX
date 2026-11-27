"""P277 private UTC civil-day coverage, no native-session authority."""
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_research.p277_civil_day_research import study_civil_days

START = datetime(2026, 11, 20, tzinfo=timezone.utc)
H = timedelta(hours=1)


def source(hours, *, missing=(), delay=timedelta(0)):
    bars, commits = [], []
    for i in range(hours):
        if i in missing:
            continue
        start = START+i*H
        end = start+H
        commits.append((end+delay, end))
        for j in range(12):
            bars.append(ClosedM5Bar(
                (start+timedelta(minutes=5*j)).isoformat(), "10", "11", "9", "10"))
    return tuple(bars), tuple(commits)


class P277Tests(TestCase):
    def test_complete_closed_days_include_weekend_as_diagnostic(self):
        result = study_civil_days(*source(72), cutoff=START+72*H)
        self.assertEqual((result.complete_days, result.complete_weekend_days,
                          result.latest_contiguous_days), (3, 2, 3))
        self.assertFalse(result.one_one_structure_capacity)
        self.assertFalse(result.public_summary()["native_d1_calendar_qualified"])

    def test_partial_day_and_late_commit(self):
        r = study_civil_days(*source(48, delay=H), cutoff=START+48*H)
        self.assertEqual((r.complete_days, r.incomplete_closed_days,
                          r.latest_contiguous_days), (1, 1, 0))

    def test_missing_hour_breaks_suffix(self):
        r = study_civil_days(*source(72, missing=(24,)), cutoff=START+72*H)
        self.assertEqual((r.complete_days, r.incomplete_closed_days,
                          r.latest_contiguous_days), (2, 1, 1))

    def test_missing_whole_day_not_silently_stitched(self):
        r = study_civil_days(*source(72, missing=tuple(range(24, 48))),
                             cutoff=START+72*H)
        self.assertEqual((r.complete_days, r.incomplete_closed_days,
                          r.latest_contiguous_days), (2, 1, 1))

    def test_grid_drift_rejected(self):
        bars, commits = source(24)
        with self.assertRaisesRegex(ValueError, "GRID"):
            study_civil_days((bars[1],)+bars[1:], commits, cutoff=START+24*H)
