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
        self.assertEqual(b["total_trailing_missing_m15_slot_observations"],4)

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
