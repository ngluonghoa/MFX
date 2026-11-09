"""A04/P0.9 actual source AST->declared future port gap tests, no runtime."""
from __future__ import annotations

from copy import deepcopy
import unittest

from tools.a04_p09_callable_port_gaps import (
    REFERENCE_ROLES, EXPECTED_PORTS, DENIED, PIN, _read_json,
    inspect_callable_gaps, verify_pinned,
)


class RealSourceCallablePortGaps(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = inspect_callable_gaps()

    def test_all_real_seven_sources_have_unresolved_port_gaps(self) -> None:
        self.assertEqual(self.report["source_reference_count"], 7)
        self.assertEqual(self.report["declared_future_schema_count"], 5)
        self.assertEqual(self.report["declared_future_port_kind_count"], 4)
        self.assertEqual(self.report["source_to_port_direct_compatible_count"], 0)
        self.assertEqual(self.report["required_mapper_review_count"], 7)
        for row in self.report["source_gap_rows"]:
            with self.subTest(reference=row["reference_function"]):
                self.assertFalse(row["direct_callable_port_compatible"])
                self.assertTrue(row["needs_separately_reviewed_explicit_mapper"])
                self.assertTrue(row["missing_required_port_input_fields"])
                self.assertTrue(row["return_port_schema_fields_not_proven"])

    def test_provider_port_fields_are_not_sourced_by_quote_or_bars(self) -> None:
        rows = self.report["source_gap_rows"]
        provider = [row for row in rows
                    if row["role_vicinity_not_adapter"] == "PROVIDER"]
        self.assertEqual(len(provider), 3)
        for row in provider:
            with self.subTest(reference=row["reference_function"]):
                missing = set(row["missing_required_port_input_fields"])
                self.assertIn("rights_policy_ref", missing)
                self.assertIn("instrument_version", missing)
                self.assertIn("timeframe", missing)

    def test_indicator_ema_is_not_verified_feature_port(self) -> None:
        rows = [row for row in self.report["source_gap_rows"]
                if row["role_vicinity_not_adapter"] == "INDICATOR"]
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertTrue("closes" in {
                param["name"] for param in row["source_parameters"]})
            self.assertTrue("source_revision" in
                            row["missing_required_port_input_fields"])
            self.assertEqual(row["source_return_annotation"],
                             "tuple[Decimal, ...]")

    def test_catalog_count_or_validate_is_not_numeric_detector(self) -> None:
        rows = [row for row in self.report["source_gap_rows"]
                if row["role_vicinity_not_adapter"] == "DETECTOR"]
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertTrue("zones" in {
                param["name"] for param in row["source_parameters"]})
            self.assertIn("quality", row["missing_required_port_input_fields"])
            self.assertFalse(row["direct_callable_port_compatible"])

    def test_tp_policy_references_are_explicitly_zero(self) -> None:
        self.assertEqual(len(REFERENCE_ROLES), 7)
        self.assertEqual(set(EXPECTED_PORTS),
                         {"PROVIDER", "INDICATOR", "DETECTOR", "TP_POLICY"})
        self.assertEqual(self.report["role_reference_counts"]["TP_POLICY"], 0)

    def test_real_source_abi_has_keyword_only_m5_fields(self) -> None:
        row = next(x for x in self.report["source_gap_rows"]
                   if x["reference_function"] ==
                   "market_data.evaluate_closed_bar")
        modes = {p["name"]: p["mode"] for p in row["source_parameters"]}
        self.assertEqual(modes["conditional_m5_early_enabled"], "KEYWORD_ONLY")
        self.assertEqual(modes["htf_context_first_known_utc"], "KEYWORD_ONLY")

    def test_fingerprints_are_sha256_not_semantic_approvals(self) -> None:
        for field in ("rows_sha256", "future_port_shapes_sha256",
                      "future_port_routes_sha256"):
            self.assertEqual(len(self.report[field]), 64)
        for row in self.report["source_gap_rows"]:
            self.assertEqual(len(row["source_ast_signature_sha256"]), 64)
            self.assertEqual(len(row["source_file_sha256"]), 64)

    def test_no_runtime_authority_from_static_ast_gap_audit(self) -> None:
        for flag in DENIED:
            with self.subTest(flag=flag):
                self.assertIs(self.report[flag], False)
        self.assertTrue(
            self.report["no_source_imported_or_executed_during_ast_audit"])

    def test_measured_real_seven_source_baseline_is_exact(self) -> None:
        pinned = _read_json(PIN)
        verify_pinned(self.report, pinned)
        self.assertEqual(
            self.report["rows_sha256"],
            "06d3abb44df35cccf10c889aaa59f358f73d01937cbbc7529970c1c248e18cba",
        )

    def test_tampered_source_row_or_source_signature_denied(self) -> None:
        pinned = _read_json(PIN)
        for key, replacement in (
            ("source_return_annotation", "TrustedBIDASKBar"),
            ("source_ast_signature_sha256", "f"*64),
            ("source_file_sha256", "f"*64),
        ):
            forged = deepcopy(self.report)
            forged["source_gap_rows"][0][key] = replacement
            with self.subTest(key=key), self.assertRaisesRegex(
                    ValueError, "A04P09_FROZEN_CALLABLE_PORT_SHAPE_DRIFT"):
                verify_pinned(forged, pinned)

    def test_tampered_future_schema_or_route_fingerprint_denied(self) -> None:
        pinned = _read_json(PIN)
        for key in ("future_port_shapes_sha256", "future_port_routes_sha256"):
            forged = dict(self.report, **{key: "0"*64})
            with self.subTest(key=key), self.assertRaisesRegex(
                    ValueError, "A04P09_FROZEN_CALLABLE_PORT_SHAPE_DRIFT"):
                verify_pinned(forged, pinned)

    def test_runtime_adapter_or_data_rights_cannot_be_invented(self) -> None:
        pinned = _read_json(PIN)
        for flag in DENIED:
            forged = dict(self.report, **{flag: True})
            with self.subTest(flag=flag), self.assertRaisesRegex(
                    ValueError, "A04P09_FORBIDDEN_RUNTIME_AUTHORITY"):
                verify_pinned(forged, pinned)

    def test_claiming_callable_compatibility_is_denied(self) -> None:
        pinned = _read_json(PIN)
        forged = dict(self.report, source_to_port_direct_compatible_count=1)
        with self.assertRaisesRegex(
                ValueError, "A04P09_FROZEN_CALLABLE_PORT_SHAPE_DRIFT"):
            verify_pinned(forged, pinned)

    def test_cannot_weaken_baseline_runtime_prohibitions(self) -> None:
        pinned = _read_json(PIN)
        forged = deepcopy(pinned)
        forged["required_false_flags"] = []
        with self.assertRaisesRegex(ValueError,
                                    "A04P09_BASELINE_AUTHORITY_WEAKENED"):
            verify_pinned(self.report, forged)

    def test_mutating_a_readonly_report_cannot_prove_compatibility(self) -> None:
        forged = deepcopy(self.report)
        forged["source_gap_rows"][0]["direct_callable_port_compatible"] = True
        self.assertNotEqual(forged["source_gap_rows"], self.report["source_gap_rows"])


if __name__ == "__main__":
    unittest.main()
