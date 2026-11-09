"""A04/P0.7 original-Forex-vs-MFX wrappers: compare 34 synthetic cases.

MFX wrapper is tooling-only, not bundled in MFX runtime wheel; exception
types and messages are part of frozen 1:1 evidence, not a trading signal.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from tools.compare_golden_contracts import (
    FROZEN_SOURCE_COMMIT, read_snapshot,
)

BASELINE = Path(__file__).resolve().parents[1] / (
    "docs/MFX_A04_P07_SOURCE_WRAPPER_BASELINE.json"
)
KIND = "MFX_A04_P07_CI_ONLY_SOURCE_WRAPPER_PARITY_V1"
SCOPE = "CI_ONLY_EXISTING_PURE_SOURCE_FUNCTIONS_NO_ADAPTER_RUNTIME"
DENIED = (
    "real_provider_io", "adapter_runtime_wired",
    "numerical_zone_detector_executed", "tp_sl_engine_executed",
    "licensed_data_used", "may_release_or_trade",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_canonical(value)).hexdigest()


def validate_wrapped_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    if (set(snapshot) != {"kind", "scope", "scenario_count", "scenarios",
                          "wrapper_matches_direct_source", *DENIED}
            or snapshot.get("kind") != KIND or snapshot.get("scope") != SCOPE
            or snapshot.get("wrapper_matches_direct_source") is not True):
        raise ValueError("A04P07_SNAPSHOT_SCOPE_OR_KIND_DRIFT")
    if any(snapshot.get(flag) is not False for flag in DENIED):
        raise ValueError("A04P07_UNAUTHORIZED_WRAPPER_AUTHORITY")
    rows = snapshot.get("scenarios")
    if not isinstance(rows, list) or type(snapshot.get("scenario_count")) is not int:
        raise ValueError("A04P07_SNAPSHOT_CASES_UNTYPED")
    if len(rows) != 34 or snapshot["scenario_count"] != 34:
        raise ValueError("A04P07_34_CASE_BUDGET_DRIFT")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "outcome"}:
            raise ValueError("A04P07_ROW_SHAPE_DRIFT")
        name = row["id"]
        outcome = row["outcome"]
        if (not isinstance(name, str) or "." not in name
                or len(name) > 96 or name in seen):
            raise ValueError("A04P07_DUPLICATE_OR_MISSING_CASE")
        seen.add(name)
        if not isinstance(outcome, dict) or (
                ("value" in outcome) == ("error_type" in outcome)):
            raise ValueError("A04P07_WRAPPER_OUTCOME_MALFORMED")
        if "error_type" in outcome and (
                outcome["error_type"] not in ("ValueError", "TypeError")
                or not isinstance(outcome.get("reason"), str)):
            raise ValueError("A04P07_UNTYPED_ERROR_REASON")
    if {x.split(".", 1)[0] for x in seen} != {
        "quote", "bar", "asof", "ema", "catalog",
    }:
        raise ValueError("A04P07_EXPECT_FIVE_PURE_SOURCE_GROUPS")
    return rows


def compare_wrapped(
    original: dict[str, Any], candidate: dict[str, Any],
) -> dict[str, Any]:
    direct = validate_wrapped_snapshot(original)
    derived = validate_wrapped_snapshot(candidate)
    if direct != derived or original != candidate:
        raise ValueError("A04P07_FROZEN_FOREX_VS_MFX_WRAPPER_DRIFT")
    return {
        "kind": "MFX_A04_P07_WRAPPER_COMPARISON_RECEIPT",
        "frozen_forex_commit": FROZEN_SOURCE_COMMIT,
        "case_count": len(direct),
        "case_sha256": _digest(direct),
        "full_snapshot_sha256": _digest(original),
        "wrapper_vs_direct_pass": True,
        "original_forex_vs_mfx_pass": True,
        "source_module_edits": False,
        "plugin_loaded": False,
        "real_provider_used": False,
        "numerical_detector_or_tp_tested": False,
        "may_release_or_trade": False,
    }


def verify_pinned_comparison(
    receipt: dict[str, Any], baseline: dict[str, Any],
) -> None:
    if (baseline.get("schema_version") != 1
            or baseline.get("kind") != "MFX_A04_P07_PINNED_REAL_SOURCE_WRAPPER"
            or baseline.get("original_forex_source_commit")
            != FROZEN_SOURCE_COMMIT
            or receipt.get("frozen_forex_commit") != FROZEN_SOURCE_COMMIT):
        raise ValueError("A04P07_PINNED_SOURCE_IDENTITY_DRIFT")
    expected = baseline.get("observed")
    if not isinstance(expected, dict):
        raise ValueError("A04P07_PINNED_RECEIPT_MISSING")
    for k in ("kind", "case_count", "case_sha256", "full_snapshot_sha256"):
        if expected.get(k) != receipt.get(k):
            raise ValueError("A04P07_PINNED_WRAPPER_DRIFT:" + k)
    if receipt.get("case_count") != 34:
        raise ValueError("A04P07_INVALID_CASE_COUNT")
    required_true = baseline.get("required_true_flags")
    required_false = baseline.get("required_false_flags")
    if required_true != ["wrapper_vs_direct_pass", "original_forex_vs_mfx_pass"] or (
            required_false != [
                "source_module_edits", "plugin_loaded", "real_provider_used",
                "numerical_detector_or_tp_tested", "may_release_or_trade",
            ]):
        raise ValueError("A04P07_BASELINE_AUTHORITY_WEAKENED")
    for flag in required_true:
        if receipt.get(flag) is not True:
            raise ValueError("A04P07_PARITY_NOT_PROVEN:" + flag)
    for flag in required_false:
        if receipt.get(flag) is not False:
            raise ValueError("A04P07_FORBIDDEN_AUTHORITY:" + flag)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--bootstrap-measure", action="store_true")
    args = parser.parse_args()
    receipt = compare_wrapped(
        read_snapshot(args.reference), read_snapshot(args.candidate))
    if args.bootstrap_measure:
        print("MFX_A04_P07_BOOTSTRAP_UNPINNED " + json.dumps(
            receipt, sort_keys=True, separators=(",", ":"),
        ))
        return
    if not BASELINE.is_file() or BASELINE.is_symlink():
        raise ValueError("A04P07_PINNED_BASELINE_FILE_MISSING")
    baseline = read_snapshot(BASELINE)
    verify_pinned_comparison(receipt, baseline)
    print("MFX_A04_P07_PINNED_34_WRAPPER_PARITY_PASS")
    print("MFX_A04_P07_RECEIPT " + json.dumps(
        receipt, sort_keys=True, separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
