"""P0.11: source AST -> future port field lineage, NO source runtime execution."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.a04_p09_callable_port_gaps import PIN, _read_json, inspect_callable_gaps, verify_pinned
from tools.a04_p10_mapper_matrix import read_matrix, verify_matrix

BASELINE = Path(__file__).resolve().parents[1] / "docs/MFX_A04_P11_FIELD_LINEAGE_BASELINE.json"
P09_ROWS = "06d3abb44df35cccf10c889aaa59f358f73d01937cbbc7529970c1c248e18cba"
P09_SCHEMAS = "e12cd296e96e2a9d0b34f658b1eb9477cdb08e748a4836c10396d4e21c623083"
P09_ROUTES = "55727bcabe0552f7f2a7db8a870b3304071dd3b72eca0740f5a5e3c3d6bf178f"
P10_GIT_BLOB = "4832fd0c31c37ac00f6ed3cdddc4136f46ba3740"
PROOF: dict[str, str] = {
  "decision_utc": "CLOCK_CAUSAL_UTC",
  "instrument_version": "BROKER_PRODUCT_AND_LICENSE",
  "price_basis": "NATIVE_BIDASK_NO_MID",
  "rights_policy_ref": "VENDOR_STORAGE_REPLAY_ENTITLEMENT",
  "timeframe": "CLOSED_CANDLE_CALENDAR_DST",
  "first_known_utc": "SOURCE_FIRST_KNOWN_UTC",
  "quality": "SOURCE_QUALITY_FAILURE",
  "source_revision": "SOURCE_REVISION_ASOF",
  "asof_utc": "CAUSAL_ASOF_NO_LOOKAHEAD",
  "feature_set_id": "FEATURE_SCHEMA_VERSION",
  "source_quality": "PROVENANCE_AND_QUALITY",
  "zone_label": "FROZEN_18_ZONE_NUMERIC_DETECTOR",
  "review_label": "OPTIONAL_DISPLAY_ONLY",
  "source_note": "OPTIONAL_NOTE_NO_RIGHTS_PROOF"
}
DENY: tuple[str, ...] = ("market_data_rights_proven", "broker_bidask_execution_verified", "first_known_semantics_verified", "source_to_port_mapper_implemented", "numerical_detector_verified", "tp_sl_fills_implemented", "oos_economic_parity_proven", "drive_live_cache_activated", "plugin_runtime_activated", "broker_trade_or_release_authorized",)


def inspect_field_lineage() -> dict[str, Any]:
    p09 = inspect_callable_gaps()
    verify_pinned(p09, _read_json(PIN))
    p10 = read_matrix()
    verify_matrix(p10)
    if (p09["rows_sha256"] != P09_ROWS or
            p09["future_port_shapes_sha256"] != P09_SCHEMAS or
            p09["future_port_routes_sha256"] != P09_ROUTES):
        raise ValueError("P011_SOURCE_GAP_FINGERPRINT_DRIFT")
    raw, previous = p09["source_gap_rows"], p10["source_candidate_rows"]
    if len(raw) != 7 or len(previous) != 7:
        raise ValueError("P011_SEVEN_REF_REQUIREMENT")
    rows: list[dict[str, Any]] = []
    count = match = miss = optional = out = only = 0
    for r, old in zip(raw, previous):
        if (r["reference_function"] != old["source_function"] or
                r["source_file_sha256"] != old["source_file_sha256"] or
                r["source_ast_signature_sha256"] != old["source_ast_signature_sha256"]):
            raise ValueError("P011_P09_P10_SOURCE_PROVENANCE_MISMATCH")
        names = {x["name"] for x in r["source_parameters"]}
        cols: list[dict[str, Any]] = []
        for direction, raw_names in (
            ("INPUT_REQUIRED", r["future_required_input_fields"]),
            ("INPUT_OPTIONAL", r["future_optional_input_fields"]),
            ("OUTPUT_REQUIRED", r["return_port_schema_fields_not_proven"]),
        ):
            if len(set(raw_names)) != len(raw_names):
                raise ValueError("P011_DUPLICATE_PORT_FIELD")
            for field in raw_names:
                if not isinstance(field, str) or field not in PROOF:
                    raise ValueError("P011_UNKNOWN_REQUIRED_PROOF")
                same = direction == "INPUT_REQUIRED" and field in names
                status = "SAME_NAME_NOT_SEMANTIC_PROOF" if same else (
                    "MISSING_NAMED_INPUT" if direction == "INPUT_REQUIRED" else
                    "OPTIONAL_UNVERIFIED" if direction == "INPUT_OPTIONAL" else
                    "OUTPUT_UNVERIFIED"
                )
                cols.append({
                    "direction": direction, "field": field,
                    "source_name_match_only": same,
                    "evidence": "AST_NAME_AND_ANNOTATION_ONLY",
                    "proof_needed": PROOF[field], "status": status,
                    "mapping_approved": False,
                })
                count += 1
                if direction == "INPUT_REQUIRED":
                    if same:
                        match += 1
                    else:
                        miss += 1
                elif direction == "INPUT_OPTIONAL":
                    optional += 1
                else:
                    out += 1
        only += len(r["source_only_parameter_names"])
        rows.append({
            "function": r["reference_function"],
            "role": r["role_vicinity_not_adapter"],
            "from_port": r["future_input_schema"],
            "to_port": r["future_output_schema"],
            "source_sha256": r["source_file_sha256"],
            "ast_sha256": r["source_ast_signature_sha256"],
            "source_only_args": r["source_only_parameter_names"],
            "field_obligations": cols, "runtime_mapper_implemented": False,
        })
    if (count, match, miss, optional, out, only) != (58, 3, 26, 5, 24, 15):
        raise ValueError("P011_REAL_FIELD_COUNTS_CHANGED")
    return {
        "schema_version": 1, "kind": "MFX_A04_P11_ACTUAL_FIELD_LINEAGE_UNVERIFIED",
        "forex_frozen_commit": "7e1c1c012b1b189be5ad7b9d07756eac012a8309",
        "first_mfx_102_blob_import": "6ee5e7c07baf4ea8f06a28889175808ea53c2316",
        "p09_row_sha": P09_ROWS, "p09_schema_sha": P09_SCHEMAS,
        "p09_route_sha": P09_ROUTES, "p10_git_blob_sha": P10_GIT_BLOB,
        "source_rows": rows, "role_reference_counts": p09["role_reference_counts"],
        "unimplemented_tp_policy": True,
        "inherited_blocked_gates": sorted(p10["cross_cutting_stop_gates"]),
        "denied_authority": {x: False for x in DENY},
        "summary": {
            "functions": 7, "field_obligations": count,
            "same_name_only": match, "unmapped_required_inputs": miss,
            "unverified_optional_inputs": optional, "unverified_outputs": out,
            "source_only_args": only, "approved_mappers": 0, "working_adapters": 0,
        },
        "decision": "DESIGN_ONLY_STATIC_NO_PROVIDER_OR_RUNTIME_ELEVATION",
    }


def read_pinned() -> dict[str, Any]:
    if BASELINE.is_symlink() or not BASELINE.is_file():
        raise ValueError("P011_PIN_UNSAFE_OR_MISSING")
    result: Any = json.loads(BASELINE.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("P011_PIN_NOT_OBJECT")
    return result


def verify_exact(data: dict[str, Any]) -> dict[str, Any]:
    expected = inspect_field_lineage()
    if expected != data:
        raise ValueError("P011_FIELD_PROOF_OR_PERMISSION_TAMPERED")
    return {
        "status": "P011_PINNED_AST_FIELD_GAPS_PASS",
        "field_obligations": expected["summary"]["field_obligations"],
        "same_name_only": 3, "approved_mappers": 0,
        "runtime_adapters": 0, "may_trade": False,
    }
