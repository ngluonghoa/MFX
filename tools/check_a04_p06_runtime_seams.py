"""A04/P0.6 CI audit CLI — real 30 module source AST, zero runtime import."""
from __future__ import annotations

import argparse
import json

from tools.a04_p06_runtime_seams import (
    PIN_FILE, PROJECT, SOURCE, inspect_source, verify_inventory,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-measure", action="store_true")
    args = parser.parse_args()
    report = inspect_source(SOURCE, PROJECT)
    if args.bootstrap_measure:
        print("MFX_A04_P06_BOOTSTRAP_REAL_SOURCE_UNPINNED " + json.dumps(
            report, sort_keys=True, separators=(",", ":"),
        ))
        return
    if not PIN_FILE.is_file() or PIN_FILE.is_symlink():
        raise ValueError("A04P06_EXPECT_IMMUTABLE_GITHUB_OBSERVATION")
    baseline = json.loads(PIN_FILE.read_text(encoding="utf-8"))
    verify_inventory(report, baseline)
    print("MFX_A04_P06_PINNED_30_CORE_AST_SEAMS_PASS")
    print("MFX_A04_P06_REAL_SOURCE_RECEIPT " + json.dumps(
        {
            "source_module_count": report["source_module_count"],
            "all_source_metadata_sha256": report["all_source_metadata_sha256"],
            "relative_import_graph_sha256": report["relative_import_graph_sha256"],
            "public_export_count": report["public_export_count"],
            "candidate_readonly_symbol_count":
                report["candidate_readonly_symbol_count"],
            "role_landing_status": report["role_landing_status"],
            "no_src_changes_or_runtime_execution": True,
        }, sort_keys=True, separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
