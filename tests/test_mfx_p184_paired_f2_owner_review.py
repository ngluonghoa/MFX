"""P0.184 paired source-owner review: exact mirrors, NO source approvals."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from unittest import TestCase
from mfx_research.p184_paired_f2_owner_review import (
    TEMPLATE, VERSION, compile_paired_f2_owner_proposals,
    read_paired_f2_owner_template,
)
from mfx_research.source_parameter_review import REQUIREMENTS, DOCUMENT_ID

def template():
    return json.loads(TEMPLATE.read_text())

def formula_row(n=0):
    obj=template()
    r=obj["paired_rows"][n]
    r.update({
        "review_intent":"PROPOSE_FORMULA",
        "b2_formula":"test-proposal close > known-high with K",
        "s2_formula":"test-proposal close < known-low with K",
        "units":"synthetic proposal units, uncalibrated",
        "causal_asof_notes":"previously known CLOSED bar only",
        "evidence_sha256":"a"*64,
        "rationale":None,
    })
    return obj

class P184PairedOwnerReviewTests(TestCase):
    def test_01_18_blank_pairs_expand_to_zero_proposals_not_approvals(self):
        r=read_paired_f2_owner_template()
        self.assertEqual(r.version,VERSION)
        self.assertEqual(r.paired_rows,18)
        self.assertEqual(r.awaiting_input_pairs,18)
        self.assertEqual(r.expanded_p035_proposal_rows,0)
        self.assertEqual(r.p035_result.awaiting_proposal_rows,36)
        self.assertEqual(r.original_pending_numeric_rules,36)
        self.assertEqual(r.action,"NO_SIGNAL")
        self.assertFalse(r.may_publish_buy_sell)

    def test_02_all_18_exact_symmetric_b2_s2_source_anchor_pairs(self):
        doc=template()
        self.assertEqual(len(doc["paired_rows"]),18)
        self.assertEqual(doc["source"]["original_source_doc_id"],DOCUMENT_ID)
        for row,expected in zip(doc["paired_rows"],REQUIREMENTS):
            name,phase,b,s=expected
            self.assertEqual((
                row["requirement_id"],row["phase"],
                row["b2_source_paragraph_index"],
                row["s2_source_paragraph_index"]),
                (name,phase,b,s))

    def test_03_one_valid_2_sided_proposal_expands_exact_p035_rows(self):
        r=compile_paired_f2_owner_proposals(formula_row())
        self.assertEqual(r.actionable_proposal_pairs,1)
        self.assertEqual(r.expanded_p035_proposal_rows,2)
        self.assertEqual(r.p035_result.proposals_count,2)
        lines=[x for x in r.p035_result.rows if x.proposal is not None]
        self.assertEqual({x.rule_id for x in lines},{"B2","S2"})
        self.assertEqual({x.source_paragraph_index for x in lines},{29,117})
        self.assertEqual({x.proposal.formula for x in lines},{
            "test-proposal close > known-high with K",
            "test-proposal close < known-low with K",
        })
        self.assertFalse(r.p035_result.may_promote_numeric_policy)

    def test_04_18_defer_pairs_expand_to_36_awaiting_owner_decisions(self):
        x=template()
        for row in x["paired_rows"]:
            row.update({"review_intent":"SUGGEST_DEFER",
                        "rationale":"unverified data and owner values"})
        report=compile_paired_f2_owner_proposals(x)
        self.assertEqual(report.actionable_proposal_pairs,18)
        self.assertEqual(report.expanded_p035_proposal_rows,36)
        self.assertEqual(report.p035_result.suggest_defer,36)
        self.assertEqual(report.original_numeric_rules_approved,0)
        self.assertEqual(report.original_pending_numeric_rules,36)

    def test_05_reject_suggestion_still_no_signal(self):
        x=template()
        x["paired_rows"][0].update({
            "review_intent":"SUGGEST_REJECT",
            "rationale":"owner must independently review",
        })
        r=compile_paired_f2_owner_proposals(x)
        self.assertEqual(r.p035_result.suggest_reject,2)
        self.assertFalse(r.may_trade)
        self.assertEqual(r.broker_orders,0)

    def test_06_partial_one_side_formula_is_invalid(self):
        x=formula_row()
        x["paired_rows"][0]["s2_formula"]=None
        with self.assertRaisesRegex(ValueError,"BOTH_SIDES"):
            compile_paired_f2_owner_proposals(x)

    def test_07_blank_with_forged_evidence_or_formula_is_invalid(self):
        x=template()
        x["paired_rows"][1]["evidence_sha256"]="a"*64
        with self.assertRaisesRegex(ValueError,"PARTIAL_PAIR"):
            compile_paired_f2_owner_proposals(x)

    def test_08_prohibit_SIM_strategy_numeric_laundering(self):
        x=formula_row()
        x["paired_rows"][0]["b2_formula"]="SIM:ATR1"
        with self.assertRaisesRegex(ValueError,"NO_SIM_VALUES"):
            compile_paired_f2_owner_proposals(x)

    def test_09_wrong_source_anchor_phase_order_and_unknown_fields_denied(self):
        for corruption in (
            ("phase","R_F"),("b2_source_paragraph_index",999),
            ("s2_source_paragraph_index",29),
            ("requirement_id","FAKE"),
            ("mirror_equivalence_status","OWNER_APPROVED"),
        ):
            x=template()
            x["paired_rows"][0][corruption[0]]=corruption[1]
            with self.subTest(corruption=corruption),self.assertRaises(ValueError):
                compile_paired_f2_owner_proposals(x)
        x=template()
        x["paired_rows"][0]["approved"]=True
        with self.assertRaises(ValueError):
            compile_paired_f2_owner_proposals(x)
        x=template()
        x["paired_rows"].reverse()
        with self.assertRaises(ValueError):
            compile_paired_f2_owner_proposals(x)

    def test_10_source_dossier_replaced_or_fake_authentication_denied(self):
        for field in ("original_forex_commit","source_p021_git_blob",
                      "decision_p034_git_blob","original_source_doc_id"):
            x=template()
            x["source"][field]="b"*40
            with self.subTest(field=field),self.assertRaises(ValueError):
                compile_paired_f2_owner_proposals(x)

    def test_11_p035_filters_unsafe_formula_credentials_and_bad_sha(self):
        for field,value in (
            ("b2_formula","https://example.test/data"),
            ("s2_formula","api_key"),
            ("evidence_sha256","0"*40),
            ("units","bad\nnewline"),
        ):
            x=formula_row()
            x["paired_rows"][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                compile_paired_f2_owner_proposals(x)

    def test_12_authority_no_signal_and_immutable_receipt(self):
        r=compile_paired_f2_owner_proposals(formula_row())
        s=r.safe_summary()
        self.assertEqual(s["action"],"NO_SIGNAL")
        self.assertEqual(s["original_source_decisions_pending"],36)
        self.assertFalse(s["independently_authenticated_owner_rules"])
        self.assertFalse(s["may_publish_buy_sell"])
        self.assertFalse(s["mirrored_formula_authenticated"])
        self.assertEqual(s["provider_calls"],0)
        self.assertEqual(s["drive_writes"],0)
        self.assertEqual(s["broker_orders"],0)
        with self.assertRaises(FrozenInstanceError):
            r.may_trade=True

    def test_13_deterministic_review_digest(self):
        x=formula_row()
        self.assertEqual(
            compile_paired_f2_owner_proposals(x).expanded_p035_digest,
            compile_paired_f2_owner_proposals(deepcopy(x)).expanded_p035_digest,
        )

    def test_14_no_actual_market_source_or_workflow_side_effect(self):
        src=Path("mfx_research/p184_paired_f2_owner_review.py").read_text()
        for banned in ("requests.get(", "requests.post(", "time_series(",
                       "googleapiclient", "broker.submit", "GITHUB_EVENT_NAME",
                       "MFX_REAL_CACHE_ENABLED", "GenUI"):
            self.assertNotIn(banned,src)
        self.assertNotIn("approved_value",src)
        spec=Path("docs/MFX_P184_18_PAIRED_F2_OWNER_REVIEW.md").read_text()
        self.assertIn("0/36",spec)
        self.assertIn("22/11/2026",spec)

    def test_15_missing_duplicate_or_oversized_template_rejected(self):
        x=template()
        x["paired_rows"].pop()
        with self.assertRaisesRegex(ValueError,"EXACT_18"):
            compile_paired_f2_owner_proposals(x)
        x=template()
        x["paired_rows"].append(deepcopy(x["paired_rows"][0]))
        with self.assertRaisesRegex(ValueError,"EXACT_18"):
            compile_paired_f2_owner_proposals(x)
        path=Path("docs/MFX_P184_18_PAIRED_F2_OWNER_PROPOSAL_TEMPLATE.json")
        self.assertLess(path.stat().st_size,65536)
