"""Negative/positive contract tests for A03 coverage receipts and floors."""
from __future__ import annotations

from copy import deepcopy
import unittest

from tools.check_a03_coverage import evaluate_report, COVERAGE_VERSION


def fixture():
    files = {
        f"src/forex_trading/module_{i:02d}.py": {
            "summary": {
                "num_statements": 1, "covered_lines": 1,
                "num_branches": 1, "covered_branches": 1,
            }
        }
        for i in range(30)
    }
    return {
        "meta": {"version": COVERAGE_VERSION, "branch_coverage": True},
        "totals": {
            "num_statements": 30, "covered_lines": 30,
            "missing_lines": 0, "num_branches": 30,
            "covered_branches": 30, "missing_branches": 0,
        },
        "files": files,
    }


def guard():
    return {
        "schema_version": 1,
        "kind": "MFX_A03_P0_4_FROZEN_COVERAGE_MINIMA",
        "coverage_version": COVERAGE_VERSION,
        "source_modules": 30,
        "minimum": {
            "covered_lines": 30, "covered_branches": 30,
            "num_statements": 30, "num_branches": 30,
        },
        "guarded_modules": {
            "module_00.py": {"covered_lines": 1, "covered_branches": 1}
        },
    }


class A03CoverageIntegrityTests(unittest.TestCase):
    def test_measured_only_is_explicitly_not_frozen_gate(self):
        value = evaluate_report(fixture(), None)
        self.assertEqual(value["stage"], "MEASURED_ONLY_BASELINE_PENDING")
        self.assertEqual(value["module_count"], 30)
        self.assertFalse(value["may_deploy_or_trade"])

    def test_exact_baseline_pass_receipt(self):
        value = evaluate_report(fixture(), guard())
        self.assertEqual(value["stage"], "FROZEN_NONREGRESSION_GATE_PASS")
        self.assertEqual(value["covered_branch_percent"], 100)

    def test_lower_observed_branch_coverage_rejected(self):
        changed = fixture()
        changed["totals"]["covered_branches"] -= 1
        changed["totals"]["missing_branches"] += 1
        changed["files"]["src/forex_trading/module_01.py"][
            "summary"]["covered_branches"] -= 1
        with self.assertRaisesRegex(ValueError, "A03_COVERAGE_REGRESSION"):
            evaluate_report(changed, guard())

    def test_missing_source_module_and_extra_file_both_rejected(self):
        missing = fixture()
        del missing["files"]["src/forex_trading/module_29.py"]
        with self.assertRaisesRegex(ValueError, "A03_COVERAGE_MODULE_COUNT"):
            evaluate_report(missing, None)
        other = fixture()
        other["files"]["tests/test_secret.py"] = {
            "summary": {"num_statements": 0, "covered_lines": 0,
                        "num_branches": 0, "covered_branches": 0}
        }
        with self.assertRaisesRegex(ValueError, "A03_COVERAGE_INCLUDED_NON_SOURCE"):
            evaluate_report(other, None)

    def test_guarded_core_module_regression_even_if_total_same(self):
        changed = fixture()
        changed["files"]["src/forex_trading/module_00.py"][
            "summary"]["covered_lines"] = 0
        # Total remains 30 to exercise per-core minimum independent of total.
        with self.assertRaisesRegex(ValueError, "A03_COVERAGE_CORE_REGRESSION"):
            evaluate_report(changed, guard())

    def test_false_branch_instrumentation_is_rejected(self):
        changed = fixture()
        changed["meta"]["branch_coverage"] = False
        with self.assertRaisesRegex(ValueError, "A03_INVALID_COVERAGE_REPORT"):
            evaluate_report(changed, None)


if __name__ == "__main__":
    unittest.main()
