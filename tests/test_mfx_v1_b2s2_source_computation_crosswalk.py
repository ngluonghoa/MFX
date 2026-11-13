"""P0.157: exact 36 B2/S2 original-source rule-to-code gap matrix.

No source-owner authorization is supplied by synthetic fixture, price math,
original doc paragraph, a locally declared 'approved' flag or GitHub CI.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
import json
from unittest import TestCase

from mfx_research.b2_s2_source_computation_crosswalk import (
    VERSION, RESEARCH_CATEGORIES, reconcile_b2s2_source_to_computation,
)
from mfx_research.p034_sim_adversarial_review import (
    verify_owner_decision_dossier,
)
from mfx_research.source_parameter_review import REQUIREMENTS
from tools.run_mfx_v1_manual_drive_six_tf import safe_summary
from test_mfx_v1_manual_signal_only_drive_output import (
    ASOF, mocked,
)
from test_mfx_v1_six_tf_sealed_archive_consumer import consume


def study(receipt=None):
    return reconcile_b2s2_source_to_computation(
        consume() if receipt is None else receipt,
    )


def row_of(result, rule, requirement):
    return next(x for x in result.rows
                if x.rule_id == rule
                and x.source_requirement_id == requirement)


class SourceNumericToRealComputationMatrixTests(TestCase):
    def test_01_exact_36_source_pinned_rows_from_real_repo_dossier(self):
        r=study()
        owner=verify_owner_decision_dossier()
        self.assertEqual(r.version,VERSION)
        self.assertEqual(len(r.rows),36)
        self.assertEqual(len(REQUIREMENTS),18)
        self.assertEqual(
            tuple((x.rule_id,x.source_requirement_id,x.phase,
                   x.original_source_paragraph_index) for x in r.rows),
            owner.rows,
        )

    def test_02_preserve_exact_two_sides_and_source_paragraphs(self):
        r=study()
        self.assertEqual(tuple(x.rule_id for x in r.rows),
                         ("B2",)*18+("S2",)*18)
        self.assertEqual(
            row_of(r,"B2","causal_d1_h4_trend").original_source_paragraph_index,29)
        self.assertEqual(
            row_of(r,"S2","causal_d1_h4_trend").original_source_paragraph_index,117)

    def test_03_no_numeric_formula_signed_by_synthetic_code(self):
        r=study()
        self.assertEqual(r.original_b2s2_numeric_approvals,0)
        self.assertEqual(r.original_source_numeric_decisions_pending,36)
        self.assertFalse(r.independently_authenticated_source_owner_formula)
        self.assertFalse(r.original_forex_parity_proven)
        self.assertFalse(r.live_signal_release_approved)
        for a in r.rows:
            self.assertEqual(a.owner_numeric_decision,"AWAITING_SOURCE_OWNER")
            self.assertFalse(a.original_source_numeric_rule_approved)
            self.assertFalse(a.independently_authenticated_owner_evidence)
            self.assertFalse(a.eligible_for_verified_buy_sell)

    def test_04_h1_observed_tr_is_not_owner_atr_period(self):
        a=study()
        for rid in ("B2","S2"):
            r=row_of(a,rid,"h1_true_range_atr_period")
            self.assertEqual(
                r.observed_research_state,
                "PRIVATE_SIMPLE_MEAN_TRUE_RANGE_PRECURSOR_NOT_ATR")
            self.assertFalse(r.original_source_numeric_rule_approved)

    def test_05_h1_source_envelope_not_approved_zone_origin(self):
        for rid in ("B2","S2"):
            r=row_of(study(),rid,"h1_zone_origin_identity")
            self.assertEqual(r.observed_research_state,
                             "PRIVATE_H1_BOUNDED_ENVELOPE_PRECURSOR_ONLY")
            self.assertFalse(r.publisher_first_known_qualified)

    def test_06_h1_nearness_multiplier_is_not_present_even_with_tr(self):
        a=study()
        for name in ("h1_near_zone_atr_multiple",
                     "h1_zone_width_atr_multiple",
                     "anti_chase_max_atr_multiple"):
            for rid in ("B2","S2"):
                r=row_of(a,rid,name)
                self.assertEqual(r.evidence_basis,"H1_OBSERVED_TR_MEAN_ONLY")
                self.assertFalse(r.original_source_numeric_rule_approved)

    def test_07_m15_closed_pivot_still_not_original_structural_rule(self):
        a=study()
        for name in ("confirmed_pivot_left_bars",
                     "confirmed_pivot_right_bars",
                     "structural_hl_lh_invalidation",
                     "m15_early_reversal_structure",
                     "known_micro_break_confirm_rule"):
            for rid in ("B2","S2"):
                self.assertEqual(
                    row_of(a,rid,name).observed_research_state,
                    "PRIVATE_SIM_PIVOT_WINDOW_RESEARCH_NOT_ORIGINAL_RULE")

    def test_08_d1_and_h4_trend_not_source_approved(self):
        a=study()
        for rid in ("B2","S2"):
            self.assertEqual(
                row_of(a,rid,"causal_d1_h4_trend").observed_research_state,
                "D1_CALENDAR_AND_D1_SOURCE_REVISION_UNQUALIFIED")

    def test_09_bidask_not_inferred_from_mid_cache(self):
        a=study()
        self.assertEqual(
            row_of(a,"B2","bid_ask_spread_and_cost_gate").observed_research_state,
            "NO_LICENSED_EXECUTABLE_BIDASK")
        self.assertFalse(a.authorized_real_bidask_net_rr)

    def test_10_broker_session_news_calendar_still_missing(self):
        self.assertEqual(
            row_of(study(),"S2","session_dst_rollover_news_gate")
            .observed_research_state,
            "NO_INDEPENDENT_BROKER_SESSION_POLICY")

    def test_11_net_sl_tp_r_has_no_source_approved_plan(self):
        self.assertEqual(row_of(
            study(),"B2","structural_sl_tp_net_r_gate").observed_research_state,
            "NO_SOURCE_APPROVED_RISK_PLAN")

    def test_12_real_idempotent_signal_lifecycle_not_sim_event(self):
        self.assertEqual(row_of(
            study(),"S2","event_expiry_and_idempotence").observed_research_state,
            "NO_APPROVED_REAL_EVENT_LIFECYCLE")

    def test_13_sha_chain_is_not_publisher_first_known(self):
        self.assertEqual(row_of(
            study(),"B2","licensed_source_first_known_revision")
            .observed_research_state,
            "NO_LICENSED_PUBLISHER_FIRST_KNOWN")

    def test_14_sim_stress_is_not_historical_forex_oos(self):
        a=study()
        self.assertEqual(row_of(
            a,"S2","historical_walkforward_oos_qualification")
            .observed_research_state,"NO_REAL_HISTORICAL_OOS")
        self.assertFalse(a.historical_oos_qualified)

    def test_15_stale_m5_m15_cannot_appear_as_ready_pivots(self):
        r=study(consume(asof=ASOF+timedelta(minutes=18)))
        self.assertEqual(
            row_of(r,"B2","m15_early_reversal_structure")
            .observed_research_state,
            "INSUFFICIENT_M15_CLOSED_PIVOT_CONTEXT")
        self.assertEqual(
            r.technical_six_frame_coverage,
            "INCOMPLETE_OR_STALE_SIX_FRAME_TECHNICAL_RESEARCH")
        self.assertEqual(r.original_source_numeric_decisions_pending,36)

    def test_16_not_even_complete_six_latest_frames_authorize_buy(self):
        a=study()
        self.assertEqual(a.technical_six_frame_coverage,
                         "LATEST_SIX_CLOSED_FRAMES_PRESENT_RESEARCH_ONLY")
        self.assertEqual((a.action,a.stage),("NO_SIGNAL","UNVERIFIED"))
        self.assertFalse(a.may_trade)

    def test_17_all_original_source_names_mapped_once(self):
        self.assertEqual(set(RESEARCH_CATEGORIES),
                         {n for n, _, _, _ in REQUIREMENTS})
        self.assertEqual(len(RESEARCH_CATEGORIES),18)

    def test_18_source_body_is_immutable_and_one_release_blocker(self):
        r=study()
        with self.assertRaises(FrozenInstanceError):
            r.action="BUY"
        with self.assertRaises(FrozenInstanceError):
            r.rows[0].original_source_numeric_rule_approved=True

    def test_19_no_external_price_reader_cache_writer_or_broker(self):
        r=study()
        self.assertEqual(
            (r.provider_calls,r.drive_market_cache_writes,r.broker_orders),
            (0,0,0))

    def test_20_untyped_receipt_is_denied(self):
        for bad in (None,{},[],"NO_SIGNAL"):
            with self.subTest(bad=bad),self.assertRaisesRegex(
                    TypeError,"TYPED_SHA_SEALED"):
                reconcile_b2s2_source_to_computation(bad)

    def test_21_no_privilege_forged_in_private_multibar(self):
        r=consume()
        forged=replace(r.private_multibar,
                       original_forex_numeric_source_approved=True)
        with self.assertRaisesRegex(ValueError,"RIGHTS_DRIFT"):
            study(replace(r,private_multibar=forged))

    def test_22_no_privilege_forged_in_pivot_source(self):
        r=consume()
        forged=replace(r.private_pivot_sensitivity,
                       original_forex_numeric_pivot_policy_approved=True)
        with self.assertRaisesRegex(ValueError,"RIGHTS_DRIFT"):
            study(replace(r,private_pivot_sensitivity=forged))

    def test_23_forged_vendor_licence_denied(self):
        r=consume()
        forged=replace(r.private_multibar,
                       vendor_source_license_verified=True)
        with self.assertRaisesRegex(ValueError,"RIGHTS_DRIFT"):
            study(replace(r,private_multibar=forged))

    def test_24_caller_replaced_pivot_result_fails_closed(self):
        r=consume()
        forged=replace(r.private_pivot_sensitivity,studied=())
        with self.assertRaisesRegex(ValueError,
                                    "SIX_TF_RESEARCH_COVERAGE_DRIFT"):
            study(replace(r,private_pivot_sensitivity=forged))

    def test_25_private_source_history_sha_still_rechecked(self):
        r=consume()
        multi=r.private_multibar
        changed=list(multi.private_closed_histories)
        name, bars=changed[0]
        changed[0]=(name,(replace(bars[0],high="1.1100"),)+bars[1:])
        with self.assertRaisesRegex(ValueError,"PRIVATE_INPUT_SHA_MISMATCH"):
            study(replace(r,private_multibar=replace(
                multi,private_closed_histories=tuple(changed))))

    def test_26_standalone_dossier_is_not_an_owner_approval(self):
        owner=verify_owner_decision_dossier()
        self.assertEqual(owner.pending_owner_decisions,36)
        self.assertEqual(owner.original_numeric_rules_approved,0)
        self.assertFalse(owner.signed_owner_evidence)

    def test_27_safe_existing_drive_report_shows_36_owner_gaps(self):
        report=safe_summary(mocked(),drive_gets=8)
        sub=report["b2_s2_source_computation_crosswalk"]
        self.assertEqual(sub["status"],
                         "36_PINNED_OWNER_DECISIONS_PENDING_RESEARCH_ONLY")
        self.assertEqual(len(sub["rows"]),36)
        self.assertEqual(sub["remaining_numeric_owner_decisions"],36)
        self.assertEqual(sub["original_numeric_approvals"],0)
        self.assertEqual(sub["public_signal_action"],"NO_SIGNAL")
        self.assertEqual(report["drive_reads"],8)

    def test_28_public_report_matches_36_source_rows_in_exact_order(self):
        report=safe_summary(mocked(),drive_gets=1)
        sub=report["b2_s2_source_computation_crosswalk"]
        expected=study(mocked())
        for record, review in zip(sub["rows"],expected.rows):
            self.assertEqual(record["rule_id"],review.rule_id)
            self.assertEqual(record["requirement_id"],
                             review.source_requirement_id)
            self.assertEqual(record["phase"],review.phase)
            self.assertFalse(record["original_numeric_owner_approved"])

    def test_29_public_output_contains_no_private_prices_or_pivots(self):
        s=json.dumps(safe_summary(mocked(),drive_gets=0))
        for token in ("candidate_mid_price","latest_true_range",
                      "observed_mean_true_range","private_input_digest_sha256",
                      "private_closed_histories","open_price","high_price",
                      "1.1000","1.0990","refresh_token","oauth_client_secret",
                      "broker_account","api_key","file_id"):
            with self.subTest(token=token):
                self.assertNotIn(token,s)

    def test_30_safe_report_does_not_generate_any_additional_drive_get(self):
        s=safe_summary(mocked(),drive_gets=3)
        x=s["b2_s2_source_computation_crosswalk"]
        self.assertEqual(x["drive_gets_added"],0)
        self.assertEqual(x["provider_requests_added"],0)
        self.assertEqual(x["drive_writes"],0)
        self.assertEqual(x["broker_orders"],0)
        self.assertEqual(s["provider_price_requests"],0)

    def test_31_m15_gap_is_visible_to_owner_reviewer(self):
        r=safe_summary(
            mocked(asof=ASOF+timedelta(minutes=18)),drive_gets=2)
        records=r["b2_s2_source_computation_crosswalk"]["rows"]
        relevant=[x for x in records
                  if x["requirement_id"]=="m15_early_reversal_structure"]
        self.assertEqual(len(relevant),2)
        self.assertTrue(all(x["private_computation_state"]==
            "INSUFFICIENT_M15_CLOSED_PIVOT_CONTEXT" for x in relevant))
        self.assertEqual(r["action"],"NO_SIGNAL")

    def test_32_source_owner_approval_cannot_be_promoted_by_summary(self):
        s=safe_summary(mocked(),drive_gets=0)
        for r in s["b2_s2_source_computation_crosswalk"]["rows"]:
            self.assertFalse(r["original_numeric_owner_approved"])
        self.assertFalse(s["numeric_buy_sell_rules_approved"])
        self.assertFalse(s["may_publish_buy_sell"])

    def test_33_forged_pivot_public_signal_denied(self):
        r=consume()
        pivot=replace(r.private_pivot_sensitivity,
                      may_publish_price_derived_values_or_signals=True)
        with self.assertRaisesRegex(ValueError,"RIGHTS_DRIFT"):
            study(replace(r,private_pivot_sensitivity=pivot))

    def test_34_no_source_approved_price_at_causal_close(self):
        r=study()
        self.assertFalse(r.authorized_real_bidask_net_rr)
        self.assertFalse(any(x.publisher_first_known_qualified
                             for x in r.rows))
        self.assertEqual(r.action,"NO_SIGNAL")
