"""MFX-only synthetic negative tests for independent wheel import ownership."""
from __future__ import annotations

import unittest
from pathlib import Path

from tools.check_mfx_import_ownership import assess_mfx_import_ownership

ROOT = Path("/synthetic-cloud-venv")
ORIGIN = ROOT / "lib" / "python3.12" / "site-packages" / "forex_trading" / "__init__.py"


def valid(**overrides):
    inputs = {
        "distribution_name": "mfx-forex-core",
        "distribution_version": "0.1.0",
        "forex_distribution_present": False,
        "package_owners": ("mfx-forex-core",),
        "import_origin": ORIGIN,
        "environment_root": ROOT,
        "is_virtual_environment": True,
    }
    inputs.update(overrides)
    return assess_mfx_import_ownership(**inputs)


class MfxCloudImportIsolationTests(unittest.TestCase):
    def test_valid_single_mfx_owner_is_qa_only(self):
        receipt = valid()
        self.assertTrue(receipt["single_distribution_owner_verified"])
        self.assertTrue(receipt["isolated_virtual_environment_verified"])
        self.assertEqual(receipt["distribution"], "mfx-forex-core")
        self.assertFalse(receipt["may_deploy_or_trade"])
        self.assertFalse(receipt["is_strategy_parity_proof"])

    def test_metadata_canonicalization_accepted(self):
        self.assertEqual(valid(distribution_name="MFX_Forex.Core")["distribution"],
                         "mfx-forex-core")

    def test_missing_mfx_distribution_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "MFX_DISTRIBUTION_MISSING_OR_WRONG"):
            valid(distribution_name=None)

    def test_upstream_distribution_name_cannot_masquerade_as_mfx(self):
        with self.assertRaisesRegex(ValueError, "MFX_DISTRIBUTION_MISSING_OR_WRONG"):
            valid(distribution_name="forex-trading-core")

    def test_missing_distribution_version_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "MFX_DISTRIBUTION_VERSION_MISSING"):
            valid(distribution_version="")

    def test_coinstalled_forex_distribution_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "FOREX_DISTRIBUTION_CO_INSTALLED"):
            valid(forex_distribution_present=True)

    def test_nonisolated_interpreter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ISOLATED_PYTHON_RUNTIME_REQUIRED"):
            valid(is_virtual_environment=False)

    def test_missing_import_owner_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "FOREX_IMPORT_NAMESPACE_OWNER_AMBIGUOUS"):
            valid(package_owners=())

    def test_duplicate_import_owners_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "FOREX_IMPORT_NAMESPACE_OWNER_AMBIGUOUS"):
            valid(package_owners=("mfx-forex-core", "forex-trading-core"))

    def test_unrelated_import_owner_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "FOREX_IMPORT_NAMESPACE_OWNER_AMBIGUOUS"):
            valid(package_owners=("other-project",))

    def test_missing_module_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "FOREX_IMPORT_MODULE_MISSING"):
            valid(import_origin=None)

    def test_import_outside_runtime_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "FOREX_IMPORT_OUTSIDE_ISOLATED_RUNTIME"):
            valid(import_origin=Path("/another-project/forex_trading/__init__.py"))


if __name__ == "__main__":
    unittest.main()
