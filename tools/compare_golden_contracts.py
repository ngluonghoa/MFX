"""A01/P0.2 strict golden snapshot comparator for frozen Forex and MFX.

Inputs are deliberately synthetic contract outputs, NOT real FX data, detector
numerics, backtest/OOS evidence or approval to release/deploy/trade.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

FROZEN_SOURCE_COMMIT = "7e1c1c012b1b189be5ad7b9d07756eac012a8309"
FROZEN_SOURCE_TREE = "5df2058346f6dc96ed5bb02581b139fe2aa2d803"
EXPECTED_KIND = "MFX_A01_SYNTHETIC_GOLDEN_CONTRACT_V1"
EXPECTED_GROUPS = frozenset((
    "catalog", "scan", "quote", "signal", "pipeline", "bar",
    "cache", "version",
))


def _no_duplicate_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("DUPLICATE_GOLDEN_JSON_KEY")
        result[key] = value
    return result


def read_snapshot(path: Path) -> dict[str, Any]:
    """Bound input and reject malformed/duplicate JSON fields."""
    if not path.is_file() or path.is_symlink():
        raise ValueError("GOLDEN_SNAPSHOT_FILE_INVALID")
    data = path.read_bytes()
    if not 0 < len(data) < 2_000_000:
        raise ValueError("GOLDEN_SNAPSHOT_BYTES_OUT_OF_RANGE")
    try:
        obj = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
                         parse_constant=lambda _: (_ for _ in ()).throw(
                             ValueError("NONFINITE_GOLDEN_JSON_NUMBER")
                         ))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ValueError("GOLDEN_SNAPSHOT_JSON_INVALID") from err
    if not isinstance(obj, dict):
        raise ValueError("GOLDEN_SNAPSHOT_ROOT_INVALID")
    return obj


def _canonical(obj: Any) -> bytes:
    return json.dumps(
        obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def validate_snapshot(obj: dict[str, Any]) -> list[dict[str, Any]]:
    if (obj.get("kind") != EXPECTED_KIND or obj.get("schema") != 1 or
            obj.get("scope") != "READ_ONLY_SYNTHETIC_CONTRACTS_NO_DETECTOR_EXECUTION"):
        raise ValueError("GOLDEN_CONTRACT_SCHEMA_OR_SCOPE_MISMATCH")
    if obj.get("may_trade") is not False or obj.get("is_oos_backtest") is not False:
        raise ValueError("GOLDEN_SNAPSHOT_UNSAFE_AUTHORITY_FLAG")
    records = obj.get("scenarios")
    if not isinstance(records, list) or len(records) < 40:
        raise ValueError("GOLDEN_SCENARIO_INSUFFICIENT")
    if type(obj.get("scenario_count")) is not int or obj["scenario_count"] != len(records):
        raise ValueError("GOLDEN_SCENARIO_COUNT_MISMATCH")
    ids: set[str] = set()
    for item in records:
        if not isinstance(item, dict):
            raise ValueError("GOLDEN_SCENARIO_INVALID")
        ident = item.get("id")
        outcome = item.get("outcome")
        if (not isinstance(ident, str) or "." not in ident or
                len(ident) > 120 or ident in ids):
            raise ValueError("GOLDEN_SCENARIO_ID_DUPLICATE_OR_INVALID")
        ids.add(ident)
        if (not isinstance(outcome, dict) or
                (("value" in outcome) == ("error_type" in outcome))):
            raise ValueError("GOLDEN_OUTCOME_MALFORMED")
        if "error_type" in outcome and (
                outcome["error_type"] not in ("ValueError", "TypeError") or
                not isinstance(outcome.get("reason"), str)):
            raise ValueError("GOLDEN_ERROR_UNVERIFIABLE")
    groups = frozenset(label.split(".", 1)[0] for label in ids)
    if groups != EXPECTED_GROUPS:
        raise ValueError("GOLDEN_COVERAGE_GROUP_MISMATCH")
    return records


def compare_snapshots(
    reference: dict[str, Any], candidate: dict[str, Any],
) -> dict[str, Any]:
    left = validate_snapshot(reference)
    right = validate_snapshot(candidate)
    by_id = {x["id"]: x["outcome"] for x in left}
    other = {x["id"]: x["outcome"] for x in right}
    if by_id.keys() != other.keys():
        missing = sorted(by_id.keys() - other.keys())
        added = sorted(other.keys() - by_id.keys())
        raise ValueError(
            "GOLDEN_SCENARIO_SET_MISMATCH:missing=" + ",".join(missing) +
            ":added=" + ",".join(added)
        )
    for ident in sorted(by_id):
        if by_id[ident] != other[ident]:
            raise ValueError("GOLDEN_OUTPUT_OR_ERROR_REASON_MISMATCH:" + ident)
    if _canonical(reference) != _canonical(candidate):
        raise ValueError("GOLDEN_METADATA_MISMATCH")
    return {
        "kind": "MFX_A01_P0_2_FROZEN_CONTRACT_GOLDEN_PARITY",
        "source_commit": FROZEN_SOURCE_COMMIT,
        "source_tree_sha": FROZEN_SOURCE_TREE,
        "scenario_count": len(left),
        "contract_groups": sorted(EXPECTED_GROUPS),
        "reference_snapshot_sha256": sha256(_canonical(reference)).hexdigest(),
        "candidate_snapshot_sha256": sha256(_canonical(candidate)).hexdigest(),
        "all_synthetic_golden_results_identical": True,
        "includes_real_market_data": False,
        "is_full_detector_strategy_parity": False,
        "is_oos_backtest": False,
        "is_release_or_lkg": False,
        "may_deploy_or_trade": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    result = compare_snapshots(read_snapshot(args.reference),
                               read_snapshot(args.candidate))
    print("MFX_A01_GOLDEN_CONTRACT_PARITY_PASS " +
          json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
