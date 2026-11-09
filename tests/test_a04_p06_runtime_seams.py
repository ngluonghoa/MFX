"""A04/P0.6 actual source AST inventory and fail-closed drift checks."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import ast
import unittest

from tools.a04_p06_runtime_seams import (
    PROJECT, SOURCE, NO_RUNTIME_AUTHORITY, ROLE_ANCHORS, _dependencies,
    _exports, inspect_source, verify_inventory,
)


class A04P06RuntimeSeamAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = inspect_source(SOURCE, PROJECT)

    def test_real_python_core_count_and_candidate_count(self) -> None:
        self.assertEqual(self.report["source_module_count"], 30)
        self.assertEqual(self.report["candidate_readonly_symbol_count"], 14)
        self.assertEqual(sum(len(v) for v in ROLE_ANCHORS.values()), 14)

    def test_four_roles_do_not_claim_hot_swappable_plugins(self) -> None:
        roles = self.report["role_landing_status"]
        self.assertEqual(set(roles), {
            "provider", "indicator", "detector", "tp_policy",
        })
        self.assertIn("NO_18_ZONE_ENGINE_PROOF", roles["detector"])
        self.assertIn("NO_TP_SL_ENGINE_PROOF", roles["tp_policy"])
        self.assertIn("NO_ADAPTER", roles["provider"])
        self.assertIn("NO_PLUGIN_INTERFACE", roles["indicator"])

    def test_all_existing_source_anchors_real_ast_symbols(self) -> None:
        for role, entries in self.report["verified_source_symbol_anchors"].items():
            with self.subTest(role=role):
                self.assertTrue(entries)
                self.assertTrue(all(len(e["signature_sha256"]) == 64
                                    for e in entries))

    def test_no_runtime_authority_claimed_by_static_inventory(self) -> None:
        for flag in NO_RUNTIME_AUTHORITY:
            with self.subTest(flag=flag):
                self.assertIs(self.report[flag], False)
        self.assertTrue(self.report["no_source_executed_during_inventory"])
        self.assertTrue(self.report["ast_only_no_dynamic_reachability_proof"])

    def test_only_static_source_hashes_not_vendor_rights(self) -> None:
        digest = self.report["source_file_sha256"]
        self.assertEqual(len(digest), 30)
        self.assertTrue(all(len(x) == 64 for x in digest.values()))
        self.assertEqual(self.report["package_name"], "mfx-forex-core")

    def test_changing_one_frozen_module_digest_must_be_denied(self) -> None:
        report = self.report
        baseline = self._fixture_baseline()
        verify_inventory(report, baseline)
        changed = deepcopy(report)
        changed["source_file_sha256"]["market_data.py"] = "0"*64
        with self.assertRaisesRegex(ValueError, "A04P06_PINNED_CORE_INTERFACE_DRIFT"):
            verify_inventory(changed, baseline)

    def test_changed_signature_and_dependency_fingerprint_denied(self) -> None:
        report = self.report
        baseline = self._fixture_baseline()
        for key in ("verified_source_symbol_anchors",
                    "relative_import_graph_sha256"):
            changed = deepcopy(report)
            if key == "relative_import_graph_sha256":
                changed[key] = "f"*64
            else:
                changed[key]["provider_review_only"][0]["signature_sha256"] = "f"*64
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                    ValueError, "A04P06_PINNED_CORE_INTERFACE_DRIFT",
                ):
                    verify_inventory(changed, baseline)

    def test_any_pretended_runtime_activation_rejected(self) -> None:
        baseline = self._fixture_baseline()
        for flag in NO_RUNTIME_AUTHORITY:
            report = dict(self.report, **{flag: True})
            with self.subTest(flag=flag):
                with self.assertRaisesRegex(
                    ValueError, "A04P06_UNAUTHORIZED_RUNTIME_CLAIM",
                ):
                    verify_inventory(report, baseline)

    def test_runtime_tools_import_from_source_ast_fails_closed(self) -> None:
        sample = ast.parse("from tools.a04_plugin_contracts import PluginManifest\n")
        with self.assertRaisesRegex(ValueError, "A04P06_SOURCE_IMPORTS_A04_OR_TOOLS"):
            _dependencies(sample, "synthetic")

    def test_import_tooling_dynamically_by_static_direct_import_fails(self) -> None:
        sample = ast.parse("import tools.a04_plugin_contracts\n")
        with self.assertRaisesRegex(ValueError, "A04P06_SOURCE_IMPORTS_A04_OR_TOOLS"):
            _dependencies(sample, "synthetic")

    def test_public_package_export_parser_rejects_dynamic_all(self) -> None:
        sample = ast.parse("__all__ = produce_exports()\n")
        with self.assertRaisesRegex(ValueError, "A04P06_PUBLIC_EXPORTS_NOT_STATIC"):
            _exports(sample)

    def test_source_dir_is_project_src_not_tools(self) -> None:
        self.assertEqual(SOURCE.name, "forex_trading")
        self.assertEqual(SOURCE.parent.name, "src")
        self.assertTrue(Path(PROJECT).name == "pyproject.toml")

    def _fixture_baseline(self) -> dict:
        result = self.report
        fields = (
            "source_module_count", "source_file_sha256",
            "all_source_metadata_sha256", "relative_import_graph_sha256",
            "package_name", "pyproject_bytes_sha256", "public_export_count",
            "public_export_names", "candidate_readonly_symbol_count",
            "verified_source_symbol_anchors", "role_landing_status",
        )
        return {
            "schema_version": 1,
            "kind": "MFX_A04_P06_PINNED_REAL_SOURCE_AST_INVENTORY",
            "original_forex_source_commit":
                "7e1c1c012b1b189be5ad7b9d07756eac012a8309",
            "observed": {k: deepcopy(result[k]) for k in fields},
            "required_false_flags": list(NO_RUNTIME_AUTHORITY),
        }


if __name__ == "__main__":
    unittest.main()
