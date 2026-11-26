"""Synthetic P229 checks; no public directional or real source values."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from unittest import TestCase

from mfx_research.p227_pretrigger_h1 import calculate_pretrigger_h1
from mfx_research.p229_pretrigger_m15 import calculate_pretrigger_m15
from test_mfx_p227_pretrigger_h1 import fixture, START


OPEN = START+timedelta(hours=4, minutes=45)
DECISION = START+timedelta(hours=5, minutes=7)


def shaped():
    raw, clocks = fixture()
    # Last fully visible hour has a distinct confirmed high and low; two
    # trigger M15s have a crossing of the earlier high, not a new pivot.
    levels = ("1.10","1.10","1.10","1.10")*3 + (
        "1.10","1.15","1.05","1.10","1.10","1.10","1.14","1.17")
    raw = tuple(replace(b, open=levels[i//3], close=levels[i//3],
                        high=str(Decimal(levels[i//3])+Decimal("0.01")),
                        low=str(Decimal(levels[i//3])-Decimal("0.01")))
                for i,b in enumerate(raw))
    return raw, clocks


def run(raw, clocks):
    h1 = calculate_pretrigger_h1(raw, clocks, latest_m15_open=OPEN, decision_utc=DECISION)
    return calculate_pretrigger_m15(raw, clocks, h1, latest_m15_open=OPEN, decision=DECISION)


class P229PretriggerM15Tests(TestCase):
    def test_preknown_high_and_low_private(self):
        raw, clocks = shaped()
        r = run(raw, clocks)
        self.assertEqual(r.status, "PRIVATE_M15_DRAFT_GEOMETRY_COMPUTED")
        self.assertEqual(tuple(s.rule_id for s in r.sides), ("B2","S2"))
        self.assertEqual(r.sides[0].level, Decimal("1.16"))
        self.assertEqual(r.sides[1].level, Decimal("1.04"))
        self.assertTrue(r.sides[0].crossed)
        self.assertFalse(r.sides[1].crossed)
        self.assertFalse(r.history_to_setup_complete)
        self.assertEqual(r.action, "NO_SIGNAL")
        self.assertFalse(r.may_publish_buy_sell)

    def test_reflection_preserves_geometry(self):
        raw, clocks = shaped()
        def reflect(x):
            return str(Decimal("2.5")-Decimal(x))
        mirror = tuple(replace(b, open=reflect(b.open), high=reflect(b.low),
                               low=reflect(b.high), close=reflect(b.close)) for b in raw)
        a,b = run(raw,clocks).sides[0],run(mirror,clocks).sides[1]
        self.assertEqual(a.level, Decimal("2.5")-b.level)
        self.assertEqual((a.near,a.crossed,a.anti_chase),(b.near,b.crossed,b.anti_chase))

    def test_trigger_hour_cannot_confirm_level(self):
        raw, clocks = shaped()
        changed = raw[:48]+tuple(replace(b,high="1.95") for b in raw[48:])
        self.assertEqual(tuple(s.level for s in run(raw,clocks).sides),
                         tuple(s.level for s in run(changed,clocks).sides))

    def test_late_archive_excluded(self):
        raw, clocks = shaped()
        late = clocks[:3]+((START+timedelta(hours=4, minutes=31),clocks[3][1]),)+clocks[4:]
        self.assertEqual(run(raw,late).status,"NO_PRETRIGGER_M15_LEVEL")

    def test_forged_h1_rejected(self):
        raw, clocks = shaped()
        h1 = calculate_pretrigger_h1(raw,clocks,latest_m15_open=OPEN,decision_utc=DECISION)
        with self.assertRaisesRegex(ValueError,"H1_SOURCE_CONTEXT_DRIFT"):
            calculate_pretrigger_m15(raw,clocks,replace(h1,mean_tr=Decimal("1")),
                                     latest_m15_open=OPEN,decision=DECISION)

class P236EarlyObservationTests(TestCase):
    def test_exact_two_closed_bar_observations(self):
        raw,clocks=shaped()
        row=run(raw,clocks)
        self.assertEqual(tuple(s.rule_id for s in row.early_sides),("B2","S2"))
        self.assertTrue(row.early_sides[0].strict_relative_extremum)
        self.assertFalse(row.early_sides[1].strict_relative_extremum)
        self.assertEqual(tuple(s.first_zone_contact for s in row.early_sides),
                         tuple(s.near for s in row.sides))
        self.assertFalse(row.early_event_approved)

    def test_reflected_early_observations(self):
        raw,clocks=shaped()
        def reflect(x):
            return str(Decimal("2.5")-Decimal(x))
        mirror=tuple(replace(b,open=reflect(b.open),high=reflect(b.low),
                             low=reflect(b.high),close=reflect(b.close)) for b in raw)
        a,b=run(raw,clocks).early_sides[0],run(mirror,clocks).early_sides[1]
        self.assertEqual((a.first_zone_contact,a.strict_relative_extremum,a.strict_zone_edge_reclaim),
                         (b.first_zone_contact,b.strict_relative_extremum,b.strict_zone_edge_reclaim))

    def test_no_confirmed_level_does_not_erase_early_observations(self):
        raw,clocks=shaped()
        flat=tuple(replace(b,open="1.10",close="1.10",high="1.11",low="1.09")
                   for b in raw[:48])+raw[48:]
        row=run(flat,clocks)
        self.assertEqual(row.status,"NO_PRETRIGGER_M15_LEVEL")
        self.assertEqual(row.sides,())
        self.assertEqual(len(row.early_sides),2)

    def test_equal_extrema_are_not_strict(self):
        raw,clocks=shaped()
        changed=raw[:-3]+tuple(replace(b,open="1.14",close="1.14",high="1.15",low="1.13")
                               for b in raw[-3:])
        row=run(changed,clocks)
        self.assertFalse(any(s.strict_relative_extremum for s in row.early_sides))
        self.assertFalse(any(s.strict_zone_edge_reclaim for s in row.early_sides))

    def test_missing_pretrigger_history_has_no_early_observations(self):
        raw,clocks=shaped()
        late=clocks[:3]+((START+timedelta(hours=4,minutes=31),clocks[3][1]),)+clocks[4:]
        self.assertEqual(run(raw,late).early_sides,())
