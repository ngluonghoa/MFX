"""Design-only P0.10; negative authority and provenance-tampering tests."""
from __future__ import annotations

from copy import deepcopy
import unittest

from tools.a04_p10_mapper_matrix import (
    CROSS_GATES, FALSE_AUTHORITIES, ROLE_REQUIREMENTS,
    expected_design_matrix, read_matrix, verify_matrix,
)


class A04P10MapperDesignGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.expected = expected_design_matrix()

    def test_pinned_design_matches_actual_prior_ast(self) -> None:
        receipt = verify_matrix(read_matrix())
        self.assertEqual(receipt["seven_source_rows"], 7)
        self.assertEqual(receipt["direct_compatible"], 0)
        self.assertEqual(receipt["runtime_adapters"], 0)
        self.assertIs(receipt["release_authorized"], False)

    def test_exact_source_and_typed_port_prerequisites(self) -> None:
        observed = self.expected["p09_measured_source_evidence"]
        self.assertEqual(observed["source_reference_count"], 7)
        self.assertEqual(observed["direct_callable_port_compatible_count"], 0)
        self.assertEqual(len(self.expected["source_candidate_rows"]), 7)
        for row in self.expected["source_candidate_rows"]:
            self.assertTrue(row["missing_input_fields"])
            self.assertTrue(row["unproven_output_fields"])
            self.assertFalse(row["source_callable_port_compatible"])
            self.assertEqual(row["mapper_review_state"],
                             "MAPPING_NOT_SPECIFIED_OR_AUTHORIZED")

    def test_four_roles_and_tp_policy_zero_callable(self) -> None:
        roles = self.expected["role_prerequisites"]
        self.assertEqual([r["role"] for r in roles],
                         ["PROVIDER", "INDICATOR", "DETECTOR", "TP_POLICY"])
        self.assertEqual([r["expected_reference_count"] for r in roles],
                         [3, 2, 2, 0])
        self.assertEqual(len(ROLE_REQUIREMENTS), 4)
        self.assertFalse(any(r["role_vicinity_not_plugin"] == "TP_POLICY"
                             for r in self.expected["source_candidate_rows"]))

    def test_all_cross_gates_block_and_all_permissions_false(self) -> None:
        self.assertEqual(self.expected["cross_cutting_stop_gates"], CROSS_GATES)
        self.assertEqual(set(self.expected["explicit_false_authority"]),
                         set(FALSE_AUTHORITIES))
        self.assertTrue(all(v is False for v in
                            self.expected["explicit_false_authority"].values()))
        self.assertEqual(self.expected["release_status"],
                         "BLOCKED_NO_LIVE_OR_TRADING")

    def test_forged_source_signature_and_future_schema_denied(self) -> None:
        for field in ("source_ast_signature_sha256", "source_file_sha256",
                      "expected_input_schema", "missing_input_fields",
                      "unproven_output_fields"):
            forged = deepcopy(self.expected)
            forged["source_candidate_rows"][0][field] = "FORGED"
            with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, "A04P10_PINNED_DESIGN_OR_AUTHORITY_DRIFT"):
                verify_matrix(forged)

    def test_source_count_or_candidate_removal_denied(self) -> None:
        forged = deepcopy(self.expected)
        forged["source_candidate_rows"].pop()
        with self.assertRaisesRegex(ValueError, "A04P10_PINNED"):
            verify_matrix(forged)
        forged = deepcopy(self.expected)
        forged["p09_measured_source_evidence"]["direct_callable_port_compatible_count"] = 1
        with self.assertRaisesRegex(ValueError, "A04P10_PINNED"):
            verify_matrix(forged)

    def test_runtime_claims_fail_closed(self) -> None:
        for flag in FALSE_AUTHORITIES:
            forged = deepcopy(self.expected)
            forged["explicit_false_authority"][flag] = True
            with self.subTest(flag=flag), self.assertRaisesRegex(
                    ValueError, "A04P10_PINNED"):
                verify_matrix(forged)

    def test_missing_rights_and_market_evidence_cannot_be_marked_approved(self) -> None:
        for gate in CROSS_GATES:
            forged = deepcopy(self.expected)
            forged["cross_cutting_stop_gates"][gate] = "APPROVED"
            with self.subTest(gate=gate), self.assertRaisesRegex(
                    ValueError, "A04P10_PINNED"):
                verify_matrix(forged)

    def test_bypass_full_18_label_detector_and_tp_criteria_denied(self) -> None:
        for index in (2, 3):
            forged = deepcopy(self.expected)
            forged["role_prerequisites"][index]["requirements"] = []
            with self.subTest(index=index), self.assertRaisesRegex(
                    ValueError, "A04P10_PINNED"):
                verify_matrix(forged)

    def test_unknown_field_or_changed_frozen_project_denied(self) -> None:
        for mutation in ("foreign_project", "additional_key"):
            forged = deepcopy(self.expected)
            if mutation == "foreign_project":
                forged["original_forex_commit"] = "0" * 40
            else:
                forged["ready_to_trade"] = True
            with self.subTest(mutation=mutation), self.assertRaisesRegex(
                    ValueError, "A04P10_PINNED"):
                verify_matrix(forged)
