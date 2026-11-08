"""Synthetic negative tests for exact legacy F401 debt monitoring under A02."""
from __future__ import annotations

from copy import deepcopy
import unittest

from tools.check_a02_pyflakes_baseline import verify_diagnostics


def approved():
    return [{"path": "src/forex_trading/a.py", "row": 3,
             "column": 5, "symbol": "typing.Sequence"}]


def observed():
    return [{"path": "src/forex_trading/a.py",
             "location": {"row": 3, "column": 5},
             "message": "`typing.Sequence` imported but unused",
             "code": "F401"}]


class A02PyflakesBaselineTests(unittest.TestCase):
    def test_exact_existing_f401_is_accepted(self):
        receipt = verify_diagnostics(observed(), approved())
        self.assertEqual(receipt["frozen_legacy_f401"], 1)
        self.assertEqual(receipt["unexpected_pyflakes"], 0)

    def test_new_unused_import_at_new_location_is_rejected(self):
        diagnostics = observed()
        extra = deepcopy(diagnostics[0])
        extra["location"]["row"] = 4
        diagnostics.append(extra)
        with self.assertRaisesRegex(ValueError, "A02_UNAPPROVED_F401"):
            verify_diagnostics(diagnostics, approved())

    def test_new_other_pyflakes_violation_is_rejected(self):
        diagnostics = observed()
        diagnostics[0]["code"] = "F821"
        with self.assertRaisesRegex(ValueError, "A02_NEW_NON_F401"):
            verify_diagnostics(diagnostics, approved())

    def test_missing_historical_diagnostic_requires_review(self):
        with self.assertRaisesRegex(ValueError, "A02_F401_BASELINE_SET_DRIFT"):
            verify_diagnostics([], approved())

    def test_changed_import_symbol_at_same_location_rejected(self):
        diagnostics = observed()
        diagnostics[0]["message"] = "`other.Symbol` imported but unused"
        with self.assertRaisesRegex(ValueError, "A02_UNAPPROVED_F401"):
            verify_diagnostics(diagnostics, approved())

    def test_duplicate_approved_location_rejected(self):
        with self.assertRaisesRegex(ValueError, "A02_DUPLICATE_APPROVED_F401"):
            verify_diagnostics(observed(), approved() + approved())

    def test_malformed_diagnostic_location_rejected(self):
        diagnostics = observed()
        diagnostics[0]["location"] = None
        with self.assertRaisesRegex(ValueError, "A02_MALFORMED_RUFF_DIAGNOSTIC"):
            verify_diagnostics(diagnostics, approved())


if __name__ == "__main__":
    unittest.main()
