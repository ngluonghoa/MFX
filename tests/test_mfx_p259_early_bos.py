"""P259 causal, strict, mirrored BOS witness."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from forex_trading.market_data import Timeframe
from mfx_research.p189_b2s2_executable_ohlc_mirror import reflect_sim_closed_ohlc
from mfx_research.p259_early_bos import early_bos
from test_mfx_p257_previous_session_watch import shift
from tools.run_a04_p19_causal_context_demo import _make_series


def bos_fixture():
    h = _make_series(Timeframe.M15, (("1.1", "1.101", "1.099", "1.1"),
                     ("1.1", "1.103", "1.1", "1.102"),
                     ("1.102", "1.102", "1.099", "1.1")))
    a, b = _make_series(Timeframe.M15, (("1.1", "1.103", "1.099", "1.103"),
                        ("1.103", "1.105", "1.102", "1.104")))
    dt = h[-1].key.bar_end_utc - a.key.bar_start_utc
    return h, shift(a, dt), shift(b, dt)


class P259Tests(TestCase):
    def test_bos_mirror(self):
        h, a, b = bos_fixture()
        def mirror(x):
            return reflect_sim_closed_ohlc(x, anchor=D("1.2"))
        r = early_bos("B2", h, (a, b), b.first_known_utc, left=1, right=1)
        s = early_bos("S2", tuple(map(mirror, h)), (mirror(a), mirror(b)),
                      b.first_known_utc, left=1, right=1)
        self.assertTrue(r.observed)
        self.assertEqual(r, s)
        self.assertEqual(r.public_summary()["action"], "NO_SIGNAL")

    def test_equality_and_already_broken(self):
        h, a, b = bos_fixture()
        self.assertFalse(early_bos("B2", h, (a, replace(b, close=D("1.103"))),
                                  b.first_known_utc, left=1, right=1).observed)
        a = replace(a, high=D("1.104"), close=D("1.104"))
        self.assertFalse(early_bos("B2", h, (a, b), b.first_known_utc,
                                  left=1, right=1).observed)

    def test_history_future_and_missing_pivot(self):
        h, a, b = bos_fixture()
        with self.assertRaises(ValueError):
            early_bos("B2", h + (a,), (a, b), b.first_known_utc, left=1, right=1)
        flat = tuple(replace(x, open=D("1.1"), high=D("1.101"),
                             low=D("1.099"), close=D("1.1")) for x in h)
        self.assertFalse(early_bos("B2", flat, (a, b), b.first_known_utc,
                                  left=1, right=1).available)
