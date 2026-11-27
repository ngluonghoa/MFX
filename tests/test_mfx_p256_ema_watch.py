"""P256 causal WATCH and exact mirrored synthetic regression."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from forex_trading.market_data import Timeframe
from mfx_research.p189_b2s2_executable_ohlc_mirror import reflect_sim_closed_ohlc
from mfx_research.p256_ema_watch import ema_watch
from tools.run_a04_p19_causal_context_demo import _make_series


def fixture():
    h1 = _make_series(Timeframe.H1, (("1.1", "1.101", "1.099", "1.1"),) * 60)
    probe = _make_series(Timeframe.M15, (("1.1", "1.101", "1.099", "1.1"),))[0]
    dt = timedelta(minutes=15)
    probe = replace(probe, key=replace(probe.key,
                    bar_start_utc=probe.key.bar_start_utc + dt,
                    bar_end_utc=probe.key.bar_end_utc + dt),
                    first_known_utc=probe.first_known_utc + dt,
                    observation=replace(probe.observation,
                        first_known_utc=probe.observation.first_known_utc + dt,
                        retrieved_at_utc=probe.observation.retrieved_at_utc + dt))
    return h1, probe


class P256Tests(TestCase):
    def test_touch_mirror_and_no_authority(self):
        h, p = fixture()
        a = ema_watch("B2", h, p, p.first_known_utc, near_atr=D("0"))
        mirror = lambda b: reflect_sim_closed_ohlc(b, anchor=D("1.2"))
        q = mirror(p)
        b = ema_watch("S2", tuple(map(mirror, h)), q, q.first_known_utc, near_atr=D("0"))
        self.assertEqual((a.near20, a.near50), (True, True))
        self.assertEqual(a, b)
        self.assertEqual(a.public_summary()["action"], "NO_SIGNAL")

    def test_distant_and_wrong_side(self):
        h, p = fixture()
        q = replace(p, open=D("1.11"), high=D("1.111"), low=D("1.109"), close=D("1.11"))
        self.assertFalse(ema_watch("B2", h, q, q.first_known_utc, near_atr=D("0.5")).near20)
        q = replace(p, close=D("1.099"))
        self.assertFalse(ema_watch("B2", h, q, q.first_known_utc, near_atr=D("0")).near50)

    def test_future_h1_and_stale_h1_rejected(self):
        h, p = fixture()
        for rows in (h[:-1], h[:-1] + (replace(h[-1],
                    first_known_utc=p.first_known_utc),)):
            with self.assertRaises(ValueError):
                ema_watch("B2", rows, p, p.first_known_utc, near_atr=D("0"))

    def test_short_history_and_invalid_tolerance(self):
        h, p = fixture()
        for rows, tol in ((h[-49:], D("0")), (h, D("NaN")), (h, D("-1"))):
            with self.assertRaises(ValueError):
                ema_watch("B2", rows, p, p.first_known_utc, near_atr=tol)
