"""P232 actual archive clocks, no artificial decision time or future leakage."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from unittest import TestCase

from mfx_research.p227_pretrigger_h1 import calculate_pretrigger_h1
from mfx_research.p232_delayed_middle_pairs import replay_delayed_middle_pairs
from test_mfx_p227_pretrigger_h1 import fixture, START


def shaped():
    raw, clocks = fixture()
    levels = ("1.10",)*12+("1.10","1.15","1.05","1.10","1.10","1.14","1.17","1.10")
    raw = tuple(replace(b,open=levels[i//3],close=levels[i//3],
                        high=str(Decimal(levels[i//3])+Decimal("0.01")),
                        low=str(Decimal(levels[i//3])-Decimal("0.01"))) for i,b in enumerate(raw))
    return raw, clocks


def run(raw, clocks):
    return replay_delayed_middle_pairs(raw, clocks, (), ())


class P232DelayedMiddlePairTests(TestCase):
    def test_middle_pair_has_settled_pretrigger_and_delayed_decision(self):
        raw,clocks = shaped()
        r = run(raw,clocks)
        last = r.samples[-1]
        self.assertEqual(last.archive_decision_utc,clocks[-1][0])
        self.assertEqual(last.trigger_end_utc,START+timedelta(hours=4,minutes=45))
        self.assertEqual(last.archive_decision_utc-last.trigger_end_utc,timedelta(minutes=22))
        self.assertTrue(last.m15.history_to_setup_complete)
        self.assertEqual(last.m15.status,"PRIVATE_M15_DRAFT_GEOMETRY_COMPUTED")
        self.assertTrue(last.m15.sides[0].crossed)
        self.assertEqual(r.public_summary()["action"],"NO_SIGNAL")
        self.assertFalse(r.public_summary()["may_publish_buy_sell"])

    def test_last_quarter_cannot_change_middle_pair(self):
        raw,clocks = shaped()
        changed = raw[:-3]+tuple(replace(b,high="1.95") for b in raw[-3:])
        self.assertEqual(run(raw,clocks).samples[-1],run(changed,clocks).samples[-1])

    def test_late_previous_archive_cannot_fill_pretrigger_history(self):
        raw,clocks = shaped()
        late = clocks[:3]+((START+timedelta(hours=4,minutes=16),clocks[3][1]),)+clocks[4:]
        last = run(raw,late).samples[-1]
        self.assertFalse(last.m15.history_to_setup_complete)
        self.assertEqual(last.h1.status,"PRETRIGGER_H1_STALE")

    def test_existing_latest_only_entrypoint_still_rejects_delayed_pair(self):
        raw,clocks = shaped()
        with self.assertRaisesRegex(ValueError,"LATEST_CLOSED_TRIGGER_GRID"):
            calculate_pretrigger_h1(raw,clocks,
                latest_m15_open=START+timedelta(hours=4,minutes=30),decision_utc=clocks[-1][0])

    def test_archive_before_hour_grace_rejected(self):
        raw,clocks = shaped()
        invalid = clocks[:-1]+((clocks[-1][1],clocks[-1][1]),)
        with self.assertRaisesRegex(ValueError,"BEFORE_SETTLED_HOUR"):
            run(raw,invalid)

    def test_empty_prefix_and_no_price_or_direction_leak(self):
        import json
        self.assertEqual(run((),()).public_summary()["middle_pairs_replayed"],0)
        raw,clocks = shaped()
        summary = json.dumps(run(raw,clocks).public_summary())
        self.assertNotIn("1.16",summary)
        self.assertNotIn("crossed",summary)
        self.assertNotIn("B2",summary)
