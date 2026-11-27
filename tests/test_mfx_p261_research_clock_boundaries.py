"""P261: fixed synthetic grids and active session rollover."""
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from forex_trading.market_data import Timeframe
from mfx_research.p256_ema_watch import ema_watch, validate_series
from mfx_research.p260_adr_session_gate import adr_session_gate
from test_mfx_p256_ema_watch import fixture
from test_mfx_p257_previous_session_watch import shift
from test_mfx_p260_adr_session_gate import adr_fixture
from tools.run_a04_p19_causal_context_demo import _make_series


class P261Tests(TestCase):
    def test_misaligned_m15_rejected(self):
        h, p = fixture()
        q = shift(p, timedelta(minutes=1))
        with self.assertRaisesRegex(ValueError, "P261_OFF_GRID"):
            ema_watch("B2", h, q, q.first_known_utc, near_atr=D("0.5"))

    def test_misaligned_hour_rejected(self):
        h, p = fixture()
        rows = tuple(shift(x, -timedelta(minutes=1)) for x in h)
        with self.assertRaisesRegex(ValueError, "P261_OFF_GRID"):
            ema_watch("B2", rows, p, p.first_known_utc, near_atr=D("0.5"))

    def test_misaligned_daily_rejected(self):
        d, _ = adr_fixture()
        rows = tuple(shift(x, -timedelta(hours=1)) for x in d)
        with self.assertRaisesRegex(ValueError, "P261_OFF_GRID"):
            validate_series(rows, Timeframe.D1, d[-1].first_known_utc)

    def test_finished_session_not_current(self):
        d, c = adr_fixture()
        all_day = _make_series(Timeframe.M15, (
            ("1.1", "1.105", "1.095", "1.1"),) * 96)
        midnight = c[0].key.bar_start_utc
        rows = tuple(shift(x, midnight - all_day[0].key.bar_start_utc)
                     for x in all_day)
        def run(now):
            return adr_session_gate(d, rows, now, lookback=3,
                                    max_adr=D("1"), allowed_utc_hours=(0, 24))
        for delay in (0, 1, 899):
            with self.assertRaisesRegex(ValueError, "P260_INCOMPLETE_OR_STALE"):
                run(rows[-1].first_known_utc + timedelta(seconds=delay))

    def test_normal_current_session_still_valid(self):
        d, c = adr_fixture()
        r = adr_session_gate(d, c, c[-1].first_known_utc, lookback=3,
                             max_adr=D("1"), allowed_utc_hours=(0, 24))
        self.assertTrue(r.adr_pass and r.session_pass)
        self.assertEqual(r.public_summary()["action"], "NO_SIGNAL")
