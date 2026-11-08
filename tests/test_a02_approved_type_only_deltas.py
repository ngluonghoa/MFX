"""A02 type-only source exception gate: explicit 6-path allowlist, no broad bypass."""
from __future__ import annotations

from copy import deepcopy
import unittest

from tools.verify_frozen_source_baseline import (
    A02_CHANGE_ID, A02_TYPED_SOURCE_PATHS, EXCEPTION_FILE, SOURCE_TREE,
    assess_checkout, exception_entries,
)

ALLOWED = "src/forex_trading/cache_core.py"


def inventory():
    original = {f"src/forex_trading/example_{i:02d}.py": {
        "path": f"src/forex_trading/example_{i:02d}.py",
        "mode": "100644", "sha": "a" * 40, "bytes": 10
    } for i in range(29)}
    original[ALLOWED] = {
        "path": ALLOWED, "mode": "100644",
        "sha": "b" * 40, "bytes": 20,
    }
    current = {path: (data["sha"], data["bytes"])
               for path, data in original.items()}
    current[ALLOWED] = ("c" * 40, 22)
    current[EXCEPTION_FILE] = ("d" * 40, 145)
    exceptions = [
        {"path": ALLOWED, "change": "modified",
         "expected_current_sha": "c" * 40,
         "approved_change_id": A02_CHANGE_ID,
         "reason": "exact reviewed A02 typed-source change"},
        {"path": EXCEPTION_FILE, "change": "added",
         "reason": "self-referential hash exemption"},
    ]
    manifest = {
        "schema_version": 1, "kind": "MFX_APPROVED_PARITY_DELTAS",
        "source_tree_sha": SOURCE_TREE, "exceptions": exceptions,
    }
    return original, current, manifest


class A02TypedSourceExceptionTests(unittest.TestCase):
    def test_explicit_six_path_policy_not_wildcard(self):
        self.assertEqual(len(A02_TYPED_SOURCE_PATHS), 6)
        self.assertTrue(all(s.startswith("src/forex_trading/") for s
                            in A02_TYPED_SOURCE_PATHS))

    def test_one_approved_type_only_difference_is_reported(self):
        original, actual, manifest = inventory()
        parsed = exception_entries(manifest)
        receipt = assess_checkout(original, actual, parsed)
        self.assertEqual(receipt["domain_python_sources_byte_equal"], 29)
        self.assertEqual(receipt["approved_typed_source_deltas"], 1)
        self.assertFalse(receipt["may_deploy_or_trade"])

    def test_missing_change_authorization_rejected(self):
        _, _, manifest = inventory()
        del manifest["exceptions"][0]["approved_change_id"]
        with self.assertRaisesRegex(ValueError, "DOMAIN_SOURCE_DELTA"):
            exception_entries(manifest)

    def test_unlisted_source_path_cannot_be_approved(self):
        _, _, manifest = inventory()
        manifest["exceptions"][0]["path"] = "src/forex_trading/evil.py"
        with self.assertRaisesRegex(ValueError, "DOMAIN_SOURCE_DELTA"):
            exception_entries(manifest)

    def test_approved_source_blob_sha_cannot_drift(self):
        original, actual, manifest = inventory()
        actual[ALLOWED] = ("e" * 40, 22)
        with self.assertRaisesRegex(ValueError, "APPROVED_DELTA_SHA_CHANGED"):
            assess_checkout(original, actual, exception_entries(manifest))

    def test_domain_source_deletion_rejected(self):
        original, actual, manifest = inventory()
        del actual[ALLOWED]
        with self.assertRaisesRegex(ValueError, "MISSING_FROZEN_SOURCE_PATH"):
            assess_checkout(original, actual, exception_entries(manifest))

    def test_no_added_source_files_under_a02_scope(self):
        _, _, manifest = inventory()
        manifest["exceptions"][0]["change"] = "added"
        with self.assertRaisesRegex(ValueError, "DOMAIN_SOURCE_DELTA"):
            exception_entries(manifest)

    def test_wrong_a02_decision_scope_rejected(self):
        _, _, manifest = inventory()
        manifest["exceptions"][0]["approved_change_id"] = "DEC-INVALID"
        with self.assertRaisesRegex(ValueError, "DOMAIN_SOURCE_DELTA"):
            exception_entries(manifest)

    def test_no_indirect_parity_claim_from_exception(self):
        original, actual, manifest = inventory()
        receipt = assess_checkout(original, actual, exception_entries(manifest))
        self.assertFalse(receipt["is_live_strategy_parity_proof"])
        self.assertFalse(receipt["is_signed_release"])


if __name__ == "__main__":
    unittest.main()
