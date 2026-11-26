"""P228: no later native archive or D1 vintage may enter earlier setup."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from mfx_cache.native_fx_htf import NativeFXBar
from mfx_research.p228_pretrigger_native import calculate_pretrigger_native
from tools.audit_mfx_p209_d1_private_cache import PrivateSnapshot

CUT = datetime(2026, 11, 26, 12, 30, tzinfo=timezone.utc)
DECISION = CUT + timedelta(minutes=37)
START = datetime(2026, 11, 25, 8, tzinfo=timezone.utc)


def h4_fixture():
    # Seven alternating strict swings, ascending highs and lows.
    levels = ("1.1", "1.3", "1.0", "1.4", "1.1", "1.5", "1.2")
    bars = []
    from decimal import Decimal
    for i, level in enumerate(levels):
        mid = Decimal(level)
        begin = START + i*timedelta(hours=4)
        bar = NativeFXBar("EUR/USD", "4h", begin.strftime("%Y-%m-%d %H:%M:%S"),
                          "UTC_INTRADAY_OPEN", "Australia/Sydney",
                          level, str(mid+Decimal("0.01")), str(mid-Decimal("0.01")), level)
        bars.append((begin+timedelta(hours=4, minutes=1), (bar,)))
    return tuple(bars)


def vintage(observed, last_day=25):
    rows = tuple(NativeFXBar("EUR/USD", "1day", f"2026-11-{day:02}",
                 "EXCHANGE_LOCAL_SESSION_DATE", "Australia/Sydney",
                 "1.1", "1.2", "1.0", "1.1") for day in range(18,last_day+1))
    return PrivateSnapshot(observed, rows, "fixture")


def run(h4=(), d1=()):
    return calculate_pretrigger_native(h4, d1, cutoff=CUT, decision=DECISION)


class P228PretriggerNativeTests(TestCase):
    def test_prior_h4_trend_and_d1_vintage(self):
        v = vintage(CUT-timedelta(hours=1))
        r = run(h4_fixture(), ((v.observed, v),))
        self.assertEqual(r.h4_status, "PRETRIGGER_H4_DRAFT_STRUCTURE_COMPUTED")
        self.assertEqual(r.h4_trend, "UP")
        self.assertEqual(r.d1_status, "PRETRIGGER_D1_VINTAGE_PRESENT_CALENDAR_UNQUALIFIED")
        self.assertFalse(r.d1_calendar_qualified)
        self.assertFalse(r.publisher_first_known_verified)
        self.assertEqual(r.action, "NO_SIGNAL")

    def test_late_confirmation_excluded(self):
        h = h4_fixture()
        late = h[:-1] + ((CUT+timedelta(minutes=1), h[-1][1]),)
        self.assertEqual(run(late).h4_status, "PRETRIGGER_H4_DRAFT_STRUCTURE_COMPUTED")
        # With only two highs and one low before the late pair no structure.
        h = h[:5]
        late = h[:4] + ((CUT+timedelta(minutes=1), h[-1][1]),)
        self.assertEqual(run(late).h4_trend, "UNKNOWN")

    def test_later_d1_revision_not_used(self):
        old = vintage(CUT-timedelta(hours=1))
        new = replace(vintage(CUT+timedelta(minutes=1)), identity="later",
                      rows=old.rows[:-1]+(replace(old.rows[-1], close="1.15"),))
        r = run(d1=((old.observed, old), (new.observed, new)))
        self.assertEqual(r.d1_rows, old.rows)
        self.assertEqual(run(d1=((new.observed,new),)).d1_status, "NO_PRETRIGGER_D1_VINTAGE")

    def test_observed_before_cutoff_but_archived_after_excluded(self):
        old = vintage(CUT-timedelta(hours=1))
        self.assertEqual(run(d1=((CUT+timedelta(minutes=1),old),)).d1_status,
                         "NO_PRETRIGGER_D1_VINTAGE")

    def test_h4_gap_not_bridged(self):
        h = h4_fixture()
        self.assertEqual(run(h[:3]+h[4:]).h4_status, "PRETRIGGER_H4_PIVOTS_INSUFFICIENT")

    def test_invalid_clocks_rejected(self):
        old = vintage(CUT-timedelta(hours=1))
        with self.assertRaises(ValueError):
            run(d1=((old.observed-timedelta(seconds=1),old),))
        with self.assertRaises(ValueError):
            run(d1=((DECISION+timedelta(seconds=1),old),))
        with self.assertRaises(ValueError):
            run(h4_fixture()[::-1])
