"""A02/P0.1 — fail-closed Pyflakes across all 30 frozen Forex domain modules.

Ruff 0.13.0 F401 diagnostics existing in the immutable original are recorded
with path/line/column/symbol (including compatibility reexports). No general
F401 ignore is applied: any new, moved or unapproved finding fails Cloud CI.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs" / "MFX_A02_F401_FROZEN_BASELINE.json"
SOURCE = ROOT / "src" / "forex_trading"


def verify_diagnostics(
    observed: list[dict[str, Any]], expected: list[dict[str, Any]]
) -> dict[str, int]:
    """Only EXACT 24 approved F401 source locations/symbols may remain."""
    if not isinstance(observed, list) or not isinstance(expected, list):
        raise ValueError("A02_INVALID_RUFF_DIAGNOSTICS")
    approved: list[tuple[str, int, int, str]] = []
    for item in expected:
        if (not isinstance(item, dict) or
                not isinstance(item.get("path"), str) or
                not isinstance(item.get("row"), int) or
                not isinstance(item.get("column"), int) or
                not isinstance(item.get("symbol"), str)):
            raise ValueError("A02_INVALID_APPROVED_F401")
        approved.append((item["path"], item["row"], item["column"], item["symbol"]))
    if len(approved) != len(set(approved)):
        raise ValueError("A02_DUPLICATE_APPROVED_F401")

    measured: list[tuple[str, int, int, str]] = []
    for item in observed:
        if not isinstance(item, dict) or item.get("code") != "F401":
            raise ValueError("A02_NEW_NON_F401_PYFLAKES_FINDING")
        path, location, message = item.get("path"), item.get("location"), item.get("message")
        if (not isinstance(path, str) or not isinstance(location, dict) or
                not isinstance(message, str)):
            raise ValueError("A02_MALFORMED_RUFF_DIAGNOSTIC")
        row, col = location.get("row"), location.get("column")
        if type(row) is not int or type(col) is not int:
            raise ValueError("A02_INVALID_RUFF_LOCATION")
        candidates = [sym for p, r, c, sym in approved
                      if p == path and r == row and c == col]
        if len(candidates) != 1 or candidates[0] not in message:
            raise ValueError("A02_UNAPPROVED_F401:" + path)
        measured.append((path, row, col, candidates[0]))
    if sorted(measured) != sorted(approved):
        raise ValueError("A02_F401_BASELINE_SET_DRIFT")
    return {"frozen_legacy_f401": len(measured),
            "unexpected_pyflakes": 0}


def main() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    if (baseline.get("schema_version") != 1 or
            baseline.get("kind") != "MFX_A02_FROZEN_SOURCE_F401_EXCEPTION_BASELINE" or
            baseline.get("source_commit") !=
            "7e1c1c012b1b189be5ad7b9d07756eac012a8309" or
            baseline.get("source_tree_sha") !=
            "5df2058346f6dc96ed5bb02581b139fe2aa2d803" or
            baseline.get("original_source_modules") != 30 or
            baseline.get("allowed_code") != "F401" or
            baseline.get("ruff_version") != "0.13.0"):
        raise ValueError("A02_APPROVED_BASELINE_IDENTITY_MISMATCH")
    if len(list(SOURCE.glob("*.py"))) != 30:
        raise ValueError("A02_FROZEN_PYTHON_MODULE_INVENTORY_DRIFT")
    version = subprocess.run(["ruff", "--version"], capture_output=True,
                             text=True, check=True)
    if version.stdout.strip() != "ruff 0.13.0":
        raise ValueError("A02_RUFF_VERSION_DRIFT")
    result = subprocess.run(
        ["ruff", "check", "--select", "F", "--output-format", "json",
         str(SOURCE)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode not in (0, 1):
        raise ValueError("A02_RUFF_SCAN_DID_NOT_RUN:" + str(result.returncode))
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("A02_RUFF_JSON_MALFORMED") from exc
    actual: list[dict[str, Any]] = []
    for diag in raw:
        raw_path = diag.get("filename")
        if not isinstance(raw_path, str):
            raise ValueError("A02_MISSING_RUFF_PATH")
        try:
            path = Path(raw_path).resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError as exc:
            raise ValueError("A02_RUFF_OUTSIDE_REPO") from exc
        actual.append({
            "path": path,
            "location": diag.get("location"),
            "message": diag.get("message"),
            "code": diag.get("code"),
        })
    receipt = verify_diagnostics(actual, baseline["records"])
    print("MFX_A02_FULL_PYFLAKES_FROZEN_BASELINE_PASS " +
          json.dumps({
              "kind": "A02_SOURCE_QUALITY_NOT_TRADING",
              "scanned_source_modules": 30,
              "ruff_version": "0.13.0",
              **receipt,
              "all_new_F_codes_blocked": True,
              "legacy_F401_exceptions_exact": True,
              "this_receipt_only_covers_pyflakes": True,
              "may_deploy_or_trade": False,
          }, sort_keys=True))


if __name__ == "__main__":
    main()
