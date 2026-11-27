"""P257 previous session extreme symmetry and causal rejection."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from forex_trading.market_data import Timeframe
from mfx_research.p189_b2s2_executable_ohlc_mirror import reflect_sim_closed_ohlc
from mfx_research.p257_previous_session_watch import previous_session_watch
from test_mfx_p256_ema_watch import fixture
from tools.run_a04_p19_causal_context_demo import _make_series


def shift(bar, delta):
    return replace(bar, key=replace(bar.key,
                   bar_start_utc=bar.key.bar_start_utc + delta,
                   bar_end_utc=bar.key.bar_end_utc + delta),
                   first_known_utc=bar.first_known_utc + delta,
                   observation=replace(bar.observation,
                       first_known_utc=bar.observation.first_known_utc + delta,
                       retrieved_at_utc=bar.observation.retrieved_at_utc + delta))


def session_fixture():
    h, p = fixture()
    cutoff = p.key.bar_start_utc
    midnight = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
    old = _make_series(Timeframe.D1, (("1.1", "1.12", "1.1", "1.11"),))[0]
    old = shift(old, midnight - old.key.bar_end_utc)
    return old, h, p


class P257Tests(TestCase):
    def test_low_high_mirror(self):
        d, h, p = session_fixture()
        def mirror(b):
            return reflect_sim_closed_ohlc(b, anchor=D("1.2"))
        a = previous_session_watch("B2", d, h, p, p.first_known_utc, near_atr=D("0"))
        b = previous_session_watch("S2", mirror(d), tuple(map(mirror, h)), mirror(p),
                                   p.first_known_utc, near_atr=D("0"))
        self.assertTrue(a.near)
        self.assertTrue(b.near)
        self.assertEqual(a.level + b.level, D("2.4"))
        self.assertEqual(a.public_summary()["action"], "NO_SIGNAL")

    def test_old_future_or_nonmidnight_session_denied(self):
        d, h, p = session_fixture()
        for x in (shift(d, -timedelta(days=1)), shift(d, timedelta(days=1)),
                  shift(d, -timedelta(minutes=1))):
            with self.assertRaises(ValueError):
                previous_session_watch("B2", x, h, p, p.first_known_utc, near_atr=D("0"))

    def test_wrong_side_and_far_level(self):
        d, h, p = session_fixture()
        for x in (replace(p, close=D("1.099")),
                  replace(p, open=D("1.11"), high=D("1.112"), low=D("1.109"), close=D("1.11"))):
            self.assertFalse(previous_session_watch("B2", d, h, x, x.first_known_utc,
                                                    near_atr=D("0")).near)
