"""A03/P0.4 audit actual coverage.py branch/line coverage in Cloud CI.

The first audited run reports real observed metrics with NO invented baseline.
Once the approved baseline is registered in Docs/JSON, this tool fails closed
on regressions. No source/financial API/network access is performed here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / ".ci-a03-coverage.json"
BASELINE = ROOT / "docs" / "MFX_A03_COVERAGE_BASELINE.json"
EXPECTED_MODULES = 30
COVERAGE_VERSION = "7.10.7"


def _require_int(x: Any, key: str) -> int:
    if type(x) is not int or x < 0:
        raise ValueError(f"A03_COVERAGE_INVALID_{key.upper()}")
    return x


def evaluate_report(report: dict[str, Any],
                    baseline: dict[str, Any] | None
                    ) -> dict[str, Any]:
    meta = report.get("meta")
    totals = report.get("totals")
    files = report.get("files")
    if (not isinstance(meta, dict) or
            meta.get("version") != COVERAGE_VERSION or
            meta.get("branch_coverage") is not True or
            not isinstance(totals, dict) or not isinstance(files, dict)):
        raise ValueError("A03_INVALID_COVERAGE_REPORT_IDENTITY")
    observed = {
        key: _require_int(totals.get(key), key)
        for key in (
            "num_statements", "covered_lines", "missing_lines",
            "num_branches", "covered_branches", "missing_branches",
        )
    }
    if (observed["num_statements"] == 0 or
            observed["num_branches"] == 0 or
            observed["covered_lines"] + observed["missing_lines"] !=
            observed["num_statements"] or
            observed["covered_branches"] + observed["missing_branches"] !=
            observed["num_branches"]):
        raise ValueError("A03_COVERAGE_INVALID_TOTALS")
    summary: dict[str, dict[str, int]] = {}
    for raw_name, item in files.items():
        if not isinstance(raw_name, str) or not isinstance(item, dict):
            raise ValueError("A03_COVERAGE_MALFORMED_MODULE")
        path = raw_name.replace("\\", "/")
        suffix = path.split("forex_trading/", 1)
        if len(suffix) != 2 or "/" in suffix[1] or not suffix[1].endswith(".py"):
            raise ValueError("A03_COVERAGE_INCLUDED_NON_SOURCE_FILE:" + path)
        mod = suffix[1]
        if mod in summary or not isinstance(item.get("summary"), dict):
            raise ValueError("A03_COVERAGE_DUPLICATE_OR_MISSING_SOURCE")
        s = item["summary"]
        summary[mod] = {k: _require_int(s.get(k), k) for k in
                        ("num_statements", "covered_lines",
                         "num_branches", "covered_branches")}
    if len(summary) != EXPECTED_MODULES:
        raise ValueError("A03_COVERAGE_MODULE_COUNT_DRIFT:" + str(len(summary)))
    if sum(v["num_statements"] for v in summary.values()) != observed[
            "num_statements"]:
        raise ValueError("A03_COVERAGE_MODULE_STATEMENTS_SUM_DRIFT")
    if sum(v["num_branches"] for v in summary.values()) != observed[
            "num_branches"]:
        raise ValueError("A03_COVERAGE_MODULE_BRANCHES_SUM_DRIFT")
    for mod, v in summary.items():
        if v["covered_lines"] > v["num_statements"] or v[
                "covered_branches"] > v["num_branches"]:
            raise ValueError("A03_COVERAGE_MODULE_IMPOSSIBLE:" + mod)
    observed["module_count"] = len(summary)
    if baseline is None:
        stage = "MEASURED_ONLY_BASELINE_PENDING"
    else:
        if (baseline.get("schema_version") != 1 or
                baseline.get("kind") != "MFX_A03_P0_4_FROZEN_COVERAGE_MINIMA" or
                baseline.get("coverage_version") != COVERAGE_VERSION or
                baseline.get("source_modules") != EXPECTED_MODULES):
            raise ValueError("A03_COVERAGE_BASELINE_IDENTITY_DRIFT")
        mins = baseline.get("minimum")
        if not isinstance(mins, dict):
            raise ValueError("A03_COVERAGE_MINIMA_INVALID")
        for k in ("covered_lines", "covered_branches", "num_statements",
                  "num_branches"):
            n = _require_int(mins.get(k), "minimum_" + k)
            if observed[k] < n:
                raise ValueError("A03_COVERAGE_REGRESSION:" + k +
                                 f":{observed[k]}<{n}")
        guarded = baseline.get("guarded_modules")
        if not isinstance(guarded, dict):
            raise ValueError("A03_COVERAGE_GUARDED_MODULES_INVALID")
        for name, requirements in guarded.items():
            if name not in summary or not isinstance(requirements, dict):
                raise ValueError("A03_COVERAGE_GUARDED_MODULE_MISSING")
            for k in ("covered_lines", "covered_branches"):
                minimum = _require_int(requirements.get(k),
                                       "guarded_" + k)
                if summary[name][k] < minimum:
                    raise ValueError("A03_COVERAGE_CORE_REGRESSION:" + name +
                                     ":" + k)
        stage = "FROZEN_NONREGRESSION_GATE_PASS"
    return {
        "kind": "A03_SYNTHETIC_SOURCE_BRANCH_COVERAGE_ONLY",
        "stage": stage,
        "coverage_version": COVERAGE_VERSION,
        **observed,
        "covered_line_percent": round(
            100 * observed["covered_lines"] /
            observed["num_statements"], 2,
        ),
        "covered_branch_percent": round(
            100 * observed["covered_branches"] /
            observed["num_branches"], 2,
        ),
        "per_module_coverage": summary,
        "this_is_not_global_fuzz_coverage": True,
        "real_market_data_used": False,
        "may_deploy_or_trade": False,
    }


def main() -> None:
    if not COVERAGE.is_file() or COVERAGE.is_symlink():
        raise ValueError("A03_COVERAGE_REPORT_MISSING")
    report = json.loads(COVERAGE.read_text(encoding="utf-8"))
    baseline = (json.loads(BASELINE.read_text(encoding="utf-8"))
                if BASELINE.is_file() and not BASELINE.is_symlink()
                else None)
    receipt = evaluate_report(report, baseline)
    print("MFX_A03_COVERAGE_MEASURED " + json.dumps(
        receipt, sort_keys=True, separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
