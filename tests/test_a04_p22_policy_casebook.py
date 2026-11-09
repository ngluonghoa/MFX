"""A04/P0.22 source policy proposal / causal casebook negative assurance."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from mfx_research.p022_policy_casebook import (
    CASEBOOK, EXPECTED_CASES, SCHEMA, VERSION, read_casebook,
    run_synthetic_case, run_truth_table, verify_casebook,
)


def load_fixture() -> dict[str, object]:
    data = json.loads(CASEBOOK.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("P022_TEST_REQUIRES_OBJECT")
    return data


def cases(data: dict[str, object]) -> list[dict[str, object]]:
    tests = data["tests"]
    assert isinstance(tests, dict)
    rows = tests["cases"]
    assert isinstance(rows, list)
    return rows


def first_requirement(data: dict[str, object]) -> dict[str, object]:
    proposals = data["proposal_parameters"]
    assert isinstance(proposals, list)
    proposal = proposals[0]
    assert isinstance(proposal, dict)
    rows = proposal["requirements"]
    assert isinstance(rows, list)
    row = rows[0]
    assert isinstance(row, dict)
    return row


class P022CasebookTests(unittest.TestCase):
    def test_genuine_code_executes_all_fourteen_outcomes(self) -> None:
        report = run_truth_table()
        self.assertEqual(report["passed_cases"], 14)
        self.assertEqual(report["research_buy_cases"], 1)
        self.assertEqual(report["research_sell_cases"], 1)
        self.assertEqual(report["no_signal_cases"], 2)
        self.assertEqual(report["denied_cases"], 10)
        self.assertFalse(report["may_publish_verified_buy_sell"])

    def test_source_review_36_of_36_still_blocked(self) -> None:
        r, digest = read_casebook()
        self.assertEqual(r["unapproved_numeric_obligations"], 36)
        self.assertEqual(r["source_rules_approved"], 0)
        self.assertEqual(r["sim_example_count"], 14)
        self.assertEqual(len(digest), 64)
        self.assertFalse(r["confirmed_signals_allowed"])
        self.assertFalse(r["release_ready"])

    def test_positive_synthetic_does_not_become_production_signal(self) -> None:
        self.assertEqual(run_synthetic_case("B2", "BASELINE")[0], "BUY")
        self.assertEqual(run_synthetic_case("S2", "BASELINE")[0], "SELL")
        self.assertEqual(run_synthetic_case("B2", "SHORT_D1")[0],
                         "NO_SIGNAL")
        self.assertEqual(run_synthetic_case("S2", "SHORT_H4")[0],
                         "NO_SIGNAL")

    def test_source_reference_forgery_denied(self) -> None:
        data = load_fixture()
        source = data["source"]
        assert isinstance(source, dict)
        source["document_id"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "source.document_id"):
            verify_casebook(data)

    def test_zero_not_false_for_approved_detectors(self) -> None:
        data = load_fixture()
        source = data["source"]
        assert isinstance(source, dict)
        source["approved_entry_detectors"] = False
        with self.assertRaisesRegex(ValueError, "approved_entry_detectors"):
            verify_casebook(data)

    def test_numeric_value_cannot_be_self_approved(self) -> None:
        data = load_fixture()
        first_requirement(data)["approved_numeric_value"] = "1"
        with self.assertRaisesRegex(ValueError, "approved_numeric_value"):
            verify_casebook(data)

    def test_fake_independent_approval_denied(self) -> None:
        data = load_fixture()
        first_requirement(data)["independent_review_evidence"] = "OWNER:APPROVED"
        with self.assertRaisesRegex(ValueError, "independent_review_evidence"):
            verify_casebook(data)

    def test_simulated_number_requires_sim_namespace(self) -> None:
        data = load_fixture()
        proposals = data["proposal_parameters"]
        assert isinstance(proposals, list)
        p = proposals[0]
        assert isinstance(p, dict)
        rows = p["requirements"]
        assert isinstance(rows, list)
        value = rows[1]
        assert isinstance(value, dict)
        value["proposed_sim_value"] = "APPROVED:1"
        with self.assertRaisesRegex(ValueError, "NON_SIM_PARAMETER_PROPOSAL"):
            verify_casebook(data)

    def test_review_status_not_self_granted(self) -> None:
        data = load_fixture()
        data["proposal_status"] = "APPROVED"
        with self.assertRaisesRegex(ValueError, "proposal_status"):
            verify_casebook(data)

    def test_real_data_and_drive_not_authorized(self) -> None:
        for flag in ("real_market_data", "drive_price_cache",
                     "confirmed_buy_sell_alerts", "broker_order_execution",
                     "release_ready"):
            with self.subTest(flag=flag):
                data = load_fixture()
                perms = data["permissions"]
                assert isinstance(perms, dict)
                perms[flag] = True
                with self.assertRaisesRegex(ValueError, flag):
                    verify_casebook(data)

    def test_fake_vendor_license_not_sufficient(self) -> None:
        data = load_fixture()
        qual = data["independent_qualifications"]
        assert isinstance(qual, dict)
        qual["vendor_license"] = "APPROVED"
        with self.assertRaisesRegex(ValueError, "qualifications.vendor_license"):
            verify_casebook(data)

    def test_unverified_bidask_remains_missing(self) -> None:
        data = load_fixture()
        qual = data["independent_qualifications"]
        assert isinstance(qual, dict)
        qual["broker_native_bidask"] = "VERIFIED"
        with self.assertRaisesRegex(ValueError, "broker_native_bidask"):
            verify_casebook(data)

    def test_truth_table_cannot_claim_unproven_buy_sell(self) -> None:
        data = load_fixture()
        cases(data)[0]["expected_action"] = "CONFIRMED_BUY"
        with self.assertRaisesRegex(ValueError, "expected_action"):
            verify_casebook(data)

    def test_missing_case_not_silent(self) -> None:
        data = load_fixture()
        cases(data).pop()
        with self.assertRaisesRegex(ValueError, "TRUTH_TABLE_INCOMPLETE"):
            verify_casebook(data)

    def test_duplicate_case_not_silent(self) -> None:
        data = load_fixture()
        cases(data)[3] = deepcopy(cases(data)[2])
        with self.assertRaisesRegex(ValueError, "case.case_id"):
            verify_casebook(data)

    def test_early_right_bar_and_future_retrieval_denied(self) -> None:
        for rid, variant, reason in (
            ("B2", "UNCONFIRMED_RIGHT", "FUTURE_PRICE_BAR"),
            ("S2", "FUTURE_RETRIEVAL", "FUTURE_KNOWN"),
        ):
            with self.subTest(variant=variant):
                action, detail = run_synthetic_case(rid, variant)
                self.assertEqual(action, "DENIED")
                self.assertIn(reason, detail)

    def test_broker_side_and_wrong_pair_not_silently_accepted(self) -> None:
        for rid, variant, reason in (
            ("B2", "MIXED_SIDE", "CROSS_TIMEFRAME_OR_SIDE"),
            ("S2", "OTHER_INSTRUMENT", "CROSS_TIMEFRAME_IDENTITY"),
        ):
            with self.subTest(variant=variant):
                action, detail = run_synthetic_case(rid, variant)
                self.assertEqual(action, "DENIED")
                self.assertIn(reason, detail)

    def test_forged_license_and_real_provider_denied(self) -> None:
        for rid, variant in (("B2", "FORGED_PROVIDER"),
                             ("S2", "FORGED_LICENSE")):
            action, detail = run_synthetic_case(rid, variant)
            self.assertEqual(action, "DENIED")
            self.assertIn("REJECT_REAL_MARKET_SOURCE", detail)

    def test_invalid_bars_and_numeric_policy_denied(self) -> None:
        for rid, variant in (
            ("B2", "OPEN_CANDLE"), ("S2", "PARTIAL_CANDLE"),
            ("B2", "FORGED_POLICY_VERSION"), ("S2", "BOOLEAN_PIVOT"),
        ):
            with self.subTest(variant=variant):
                self.assertEqual(run_synthetic_case(rid, variant)[0], "DENIED")

    def test_duplicate_json_keys_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "dupe.json"
            p.write_text('{"schema":"X","schema":"Y"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "DUPLICATE_KEY"):
                read_casebook(p)

    def test_oversized_casebook_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "oversize.json"
            p.write_bytes(b"A" * 131073)
            with self.assertRaisesRegex(ValueError, "INVALID_CASEBOOK_LENGTH"):
                read_casebook(p)

    def test_schema_and_case_count_pinned(self) -> None:
        self.assertEqual(SCHEMA, "MFX_A04_P22_SIM_POLICY_AND_CASEBOOK_V1")
        self.assertEqual(VERSION, "SIM:P022-B2-S2-REVIEW-001")
        self.assertEqual(len(EXPECTED_CASES), 14)
