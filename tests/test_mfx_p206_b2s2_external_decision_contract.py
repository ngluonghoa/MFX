"""Hermetic P206 source-owner remaining-seven design contract (never auth)."""
from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

from mfx_research.p188_b2s2_numeric_owner_review_candidates import (
    EXTERNAL_UNRESOLVED, compile_p188_review_draft,
)
from mfx_research.p206_b2s2_external_decision_contract import (
    _CONTRACTS, STATE, VERSION, compile_p206_remaining_decisions,
)
from mfx_research.source_parameter_review import REQUIREMENTS


class TestP206RemainingSeven(unittest.TestCase):
    def setUp(self) -> None:
        self.report = compile_p206_remaining_decisions()

    def test_full_original_18_paired_review_coverage(self) -> None:
        self.assertEqual(self.report.complete_source_review_questions, 18)
        self.assertEqual(self.report.existing_experimental_paired_drafts, 11)
        self.assertEqual(self.report.remaining_conditional_paired_questions, 7)
        self.assertEqual(len(self.report.external), 7)

    def test_precise_source_requirement_ids(self) -> None:
        self.assertEqual(
            {x.requirement_id for x in self.report.external},
            set(EXTERNAL_UNRESOLVED),
        )

    def test_source_phase_and_paragraph_anchors(self) -> None:
        source = {a: (b, c, d) for a, b, c, d in REQUIREMENTS}
        for q in self.report.external:
            self.assertEqual(
                (q.phase, q.b2_source_paragraph_index,
                 q.s2_source_paragraph_index), source[q.requirement_id],
            )

    def test_both_sides_expressed_no_source_numbers_invented(self) -> None:
        orig = {r.requirement_id: r for r in compile_p188_review_draft().rows}
        for q in self.report.external:
            self.assertTrue(q.b2_conditional_design.startswith("B2:"))
            self.assertTrue(q.s2_conditional_design.startswith("S2:"))
            self.assertIsNone(orig[q.requirement_id].b2_formula)
            self.assertIsNone(orig[q.requirement_id].s2_formula)

    def test_no_owner_numeric_signoff_or_trade(self) -> None:
        r = self.report
        self.assertEqual((r.original_source_numeric_approvals,
                          r.original_source_numeric_pending), (0, 36))
        self.assertEqual(r.action, "NO_SIGNAL")
        self.assertFalse(r.may_publish_buy_sell or r.may_trade)
        self.assertFalse(r.owner_authentication_verified)
        self.assertFalse(r.account_license_verified)
        self.assertFalse(r.publisher_first_known_verified)
        self.assertFalse(r.bidask_net_r_verified)
        self.assertFalse(r.historical_oos_verified)

    def test_no_side_effect_permissions(self) -> None:
        self.assertEqual(
            (self.report.provider_calls, self.report.drive_writes,
             self.report.broker_orders), (0, 0, 0),
        )

    def test_all_seven_non_numeric_and_evidence_missing(self) -> None:
        for row in self.report.external:
            self.assertEqual(row.state, STATE)
            self.assertTrue(row.owner_values_missing)
            self.assertTrue(row.independent_evidence_missing)
            self.assertFalse(row.owner_approved)
            self.assertFalse(row.original_forex_numeric_parity)
            self.assertFalse(row.may_publish_buy_sell)

    def test_repeat_determinism_and_64_character_digest(self) -> None:
        other = compile_p206_remaining_decisions()
        self.assertEqual(self.report, other)
        self.assertEqual(len(self.report.review_digest_sha256), 64)

    def test_public_summary_is_not_a_source_signature(self) -> None:
        s = self.report.public_summary()
        self.assertEqual(s["action"], "NO_SIGNAL")
        self.assertEqual(s["approved_original_source_numeric_decisions"], 0)
        self.assertFalse(s["may_publish_buy_sell"])
        self.assertNotIn("review_digest_sha256", s)
        self.assertNotIn("b2_conditional_design", s)

    def test_missing_source_gate_rejected(self) -> None:
        with self.assertRaises(ValueError):
            compile_p206_remaining_decisions(expected_contracts=_CONTRACTS[:-1])

    def test_duplicate_source_gate_rejected(self) -> None:
        with self.assertRaises(ValueError):
            compile_p206_remaining_decisions(
                expected_contracts=_CONTRACTS[:-1] + (_CONTRACTS[0],),
            )

    def test_forged_owner_numeric_value_rejected(self) -> None:
        fake = tuple(
            replace(q, owner_approved=True) if q.requirement_id == "event_expiry_and_idempotence" else q
            for q in self.report.external
        )
        self.assertNotEqual(fake, self.report.external)
        with self.assertRaises(ValueError):
            compile_p206_remaining_decisions(expected_contracts=(
                _CONTRACTS[:-1] + ((
                    _CONTRACTS[-1][0], "B2: approved entry", "S2: approved entry",
                    ("signed",), ("fake",),
                ),)
            ))

    def test_no_external_data_network_or_drive_dependency(self) -> None:
        self.assertEqual(self.report.provider_calls, 0)
        self.assertEqual(self.report.drive_writes, 0)
        self.assertEqual(self.report.broker_orders, 0)

    def test_no_semantic_b2_s2_side_confusion_in_risk(self) -> None:
        risk = next(q for q in self.report.external
                    if q.requirement_id == "structural_sl_tp_net_r_gate")
        self.assertIn("ASK entry/BID exit", risk.b2_conditional_design)
        self.assertIn("BID entry/ASK exit", risk.s2_conditional_design)

    def test_original_source_mirror_params_still_unsigned(self) -> None:
        p188 = compile_p188_review_draft()
        self.assertEqual(p188.original_owner_numeric_approvals, 0)
        self.assertEqual(p188.pending_original_numeric_decisions, 36)

    def test_version_declares_non_authorizing_scope(self) -> None:
        self.assertTrue(VERSION.startswith("MFX_P206_"))
        self.assertEqual(self.report.original_source_numeric_approvals, 0)


if __name__ == "__main__":
    unittest.main()
