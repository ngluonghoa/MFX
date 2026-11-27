"""P237 source context identity is private, causal, bounded and NO_SIGNAL."""
from dataclasses import replace
from datetime import timedelta
import json
from unittest import TestCase

from mfx_research.p232_delayed_middle_pairs import replay_delayed_middle_pairs
from test_mfx_p232_delayed_middle_pairs import shaped, START
from test_mfx_p228_pretrigger_native import h4_fixture, vintage

CUTOFF = START+timedelta(hours=4, minutes=15)


def run(raw=None, clocks=None, h4=None, snapshots=None):
    fixture_raw, fixture_clocks = shaped()
    raw = fixture_raw if raw is None else raw
    clocks = fixture_clocks if clocks is None else clocks
    h4 = h4_fixture() if h4 is None else h4
    old = vintage(CUTOFF-timedelta(hours=1))
    snapshots = ((old.observed,old),) if snapshots is None else snapshots
    return replay_delayed_middle_pairs(raw, clocks, h4, snapshots)


class P237SetupContextTests(TestCase):
    def test_joint_private_binding_and_coverage(self):
        r=run()
        row=r.samples[-1]
        self.assertIsNotNone(row.setup_context_identity)
        self.assertEqual(len(row.setup_context_identity.bounded_context_sha256),64)
        self.assertEqual(r.public_summary()["bounded_setup_context_identity_coverage"],1)
        self.assertFalse(r.public_summary()["full_setup_revision_identity_verified"])

    def test_posttrigger_changes_do_not_rewrite_source_context(self):
        raw,clocks=shaped()
        a=run(raw,clocks).samples[-1]
        changed=raw[:-1]+(replace(raw[-1],low="0.99",close="1.00"),)
        b=run(changed,clocks).samples[-1]
        self.assertEqual(a.setup_context_identity,b.setup_context_identity)
        self.assertNotEqual(a.delayed_decision,b.delayed_decision)

    def test_same_trigger_different_pretrigger_source_changes_binding(self):
        raw,clocks=shaped()
        a=run(raw,clocks).samples[-1]
        changed=(replace(raw[0],open="1.101"),)+raw[1:]
        b=run(changed,clocks).samples[-1]
        self.assertEqual(a.trigger_identity,b.trigger_identity)
        self.assertNotEqual(a.setup_context_identity,b.setup_context_identity)

    def test_later_d1_vintage_cannot_rewrite_frozen_context(self):
        old=vintage(CUTOFF-timedelta(hours=1))
        later=replace(vintage(CUTOFF+timedelta(minutes=1)),identity="later",
                      rows=old.rows[:-1]+(replace(old.rows[-1],close="1.15"),))
        a=run(snapshots=((old.observed,old),)).samples[-1]
        b=run(snapshots=((old.observed,old),(later.observed,later))).samples[-1]
        self.assertEqual(a.setup_context_identity,b.setup_context_identity)
        prior=replace(later,observed=CUTOFF-timedelta(minutes=1))
        c=run(snapshots=((old.observed,old),(prior.observed,prior))).samples[-1]
        self.assertNotEqual(a.setup_context_identity,c.setup_context_identity)

    def test_missing_native_context_does_not_fabricate_identity(self):
        row=run(h4=(),snapshots=()).samples[-1]
        self.assertIsNone(row.setup_context_identity)

    def test_private_digest_and_forged_binding_are_not_published(self):
        r=run()
        row=r.samples[-1]
        summary=json.dumps(r.public_summary())
        self.assertNotIn(row.setup_context_identity.bounded_context_sha256,summary)
        self.assertNotIn(row.h1.source_context_sha256,summary)
        bad=replace(row,setup_context_identity=replace(row.setup_context_identity,
                                                       persistent_idempotence_verified=True))
        with self.assertRaisesRegex(ValueError,"SETUP_CONTEXT_BINDING_DRIFT"):
            replace(r,samples=r.samples[:-1]+(bad,)).public_summary()

class P240CombinedCoverageTests(TestCase):
    def test_bound_and_decision_intersection_not_marginal_count(self):
        r=run()
        s=r.public_summary()
        self.assertEqual(s["bound_context_with_decision_recheck_coverage"],1)
        self.assertEqual(s["joint_clock_selected_replay"]["bound_context_with_decision_recheck_coverage"],1)
        u=s["unique_receipt_technical_coverage"]
        self.assertEqual(u["middle_pairs_replayed"],5)
        self.assertEqual(u["cohort_observations"],7)
        self.assertEqual(u["repeated_cohort_observations"],2)
        self.assertEqual(u["bound_context_with_decision_recheck_coverage"],1)

    def test_missing_native_not_combined_even_if_recheck(self):
        s=run(h4=(),snapshots=()).public_summary()
        self.assertEqual(s["delayed_decision_frozen_level_rechecks_computed"],1)
        self.assertEqual(s["bound_context_with_decision_recheck_coverage"],0)
        self.assertEqual(s["bound_context_decision_and_both_boundary_grids_coverage"],0)

    def test_missing_decision_grid_not_combined_even_with_binding(self):
        raw,clocks=shaped()
        late=clocks[:-1]+((clocks[-1][0]+timedelta(minutes=15),clocks[-1][1]),)
        s=run(raw,late).public_summary()
        self.assertEqual(s["bounded_setup_context_identity_coverage"],1)
        self.assertEqual(s["bound_context_with_decision_recheck_coverage"],0)

    def test_combined_is_intersection_of_actual_receipts(self):
        r=run()
        expected=sum(row.setup_context_identity is not None
                     and bool(row.delayed_decision.sides)
                     and all(x.h1 is not None and x.h4 is not None
                             and x.h1.closed_grid_complete and x.h4.closed_grid_complete
                             for x in row.boundary.sides)
                     for row in r.samples)
        s=r.public_summary()
        self.assertEqual(s["bound_context_decision_and_both_boundary_grids_coverage"],expected)
        self.assertFalse(s["unique_receipt_technical_coverage"]["market_signal_eligibility_assessed"])

    def test_unique_coverage_does_not_leak_source_or_outcome(self):
        r=run()
        s=json.dumps(r.public_summary()["unique_receipt_technical_coverage"])
        self.assertNotIn(r.samples[-1].setup_context_identity.bounded_context_sha256,s)
        for value in ("unbuffered_boundary_breach","within_draft_chase_window","B2","S2"):
            self.assertNotIn(value,s)
        self.assertIn("NO_SIGNAL",s)

    def test_flat_h1_keeps_clock_selected_denominator(self):
        raw,clocks=shaped()
        flat=tuple(replace(b,open="1.10",high="1.10",low="1.10",close="1.10") for b in raw)
        r=run(flat,clocks)
        self.assertEqual(r.joint_clock_samples[0].h1.status,"PRETRIGGER_H1_ZERO_RANGE")
        s=r.public_summary()["joint_clock_selected_replay"]
        self.assertEqual(s["middle_pairs_replayed"],1)
        self.assertEqual(s["pretrigger_h1_draft_contexts_computed"],0)
        self.assertEqual(s["bound_context_decision_and_both_boundary_grids_coverage"],0)

class P241NativeGapAccountingTests(TestCase):
    def test_d1_and_h4_partition_every_cohort(self):
        s=run().public_summary()
        for c in (s,s["clock_selected_replay"],s["joint_clock_selected_replay"],
                  s["unique_receipt_technical_coverage"]):
            self.assertEqual(c["middle_pairs_replayed"],
                sum(c[k] for k in ("pretrigger_d1_no_visible_vintage",
                    "pretrigger_d1_stale_vintage","pretrigger_d1_short_history",
                    "pretrigger_d1_fresh_vintages_with_five_rows")))
            self.assertEqual(c["middle_pairs_replayed"],
                sum(c[k] for k in ("pretrigger_h4_no_visible_archive",
                    "pretrigger_h4_stale_archive","pretrigger_h4_insufficient_pivots",
                    "pretrigger_h4_draft_structures_computed")))

    def test_no_visible_d1_and_h4_are_not_fresh(self):
        s=run(h4=(),snapshots=()).public_summary()
        j=s["joint_clock_selected_replay"]
        self.assertEqual(j["pretrigger_d1_no_visible_vintage"],1)
        self.assertEqual(j["pretrigger_h4_no_visible_archive"],1)
        self.assertEqual(j["decision_recheck_without_fresh_five_row_d1"],1)
        self.assertEqual(j["pretrigger_d1_fresh_vintages_with_five_rows"],0)

    def test_short_d1_history_is_distinct(self):
        old=vintage(CUTOFF-timedelta(hours=1))
        short=replace(old,rows=old.rows[-1:])
        s=run(snapshots=((short.observed,short),)).public_summary()
        self.assertEqual(s["joint_clock_selected_replay"]["pretrigger_d1_short_history"],1)

    def test_after_cutoff_vintage_does_not_fill_gap(self):
        late=vintage(CUTOFF+timedelta(minutes=1))
        s=run(snapshots=((late.observed,late),)).public_summary()
        self.assertEqual(s["joint_clock_selected_replay"]["pretrigger_d1_no_visible_vintage"],1)

    def test_unknown_native_status_fails_closed(self):
        r=run()
        row=r.samples[0]
        bad=replace(row,native=replace(row.native,d1_status="UNKNOWN"))
        with self.assertRaisesRegex(ValueError,"P241_NATIVE_GAP_STATUS_DRIFT"):
            replace(r,samples=(bad,)+r.samples[1:]).public_summary()

    def test_recheck_gap_and_bound_context_are_disjoint(self):
        s=run(h4=(),snapshots=()).public_summary()["unique_receipt_technical_coverage"]
        self.assertEqual(s["decision_recheck_without_fresh_five_row_d1"],1)
        self.assertEqual(s["bound_context_with_decision_recheck_coverage"],0)
        self.assertFalse(s["market_signal_eligibility_assessed"])
        self.assertEqual(s["action"],"NO_SIGNAL")

class P242D1ClockVisibilityTests(TestCase):
    def test_no_d1_archive_keeps_full_denominator(self):
        s=run(snapshots=()).public_summary()["d1_archive_clock_visibility_census"]
        self.assertEqual(s["without_visible_d1_archive"]["verified_hours"],5)
        self.assertEqual(s["without_visible_d1_archive"]["joint_clock_complete"],1)
        self.assertEqual(s["with_visible_d1_archive"]["verified_hours"],0)
        self.assertFalse(s["publisher_first_known_verified"])

    def test_exact_cutoff_archive_is_visible(self):
        v=vintage(CUTOFF)
        r=run(snapshots=((v.observed,v),))
        s=r.public_summary()["d1_archive_clock_visibility_census"]
        self.assertEqual(s["with_visible_d1_archive"]["verified_hours"],1)
        self.assertEqual(s["with_visible_d1_archive"]["joint_clock_complete"],1)
        self.assertEqual(s["without_visible_d1_archive"]["verified_hours"],4)

    def test_late_archive_never_backfills_earlier_cutoff(self):
        v=vintage(CUTOFF-timedelta(minutes=1))
        r=run(snapshots=((CUTOFF+timedelta(minutes=1),v),))
        s=r.public_summary()["d1_archive_clock_visibility_census"]
        self.assertEqual(s["with_visible_d1_archive"]["verified_hours"],0)
        self.assertEqual(s["without_visible_d1_archive"]["joint_clock_complete"],1)

    def test_partition_matches_independent_clock_denominators(self):
        s=run().public_summary()
        p=s["d1_archive_clock_visibility_census"]
        a,b=p["without_visible_d1_archive"],p["with_visible_d1_archive"]
        self.assertEqual(a["verified_hours"]+b["verified_hours"],s["verified_hours"])
        self.assertEqual(a["precursor_clock_complete"]+b["precursor_clock_complete"],
                         s["clock_census"]["four_contiguous_h1_hours_available_before_setup"])
        self.assertEqual(a["decision_clock_complete"]+b["decision_clock_complete"],
                         s["decision_clock_census"]["decision_grid_complete"])
        self.assertEqual(a["joint_clock_complete"]+b["joint_clock_complete"],
                         s["decision_clock_census"]["pretrigger_and_decision_clock_complete"])

    def test_forged_visibility_is_rejected(self):
        r=run()
        wrong=tuple(not v for v in r.d1_archive_visible_at_setup)
        with self.assertRaisesRegex(ValueError,"P242_D1_CLOCK_RAW_VISIBILITY_DRIFT"):
            replace(r,d1_archive_visible_at_setup=wrong).public_summary()

    def test_visibility_census_is_price_independent_and_redacted(self):
        raw,clocks=shaped()
        a=run(raw,clocks).public_summary()["d1_archive_clock_visibility_census"]
        b=run(tuple(replace(x,high="1.95") for x in raw),clocks).public_summary()[
            "d1_archive_clock_visibility_census"]
        self.assertEqual(a,b)
        self.assertNotIn("2026-11",json.dumps(a))
        self.assertFalse(a["d1_calendar_qualified"])
        self.assertFalse(a["selection_uses_prices_or_outcomes"])


class P243JointClockBlockerTests(TestCase):
    def test_matrix_conserves_every_era_and_margin(self):
        s=run().public_summary()
        for key, era in s["d1_archive_clock_visibility_census"].items():
            if not isinstance(era,dict):
                continue
            b=s["joint_clock_blocker_matrix"][key]
            m=b["precursor_by_decision_clock"]
            self.assertEqual(sum(sum(row.values()) for row in m.values()),era["verified_hours"])
            self.assertEqual(sum(m["complete"].values()),era["precursor_clock_complete"])
            self.assertEqual(sum(row["complete"] for row in m.values()),era["decision_clock_complete"])
            self.assertEqual(m["complete"]["complete"],era["joint_clock_complete"])

    def test_prior_late_and_decision_trailing_are_separate_and_joint(self):
        raw, clocks=shaped()
        late=clocks[:3]+((START+timedelta(hours=4,minutes=16),clocks[3][1]),
                         (START+timedelta(hours=5,minutes=16),clocks[4][1]))
        s=run(raw,late,snapshots=()).public_summary()["joint_clock_blocker_matrix"]
        m=s["without_visible_d1_archive"]["precursor_by_decision_clock"]
        self.assertEqual(m["prior_late"]["trailing_only"],1)
        self.assertEqual(m["earlier_gap_or_late"]["trailing_only"],1)
        self.assertEqual(s["without_visible_d1_archive"]["total_trailing_missing_m15_slot_observations"],2)

    def test_interior_and_trailing_slots_are_not_deduplicated_across_decisions(self):
        from mfx_research.p232_delayed_middle_pairs import (
            middle_pair_clock_census, decision_clock_coverage, summarize_joint_clock_blockers)
        _, clocks=shaped()
        end=clocks[-1][1]
        known=end+timedelta(hours=2,minutes=30)
        clocks=clocks[:-1]+((known,end),(known,end+timedelta(hours=2)))
        s=summarize_joint_clock_blockers(middle_pair_clock_census(clocks),
            decision_clock_coverage(clocks),(False,)*len(clocks))
        b=s["without_visible_d1_archive"]
        self.assertEqual(b["precursor_by_decision_clock"]["complete"]["both_gaps"],1)
        self.assertEqual(b["total_interior_missing_m15_slot_observations"],4)
        # :30 decision minus 15s grace settles only through :15.
        self.assertEqual(b["total_trailing_missing_m15_slot_observations"],2)

    def test_forged_precursor_state_fails_closed(self):
        r=run()
        c=replace(r.clock_census,private_precursor_states=("complete",)*r.verified_hours)
        with self.assertRaisesRegex(ValueError,"P243_PRECURSOR_STATE_ACCOUNTING_DRIFT"):
            replace(r,clock_census=c).public_summary()

    def test_empty_and_exact_d1_cutoff(self):
        from mfx_research.p232_delayed_middle_pairs import replay_delayed_middle_pairs
        s=replay_delayed_middle_pairs((),(),(),()).public_summary()["joint_clock_blocker_matrix"]
        self.assertEqual(s["without_visible_d1_archive"]["verified_hours"],0)
        v=vintage(CUTOFF)
        s=run(snapshots=((v.observed,v),)).public_summary()["joint_clock_blocker_matrix"]
        self.assertEqual(s["with_visible_d1_archive"]["precursor_by_decision_clock"]["complete"]["complete"],1)

    def test_price_independent_redacted_no_authority(self):
        raw,clocks=shaped()
        a=run(raw,clocks).public_summary()["joint_clock_blocker_matrix"]
        b=run(tuple(replace(x,high="1.95") for x in raw),clocks).public_summary()["joint_clock_blocker_matrix"]
        self.assertEqual(a,b)
        self.assertNotIn("2026-11",json.dumps(a))
        self.assertFalse(a["schedule_change_selected"])
        self.assertFalse(a["expiry_policy_selected"])
        self.assertEqual(a["action"],"NO_SIGNAL")


class P244BoundaryGapTests(TestCase):
    def test_each_frame_partition_and_combined_denominator(self):
        s=run().public_summary()
        for c in (s,s["clock_selected_replay"],s["joint_clock_selected_replay"],
                  s["unique_receipt_technical_coverage"]):
            for f in ("h1","h4"):
                self.assertEqual(c["middle_pairs_replayed"],sum(c[f"boundary_{f}_{k}"]
                    for k in ("anchor_unavailable","no_new_closed_slot_due","complete_nonempty",
                              "all_due_slots_missing","partial_grid")))
            self.assertEqual(c["bound_context_with_decision_recheck_coverage"],
                sum(c[k] for k in ("bound_recheck_h1_only_gap","bound_recheck_h4_only_gap",
                    "bound_recheck_both_boundary_gaps","bound_context_decision_and_both_boundary_grids_coverage")))

    def test_h4_no_new_slot_is_not_missing(self):
        c=run().public_summary()["joint_clock_selected_replay"]
        self.assertEqual(c["boundary_h1_complete_nonempty"],1)
        self.assertEqual(c["boundary_h4_no_new_closed_slot_due"],1)
        self.assertEqual(c["boundary_h4_missing_slot_observations"],0)

    def test_h4_due_but_not_archived_is_distinct_from_no_due_slot(self):
        from mfx_research.p232_delayed_middle_pairs import _boundary_clock_gap
        from mfx_research.p230_private_boundary_path import PrivateBoundaryPath
        row=run().samples[-1]
        missing=PrivateBoundaryPath(0,False,None,False)
        r=replace(row,native=replace(row.native,h4_prior_end=row.native.h4_prior_end-timedelta(hours=4)),
                  boundary=replace(row.boundary,sides=tuple(replace(s,h4=missing) for s in row.boundary.sides)))
        self.assertEqual(_boundary_clock_gap(r,"H4"),("all_due_slots_missing",1))
        c=run()._summary((r,))
        self.assertEqual(c["bound_recheck_h4_only_gap"],1)
        self.assertEqual(c["bound_context_decision_and_both_boundary_grids_coverage"],0)

    def test_missing_anchor_is_not_missing_slot_count(self):
        c=run(h4=(),snapshots=()).public_summary()["joint_clock_selected_replay"]
        self.assertEqual(c["boundary_h4_anchor_unavailable"],1)
        self.assertEqual(c["boundary_h4_missing_slot_observations"],0)

    def test_forged_complete_or_asymmetric_slot_count_rejected(self):
        from mfx_research.p232_delayed_middle_pairs import _boundary_clock_gap
        row=run().samples[-1]
        sides=row.boundary.sides
        bad=replace(row,boundary=replace(row.boundary,sides=(replace(sides[0],
                    h1=replace(sides[0].h1,closed_grid_complete=False)),sides[1])))
        with self.assertRaisesRegex(ValueError,"P244_BOUNDARY_SLOT_ACCOUNTING_DRIFT"):
            _boundary_clock_gap(bad,"H1")
        bad=replace(row,boundary=replace(row.boundary,sides=(replace(sides[0],
                    h1=replace(sides[0].h1,observed_closed_bars=0,closed_grid_complete=False)),sides[1])))
        with self.assertRaisesRegex(ValueError,"P244_BOUNDARY_MIRROR_GRID_DRIFT"):
            _boundary_clock_gap(bad,"H1")

    def test_partial_grid_counts_slots_without_exposing_breach(self):
        from mfx_research.p232_delayed_middle_pairs import _boundary_clock_gap
        row=run().samples[-1]
        later=replace(row,archive_decision_utc=row.archive_decision_utc+timedelta(hours=2),
            boundary=replace(row.boundary,sides=tuple(replace(s,h1=replace(s.h1,
                closed_grid_complete=False)) for s in row.boundary.sides)))
        self.assertEqual(_boundary_clock_gap(later,"H1"),("partial_grid",2))
        s=json.dumps(run().public_summary())
        self.assertNotIn("minimum_signed_distance",s)
        self.assertNotIn("unbuffered_boundary_breach",s)


class P245ObservedH4FollowupTests(TestCase):
    def shifted(self, minutes=None):
        from datetime import datetime
        raw,clocks=shaped()
        shift=timedelta(hours=3)
        raw=tuple(replace(b,start_utc=(datetime.fromisoformat(b.start_utc)+shift).isoformat()) for b in raw)
        clocks=tuple((known+shift,end+shift) for known,end in clocks)
        h4=h4_fixture()
        if minutes is not None:
            end=clocks[-1][1]
            bar=replace(h4[-1][1][0],native_open_label=(end-timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"))
            h4=h4+((end+timedelta(minutes=minutes),(bar,)),)
        return run(raw,clocks,h4=h4)

    def test_later_actual_h4_arrival_is_distinct_frozen_recheck(self):
        r=self.shifted(12)
        s=r.public_summary()
        f=s["observed_later_h4_archive_recheck"]
        self.assertEqual(f["original_joint_bound_recheck_with_h4_gap"],1)
        self.assertEqual(f["original_due_h4_slots_later_visible"],1)
        self.assertEqual(f["later_bound_recheck_and_both_boundaries"],1)
        self.assertEqual(s["joint_clock_selected_replay"]["bound_context_decision_and_both_boundary_grids_coverage"],0)
        original,later=r.h4_followups[0]
        self.assertEqual(original.setup_context_identity,later.setup_context_identity)
        self.assertGreater(later.archive_decision_utc,original.archive_decision_utc)

    def test_h4_arrival_after_m15_settlement_cannot_reuse_stale_decision(self):
        f=self.shifted(20).public_summary()["observed_later_h4_archive_recheck"]
        self.assertEqual(f["later_h4_grid_complete"],1)
        self.assertEqual(f["later_m15_grid_complete"],0)
        self.assertEqual(f["later_frozen_level_recheck"],0)
        self.assertEqual(f["later_bound_recheck_and_both_boundaries"],0)

    def test_no_observed_later_archive_no_fabricated_revisit(self):
        f=self.shifted().public_summary()["observed_later_h4_archive_recheck"]
        self.assertEqual(f["no_observed_recovery_in_audited_history"],1)
        self.assertEqual(f["original_due_h4_slots_later_visible"],0)

    def test_same_decision_clock_is_not_followup(self):
        f=self.shifted(7).public_summary()["observed_later_h4_archive_recheck"]
        self.assertEqual(f["original_joint_bound_recheck_with_h4_gap"],0)
        self.assertEqual(f["original_due_h4_slots_later_visible"],0)

    def test_forged_frozen_context_or_duplicate_rejected(self):
        r=self.shifted(12)
        original,later=r.h4_followups[0]
        for rows in (((original,replace(later,trigger_identity=replace(later.trigger_identity,
                     persistent_idempotence_verified=True))),),
                     ((original,later),(original,later))):
            with self.assertRaisesRegex(ValueError,"P245_FROZEN_FOLLOWUP_DRIFT"):
                replace(r,h4_followups=rows).public_summary()

    def test_followup_summary_masks_values_and_has_no_authority(self):
        r=self.shifted(12)
        f=r.public_summary()["observed_later_h4_archive_recheck"]
        s=json.dumps(f)
        self.assertNotIn("2026-11",s)
        self.assertNotIn(r.h4_followups[0][0].setup_context_identity.bounded_context_sha256,s)
        self.assertFalse(f["original_decision_rewritten"])
        self.assertFalse(f["expiry_policy_selected"])
        self.assertEqual(f["action"],"NO_SIGNAL")


class P246CrossFrameFollowupTests(TestCase):
    def fixture(self, minutes=20, extend=False):
        from datetime import datetime
        raw,clocks=shaped()
        shift=timedelta(hours=3)
        raw=tuple(replace(b,start_utc=(datetime.fromisoformat(b.start_utc)+shift).isoformat()) for b in raw)
        clocks=tuple((known+shift,end+shift) for known,end in clocks)
        end=clocks[-1][1]
        h4=h4_fixture()
        bar=replace(h4[-1][1][0],native_open_label=(end-timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"))
        h4=h4+((end+timedelta(minutes=minutes),(bar,)),)
        if extend:
            raw=raw+tuple(replace(b,start_utc=(datetime.fromisoformat(b.start_utc)+timedelta(hours=1)).isoformat()) for b in raw[-12:])
            clocks=clocks+((end+timedelta(hours=1,minutes=7),end+timedelta(hours=1)),)
        return run(raw,clocks,h4=h4)

    def test_first_h4_arrival_can_be_complete(self):
        r=self.fixture(12)
        f=r.public_summary()["first_complete_observed_cross_frame_recheck"]
        self.assertEqual(f["joint_grid_recoveries"],1)
        self.assertEqual(r.complete_followups[0][1],r.h4_followups[0][1])

    def test_next_m5_actual_arrival_recovers_all_grids(self):
        r=self.fixture(20,True)
        f=r.public_summary()["first_complete_observed_cross_frame_recheck"]
        self.assertEqual(f["joint_grid_recoveries"],1)
        self.assertEqual(f["frozen_level_rechecks"],1)
        original,later=r.complete_followups[0]
        self.assertEqual(later.archive_decision_utc,r.samples[-1].archive_decision_utc)
        self.assertEqual(original.setup_context_identity,later.setup_context_identity)
        self.assertGreater(later.archive_decision_utc,r.h4_followups[0][1].archive_decision_utc)

    def test_no_actual_later_complete_clock(self):
        r=self.fixture()
        f=r.public_summary()["first_complete_observed_cross_frame_recheck"]
        self.assertEqual(f["first_h4_recoveries"],1)
        self.assertEqual(f["joint_grid_recoveries"],0)
        self.assertEqual(f["no_joint_grid_recovery_in_audited_history"],1)

    def test_no_h4_gap_no_followup(self):
        f=self.fixture(7,True).public_summary()["first_complete_observed_cross_frame_recheck"]
        self.assertEqual(f["first_h4_recoveries"],0)
        self.assertEqual(f["joint_grid_recoveries"],0)

    def test_duplicate_complete_followup_rejected(self):
        r=self.fixture(12)
        with self.assertRaisesRegex(ValueError,"P246_COMPLETE_FOLLOWUP_DRIFT"):
            replace(r,complete_followups=r.complete_followups*2).public_summary()

    def test_redacted_coverage_only(self):
        r=self.fixture(20,True)
        f=r.public_summary()["first_complete_observed_cross_frame_recheck"]
        s=json.dumps(f)
        self.assertNotIn("2026-11",s)
        self.assertNotIn(r.complete_followups[0][0].setup_context_identity.bounded_context_sha256,s)
        self.assertFalse(f["selection_uses_prices_or_outcomes"])
        self.assertFalse(f["expiry_policy_selected"])
        self.assertEqual(f["action"],"NO_SIGNAL")
