"""A01/P0.2 synthetic golden comparison rejects drift and false authority."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from tools.compare_golden_contracts import (
    EXPECTED_GROUPS, EXPECTED_KIND, compare_snapshots,
    read_snapshot, validate_snapshot,
)


def sample() -> dict:
    cases = []
    for group in sorted(EXPECTED_GROUPS):
        for i in range(5):
            cases.append({
                "id": f"{group}.case_{i}",
                "outcome": {"value": {"allowed": False, "index": i}},
            })
    return {
        "kind": EXPECTED_KIND,
        "schema": 1,
        "scope": "READ_ONLY_SYNTHETIC_CONTRACTS_NO_DETECTOR_EXECUTION",
        "scenario_count": len(cases),
        "may_trade": False,
        "is_oos_backtest": False,
        "scenarios": cases,
    }


class GoldenContractComparatorTests(unittest.TestCase):
    def test_identical_snapshots_give_read_only_receipt(self):
        snap = sample()
        result = compare_snapshots(snap, deepcopy(snap))
        self.assertEqual(result["scenario_count"], 40)
        self.assertEqual(result["reference_snapshot_sha256"],
                         result["candidate_snapshot_sha256"])
        self.assertTrue(result["all_synthetic_golden_results_identical"])
        self.assertFalse(result["may_deploy_or_trade"])
        self.assertFalse(result["is_full_detector_strategy_parity"])

    def test_modified_financial_value_blocks(self):
        snap = sample()
        other = deepcopy(snap)
        other["scenarios"][4]["outcome"]["value"]["index"] = 999
        with self.assertRaisesRegex(ValueError, "GOLDEN_OUTPUT_OR_ERROR_REASON"):
            compare_snapshots(snap, other)

    def test_error_reason_drift_blocks(self):
        snap = sample()
        snap["scenarios"][1]["outcome"] = {
            "error_type": "ValueError", "reason": "NO_QUOTE_SIDE",
        }
        other = deepcopy(snap)
        other["scenarios"][1]["outcome"]["reason"] = "NO_LONGER_BLOCKED"
        with self.assertRaisesRegex(ValueError, "GOLDEN_OUTPUT_OR_ERROR_REASON"):
            compare_snapshots(snap, other)

    def test_missing_case_blocks(self):
        snap = sample()
        other = deepcopy(snap)
        other["scenarios"] = other["scenarios"][1:]
        other["scenario_count"] -= 1
        with self.assertRaisesRegex(ValueError, "GOLDEN_SCENARIO_INSUFFICIENT"):
            compare_snapshots(snap, other)

    def test_hidden_extra_case_blocks(self):
        snap = sample()
        other = deepcopy(snap)
        other["scenarios"].append({"id": "cache.EXTRA_GOLDEN",
                                   "outcome": {"value": 0}})
        other["scenario_count"] += 1
        with self.assertRaisesRegex(ValueError, "GOLDEN_SCENARIO_SET_MISMATCH"):
            compare_snapshots(snap, other)

    def test_duplicate_case_blocks(self):
        snap = sample()
        snap["scenarios"][1]["id"] = snap["scenarios"][0]["id"]
        with self.assertRaisesRegex(ValueError, "GOLDEN_SCENARIO_ID_DUPLICATE"):
            validate_snapshot(snap)

    def test_missing_scenario_group_blocks(self):
        snap = sample()
        snap["scenarios"] = [x for x in snap["scenarios"]
                             if not x["id"].startswith("version.")]
        snap["scenario_count"] = len(snap["scenarios"])
        snap["scenarios"].extend([
            {"id": f"scan.extra_{i}", "outcome": {"value": 0}}
            for i in range(5)
        ])
        snap["scenario_count"] = len(snap["scenarios"])
        with self.assertRaisesRegex(ValueError, "GOLDEN_COVERAGE_GROUP_MISMATCH"):
            validate_snapshot(snap)

    def test_broker_authority_flag_blocks(self):
        snap = sample()
        snap["may_trade"] = True
        with self.assertRaisesRegex(ValueError, "GOLDEN_SNAPSHOT_UNSAFE"):
            validate_snapshot(snap)

    def test_false_oos_claim_blocks(self):
        snap = sample()
        snap["is_oos_backtest"] = True
        with self.assertRaisesRegex(ValueError, "GOLDEN_SNAPSHOT_UNSAFE"):
            validate_snapshot(snap)

    def test_unexpected_exception_type_blocks(self):
        snap = sample()
        snap["scenarios"][3]["outcome"] = {
            "error_type": "RuntimeError", "reason": "UNKNOWN",
        }
        with self.assertRaisesRegex(ValueError, "GOLDEN_ERROR_UNVERIFIABLE"):
            validate_snapshot(snap)

    def test_missing_outcome_blocks(self):
        snap = sample()
        snap["scenarios"][0]["outcome"] = {}
        with self.assertRaisesRegex(ValueError, "GOLDEN_OUTCOME_MALFORMED"):
            validate_snapshot(snap)

    def test_duplicate_json_object_keys_block(self):
        with tempfile.TemporaryDirectory() as location:
            p = Path(location) / "double.json"
            p.write_text('{"kind":"safe","kind":"unsafe"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "DUPLICATE_GOLDEN_JSON_KEY"):
                read_snapshot(p)

    def test_invalid_json_blocks(self):
        with tempfile.TemporaryDirectory() as location:
            p = Path(location) / "invalid.json"
            p.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "GOLDEN_SNAPSHOT_JSON_INVALID"):
                read_snapshot(p)

    def test_json_roundtrip_preserves_contract(self):
        obj = sample()
        with tempfile.TemporaryDirectory() as location:
            p = Path(location) / "golden.json"
            p.write_text(json.dumps(obj), encoding="utf-8")
            self.assertEqual(read_snapshot(p), obj)


if __name__ == "__main__":
    unittest.main()
