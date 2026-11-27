"""P262: one joined snapshot, independent branches, reflection and tamper."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from forex_trading.market_data import Timeframe
from mfx_research.p189_b2s2_executable_ohlc_mirror import reflect_sim_closed_ohlc
from mfx_research.p262_shared_research_observations import (
    ObservationPolicy, ObservationSnapshot, observe_shared_snapshot,
    verify_shared_observations,
)
from test_mfx_p256_ema_watch import fixture
from test_mfx_p257_previous_session_watch import shift
from test_mfx_p260_adr_session_gate import adr_fixture
from tools.run_a04_p19_causal_context_demo import _make_series


def shared_fixture():
    daily, current = adr_fixture()
    h1, _ = fixture()
    rows = _make_series(Timeframe.M15, (
        ("1.1", "1.101", "1.099", "1.1"),
        ("1.1", "1.103", "1.1", "1.102"),
        ("1.102", "1.102", "1.099", "1.1"),
        ("1.1", "1.102", "1.098", "1.1"),
        ("1.1", "1.101", "1.089", "1.089"),
        ("1.089", "1.105", "1.088", "1.104"),
    ))
    midnight = current[0].key.bar_start_utc
    rows = tuple(shift(x, midnight - rows[0].key.bar_start_utc) for x in rows)
    cutoff = rows[-2].key.bar_start_utc
    hour = cutoff.replace(minute=0, second=0, microsecond=0)
    h1 = tuple(shift(x, hour - h1[-1].key.bar_end_utc) for x in h1)
    return ObservationSnapshot(daily, h1, rows, rows[-1].first_known_utc), ObservationPolicy(
        D("0.5"), 1, 1, 3, D("1"), (0, 24))


class P262Tests(TestCase):
    def test_independent_branches_and_no_promotion(self):
        snap, policy = shared_fixture()
        value = observe_shared_snapshot(snap, policy)
        a, b = value.sides
        self.assertEqual((a.rule, b.rule), ("B2", "S2"))
        self.assertTrue(a.reclaim_reject and a.bos and a.bos_available)
        self.assertFalse(a.previous_session)
        self.assertTrue(value.adr_pass and value.session_pass)
        self.assertTrue(verify_shared_observations(value))
        public = value.public_summary()
        self.assertEqual(public["action"], "NO_SIGNAL")
        self.assertNotIn("reclaim_reject", str(public))
        self.assertNotIn("1.104", repr(value))

    def test_exact_reflection(self):
        snap, policy = shared_fixture()
        def mirror(x):
            return reflect_sim_closed_ohlc(x, anchor=D("1.2"))
        other = replace(snap, daily=tuple(map(mirror, snap.daily)),
                        h1=tuple(map(mirror, snap.h1)), current=tuple(map(mirror, snap.current)))
        a = observe_shared_snapshot(snap, policy)
        b = observe_shared_snapshot(other, policy)
        self.assertEqual(replace(a.sides[0], rule="S2"), b.sides[1])
        self.assertEqual(replace(a.sides[1], rule="B2"), b.sides[0])
        self.assertEqual((a.adr_pass, a.session_pass), (b.adr_pass, b.session_pass))

    def test_tamper_or_future_fails(self):
        snap, policy = shared_fixture()
        value = observe_shared_snapshot(snap, policy)
        with self.assertRaisesRegex(ValueError, "P262_RECEIPT"):
            verify_shared_observations(replace(value, adr_pass=not value.adr_pass))
        with self.assertRaises(ValueError):
            observe_shared_snapshot(replace(snap, decision_utc=snap.decision_utc-timedelta(seconds=1)),
                                    policy)

    def test_no_bos_history_is_unavailable_not_negative_proof(self):
        snap, policy = shared_fixture()
        rows = snap.current[:2]
        value = observe_shared_snapshot(replace(snap, current=rows,
                                               h1=snap.h1[:-1], decision_utc=rows[-1].first_known_utc),
                                         policy)
        self.assertTrue(all(not x.bos_available and not x.bos for x in value.sides))

    def test_no_mixed_source_or_gap(self):
        snap, policy = shared_fixture()
        for rows in (snap.current[:1]+snap.current[2:],
                     (replace(snap.current[0], observation=replace(snap.current[0].observation,
                              stream_id="SIM:OTHER")),)+snap.current[1:]):
            with self.assertRaises(ValueError):
                observe_shared_snapshot(replace(snap, current=rows), policy)
