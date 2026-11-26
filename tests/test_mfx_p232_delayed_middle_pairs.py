"""P232 actual archive clocks, no artificial decision time or future leakage."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from unittest import TestCase

from mfx_research.p227_pretrigger_h1 import calculate_pretrigger_h1
from mfx_research.p231_private_trigger_identity import identify_private_trigger_pair
from mfx_research.p232_delayed_middle_pairs import (
    middle_pair_clock_census, replay_delayed_middle_pairs,
)
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
        with self.assertRaisesRegex(ValueError,"ARCHIVE_CLOCK_DRIFT"):
            run(raw,invalid)

    def test_empty_prefix_and_no_price_or_direction_leak(self):
        import json
        self.assertEqual(run((),()).public_summary()["middle_pairs_replayed"],0)
        raw,clocks = shaped()
        summary = json.dumps(run(raw,clocks).public_summary())
        self.assertNotIn("1.16",summary)
        self.assertNotIn("crossed",summary)
        self.assertNotIn("B2",summary)


class P233MiddleClockCensusTests(TestCase):
    def test_full_denominator_and_reused_selected_receipt(self):
        raw,clocks=shaped()
        r=run(raw,clocks)
        self.assertEqual(r.clock_census.private_eligible_indices,(4,))
        self.assertIs(r.clock_eligible_samples[0],r.samples[-1])
        summary=r.public_summary()
        self.assertEqual(summary["clock_census"]["prior_hour_missing_in_verified_tail"],1)
        self.assertEqual(summary["clock_census"]["earlier_required_history_gap_or_late"],3)
        self.assertEqual(summary["clock_census"]["four_contiguous_h1_hours_available_before_setup"],1)
        self.assertEqual(summary["clock_selected_replay"]["middle_pairs_replayed"],1)
        self.assertFalse(summary["clock_census"]["selection_uses_prices_or_outcomes"])

    def test_late_previous_hour_excluded(self):
        raw,clocks=shaped()
        late=clocks[:3]+((START+timedelta(hours=4,minutes=16),clocks[3][1]),)+clocks[4:]
        r=run(raw,late)
        self.assertEqual(r.clock_census.private_eligible_indices,())
        self.assertEqual(r.public_summary()["clock_census"]["prior_hour_archived_after_setup"],1)
        self.assertEqual(len(r.clock_eligible_samples),0)

    def test_gap_cannot_be_filled_by_older_history(self):
        _,clocks=fixture()
        r=middle_pair_clock_census(clocks[:1]+clocks[2:])
        self.assertEqual(r.private_eligible_indices,())
        self.assertEqual(r.prior_hour_missing,2)

    def test_selection_independent_of_prices_and_bounded(self):
        raw,clocks=shaped()
        changed=tuple(replace(b,high="1.95") for b in raw)
        a,b=run(raw,clocks),run(changed,clocks)
        self.assertEqual(a.clock_census,b.clock_census)
        times=tuple((START+timedelta(hours=i+1,minutes=7),
                     START+timedelta(hours=i+1)) for i in range(100))
        census=middle_pair_clock_census(times)
        self.assertEqual(len(census.private_eligible_indices),96)
        self.assertEqual(census.public_summary()["clock_eligible_not_replayed_due_to_limit"],64)

    def test_nonmonotone_commit_or_duplicate_hour_rejected(self):
        _,clocks=fixture()
        with self.assertRaisesRegex(ValueError,"ARCHIVE_CLOCK_DRIFT"):
            middle_pair_clock_census(clocks[:2]+clocks[1:])

    def test_no_private_indices_or_signal_in_public_summary(self):
        import json
        raw,clocks=shaped()
        s=json.dumps(run(raw,clocks).public_summary())
        self.assertNotIn("private_eligible_indices",s)
        self.assertNotIn("2026-11-26",s)
        self.assertIn("NO_SIGNAL",s)


class P234DelayedBoundaryIdentityTests(TestCase):
    def test_boundary_and_trigger_identity_join_at_actual_archive_time(self):
        raw,clocks=shaped()
        r=run(raw,clocks)
        last=r.samples[-1]
        self.assertEqual(last.boundary.cutoff_utc,last.h1.cutoff_utc)
        self.assertEqual(last.boundary.sides[0].h1.observed_closed_bars,1)
        self.assertTrue(last.boundary.sides[0].h1.closed_grid_complete)
        self.assertFalse(last.boundary.buffer_selected)
        summary=r.public_summary()
        self.assertEqual(summary["boundary_h1_paths_inspected"],1)
        self.assertFalse(summary["post_entry_monitoring_verified"])
        self.assertEqual(summary["delayed_trigger_slot_accounting"]["distinct_paired_trigger_slots"],5)
        self.assertEqual(summary["delayed_trigger_slot_accounting"]["repeated_paired_slot_observations"],1)

    def test_last_quarter_close_updates_boundary_not_middle_trigger(self):
        raw,clocks=shaped()
        a=run(raw,clocks).samples[-1]
        changed=raw[:-1]+(replace(raw[-1],low="0.99",close="1.00"),)
        b=run(changed,clocks).samples[-1]
        self.assertEqual(a.m15,b.m15)
        self.assertEqual(a.trigger_identity,b.trigger_identity)
        self.assertNotEqual(a.boundary,b.boundary)
        self.assertTrue(b.boundary.sides[0].h1.unbuffered_boundary_breach)
        self.assertFalse(b.boundary.invalidation_rule_approved)

    def test_long_delay_cannot_assert_complete_boundary_grid(self):
        raw,clocks=shaped()
        late=clocks[:-1]+((clocks[-1][0]+timedelta(hours=2),clocks[-1][1]),)
        row=run(raw,late).samples[-1]
        self.assertEqual(row.boundary.sides[0].h1.observed_closed_bars,1)
        self.assertFalse(row.boundary.sides[0].h1.closed_grid_complete)
        self.assertEqual(row.trigger_identity,run(raw,clocks).samples[-1].trigger_identity)

    def test_shared_manifest_clock_uses_all_visible_closed_hours_for_boundary_only(self):
        raw,clocks=shaped()
        known=clocks[-1][0]+timedelta(hours=1)
        extra=tuple(replace(x,start_utc=(
            START+timedelta(hours=5,minutes=5*j)).isoformat())
            for j,x in enumerate(raw[-12:]))
        extended=clocks[:-1]+((known,clocks[-1][1]),
                                 (known,clocks[-1][1]+timedelta(hours=1)))
        a=run(raw,clocks).samples[-1]
        b=run(raw+extra,extended).samples[-2]
        self.assertEqual(a.m15,b.m15)
        self.assertEqual(a.trigger_identity,b.trigger_identity)
        self.assertEqual(b.boundary.sides[0].h1.observed_closed_bars,2)
        self.assertTrue(b.boundary.sides[0].h1.closed_grid_complete)

    def test_latest_identity_entrypoint_stays_strict(self):
        raw,clocks=shaped()
        with self.assertRaisesRegex(ValueError,"EXACT_LATEST_TRIGGER_REQUIRED"):
            identify_private_trigger_pair(raw,
                latest_m15_open=START+timedelta(hours=4,minutes=30),
                decision=clocks[-1][0])

    def test_summary_masks_identity_and_breach_and_rejects_authority_drift(self):
        import json
        raw,clocks=shaped()
        r=run(raw,clocks)
        row=r.samples[-1]
        encoded=json.dumps(r.public_summary())
        self.assertNotIn(row.trigger_identity.private_slots[0].slot_sha256,encoded)
        self.assertNotIn("unbuffered_boundary_breach",encoded)
        self.assertNotIn("minimum_signed_distance",encoded)
        bad=replace(row,boundary=replace(row.boundary,buffer_selected=True))
        with self.assertRaisesRegex(ValueError,"DELAYED_BOUNDARY_AUTHORITY_DRIFT"):
            replace(r,samples=r.samples[:-1]+(bad,)).public_summary()
