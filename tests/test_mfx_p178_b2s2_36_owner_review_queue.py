"""P0.178: 36 source-owner decisions linked to sealed B2/S2 private gaps.

Pure offline synthetic fixtures, NOT owner approval or true vendor source data.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from unittest import TestCase

from mfx_research.b2_s2_source_computation_crosswalk import (
    reconcile_b2s2_source_to_computation,
)
from mfx_research.p178_b2s2_36_owner_review_queue import (
    VERSION, EXTERNAL, PRIVATE_GAP, PRIVATE_ONLY, RULES,
    compile_source_owner_36_review_queue,
)
from mfx_research.source_parameter_review import REQUIREMENTS, DOCUMENT_ID
from test_mfx_v1_manual_signal_only_drive_output import mocked
from tools.run_mfx_v1_manual_drive_six_tf import safe_summary


def evidence():
    r=mocked()
    return r, reconcile_b2s2_source_to_computation(r),r.private_b2s2_source_readiness


def compile_queue(*, crosswalk=None, readiness=None, sha=None):
    r,s,g=evidence()
    return compile_source_owner_36_review_queue(
        s if crosswalk is None else crosswalk,
        g if readiness is None else readiness,
        same_private_source_sha256=(r.private_multibar.private_input_digest_sha256
                                   if sha is None else sha),
    )


def find(queue,rule,requirement):
    return next(x for x in queue.rows if
                x.rule_id==rule and x.requirement_id==requirement)


class MfxP178SourceOwner36QueueTests(TestCase):
    def test_01_exactly_18_source_requirements_by_two_sides(self):
        q=compile_queue()
        self.assertEqual(q.version,VERSION)
        self.assertEqual(len(q.rows),36)
        self.assertEqual(tuple(x.rule_id for x in q.rows),
                         ("B2",)*18+("S2",)*18)
        self.assertEqual(q.source_locked_doc_id,DOCUMENT_ID)

    def test_02_source_paragraphs_and_phases_match_original_locked_docs(self):
        q=compile_queue()
        expected=tuple(
            (rid,n,phase,b if rid=="B2" else s)
            for rid in RULES for n,phase,b,s in REQUIREMENTS
        )
        self.assertEqual(tuple(
            (x.rule_id,x.requirement_id,x.phase,
             x.original_source_paragraph_index)
            for x in q.rows),expected)

    def test_03_all_36_owner_numeric_values_are_always_pending(self):
        q=compile_queue()
        self.assertEqual(q.remaining_owner_decisions,36)
        self.assertEqual(q.source_numeric_approvals,0)
        self.assertTrue(all(
            x.source_numeric_status=="ORIGINAL_SOURCE_OWNER_DECISION_PENDING"
            and not x.authenticated_owner_numeric_evidence
            and not x.original_forex_numeric_rule_approved
            and not x.is_executable_signal
            for x in q.rows))

    def test_04_H4_and_D1_source_structural_constraints_are_not_hidden(self):
        q=compile_queue()
        for side in RULES:
            for key in ("causal_d1_h4_trend",
                        "confirmed_pivot_left_bars",
                        "confirmed_pivot_right_bars",
                        "structural_hl_lh_invalidation"):
                x=find(q,side,key)
                self.assertEqual(x.private_input_status,PRIVATE_GAP)
                self.assertIn(
                    "D1_TWO_RIGHT_CONFIRMED_HIGH_LOWS_UNQUALIFIED",
                    x.technical_precondition_gaps)

    def test_05_H1_TR3_short_history_both_sides_needs_more_candles(self):
        q=compile_queue()
        for side in RULES:
            x=find(q,side,"h1_true_range_atr_period")
            self.assertEqual(x.private_input_status,PRIVATE_GAP)
            self.assertIn("H1_DRAFT_TR_PERIOD_NOT_CLOSED",
                          x.technical_precondition_gaps)

    def test_06_M15_right_confirmed_level_vs_closed_break_not_same(self):
        q=compile_queue()
        for side in RULES:
            a=find(q,side,"m15_early_reversal_structure")
            b=find(q,side,"known_micro_break_confirm_rule")
            self.assertEqual(a.private_input_status,PRIVATE_GAP)
            self.assertEqual(b.private_input_status,PRIVATE_GAP)
            self.assertEqual(
                a.technical_precondition_gaps,
                ("M15_PRETRIGGER_CONFIRMED_LEVEL_MISSING",))
            self.assertIn(
                "M15_CLOSED_MICROBREAK_NOT_OBSERVED",
                b.technical_precondition_gaps)

    def test_07_external_policy_licensing_and_OOS_require_other_evidence(self):
        q=compile_queue()
        for side in RULES:
            for key in ("bid_ask_spread_and_cost_gate",
                        "session_dst_rollover_news_gate",
                        "structural_sl_tp_net_r_gate",
                        "event_expiry_and_idempotence",
                        "licensed_source_first_known_revision",
                        "historical_walkforward_oos_qualification"):
                x=find(q,side,key)
                self.assertEqual(x.private_input_status,EXTERNAL)
                self.assertEqual(x.technical_precondition_gaps,())

    def test_08_missing_technical_input_can_change_without_owner_approval(self):
        r,s,g=evidence()
        gate0=g.gates[0]
        minus=replace(gate0,missing_preconditions=tuple(
            z for z in gate0.missing_preconditions
            if z!="H1_DRAFT_TR_PERIOD_NOT_CLOSED"))
        updated=replace(g,gates=(minus,g.gates[1]))
        q=compile_queue(crosswalk=s,readiness=updated)
        self.assertEqual(find(q,"B2","h1_true_range_atr_period")
                         .private_input_status,PRIVATE_ONLY)
        self.assertEqual(find(q,"S2","h1_true_range_atr_period")
                         .private_input_status,PRIVATE_GAP)
        self.assertEqual(q.source_numeric_approvals,0)
        self.assertEqual(q.public_action,"NO_SIGNAL")

    def test_09_wrong_source_locked_paragraph_denied(self):
        _,s,g=evidence()
        rows=list(s.rows)
        rows[1]=replace(rows[1],original_source_paragraph_index=999)
        with self.assertRaisesRegex(ValueError,
                                    "WRONG_SOURCE_DOC_PARAGRAPH"):
            compile_queue(crosswalk=replace(s,rows=tuple(rows)))

    def test_10_forged_one_owner_numerical_approval_denied(self):
        _,s,g=evidence()
        rows=list(s.rows)
        rows[0]=replace(rows[0],
                        original_source_numeric_rule_approved=True)
        with self.assertRaisesRegex(ValueError,
                                    "FORGED_SOURCE_APPROVAL"):
            compile_queue(crosswalk=replace(s,rows=tuple(rows)))

    def test_11_one_missing_source_row_denied(self):
        _,s,g=evidence()
        with self.assertRaisesRegex(ValueError,"REQUIREMENT_COVERAGE"):
            compile_queue(crosswalk=replace(s,rows=s.rows[:-1]))

    def test_12_duplicate_swapped_source_row_denied(self):
        _,s,g=evidence()
        rows=list(s.rows)
        rows[1]=rows[0]
        with self.assertRaisesRegex(ValueError,"WRONG_SOURCE_DOC_PARAGRAPH"):
            compile_queue(crosswalk=replace(s,rows=tuple(rows)))

    def test_13_private_source_sha_and_asof_mismatch_denied(self):
        _,s,g=evidence()
        with self.assertRaisesRegex(ValueError,"FALSE_SOURCE_OR_LIVE"):
            compile_queue(sha="b"*64)
        with self.assertRaisesRegex(ValueError,"FALSE_SOURCE_OR_LIVE"):
            compile_queue(readiness=replace(
                g,asof_utc="2026-11-01T00:00:00+00:00"))

    def test_14_duplicate_B2_or_S2_gate_denied(self):
        _,s,g=evidence()
        wrong=replace(g,gates=(g.gates[0],g.gates[0]))
        with self.assertRaisesRegex(ValueError,"REQUIREMENT_COVERAGE"):
            compile_queue(readiness=wrong)

    def test_15_forged_review_flags_or_bidask_denied(self):
        _,s,g=evidence()
        with self.assertRaisesRegex(ValueError,"FALSE_SOURCE_OR_LIVE"):
            compile_queue(crosswalk=replace(
                s,original_source_numeric_decisions_pending=35))
        with self.assertRaisesRegex(ValueError,"FALSE_SOURCE_OR_LIVE"):
            compile_queue(readiness=replace(
                g,bidask_net_rr_qualified=True))

    def test_16_safe_summary_does_not_leak_price_derived_state(self):
        q=compile_queue()
        encoded=json.dumps(q.as_safe_summary(),sort_keys=True)
        for forbidden in (
            "technical_precondition_gaps",
            "M15_CLOSED_MICROBREAK_NOT_OBSERVED",
            "h4_confirmed_high_pivots","private_input_status",
            "experimental_cross","candidate_mid_price","1.100",
            "private_input_digest_sha256",
        ):
            self.assertNotIn(forbidden,encoded)
        self.assertEqual(q.as_safe_summary()["action"],"NO_SIGNAL")

    def test_17_source_review_phases_add_exactly_18_for_each(self):
        q=compile_queue()
        for p in q.as_safe_summary()["by_rule"]:
            self.assertEqual(sum(p["source_requirement_phases"].values()),18)
            self.assertEqual(p["source_numeric_decisions_pending"],18)

    def test_18_workflow_summary_includes_36_owner_pending_checkpoint(self):
        summary=safe_summary(mocked(),drive_gets=3)
        x=summary["b2_s2_original_source_owner_review"]
        self.assertEqual(x["remaining_owner_decisions"],36)
        self.assertEqual(x["original_source_numeric_approvals"],0)
        self.assertEqual([z["rule_id"] for z in x["by_rule"]],
                         ["B2","S2"])
        self.assertFalse(x["source_numeric_owner_evidence_approved"])
        self.assertEqual(summary["action"],"NO_SIGNAL")
        self.assertEqual(summary["broker_orders"],0)

    def test_19_no_external_source_or_drive_changes(self):
        from pathlib import Path
        source=Path(
            "mfx_research/p178_b2s2_36_owner_review_queue.py"
        ).read_text()
        for forbidden in ("requests.get(","requests.post(",
                          "googleapiclient","broker.submit(",
                          "workflow_dispatch","TWELVE_DATA_API_KEY"):
            self.assertNotIn(forbidden,source)

    def test_20_frozen_no_live_source_permissions(self):
        q=compile_queue()
        self.assertEqual((q.public_action,q.stage),
                         ("NO_SIGNAL","UNVERIFIED"))
        self.assertFalse(q.may_trade)
        self.assertFalse(q.may_publish_buy_sell)
        self.assertEqual((q.provider_requests,q.drive_reads_added,
                          q.drive_writes,q.broker_orders),(0,0,0,0))
        with self.assertRaises(FrozenInstanceError):
            q.source_numeric_approvals=36

    def test_21_deterministic_complete_owner_queue(self):
        a,b=compile_queue(),compile_queue()
        self.assertEqual(a,b)
        self.assertEqual(len({(r.rule_id,r.requirement_id)
                              for r in a.rows}),36)

    def test_22_source_phase_and_paragraph_public_not_secret_price(self):
        q=compile_queue()
        self.assertIn("INVALIDATION",tuple(x.phase for x in q.rows))
        self.assertEqual(q.source_locked_doc_id,DOCUMENT_ID)
        self.assertTrue(len(q.source_register_git_blob)>=32)
        self.assertTrue(len(q.source_dossier_git_blob)>=32)
        self.assertFalse(q.owner_evidence_authenticated)
