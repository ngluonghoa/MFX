"""P230 source-boundary distance is not an approved invalidation rule."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest import TestCase

from mfx_research.p230_private_boundary_path import inspect_boundary_path, inspect_private_setup_boundaries
from mfx_research.p227_pretrigger_h1 import calculate_pretrigger_h1
from mfx_research.p228_pretrigger_native import calculate_pretrigger_native
from test_mfx_p227_pretrigger_h1 import fixture, START
from test_mfx_p228_pretrigger_native import h4_fixture, CUT, DECISION

T = datetime(2026, 11, 26, 8, tzinfo=timezone.utc)
H = timedelta(hours=1)


def inspect(path, rule="B2", decision=T+2*H+timedelta(minutes=1), anchor="1.2"):
    return inspect_boundary_path(rule=rule, anchor=Decimal(anchor), prior_end=T,
                                 decision=decision, minutes=60, path=path)


class P230PrivateBoundaryTests(TestCase):
    def test_strict_raw_breach_and_complete_path(self):
        r = inspect(((T,T+H,Decimal("1.2")),(T+H,T+2*H,Decimal("1.1"))))
        self.assertEqual(r.minimum_signed_distance, Decimal("-0.1"))
        self.assertTrue(r.unbuffered_boundary_breach)
        self.assertTrue(r.closed_grid_complete)

    def test_mirror_and_equality(self):
        a = inspect(((T,T+H,Decimal("1.2")),(T+H,T+2*H,Decimal("1.1"))))
        b = inspect(((T,T+H,Decimal("1.3")),(T+H,T+2*H,Decimal("1.4"))), "S2", anchor="1.3")
        self.assertEqual(a,b)
        eq = inspect(((T,T+H,Decimal("1.2")),),decision=T+H+timedelta(minutes=1))
        self.assertFalse(eq.unbuffered_boundary_breach)

    def test_gap_not_an_intact_path(self):
        r = inspect(((T+H,T+2*H,Decimal("1.1")),))
        self.assertFalse(r.closed_grid_complete)
        self.assertTrue(r.unbuffered_boundary_breach)

    def test_empty_distinguishes_no_new_slot_and_missing_slot(self):
        self.assertTrue(inspect((), decision=T+timedelta(minutes=1)).closed_grid_complete)
        r = inspect(())
        self.assertFalse(r.closed_grid_complete)
        self.assertIsNone(r.minimum_signed_distance)

    def test_future_and_reordered_path_rejected(self):
        with self.assertRaises(ValueError):
            inspect(((T+2*H,T+3*H,Decimal("1.1")),))
        with self.assertRaises(ValueError):
            inspect(((T+H,T+2*H,Decimal("1.1")),(T,T+H,Decimal("1.1"))))

    def test_integrated_pretrigger_receipt_is_private(self):
        raw, commits = fixture()
        latest = START+timedelta(hours=4,minutes=45)
        decision = START+timedelta(hours=5,minutes=7)
        h1 = calculate_pretrigger_h1(raw,commits,latest_m15_open=latest,decision_utc=decision)
        native = calculate_pretrigger_native((),(),cutoff=h1.cutoff_utc,decision=decision)
        r = inspect_private_setup_boundaries(raw,(),h1,native,decision=decision)
        self.assertEqual(r.action,"NO_SIGNAL")
        self.assertFalse(r.buffer_selected)
        self.assertFalse(r.invalidation_rule_approved)
        self.assertEqual(r.sides[0].h1.observed_closed_bars,1)
        self.assertTrue(r.sides[0].h1.closed_grid_complete)
        self.assertIsNone(r.sides[0].h4)

    def test_h4_frozen_anchors_from_prior_pivots(self):
        native = calculate_pretrigger_native(h4_fixture(),(),cutoff=CUT,decision=DECISION)
        self.assertEqual(native.h4_low_anchor, Decimal("1.09"))
        self.assertEqual(native.h4_high_anchor, Decimal("1.51"))
