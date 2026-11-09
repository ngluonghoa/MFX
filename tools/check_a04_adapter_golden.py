"""A04/P0.2: compare frozen Forex-vs-MFX synthetic golden by contract group.

Use only already generated immutable source and candidate golden JSON in
GitHub Actions. No plugin execution, live feed, real detector/TP or trade.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from tools.a04_adapter_conformance import (
    synthetic_reference_graph, validate_declared_adapter_graph,
)
from tools.compare_golden_contracts import (
    EXPECTED_GROUPS, FROZEN_SOURCE_COMMIT, compare_snapshots,
    read_snapshot, validate_snapshot,
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")


def assess_adapter_golden(
    reference: dict[str, Any], candidate: dict[str, Any],
) -> dict[str, Any]:
    """Never transform the source outputs; preserve exact error reason parity."""
    # The original comparator guards all metadata and every outcome.
    existing = compare_snapshots(reference, candidate)
    scenarios = validate_snapshot(reference)
    if len(scenarios) != 50:
        raise ValueError("A04P2_EXPECT_FROZEN_50_SYNTHETIC_SCENARIOS")
    grouped: dict[str, list[dict[str, Any]]] = {
        group: [] for group in sorted(EXPECTED_GROUPS)
    }
    for entry in scenarios:
        group = entry["id"].split(".", 1)[0]
        grouped[group].append(entry)
    if any(not entries for entries in grouped.values()):
        raise ValueError("A04P2_MISSING_GOLDEN_GROUP")
    per_group = {
        group: {
            "scenario_count": len(items),
            "source_and_candidate_sha256": sha256(
                _canonical(sorted(items, key=lambda e: e["id"]))
            ).hexdigest(),
        }
        for group, items in grouped.items()
    }
    registry, ports = synthetic_reference_graph()
    receipt = validate_declared_adapter_graph(registry, ports)
    if not receipt.declared_schema_compatible or receipt.port_count != 4:
        raise ValueError("A04P2_DECLARED_GRAPH_NOT_READY")
    if existing["reference_snapshot_sha256"] != existing["candidate_snapshot_sha256"]:
        raise ValueError("A04P2_SOURCE_VS_MFX_GOLDEN_DRIFT")
    return {
        "kind": "MFX_A04_P02_INERT_ADAPTER_CONTRACT_GOLDEN",
        "source_commit": FROZEN_SOURCE_COMMIT,
        "synthetic_scenario_count": len(scenarios),
        "contract_group_count": len(per_group),
        "contract_groups": per_group,
        "adapter_graph_sha256": receipt.graph_sha256,
        "adapter_declared_port_count": receipt.port_count,
        "frozen_golden_sha256": existing["reference_snapshot_sha256"],
        "mfx_golden_sha256": existing["candidate_snapshot_sha256"],
        "frozen_synthetic_contracts_exact": True,
        "adapter_implementation_executed": False,
        "detector_or_tp_execution_tested": False,
        "licensed_real_data_used": False,
        "may_cache_real_data": False,
        "may_deploy_or_trade": False,
    }


BASELINE_FILE = (
    Path(__file__).resolve().parents[1]
    / "docs" / "MFX_A04_P02_GOLDEN_GROUP_BASELINE.json"
)


def verify_pinned_adapter_golden(
    report: dict[str, Any], baseline: dict[str, Any],
) -> None:
    """Fail closed when source group identities or inert scope drift."""
    if (
        baseline.get("schema_version") != 1
        or baseline.get("kind")
        != "MFX_A04_P02_PINNED_SYNTHETIC_GOLDEN_GROUP_BASELINE"
        or baseline.get("frozen_forex_source_commit") != FROZEN_SOURCE_COMMIT
        or report.get("source_commit") != FROZEN_SOURCE_COMMIT
    ):
        raise ValueError("A04P2_PINNED_GOLDEN_SOURCE_IDENTITY_MISMATCH")
    measured = baseline.get("measured")
    if not isinstance(measured, dict):
        raise ValueError("A04P2_PINNED_GOLDEN_BASELINE_UNTYPED")
    for name in (
        "synthetic_scenario_count", "contract_group_count",
        "contract_groups", "adapter_graph_sha256",
        "adapter_declared_port_count", "frozen_golden_sha256",
    ):
        if report.get(name) != measured.get(name):
            raise ValueError("A04P2_PINNED_GOLDEN_DRIFT:" + name)
    if (report.get("frozen_golden_sha256")
            != report.get("mfx_golden_sha256")
            or report.get("frozen_synthetic_contracts_exact") is not True):
        raise ValueError("A04P2_ORIGINAL_VS_MFX_GOLDEN_DRIFT")
    forbidden = baseline.get("expected_false_flags")
    if not isinstance(forbidden, list) or sorted(forbidden) != sorted([
        "adapter_implementation_executed", "detector_or_tp_execution_tested",
        "licensed_real_data_used", "may_cache_real_data",
        "may_deploy_or_trade",
    ]):
        raise ValueError("A04P2_PINNED_SCOPE_FLAGS_DRIFT")
    for name in forbidden:
        if report.get(name) is not False:
            raise ValueError("A04P2_UNAUTHORIZED_SCOPE:" + name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    report = assess_adapter_golden(
        read_snapshot(args.reference), read_snapshot(args.candidate),
    )
    if not BASELINE_FILE.is_file() or BASELINE_FILE.is_symlink():
        raise ValueError("A04P2_PINNED_GOLDEN_BASELINE_MISSING")
    baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    verify_pinned_adapter_golden(report, baseline)
    print("MFX_A04_P02_PINNED_GROUP_GOLDEN_PASS")
    print("MFX_A04_P02_DECLARATION_GOLDEN_PASS " +
          json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
