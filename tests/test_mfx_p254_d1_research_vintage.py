"""P254 selection uses whole visible vintage; no fallback or stitching."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase

from mfx_research.p254_d1_research_vintage import select_private_d1_research_vintage
from test_mfx_p228_pretrigger_native import CUT, DECISION, vintage, run


class P254Tests(TestCase):
    def test_latest_observed_not_latest_created(self):
        old = vintage(CUT-timedelta(hours=2))
        new = replace(vintage(CUT-timedelta(hours=1)), identity="new")
        h = ((CUT-timedelta(seconds=1), old),
             (CUT-timedelta(minutes=1), new))
        self.assertIs(select_private_d1_research_vintage(h, cutoff=CUT), new)
        self.assertIs(select_private_d1_research_vintage(h[::-1], cutoff=CUT), new)

    def test_late_archive_not_historically_visible(self):
        a = vintage(CUT-timedelta(hours=1))
        self.assertIsNone(select_private_d1_research_vintage(
            ((CUT+timedelta(seconds=1), a),), cutoff=CUT))

    def test_latest_short_vintage_no_older_long_fallback(self):
        old = vintage(CUT-timedelta(hours=2))
        short = replace(vintage(CUT-timedelta(hours=1), last_day=18),
                        identity="short")
        history = ((old.observed, old), (short.observed, short))
        self.assertIs(select_private_d1_research_vintage(history, cutoff=CUT), short)
        r = run(d1=history)
        self.assertEqual(r.d1_rows, short.rows)
        self.assertEqual(r.d1_status, "PRETRIGGER_D1_STALE")
        self.assertFalse(r.d1_calendar_qualified)

    def test_equal_cutoff_visible_without_rewriting_old(self):
        a = vintage(CUT-timedelta(hours=1))
        b = replace(vintage(CUT), identity="new")
        h = ((a.observed, a), (CUT, b))
        self.assertIs(select_private_d1_research_vintage(h, cutoff=CUT), b)
        self.assertIs(select_private_d1_research_vintage(h, cutoff=CUT-timedelta(seconds=1)), a)

    def test_bad_clock_and_duplicate_observation_denied(self):
        a = vintage(CUT-timedelta(hours=1))
        for h in (((a.observed-timedelta(seconds=1), a),),
                  ((a.observed, a), (CUT, replace(a, identity="duplicate")))):
            with self.assertRaisesRegex(ValueError, "CLOCK"):
                select_private_d1_research_vintage(h, cutoff=DECISION)

    def test_empty_and_malformed_history(self):
        self.assertIsNone(select_private_d1_research_vintage((), cutoff=CUT))
        for h in ([], ((CUT,),), ((CUT, object()),)):
            with self.assertRaises(ValueError):
                select_private_d1_research_vintage(h, cutoff=CUT)
