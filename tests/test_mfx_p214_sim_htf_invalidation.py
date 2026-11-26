"""P214 setup-linked structural invalidation, synthetic fixtures only."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from forex_trading.market_data import Timeframe
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    compute_mfx_b2s2_v2_closed_candidate, read_mfx_confirmed_b2s2_v2,
)
from mfx_research.p214_sim_htf_invalidation import (
    SimInvalidationPolicy, check_sim_setup_invalidation,
)
from mfx_research.confirmed_swings import PivotKind
from test_mfx_p165_option_b_v2_chronological_replay import snapshot


def levels(s):
    r = compute_mfx_b2s2_v2_closed_candidate(
        s.rule_id, s.bars, s.confirmed_m15_history,
        read_mfx_confirmed_b2s2_v2(), s.decision_utc,
    )
    c = r.source.derived_context
    long = s.rule_id == "B2"
    p = [p for p in r.source.four_hour.pivots
         if p.kind is (PivotKind.LOW if long else PivotKind.HIGH)]
    return c.h1_zone_low if long else c.h1_zone_high, p[-1].price


def later(s, tf, close, *, wick=None):
    old = s.bars.hourly[-1] if tf is Timeframe.H1 else s.bars.four_hour[-1]
    start = old.key.bar_end_utc
    end = start + (timedelta(hours=1) if tf is Timeframe.H1 else timedelta(hours=4))
    known = end + timedelta(seconds=1)
    values = (close,) if wick is None else (close, wick)
    return replace(old, key=replace(old.key, bar_start_utc=start, bar_end_utc=end),
                   observation=replace(old.observation, first_known_utc=known,
                                       retrieved_at_utc=known),
                   first_known_utc=known, open=close, close=close,
                   high=max(values), low=min(values))


class P214Tests(TestCase):
    def check(self, s, tf, path, now=None, buffer=D("0")):
        return check_sim_setup_invalidation(
            s, SimInvalidationPolicy((tf,), buffer),
            h1_path=path if tf is Timeframe.H1 else (),
            h4_path=path if tf is Timeframe.H4 else (),
            evaluation_utc=now or (path[-1].first_known_utc if path else
                                   s.decision_utc + timedelta(minutes=1)),
        )

    def test_both_sides_both_frames_close_breach(self):
        for rule in ("B2", "S2"):
            s = snapshot(rule)
            sign = -1 if rule == "B2" else 1
            for tf, anchor in zip((Timeframe.H1, Timeframe.H4), levels(s)):
                with self.subTest(rule=rule, tf=tf):
                    b = later(s, tf, anchor + sign * D("0.0001"))
                    r = self.check(s, tf, (b,))
                    self.assertEqual(r.status, "INVALIDATED")
                    self.assertEqual(r.frames[0].first_breach_known_utc, b.first_known_utc)
                    self.assertEqual(r.public_summary()["action"], "NO_SIGNAL")

    def test_wick_and_equality_not_closed_breach(self):
        for rule in ("B2", "S2"):
            s = snapshot(rule)
            anchor = levels(s)[0]
            sign = -1 if rule == "B2" else 1
            b = later(s, Timeframe.H1, anchor, wick=anchor + sign * D("0.001"))
            self.assertEqual(self.check(s, Timeframe.H1, (b,)).status,
                             "INTACT_THROUGH_CLOSED_GRID")

    def test_buffer_shared_across_sides(self):
        for rule in ("B2", "S2"):
            s = snapshot(rule)
            anchor = levels(s)[0]
            sign = -1 if rule == "B2" else 1
            b = later(s, Timeframe.H1, anchor + sign * D("0.0001"))
            self.assertEqual(self.check(s, Timeframe.H1, (b,), buffer=D("0.0002")).status,
                             "INTACT_THROUGH_CLOSED_GRID")

    def test_missing_path_is_unknown(self):
        s = snapshot()
        self.assertEqual(self.check(s, Timeframe.H1, ()).status, "UNKNOWN_INCOMPLETE")

    def test_later_missing_slot_is_unknown(self):
        s = snapshot()
        b = later(s, Timeframe.H1, levels(s)[0])
        r = self.check(s, Timeframe.H1, (b,), now=b.first_known_utc+timedelta(hours=2))
        self.assertEqual(r.status, "UNKNOWN_INCOMPLETE")

    def test_future_known_rejected(self):
        s = snapshot()
        b = later(s, Timeframe.H1, levels(s)[0])
        with self.assertRaises(ValueError):
            self.check(s, Timeframe.H1, (b,), now=b.first_known_utc-timedelta(seconds=1))

    def test_cross_source_rejected(self):
        s = snapshot()
        b = later(s, Timeframe.H1, levels(s)[0])
        b = replace(b, observation=replace(b.observation, stream_id="SIM:OTHER"))
        with self.assertRaisesRegex(ValueError, "SOURCE_DRIFT"):
            self.check(s, Timeframe.H1, (b,))

    def test_invalid_policy_rejected(self):
        for frames, buffer in (((), D("0")), ((Timeframe.M15,), D("0")),
                               ((Timeframe.H1,), D("-1"))):
            with self.assertRaises(ValueError):
                SimInvalidationPolicy(frames, buffer)
