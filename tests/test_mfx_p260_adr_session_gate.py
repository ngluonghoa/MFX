"""P260 exhaustion, session boundary, mirror and no lookahead."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from forex_trading.market_data import Timeframe
from mfx_research.p189_b2s2_executable_ohlc_mirror import reflect_sim_closed_ohlc
from mfx_research.p260_adr_session_gate import adr_session_gate
from test_mfx_p257_previous_session_watch import shift
from tools.run_a04_p19_causal_context_demo import _make_series


def adr_fixture():
    d = _make_series(Timeframe.D1, (("1.1", "1.11", "1.09", "1.1"),) * 3)
    c = _make_series(Timeframe.M15, (("1.1", "1.105", "1.095", "1.1"),) * 4)
    midnight = d[-1].key.bar_end_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    d = tuple(shift(x, midnight - d[-1].key.bar_end_utc) for x in d)
    c = tuple(shift(x, midnight - c[0].key.bar_start_utc) for x in c)
    return d, c


class P260Tests(TestCase):
    def test_mirror_and_exact_adr_boundary(self):
        d, c = adr_fixture()
        def mirror(x):
            return reflect_sim_closed_ohlc(x, anchor=D("1.2"))
        def run(days, rows, limit):
            return adr_session_gate(days, rows, rows[-1].first_known_utc,
                                    lookback=3, max_adr=limit, allowed_utc_hours=(1, 2))
        a = run(d, c, D("0.6"))
        self.assertTrue(a.adr_pass)
        self.assertTrue(a.session_pass)
        self.assertEqual(a, run(tuple(map(mirror, d)), tuple(map(mirror, c)), D("0.6")))
        self.assertFalse(run(d, c, D("0.5")).adr_pass)
        self.assertEqual(a.public_summary()["action"], "NO_SIGNAL")

    def test_half_open_session(self):
        d, c = adr_fixture()
        r = adr_session_gate(d, c, c[-1].first_known_utc, lookback=3,
                             max_adr=D("1"), allowed_utc_hours=(0, 1))
        self.assertFalse(r.session_pass)

    def test_missing_open_and_future_daily(self):
        d, c = adr_fixture()
        for days, rows in ((d, c[1:]), (d[1:] + (shift(d[-1], timedelta(days=1)),), c)):
            with self.assertRaises(ValueError):
                adr_session_gate(days, rows, rows[-1].first_known_utc,
                                 lookback=3, max_adr=D("1"), allowed_utc_hours=(0, 2))
