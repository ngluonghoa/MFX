"""A04/P0.11 exact field-level structural proof, negative authority tests."""
from __future__ import annotations

from copy import deepcopy
import unittest

from tools.a04_p11_field_lineage import DENY, PROOF, inspect_field_lineage, read_pinned, verify_exact


class FieldLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reference = inspect_field_lineage()

    def reject(self, altered: dict[str, object]) -> None:
        with self.assertRaisesRegex(ValueError, "P011_FIELD_PROOF_OR_PERMISSION_TAMPERED"):
            verify_exact(altered)

    def test_exact_prior_ast_matrix(self) -> None:
        self.assertEqual(verify_exact(read_pinned())["field_obligations"], 58)

    def test_58_fields_and_zero_approved_mappers(self) -> None:
        s = self.reference["summary"]
        self.assertEqual((s["field_obligations"], s["approved_mappers"], s["working_adapters"]), (58, 0, 0))

    def test_three_matching_names_are_not_semantically_proven(self) -> None:
        matches = [x for r in self.reference["source_rows"] for x in r["field_obligations"] if x["source_name_match_only"]]
        self.assertEqual(len(matches), 3)
        self.assertTrue(all(x["field"] == "decision_utc" and x["status"] == "SAME_NAME_NOT_SEMANTIC_PROOF" for x in matches))

    def test_broker_price_rights_and_timeframe_unmapped(self) -> None:
        for r in self.reference["source_rows"][:3]:
            fields = {x["field"]: x for x in r["field_obligations"] if x["direction"] == "INPUT_REQUIRED"}
            for key in ("instrument_version", "price_basis", "rights_policy_ref", "timeframe"):
                self.assertEqual(fields[key]["status"], "MISSING_NAMED_INPUT")

    def test_optional_source_note_not_omitted(self) -> None:
        xs = [x for r in self.reference["source_rows"] for x in r["field_obligations"] if x["field"] == "source_note"]
        self.assertEqual(len(xs), 2)
        self.assertTrue(all(x["direction"] == "INPUT_OPTIONAL" for x in xs))

    def test_output_never_proven_from_return_annotation(self) -> None:
        xs = [x for r in self.reference["source_rows"] for x in r["field_obligations"] if x["direction"] == "OUTPUT_REQUIRED"]
        self.assertEqual(len(xs), 24)
        self.assertTrue(all(x["status"] == "OUTPUT_UNVERIFIED" and not x["mapping_approved"] for x in xs))

    def test_source_only_args_are_preserved(self) -> None:
        self.assertEqual(self.reference["summary"]["source_only_args"], 15)
        self.assertIn("max_age", self.reference["source_rows"][0]["source_only_args"])

    def test_tp_source_reference_count_stays_zero(self) -> None:
        self.assertEqual(self.reference["role_reference_counts"]["TP_POLICY"], 0)

    def test_change_source_ast_or_port_rejected(self) -> None:
        for field in ("ast_sha256", "source_sha256", "from_port", "to_port"):
            fake = deepcopy(self.reference)
            fake["source_rows"][0][field] = "FORGED"
            self.reject(fake)

    def test_forged_mapping_approval_and_new_field_rejected(self) -> None:
        for key, val in (("mapping_approved", True), ("status", "VERIFIED"), ("field", "fake"), ("proof_needed", "fake")):
            fake = deepcopy(self.reference)
            fake["source_rows"][0]["field_obligations"][0][key] = val
            self.reject(fake)

    def test_missing_input_output_field_rejected(self) -> None:
        fake = deepcopy(self.reference)
        fake["source_rows"][0]["field_obligations"].pop()
        self.reject(fake)

    def test_authority_flags_cannot_be_elevated(self) -> None:
        self.assertGreater(len(PROOF), 10)
        for name in DENY:
            fake = deepcopy(self.reference)
            fake["denied_authority"][name] = True
            self.reject(fake)

    def test_changed_p10_rights_gate_or_source_rejected(self) -> None:
        fake = deepcopy(self.reference)
        fake["inherited_blocked_gates"].pop()
        self.reject(fake)
        fake = deepcopy(self.reference)
        fake["forex_frozen_commit"] = "0" * 40
        self.reject(fake)

    def test_tp_runtime_and_project_injection_denied(self) -> None:
        fake = deepcopy(self.reference)
        fake["unimplemented_tp_policy"] = False
        self.reject(fake)
        fake = deepcopy(self.reference)
        fake["source_rows"][-1]["runtime_mapper_implemented"] = True
        self.reject(fake)
