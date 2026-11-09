"""A04/P0.10 inert matrix: checked source AST facts plus unmet adapter gates.

There is NO adapter implementation, source execution, provider access, trade or
release authority in this module. Every assertion is fail-closed against P0.9.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.a04_p09_callable_port_gaps import (
    FROZEN, PIN, _read_json, inspect_callable_gaps, verify_pinned,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs" / "MFX_A04_P10_MAPPER_PREREQUISITE_MATRIX.json"
FROZEN_MFX_IMPORT = "6ee5e7c07baf4ea8f06a28889175808ea53c2316"
P09_ROWS = "06d3abb44df35cccf10c889aaa59f358f73d01937cbbc7529970c1c248e18cba"
P09_SCHEMAS = "e12cd296e96e2a9d0b34f658b1eb9477cdb08e748a4836c10396d4e21c623083"
P09_ROUTES = "55727bcabe0552f7f2a7db8a870b3304071dd3b72eca0740f5a5e3c3d6bf178f"

ROLE_REQUIREMENTS: tuple[tuple[str, int, str, str, tuple[str, ...]], ...] = (
    ("PROVIDER", 3, "PROVIDER_QUERY_V1", "PROVIDER_READONLY_UNVERIFIED_V1", (
        "Verify vendor/account/instrument-product entitlement, redistribution, retention and Drive replay rights with documentary evidence",
        "Qualify native BID/ASK quote-side provenance and broker-product match; MID/OHLCV must never be treated as execution price",
        "Prove first_known_utc, decision/asof clock, closed-bar/calendar/DST, duplicate and correction revision semantics",
        "Pin symbol/timeframe/price-basis/version/freshness/error mappings with negative missing, stale, 429, rights-denied and unsupported-TF cases",
        "Separate read-only source observations from execution or strategy authorization",
    )),
    ("INDICATOR", 2, "PROVIDER_READONLY_UNVERIFIED_V1", "FEATURES_UNVERIFIED_V1", (
        "Define versioned FeaturesV1 payload, field identities, source revision, quality, first-known UTC, price basis and failure states",
        "Specify exact Decimal/EMA precision, warm-up, missing values and full-recompute versus dirty-prefix equivalence",
        "Provide causal as-of dependency graph; no provisional candles or future HTF pivots promoted to verified features",
        "Prove input/output serializer and failure-reason parity against frozen Forex golden semantics before any source change",
    )),
    ("DETECTOR", 2, "FEATURES_UNVERIFIED_V1", "CANDIDATES_UNVERIFIED_V1", (
        "Implement and separately verify numerical, versioned per-label rules before calling any detector executable",
        "Preserve frozen 18-label taxonomy: 7 long-entry, 8 short-entry, B7 watch-only, S3/S8 exit-warning; FX-B9 research-only",
        "Pin LONG/SHORT state/reason, 8 pipeline stages, first-known causal evidence, signal lifecycle and overlap/dedup semantics",
        "Demonstrate deterministic reference parity plus independently held-out source-qualified after-cost tests; catalog validation alone is insufficient",
    )),
    ("TP_POLICY", 0, "CANDIDATES_UNVERIFIED_V1", "TP_PROPOSAL_UNVERIFIED_V1", (
        "Obtain independently approved executable TP/SL policy design: there is zero approved pure-source function in P0.9 scope",
        "Define side-correct entry/exit, broker/product constraints, risk sizing, fees, spread, swap, slippage and stop-out",
        "Specify partial/gap fills, same-bar ordering ambiguity, liquidity and unverified-cost safe rejection",
        "Require separate deterministic frozen-source and out-of-sample economic parity evidence before code or release authorization",
    )),
)
CROSS_GATES: dict[str, str] = {
    "provider_licence_and_drive_retention": "EVIDENCE_MISSING",
    "native_historical_broker_bid_ask": "UNVERIFIED",
    "first_known_clock_and_revision": "REQUIRES_VALIDATION",
    "versioned_input_output_mappers": "NOT_IMPLEMENTED",
    "numeric_entry_zone_detector": "NOT_PROVEN",
    "executable_tp_sl_and_broker_fill": "NOT_IMPLEMENTED",
    "source_qualified_real_market_oos": "NOT_RUN",
    "live_drive_cache_write": "NOT_AUTHORIZED",
    "runtime_plugin_activation": "NOT_AUTHORIZED",
    "signed_release_or_trading": "NOT_AUTHORIZED",
}
FALSE_AUTHORITIES: tuple[str, ...] = (
    "source_functions_changed", "provider_entitlement_verified",
    "native_bidask_execution_price_verified", "mapper_runtime_implemented",
    "numeric_detector_verified", "tp_sl_risk_engine_verified",
    "real_market_oos_approved", "drive_cache_live_authorized",
    "plugin_runtime_activated", "signed_release_authorized",
    "broker_orders_authorized",
)


def expected_design_matrix() -> dict[str, Any]:
    """Derive design claims ONLY from frozen verified seven-function AST rows."""
    actual = inspect_callable_gaps()
    verify_pinned(actual, _read_json(PIN))
    if (actual["rows_sha256"] != P09_ROWS or
            actual["future_port_shapes_sha256"] != P09_SCHEMAS or
            actual["future_port_routes_sha256"] != P09_ROUTES or
            actual["source_reference_count"] != 7 or
            actual["source_to_port_direct_compatible_count"] != 0 or
            actual["role_reference_counts"] != {
                "PROVIDER": 3, "INDICATOR": 2, "DETECTOR": 2, "TP_POLICY": 0,
            }):
        raise ValueError("A04P10_PINNED_SOURCE_PROVENANCE_MISMATCH")
    raw_rows = actual.get("source_gap_rows")
    if not isinstance(raw_rows, list) or len(raw_rows) != 7:
        raise ValueError("A04P10_EXACT_SEVEN_SOURCE_ROWS_REQUIRED")
    candidates: list[dict[str, Any]] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            raise ValueError("A04P10_UNTRUSTED_SOURCE_ROW")
        if (item.get("direct_callable_port_compatible") is not False
                or item.get("needs_separately_reviewed_explicit_mapper") is not True
                or not item.get("missing_required_port_input_fields")
                or not item.get("return_port_schema_fields_not_proven")):
            raise ValueError("A04P10_CANNOT_GRANT_PORT_COMPATIBILITY")
        candidates.append({
            "source_function": item["reference_function"],
            "role_vicinity_not_plugin": item["role_vicinity_not_adapter"],
            "expected_input_schema": item["future_input_schema"],
            "expected_output_schema": item["future_output_schema"],
            "missing_input_fields": item["missing_required_port_input_fields"],
            "unproven_output_fields": item["return_port_schema_fields_not_proven"],
            "source_file_sha256": item["source_file_sha256"],
            "source_ast_signature_sha256": item["source_ast_signature_sha256"],
            "mapper_review_state": "MAPPING_NOT_SPECIFIED_OR_AUTHORIZED",
            "source_callable_port_compatible": False,
        })
    roles: list[dict[str, Any]] = [
        {
            "role": role, "expected_reference_count": count,
            "input_schema": incoming, "output_schema": outgoing,
            "requirements": list(requirements),
        }
        for role, count, incoming, outgoing, requirements in ROLE_REQUIREMENTS
    ]
    return {
        "schema_version": 1,
        "kind": "MFX_A04_P10_DESIGN_ONLY_MAPPER_PREREQUISITE_MATRIX",
        "original_forex_commit": FROZEN,
        "original_102_blob_mfx_import": FROZEN_MFX_IMPORT,
        "p09_measured_source_evidence": {
            "rows_sha256": P09_ROWS,
            "future_port_shapes_sha256": P09_SCHEMAS,
            "future_port_routes_sha256": P09_ROUTES,
            "source_reference_count": 7,
            "direct_callable_port_compatible_count": 0,
        },
        "source_candidate_rows": candidates,
        "role_prerequisites": roles,
        "cross_cutting_stop_gates": dict(CROSS_GATES),
        "explicit_false_authority": {name: False for name in FALSE_AUTHORITIES},
        "decision": "DESIGN_REVIEW_ONLY_NO_SOURCE_OR_RUNTIME_AUTHORIZATION",
        "release_status": "BLOCKED_NO_LIVE_OR_TRADING",
        "next_authorization": (
            "SEPARATE_OWNER_APPROVED_RIGHTS_SECURITY_SOURCE_DELTA_PR_AND_REAL_PARITY_EVIDENCE"
        ),
    }


def verify_matrix(document: dict[str, Any]) -> dict[str, Any]:
    """Exact allowlist: changes to fields/claims cannot silently pass CI."""
    expected = expected_design_matrix()
    if document != expected:
        raise ValueError("A04P10_PINNED_DESIGN_OR_AUTHORITY_DRIFT")
    return {
        "status": "A04P10_DESIGN_ONLY_BLOCKED_BY_EVIDENCE",
        "seven_source_rows": 7,
        "direct_compatible": 0,
        "role_count": len(ROLE_REQUIREMENTS),
        "blocked_cross_gates": len(CROSS_GATES),
        "runtime_adapters": 0,
        "release_authorized": False,
    }


def read_matrix(path: Path = MATRIX_PATH) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("A04P10_MATRIX_MISSING_OR_UNSAFE")
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("A04P10_MATRIX_MUST_BE_OBJECT")
    return value
