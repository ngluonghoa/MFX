"""P258 mirrored strict closed reclaim/reject."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from mfx_research.p189_b2s2_executable_ohlc_mirror import reflect_sim_closed_ohlc
from mfx_research.p258_session_reclaim_reject import session_reclaim_reject
from test_mfx_p257_previous_session_watch import session_fixture, shift


def reclaim_fixture():
    d, _, p = session_fixture()
    a = replace(p, close=D("1.099"))
    b = replace(shift(p, timedelta(minutes=15)), close=D("1.101"))
    return d, a, b


class P258Tests(TestCase):
    def test_mirror_and_no_signal(self):
        d, a, b = reclaim_fixture()
        def mirror(x):
            return reflect_sim_closed_ohlc(x, anchor=D("1.2"))
        r = session_reclaim_reject("B2", d, (a, b), b.first_known_utc)
        s = session_reclaim_reject("S2", mirror(d), (mirror(a), mirror(b)), b.first_known_utc)
        self.assertTrue(r.observed)
        self.assertEqual(r, s)
        self.assertEqual(r.public_summary()["action"], "NO_SIGNAL")

    def test_equality_wick_and_already_crossed_do_not_trigger(self):
        d, a, b = reclaim_fixture()
        for x, y in ((a, replace(b, close=D("1.1"))),
                     (a, replace(b, close=D("1.099"))),
                     (replace(a, close=D("1.1")), b)):
            self.assertFalse(session_reclaim_reject("B2", d, (x, y), y.first_known_utc).observed)

    def test_late_prior_and_gap_rejected(self):
        d, a, b = reclaim_fixture()
        late = replace(a, first_known_utc=b.first_known_utc)
        for x, y in ((late, b), (a, shift(b, timedelta(minutes=15)))):
            with self.assertRaises(ValueError):
                session_reclaim_reject("B2", d, (x, y), y.first_known_utc)
