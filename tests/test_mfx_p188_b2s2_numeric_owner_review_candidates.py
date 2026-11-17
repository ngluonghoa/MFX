"""P0.188: 11 experimental B2/S2 pair suggestions, NEVER source approval."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from unittest import TestCase
from unittest.mock import patch

from mfx_research.mfx_b2s2_independent_policy_draft import (
    read_independent_mfx_policy_draft,
)
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    read_mfx_confirmed_b2s2_v2,
)
from mfx_research.p188_b2s2_numeric_owner_review_candidates import (
    PROPOSEABLE, EXTERNAL_UNRESOLVED, POLICY_STATUS,
    UNRESOLVED_STATUS, VERSION, compile_p188_review_draft,
    prepare_p184_external_review,
)
from mfx_research.p184_paired_f2_owner_review import (
    TEMPLATE, compile_paired_f2_owner_proposals,
)
from mfx_research.source_parameter_review import REQUIREMENTS

DUMMY_EVIDENCE = "e"*64  # CI-only shape fixture, NOT a real reviewer artifact.


class P188B2S2OwnerFormulaReviewTests(TestCase):
    def test_01_exact_18_original_requirement_pairs_11_experiments(self):
        r=compile_p188_review_draft()
        self.assertEqual(r.version,VERSION)
        self.assertEqual(len(r.rows),18)
        self.assertEqual((r.experimental_pairs_for_review,
                          r.unresolved_source_pairs),(11,7))
        self.assertEqual([(
            x.requirement_id,x.phase,x.b2_source_paragraph_index,
            x.s2_source_paragraph_index) for x in r.rows],list(REQUIREMENTS))
        self.assertEqual(
            {x.requirement_id for x in r.rows if x.status==POLICY_STATUS},
            set(PROPOSEABLE))
        self.assertEqual(
            {x.requirement_id for x in r.rows if x.status==UNRESOLVED_STATUS},
            set(EXTERNAL_UNRESOLVED))

    def test_02_pinned_only_MFX_versioned_draft_sha_and_unapproved(self):
        r=compile_p188_review_draft()
        self.assertEqual(r.p160_policy_sha256,
                         read_independent_mfx_policy_draft().canonical_sha256)
        self.assertEqual(r.p161_policy_sha256,
                         read_mfx_confirmed_b2s2_v2().fingerprint_sha256)
        self.assertEqual((r.original_owner_numeric_approvals,
                          r.pending_original_numeric_decisions),(0,36))
        self.assertEqual(r.action,"NO_SIGNAL")
        self.assertFalse(r.owner_authenticated)
        self.assertFalse(r.may_publish_buy_sell)

    def test_03_symmetric_trend_reversal_formula_requirements(self):
        x={p.requirement_id:p for p in compile_p188_review_draft().rows}
        a=x["causal_d1_h4_trend"]
        self.assertIn("higher",a.b2_formula)
        self.assertIn("lower",a.s2_formula)
        self.assertIn("1L/1R",a.b2_formula)
        self.assertIn("1L/1R",a.s2_formula)

    def test_04_close_causal_pivots_not_forged_vendor_first_known(self):
        x={p.requirement_id:p for p in compile_p188_review_draft().rows}
        self.assertIn("1",x["confirmed_pivot_left_bars"].b2_formula)
        self.assertIn("1",x["confirmed_pivot_right_bars"].s2_formula)
        for q in ("causal_d1_h4_trend","m15_early_reversal_structure"):
            self.assertIn("first-known",x[q].causal_asof_notes)
        self.assertFalse(compile_p188_review_draft().publisher_first_known_verified)

    def test_05_h1_mid_zone_and_simple_mean_TR_are_explicit(self):
        x={p.requirement_id:p for p in compile_p188_review_draft().rows}
        self.assertIn("MIN",x["h1_zone_origin_identity"].b2_formula)
        self.assertIn("MAX",x["h1_zone_origin_identity"].s2_formula)
        self.assertIn("3",x["h1_zone_lookback"].b2_formula)
        self.assertIn("3",x["h1_true_range_atr_period"].b2_formula)
        self.assertIn("not Wilder ATR",x["h1_true_range_atr_period"].s2_formula)
        self.assertIn("0.3",x["h1_zone_width_atr_multiple"].b2_formula)
        self.assertIn("0.5",x["h1_near_zone_atr_multiple"].s2_formula)
        self.assertIn("0.5",x["anti_chase_max_atr_multiple"].b2_formula)

    def test_06_microbreak_strict_symmetry_not_pub_signal(self):
        x={p.requirement_id:p for p in compile_p188_review_draft().rows}
        self.assertIn("close >",x["known_micro_break_confirm_rule"].b2_formula)
        self.assertIn("close <",x["known_micro_break_confirm_rule"].s2_formula)
        self.assertFalse(x["known_micro_break_confirm_rule"].may_publish_buy_sell)

    def test_07_seven_unavailable_requirements_have_no_fabricated_values(self):
        x={p.requirement_id:p for p in compile_p188_review_draft().rows}
        self.assertEqual(set(EXTERNAL_UNRESOLVED),
                         {k for k,r in x.items() if r.b2_formula is None})
        for name in EXTERNAL_UNRESOLVED:
            self.assertEqual((x[name].b2_formula,x[name].s2_formula,
                              x[name].units,x[name].causal_asof_notes),
                             (None,None,None,None))

    def test_08_public_summary_no_price_or_formulas_or_permissions(self):
        r=compile_p188_review_draft()
        out=r.public_summary()
        self.assertEqual(out["source_requirements_paired"],18)
        self.assertEqual(out["mfx_experimental_pairs_for_owner_review"],11)
        self.assertEqual(out["original_source_numeric_approvals"],0)
        self.assertFalse(out["owner_authenticated"])
        self.assertFalse(out["may_publish_buy_sell"])
        rendered=json.dumps(out,sort_keys=True)
        self.assertNotIn("MIN of LOW",rendered)
        self.assertNotIn("EUR/USD",rendered)
        self.assertNotIn("MID price",rendered)
        self.assertNotIn("source_config_sha",rendered)
        self.assertEqual((out["provider_price_requests"],
                          out["drive_cache_writes"],out["broker_orders"]),
                         (0,0,0))

    def test_09_unsigned_missing_evidence_cannot_create_proposals(self):
        for sha in ("", "0"*40, "0"*63, "A"*64, "g"*64, None):
            with self.subTest(sha=sha),self.assertRaises(ValueError):
                prepare_p184_external_review(
                    externally_supplied_evidence_sha256=sha,
                    selected_requirement_ids=(PROPOSEABLE[0],),
                )

    def test_10_selection_type_unknown_duplicates_and_empty_denied(self):
        for ids in (
            (), [PROPOSEABLE[0]], ("fake_name",),
            (PROPOSEABLE[0],PROPOSEABLE[0]), EXTERNAL_UNRESOLVED[:1],
        ):
            with self.subTest(ids=ids),self.assertRaises(ValueError):
                prepare_p184_external_review(
                    externally_supplied_evidence_sha256=DUMMY_EVIDENCE,
                    selected_requirement_ids=ids,
                )

    def test_11_one_proposed_pair_expands_to_two_unapproved_sides(self):
        packet,receipt=prepare_p184_external_review(
            externally_supplied_evidence_sha256=DUMMY_EVIDENCE,
            selected_requirement_ids=("causal_d1_h4_trend",),
        )
        self.assertEqual(receipt.actionable_proposal_pairs,1)
        self.assertEqual(receipt.expanded_p035_proposal_rows,2)
        self.assertEqual(receipt.original_numeric_rules_approved,0)
        self.assertEqual(receipt.original_pending_numeric_rules,36)
        self.assertEqual(receipt.action,"NO_SIGNAL")
        self.assertEqual(compile_paired_f2_owner_proposals(packet).safe_summary(),
                         receipt.safe_summary())
        self.assertIsNone(packet["paired_rows"][1]["review_intent"])

    def test_12_eleven_technical_pairs_expand_to_22_review_rows_not_signoff(self):
        packet,receipt=prepare_p184_external_review(
            externally_supplied_evidence_sha256=DUMMY_EVIDENCE,
            selected_requirement_ids=tuple(reversed(PROPOSEABLE)),
        )
        self.assertEqual(receipt.actionable_proposal_pairs,11)
        self.assertEqual(receipt.expanded_p035_proposal_rows,22)
        self.assertEqual(receipt.p035_result.proposals_count,22)
        self.assertEqual(receipt.p035_result.source_numeric_rules_approved,0)
        self.assertEqual(receipt.p035_result.source_owner_decisions_still_pending,36)
        self.assertFalse(receipt.may_publish_buy_sell)
        self.assertTrue(all(r["review_intent"] is None
                        for r in packet["paired_rows"]
                        if r["requirement_id"] in EXTERNAL_UNRESOLVED))

    def test_13_original_empty_p184_template_is_never_modified(self):
        prior=TEMPLATE.read_bytes()
        packet,receipt=prepare_p184_external_review(
            externally_supplied_evidence_sha256=DUMMY_EVIDENCE,
            selected_requirement_ids=PROPOSEABLE,
        )
        self.assertEqual(TEMPLATE.read_bytes(),prior)
        packet["paired_rows"][0]["b2_formula"]="tampered"
        self.assertEqual(TEMPLATE.read_bytes(),prior)
        self.assertEqual(receipt.original_numeric_rules_approved,0)

    def test_14_reviewer_input_not_cryptographic_owner_authentication(self):
        _,receipt=prepare_p184_external_review(
            externally_supplied_evidence_sha256=DUMMY_EVIDENCE,
            selected_requirement_ids=("confirmed_pivot_right_bars",),
        )
        self.assertFalse(receipt.mirrored_formula_authenticated)
        self.assertFalse(receipt.p035_result.may_promote_numeric_policy)
        self.assertFalse(receipt.p035_result.release_ready)
        self.assertFalse(receipt.may_trade)
        self.assertEqual(receipt.broker_orders,0)

    def test_15_rejected_forged_policy_signoffs(self):
        original=read_independent_mfx_policy_draft()
        with patch(
            "mfx_research.p188_b2s2_numeric_owner_review_candidates."
            "read_independent_mfx_policy_draft",
            return_value=replace(original,may_publish_buy_sell=True),
        ):
            with self.assertRaises(ValueError):
                compile_p188_review_draft()
        other=read_mfx_confirmed_b2s2_v2()
        with patch(
            "mfx_research.p188_b2s2_numeric_owner_review_candidates."
            "read_mfx_confirmed_b2s2_v2",
            return_value=replace(other,numeric_rules_approved=True),
        ):
            with self.assertRaises(ValueError):
                compile_p188_review_draft()

    def test_16_deterministic_and_immutable_reviewer_draft(self):
        a,b=compile_p188_review_draft(),compile_p188_review_draft()
        self.assertEqual(a,b)
        with self.assertRaises(FrozenInstanceError):
            a.action="BUY"
        with self.assertRaises(FrozenInstanceError):
            a.rows[0].status="APPROVED"
        self.assertFalse(a.real_vendor_rights_verified)

    def test_17_no_broker_provider_drive_apis_in_module_source(self):
        from pathlib import Path
        source=Path("mfx_research/p188_b2s2_numeric_owner_review_candidates.py").read_text()
        for blocked in ("requests.get(", "requests.post(", "googleapiclient",
                        "place_order(", "send_alert(", "put_if_absent("):
            self.assertNotIn(blocked,source)
