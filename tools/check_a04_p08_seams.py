"""A04/P0.8 GitHub-only source/port boundary, deterministic fail-closed QA."""
from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast

from tools.a04_adapter_conformance import PortSchema
from tools.a04_p08_seam_review import (
    ReferenceFunction, SOURCE_TO_ROLE, SourceBindingPins,
    proposal_for, review_source_seam,
)
from tools.a04_plugin_contracts import PluginKind

ROOT = Path(__file__).resolve().parents[1]
P02 = ROOT / "docs" / "MFX_A04_P02_GOLDEN_GROUP_BASELINE.json"
P03 = ROOT / "docs" / "MFX_A04_P03_COMPAT_MATRIX_BASELINE.json"
P06 = ROOT / "docs" / "MFX_A04_P06_RUNTIME_SEAM_BASELINE.json"
P07 = ROOT / "docs" / "MFX_A04_P07_SOURCE_WRAPPER_BASELINE.json"
PIN = ROOT / "docs" / "MFX_A04_P08_SEAM_AUTHORITY_BASELINE.json"

FROZEN_COMMIT = "7e1c1c012b1b189be5ad7b9d07756eac012a8309"
FROZEN_GOLDEN = "747d029192e080f88b214c76967fa9b91c8e1283f6a4464673cb2bff0b4eabb2"
PORT_GRAPH = "fee5c25ab04139a3da502ebc372d981946c1e1e22965fb36987915220cff9ebe"
AST_GRAPH = "734f1fda1e590ab1e5341e53b05ce31631b139f0108f7407227c87088b65cb47"
P07_CASE = "6ccb082b7940a3bb5c2c27d86151cde1874c6f791eb02cfeac12cf94c2ff49f5"
REQUIRED_FALSE = [
    "may_construct_runtime_adapter", "may_load_plugin",
    "p02_ports_callable_compatible", "may_fetch_real_data",
    "may_write_real_cache", "numeric_detector_verified",
    "tp_sl_engine_verified", "may_release_or_trade",
]


def _json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("A04P8_PINNED_SOURCE_FILE_UNAVAILABLE")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("A04P8_UNTYPED_PINNED_SOURCE")
    return value


def source_pins() -> SourceBindingPins:
    """Bind the seven references to previously observed GitHub CI evidence."""
    p02, p03, p06, p07 = (_json(p) for p in (P02, P03, P06, P07))
    a = p02.get("measured")
    b = p03.get("observed")
    c = p06.get("observed")
    d = p07.get("observed")
    if (not isinstance(a, dict) or not isinstance(b, dict)
            or not isinstance(c, dict) or not isinstance(d, dict)):
        raise ValueError("A04P8_PREVIOUS_OBSERVATION_MISSING")
    if (p02.get("kind") != "MFX_A04_P02_PINNED_SYNTHETIC_GOLDEN_GROUP_BASELINE"
            or p03.get("kind") != "MFX_A04_P03_PINNED_DECLARATIVE_SCHEMA_MATRIX"
            or p06.get("kind") != "MFX_A04_P06_PINNED_REAL_SOURCE_AST_INVENTORY"
            or p07.get("kind") != "MFX_A04_P07_PINNED_REAL_SOURCE_WRAPPER"
            or p02.get("frozen_forex_source_commit") != FROZEN_COMMIT
            or p03.get("frozen_forex_commit") != FROZEN_COMMIT
            or p06.get("original_forex_source_commit") != FROZEN_COMMIT
            or p07.get("original_forex_source_commit") != FROZEN_COMMIT):
        raise ValueError("A04P8_FROZEN_FOREX_IDENTITY_CHANGED")
    if (a.get("synthetic_scenario_count") != 50
            or a.get("adapter_declared_port_count") != 4
            or a.get("frozen_golden_sha256") != FROZEN_GOLDEN
            or a.get("adapter_graph_sha256") != PORT_GRAPH
            or b.get("frozen_original_golden_sha256") != FROZEN_GOLDEN
            or b.get("frozen_declared_graph_sha256") != PORT_GRAPH
            or b.get("case_count") != 14
            or c.get("source_module_count") != 30
            or c.get("candidate_readonly_symbol_count") != 14
            or c.get("relative_import_graph_sha256") != AST_GRAPH
            or d.get("case_count") != 34
            or d.get("case_sha256") != P07_CASE):
        raise ValueError("A04P8_ANCESTOR_EVIDENCE_CHANGED")

    files = c.get("source_file_sha256")
    anchors = c.get("verified_source_symbol_anchors")
    if not isinstance(files, dict) or len(files) != 30 or not isinstance(
            anchors, dict):
        raise ValueError("A04P8_UNTYPED_SOURCE_AST_PINS")
    symbol_digests: dict[str, str] = {}
    for group in anchors.values():
        if not isinstance(group, list):
            raise ValueError("A04P8_UNTYPED_AST_GROUP")
        for entry in group:
            if not isinstance(entry, dict):
                raise ValueError("A04P8_UNTYPED_AST_ENTRY")
            key = str(entry.get("module")) + "." + str(entry.get("symbol"))
            if key in symbol_digests:
                raise ValueError("A04P8_DUPLICATED_AST_SYMBOL")
            sig = entry.get("signature_sha256")
            if not isinstance(sig, str) or len(sig) != 64:
                raise ValueError("A04P8_INVALID_AST_SHA")
            symbol_digests[key] = sig
    if any(ref.value not in symbol_digests for ref in ReferenceFunction):
        raise ValueError("A04P8_P07_SOURCE_SEAM_NOT_PRESENT_IN_P06")
    return SourceBindingPins(files, symbol_digests, AST_GRAPH,
                             P07_CASE, FROZEN_GOLDEN, PORT_GRAPH)


def measure_matrix() -> dict[str, Any]:
    pins = source_pins()
    records: list[dict[str, Any]] = []

    def record(name: str, proposal: Any) -> None:
        review = review_source_seam(proposal, pins)
        if any(getattr(review, flag) is not False for flag in REQUIRED_FALSE):
            raise ValueError("A04P8_UNAUTHORIZED_RUNTIME_AUTHORITY")
        records.append({"case": name,
                        "documentable_only": review.source_reference_documentable,
                        "reason": review.reason})

    good = {ref: proposal_for(ref, pins) for ref in ReferenceFunction}
    for ref in ReferenceFunction:
        record("reference." + ref.name.lower(), good[ref])

    quote = good[ReferenceFunction.QUOTE_INDICATIVE]
    ema = good[ReferenceFunction.EMA_FULL]
    negative = [
        ("wrong_project", replace(quote, project_id="FOREX")),
        ("unknown_reference", replace(
            quote, reference=cast(ReferenceFunction, "provider.unknown"))),
        ("provider_role_swapped", replace(quote, kind=PluginKind.INDICATOR)),
        ("tp_engine_role", replace(quote, kind=PluginKind.TP_POLICY)),
        ("wrong_plugin_id", replace(quote, plugin_id="external.livebroker")),
        ("abi_drift", replace(quote, abi_major=2)),
        ("schema_major_drift", replace(quote, target_schema_major=2)),
        ("schema_minor_drift", replace(quote, target_schema_minor=1)),
        ("wrong_input_port", replace(quote,
                                      target_input_schema=PortSchema.FEATURES_UNVERIFIED_V1)),
        ("wrong_output_port", replace(ema,
                                       target_output_schema=PortSchema.CANDIDATES_UNVERIFIED_V1)),
        ("source_sha_drift", replace(quote, source_file_sha256="f"*64)),
        ("signature_sha_drift", replace(quote, ast_signature_sha256="f"*64)),
        ("p07_wrapper_sha_drift", replace(quote, p07_wrapper_case_sha256="f"*64)),
        ("request_runtime_bind", replace(quote, request_runtime_bind=True)),
        ("request_real_data", replace(quote, request_real_feed=True)),
        ("request_real_cache", replace(quote, request_write_cache=True)),
        ("request_trade", replace(quote, request_trade=True)),
        ("request_schema_fallback", replace(quote, request_schema_fallback=True)),
        ("claim_licensed_data", replace(quote, licensed_data_claim=True)),
        ("claim_numeric_detector", replace(
            good[ReferenceFunction.CATALOG_COUNT], numeric_detector_claim=True)),
        ("claim_tp_sl_engine", replace(quote, tp_sl_engine_claim=True)),
    ]
    for name, bad in negative:
        record("denied." + name, bad)
    allowed = sum(x["documentable_only"] is True for x in records)
    if len(records) != 28 or allowed != 7:
        raise ValueError("A04P8_EXACT_28_CASE_MATRIX_REGRESSION")
    matrix = json.dumps(records, sort_keys=True, separators=(",", ":"),
                        ensure_ascii=True, allow_nan=False).encode("utf-8")
    return {
        "kind": "MFX_A04_P08_PURE_REFERENCE_SEAM_AUTHORITY_REVIEW",
        "total_cases": len(records),
        "source_reference_documentable_only": allowed,
        "blocked": len(records) - allowed,
        "existing_pure_source_functions": len(ReferenceFunction),
        "working_runtime_adapter_count": 0,
        "p06_import_graph_sha256": pins.p06_source_graph_sha256,
        "p07_original_wrapper_case_sha256": pins.p07_wrapper_case_sha256,
        "frozen_original_golden_sha256": pins.frozen_golden_sha256,
        "declared_future_port_graph_sha256": pins.declared_port_graph_sha256,
        "matrix_sha256": sha256(matrix).hexdigest(),
        "no_source_code_modified": True,
        "no_actual_port_callable_equivalence_proven": True,
        "no_plugin_loaded": True,
        "no_real_data_used": True,
        "no_trades_or_release": True,
    }


def verify_pinned(report: dict[str, Any],
                  baseline: dict[str, Any]) -> None:
    if baseline.get("schema_version") != 1 or baseline.get("kind") != (
            "MFX_A04_P08_PINNED_PURE_REFERENCE_SEAM_REVIEW"):
        raise ValueError("A04P8_BASELINE_IDENTITY_CHANGED")
    expected = baseline.get("observed")
    if not isinstance(expected, dict):
        raise ValueError("A04P8_PINNED_MEASUREMENT_MISSING")
    for field in ("kind", "total_cases", "source_reference_documentable_only",
                  "blocked", "existing_pure_source_functions",
                  "working_runtime_adapter_count", "p06_import_graph_sha256",
                  "p07_original_wrapper_case_sha256",
                  "frozen_original_golden_sha256",
                  "declared_future_port_graph_sha256", "matrix_sha256"):
        if report.get(field) != expected.get(field):
            raise ValueError("A04P8_PINNED_SOURCE_SEAM_MATRIX_DRIFT:" + field)
    if (report.get("total_cases") != 28 or
            report.get("source_reference_documentable_only") != 7 or
            report.get("blocked") != 21 or
            report.get("working_runtime_adapter_count") != 0):
        raise ValueError("A04P8_SEAM_MATRIX_BUDGET_CHANGED")
    required = [
        "no_source_code_modified", "no_actual_port_callable_equivalence_proven",
        "no_plugin_loaded", "no_real_data_used", "no_trades_or_release",
    ]
    if baseline.get("required_true_flags") != required:
        raise ValueError("A04P8_BASELINE_AUTHORITY_WEAKENED")
    for flag in required:
        if report.get(flag) is not True:
            raise ValueError("A04P8_UNAUTHORIZED_RUNTIME_FLAG:" + flag)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-measure", action="store_true")
    args = parser.parse_args()
    report = measure_matrix()
    if args.bootstrap_measure:
        print("MFX_A04_P08_BOOTSTRAP_UNPINNED " + json.dumps(
            report, sort_keys=True, separators=(",", ":"),
        ))
        return
    baseline = _json(PIN)
    verify_pinned(report, baseline)
    print("MFX_A04_P08_PINNED_ZERO_RUNTIME_ADAPTERS_PASS")
    print("MFX_A04_P08_RECEIPT " + json.dumps(
        report, sort_keys=True, separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
