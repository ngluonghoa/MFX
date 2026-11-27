"""P279 revision location and observation-age profile; no maturity authority."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from mfx_research.p278_d1_vintage_research import _age_bin, study_native_vintages
from test_mfx_p278_d1_vintage_research import row, snap, BASE, H


class P279Tests(TestCase):
    def test_terminal_vs_older_and_numeric_fields(self):
        a = snap(BASE, (row(18), row(19), row(20)))
        b = snap(BASE+H, (replace(a.rows[0], high="12"),
                          a.rows[1], replace(a.rows[2], close="10.5")))
        p = study_native_vintages(((BASE, a), (BASE+H, b)),
                                  cutoff=BASE+H).revision_profile
        self.assertEqual((p.prior_terminal_overlaps, p.prior_older_overlaps), (1, 2))
        self.assertEqual((p.prior_terminal_changes, p.prior_older_changes), (1, 1))
        self.assertEqual((p.numeric_open_changes, p.numeric_high_changes,
                          p.numeric_low_changes, p.numeric_close_changes), (0, 1, 0, 1))
        self.assertEqual(p.revised_distinct_labels, 2)
        self.assertEqual(p.observed_age_bins, (0, 0, 0, 0, 0, 2))
        self.assertFalse(p.public_summary()["maturity_policy_selected"])

    def test_previous_terminal_on_append_not_current_terminal(self):
        a = snap(BASE, (row(18), row(19)))
        b = snap(BASE+H, (row(18), replace(a.rows[1], close="10.5"), row(20)))
        p = study_native_vintages(((BASE, a), (BASE+H, b)),
                                  cutoff=BASE+H).revision_profile
        self.assertEqual((p.prior_terminal_changes, p.prior_older_changes), (1, 0))

    def test_same_numeric_different_sha(self):
        a = snap(BASE, (row(18),))
        b = snap(BASE+H, (replace(a.rows[0], close="10.0"),))
        p = study_native_vintages(((BASE, a), (BASE+H, b)),
                                  cutoff=BASE+H).revision_profile
        self.assertEqual(p.sha_changes_without_numeric_ohlc_change, 1)
        self.assertEqual(p.numeric_close_changes, 0)

    def test_age_bins_exact_boundary_and_dst(self):
        for label, end in (
            ("2026-11-24", datetime(2026, 11, 24, 13, tzinfo=timezone.utc)),
            ("2026-07-24", datetime(2026, 7, 24, 14, tzinfo=timezone.utc)),
        ):
            self.assertEqual(_age_bin(label, end-timedelta(seconds=1)), 0)
            for n, h in enumerate((0, 3, 6, 12, 24), 1):
                self.assertEqual(_age_bin(label, end+h*H), n)

    def test_late_old_and_future_not_counted(self):
        a = snap(BASE, (row(18),))
        b = snap(BASE+H, (replace(a.rows[0], close="10.5"),))
        c = snap(BASE+3*H, (row(18),))
        p = study_native_vintages(((BASE+2*H, a), (BASE+H, b),
                                   (BASE+3*H, c)), cutoff=BASE+2*H).revision_profile
        self.assertEqual(p.prior_terminal_overlaps, 0)
        self.assertEqual(sum(p.observed_age_bins), 0)

    def test_repeated_revision_count_not_independent_labels(self):
        a = snap(BASE, (row(18),))
        b = snap(BASE+H, (replace(a.rows[0], close="10.5"),))
        c = snap(BASE+2*H, a.rows)
        p = study_native_vintages(((BASE, a), (BASE+H, b), (BASE+2*H, c)),
                                  cutoff=BASE+2*H).revision_profile
        self.assertEqual((p.prior_terminal_changes, p.revised_distinct_labels), (2, 1))
        self.assertEqual(p.numeric_close_changes, 2)
