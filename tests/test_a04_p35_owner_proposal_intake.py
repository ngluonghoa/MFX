"""P0.35: 24 preregistered source-owner proposal intake safety tests.

No self-approved original Forex numeric rules or broker integration.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from forex_trading.catalog import ZONES, validate_catalog
from mfx_research.p030_approved_nonentry_design import read_22_zone_design_manifest
from mfx_research.p034_sim_adversarial_review import (
    DOSSIER, DOSSIER_BLOB_SHA, P021, P021_BLOB_SHA,
    _blob_sha, verify_owner_decision_dossier,
)
from mfx_research.p035_owner_proposal_intake import (
    SCHEMA, VERSION, MODE, TEMPLATE,
    verify_public_owner_proposals, read_public_owner_proposal_template,
)


def template() -> dict:
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def proposal(rule: str = "B2", requirement: str = "h1_zone_lookback",
             intent: str = "PROPOSE_FORMULA") -> dict:
    owner = verify_owner_decision_dossier()
    match = next((r for r in owner.rows if r[0] == rule and r[1] == requirement),
                 None)
    if match is None:
        raise ValueError("TEST_REQUIRES_SOURCE_ROW")
    _, _, phase, index = match
    has_formula = intent == "PROPOSE_FORMULA"
    return {
        "rule_id": rule,
        "requirement_id": requirement,
        "phase": phase,
        "source_paragraph_index": index,
        "review_intent": intent,
        "formula": "N = count of known CLOSED H1 bars" if has_formula else None,
        "units": "bars" if has_formula else None,
        "causal_asof_notes": (
            "Use only candles known before decision UTC" if has_formula else None
        ),
        "evidence_sha256": "a" * 64 if has_formula else None,
        "rationale": None if has_formula else "Needs external owner review",
    }


class P035OwnerProposalIntakeTests(unittest.TestCase):
    def test_01_frozen_18_original_and_approved_22_design(self) -> None:
        validate_catalog(ZONES)
        self.assertEqual(len(ZONES), 18)
        m = read_22_zone_design_manifest()
        self.assertEqual(len(m.zones), 22)
        self.assertEqual((len(m.entry_long_labels), len(m.entry_short_labels),
                          len(m.watch_labels),
                          len(m.exit_long_warning_labels) +
                          len(m.exit_short_warning_labels)), (8, 8, 2, 4))

    def test_02_pinned_source_blobs_readback(self) -> None:
        self.assertEqual(_blob_sha(P021.read_bytes()), P021_BLOB_SHA)
        self.assertEqual(_blob_sha(DOSSIER.read_bytes()), DOSSIER_BLOB_SHA)
        r = read_public_owner_proposal_template()
        self.assertEqual(r.source_p021_git_blob, P021_BLOB_SHA)
        self.assertEqual(r.source_p034_git_blob, DOSSIER_BLOB_SHA)

    def test_03_public_template_zero_proposals_and_36_pending(self) -> None:
        r = read_public_owner_proposal_template()
        self.assertEqual(r.proposals_count, 0)
        self.assertEqual(r.awaiting_proposal_rows, 36)
        self.assertEqual(r.source_owner_decisions_still_pending, 36)
        self.assertEqual(len(r.rows), 36)
        self.assertTrue(all(x.proposal is None for x in r.rows))

    def test_04_original_source_anchor_ids_exact(self) -> None:
        owner = verify_owner_decision_dossier()
        report = read_public_owner_proposal_template()
        self.assertEqual(
            tuple((r.rule_id, r.requirement_id, r.phase,
                   r.source_paragraph_index) for r in report.rows),
            owner.rows,
        )
        self.assertEqual(len(report.rows[:18]), 18)
        self.assertEqual([r.rule_id for r in report.rows[:18]], ["B2"] * 18)
        self.assertEqual([r.rule_id for r in report.rows[18:]], ["S2"] * 18)

    def test_05_sim_examples_stay_14_and_approval_zero(self) -> None:
        r = read_public_owner_proposal_template()
        self.assertEqual(r.research_sim_examples_not_approved, 14)
        self.assertEqual(r.source_numeric_rules_approved, 0)
        self.assertEqual(r.authenticated_owner_signoffs, 0)

    def test_06_partial_b2_formula_proposal_never_approval(self) -> None:
        data = template()
        data["proposal_rows"] = [proposal()]
        r = verify_public_owner_proposals(data)
        self.assertEqual(r.proposals_count, 1)
        self.assertEqual(r.formula_proposals, 1)
        self.assertEqual(r.awaiting_proposal_rows, 35)
        self.assertEqual(r.source_numeric_rules_approved, 0)
        self.assertEqual(next(x for x in r.rows if x.proposal is not None)
                         .intake_status, "FORMULA_FOR_EXTERNAL_OWNER_REVIEW")

    def test_07_partial_s2_draft_remains_unverified(self) -> None:
        data = template()
        data["proposal_rows"] = [proposal("S2", "h1_zone_lookback")]
        r = verify_public_owner_proposals(data)
        self.assertEqual(r.formula_proposals, 1)
        self.assertTrue(all(not x.independently_authenticated_source_approval
                            for x in r.rows))

    def test_08_defer_suggestion_never_owner_signoff(self) -> None:
        data = template()
        data["proposal_rows"] = [
            proposal("B2", "session_dst_rollover_news_gate",
                     "SUGGEST_DEFER"),
        ]
        r = verify_public_owner_proposals(data)
        self.assertEqual(r.suggest_defer, 1)
        self.assertIn("DEFER_SUGGESTED_UNVERIFIED",
                      [x.intake_status for x in r.rows])
        self.assertEqual(r.source_owner_decisions_still_pending, 36)

    def test_09_reject_suggestion_never_owner_signoff(self) -> None:
        data = template()
        data["proposal_rows"] = [
            proposal("S2", "historical_walkforward_oos_qualification",
                     "SUGGEST_REJECT"),
        ]
        r = verify_public_owner_proposals(data)
        self.assertEqual(r.suggest_reject, 1)
        self.assertEqual(r.source_numeric_rules_approved, 0)

    def test_10_all_36_proposals_still_zero_authenticated(self) -> None:
        data = template()
        owner = verify_owner_decision_dossier()
        data["proposal_rows"] = [
            proposal(rule, requirement)
            for rule, requirement, _, _ in owner.rows
        ]
        r = verify_public_owner_proposals(data)
        self.assertEqual((len(r.rows), r.proposals_count,
                          r.awaiting_proposal_rows), (36, 36, 0))
        self.assertEqual((r.source_numeric_rules_approved,
                          r.authenticated_owner_signoffs,
                          r.confirmed_user_buy_sell_alerts), (0, 0, 0))

    def test_11_digest_order_independent_for_same_proposals(self) -> None:
        a = template()
        x = proposal("B2", "h1_zone_lookback")
        y = proposal("S2", "h1_zone_lookback")
        a["proposal_rows"] = [x, y]
        b = deepcopy(a)
        b["proposal_rows"].reverse()
        r, rr = verify_public_owner_proposals(a), verify_public_owner_proposals(b)
        self.assertEqual(r, rr)
        self.assertRegex(r.bundle_sha256, "^[a-f0-9]{64}$")

    def test_12_duplicate_source_requirement_rejected(self) -> None:
        data = template()
        data["proposal_rows"] = [proposal(), proposal()]
        with self.assertRaisesRegex(ValueError, "P035_DUPLICATE_SOURCE_ROW"):
            verify_public_owner_proposals(data)

    def test_13_unknown_rule_or_requirement_rejected(self) -> None:
        for key, bad in (("rule_id", "FX-B9"),
                         ("requirement_id", "nonexistent_rule")):
            data = template()
            row = proposal()
            row[key] = bad
            data["proposal_rows"] = [row]
            with self.subTest(key=key), self.assertRaisesRegex(
                ValueError, "P035_UNKNOWN_SOURCE_REQUIREMENT"
            ):
                verify_public_owner_proposals(data)

    def test_14_wrong_source_paragraph_rejected(self) -> None:
        data = template()
        row = proposal()
        row["source_paragraph_index"] += 1
        data["proposal_rows"] = [row]
        with self.assertRaisesRegex(ValueError, "P035_SOURCE_PARAGRAPH_ANCHOR"):
            verify_public_owner_proposals(data)

    def test_15_wrong_phase_rejected(self) -> None:
        data = template()
        row = proposal()
        row["phase"] = "QA"
        data["proposal_rows"] = [row]
        with self.assertRaisesRegex(ValueError, "P035_SOURCE_PHASE"):
            verify_public_owner_proposals(data)

    def test_16_stale_source_blob_denied(self) -> None:
        data = template()
        for key in ("source_p021_git_blob", "decision_p034_git_blob",
                    "original_forex_commit"):
            other = deepcopy(data)
            other["source"][key] = "0" * 40
            with self.subTest(key=key), self.assertRaisesRegex(
                ValueError, "P035_SEALED_PROVENANCE"
            ):
                verify_public_owner_proposals(other)

    def test_17_forged_approved_status_denied(self) -> None:
        data = template()
        row = proposal()
        row["review_intent"] = "APPROVED"
        data["proposal_rows"] = [row]
        with self.assertRaisesRegex(ValueError, "P035_NO_SELF_APPROVED"):
            verify_public_owner_proposals(data)

    def test_18_real_data_broker_or_release_fields_denied(self) -> None:
        for key in ("may_trade", "may_publish_confirmed", "real_data_allowed",
                    "broker_orders", "release_ready"):
            data = template()
            data[key] = True
            with self.subTest(key=key), self.assertRaisesRegex(
                ValueError, "P035_EXACT_PUBLIC_SCHEMA"
            ):
                verify_public_owner_proposals(data)

    def test_19_secret_url_or_email_public_field_denied(self) -> None:
        for text in ("password not public", "api_key withheld",
                     "https://" + "example.test/private",
                     "owner" + "@" + "example.test",
                     "Bearer not public"):
            data = template()
            row = proposal()
            row["formula"] = text
            data["proposal_rows"] = [row]
            with self.subTest(text=text), self.assertRaisesRegex(
                ValueError, "P035_PUBLIC_REVIEW_FIELD_UNSAFE"
            ):
                verify_public_owner_proposals(data)

    def test_20_oversize_controls_or_blank_text_denied(self) -> None:
        for formula in ("x" * 513, "line1\nline2", ""):
            data = template()
            row = proposal()
            row["formula"] = formula
            data["proposal_rows"] = [row]
            with self.subTest(formula=formula[:8]), self.assertRaisesRegex(
                ValueError, "P035_PUBLIC_REVIEW_FIELD_UNSAFE|P035_REQUIRED"
            ):
                verify_public_owner_proposals(data)

    def test_21_wrong_evidence_sha256_denied(self) -> None:
        for digest in ("a" * 63, "Z" * 64, None):
            data = template()
            row = proposal()
            row["evidence_sha256"] = digest
            data["proposal_rows"] = [row]
            with self.subTest(digest=digest), self.assertRaisesRegex(
                ValueError, "P035_UNVERIFIED_OR_MISSING_EVIDENCE_SHA256"
            ):
                verify_public_owner_proposals(data)

    def test_22_extra_key_and_malformed_json_denied(self) -> None:
        data = template()
        row = proposal()
        row["approved"] = True
        data["proposal_rows"] = [row]
        with self.assertRaisesRegex(ValueError, "P035_EXACT_PUBLIC_SCHEMA"):
            verify_public_owner_proposals(data)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.json"
            path.write_text('{"schema":"a","schema":"b"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "P035_DUPLICATE_JSON_KEY"):
                read_public_owner_proposal_template(path)
            path.write_bytes(b" " * 65537)
            with self.assertRaisesRegex(ValueError, "P035_BOUNDED_TEMPLATE"):
                read_public_owner_proposal_template(path)

    def test_23_even_three_proposals_cannot_trade_or_alert(self) -> None:
        data = template()
        data["proposal_rows"] = [
            proposal("B2", "h1_zone_lookback"),
            proposal("S2", "h1_zone_lookback"),
            proposal("B2", "session_dst_rollover_news_gate", "SUGGEST_DEFER"),
        ]
        r = verify_public_owner_proposals(data)
        self.assertEqual((r.proposals_count, r.formula_proposals,
                          r.suggest_defer), (3, 2, 1))
        self.assertEqual(r.action, "NO_SIGNAL")
        self.assertFalse(r.may_promote_numeric_policy)
        self.assertFalse(r.may_publish_confirmed_alerts)
        self.assertFalse(r.release_ready)
        self.assertEqual((r.confirmed_user_buy_sell_alerts,
                          r.real_market_provider_calls,
                          r.real_drive_quote_cache_writes,
                          r.broker_orders), (0, 0, 0, 0))

    def test_24_public_template_version_and_determinism(self) -> None:
        self.assertEqual(SCHEMA, "MFX_A04_P35_OWNER_EVIDENCE_PROPOSAL_INTAKE_V1")
        self.assertEqual(VERSION, "MFX:P035-PUBLIC_SAFE_REVIEW_PROPOSAL-001")
        self.assertEqual(MODE, "PUBLIC_SAFE_PROPOSALS_NOT_APPROVALS")
        self.assertEqual(read_public_owner_proposal_template(),
                         verify_public_owner_proposals(template()))
        with self.assertRaisesRegex(TypeError, "P035_TYPED_TEMPLATE_PATH"):
            read_public_owner_proposal_template(None)  # type: ignore[arg-type]
        invalid = template()
        invalid["proposal_rows"] = "not-a-list"
        with self.assertRaisesRegex(ValueError, "P035_BOUNDED_PUBLIC_PROPOSALS"):
            verify_public_owner_proposals(invalid)


if __name__ == "__main__":
    unittest.main()
