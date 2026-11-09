"""A03/P0.5: emit REAL source missing branch arcs from coverage.py JSON.

Read-only diagnostics only. Uses the CI coverage report already measured with
--branch; does not invent thresholds, mutate source or run any data provider.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".ci-a03-coverage.json"
TARGETS = (
    "provider_delta_contract.py",
    "cache_core.py",
    "cache_storage_review.py",
    "synthetic_evidence_lineage.py",
    "cache_dependency.py",
)


def main() -> None:
    if not REPORT.is_file() or REPORT.is_symlink():
        raise ValueError("P05_MEASURED_COVERAGE_REPORT_MISSING")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    if report.get("meta", {}).get("branch_coverage") is not True:
        raise ValueError("P05_MEASURED_BRANCH_INSTRUMENTATION_REQUIRED")
    files = report.get("files")
    if not isinstance(files, dict):
        raise ValueError("P05_MEASURED_MODULES_MISSING")
    for target in TARGETS:
        matched = [
            record for path, record in files.items()
            if path.replace("\\", "/").endswith("/forex_trading/" + target)
        ]
        if len(matched) != 1 or not isinstance(matched[0], dict):
            raise ValueError("P05_TARGET_IDENTITY_MISMATCH:" + target)
        record = matched[0]
        arcs = record.get("missing_branches")
        summary = record.get("summary", {})
        missing_count = summary.get("missing_branches")
        if (not isinstance(arcs, list) or
                type(missing_count) is not int or missing_count != len(arcs)):
            raise ValueError("P05_BRANCH_ARC_RECEIPT_INCONSISTENT:" + target)
        if any(
            not isinstance(a, list) or len(a) != 2 or
            any(type(v) is not int for v in a)
            for a in arcs
        ):
            raise ValueError("P05_INVALID_BRANCH_ARC:" + target)
        print("MFX_P05_MEASURED_MISSING_ARCS " + json.dumps({
            "module": target,
            "missing_count": missing_count,
            "arcs": arcs,
            "scope": "SYNTHETIC_ONLY_NO_TRADING_AUTHORITY",
        }, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
