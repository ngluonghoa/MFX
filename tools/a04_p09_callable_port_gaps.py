"""A04/P0.9 — actual source-callable vs future declared port SHAPE gaps.

All evidence is local to GitHub-hosted CI: Python stdlib AST reads source
files as bytes without importing forex_trading or invoking source functions.
The declared A04 PortSchemas are only synthetic future field claims.
A shape comparison is NOT a working adapter, executable schema transform,
vendor entitlement, detector/TP strategy or a broker fill.
"""
from __future__ import annotations

import ast
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from tools.a04_p06_runtime_seams import _declaration_signature

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "forex_trading"
PIN = ROOT / "docs" / "MFX_A04_P09_CALLABLE_ABI_GAP_BASELINE.json"

FROZEN = "7e1c1c012b1b189be5ad7b9d07756eac012a8309"
P02_GOLDEN = "747d029192e080f88b214c76967fa9b91c8e1283f6a4464673cb2bff0b4eabb2"
P02_GRAPH = "fee5c25ab04139a3da502ebc372d981946c1e1e22965fb36987915220cff9ebe"
P06_GRAPH = "734f1fda1e590ab1e5341e53b05ce31631b139f0108f7407227c87088b65cb47"
P07_CASE = "6ccb082b7940a3bb5c2c27d86151cde1874c6f791eb02cfeac12cf94c2ff49f5"
P08_MATRIX = "068353f91a8131f5f7750c77e46ad041c1e046af9c54a1e557a616c23ab9d463"

# Seven previously measured pure function references ONLY. No TP executable.
REFERENCE_ROLES: tuple[tuple[str, str, str], ...] = (
    ("quotes", "indicative_price", "PROVIDER"),
    ("market_data", "evaluate_closed_bar", "PROVIDER"),
    ("market_data", "select_asof_revision", "PROVIDER"),
    ("cache_indicators", "ema_full", "INDICATOR"),
    ("cache_indicators", "ema_recompute", "INDICATOR"),
    ("catalog", "catalog_counts", "DETECTOR"),
    ("catalog", "validate_catalog", "DETECTOR"),
)
EXPECTED_PORTS: dict[str, tuple[str, str]] = {
    "PROVIDER": ("PROVIDER_QUERY_V1", "PROVIDER_READONLY_UNVERIFIED_V1"),
    "INDICATOR": ("PROVIDER_READONLY_UNVERIFIED_V1", "FEATURES_UNVERIFIED_V1"),
    "DETECTOR": ("FEATURES_UNVERIFIED_V1", "CANDIDATES_UNVERIFIED_V1"),
    "TP_POLICY": ("CANDIDATES_UNVERIFIED_V1", "TP_PROPOSAL_UNVERIFIED_V1"),
}
DENIED: tuple[str, ...] = (
    "source_code_executed", "plugin_runtime_bound", "port_callables_compatible",
    "native_bid_ask_rights_verified", "numeric_18_zone_detector_verified",
    "tp_sl_engine_verified", "may_write_real_cache", "may_trade_or_release",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _sha(value: bytes) -> str:
    return sha256(value).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("A04P09_REQUIRED_PINNED_SOURCE_MISSING")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("A04P09_UNTYPED_PINNED_SOURCE")
    return value


def _attr(node: ast.AST, parent: str) -> str:
    if not isinstance(node, ast.Attribute) or not isinstance(
            node.value, ast.Name) or node.value.id != parent:
        raise ValueError("A04P09_UNTRUSTED_ENUM_SCHEMA_AST")
    return node.attr


def _tuple_strings(node: ast.AST) -> tuple[str, ...]:
    if not isinstance(node, ast.Tuple) or any(
            not isinstance(x, ast.Constant) or not isinstance(x.value, str)
            for x in node.elts):
        raise ValueError("A04P09_UNTRUSTED_FIELD_AST")
    names = tuple(x.value for x in node.elts if isinstance(x, ast.Constant))
    if len(set(names)) != len(names):
        raise ValueError("A04P09_DUPLICATE_PORT_FIELD")
    return names


def _declared_ports(path: Path) -> dict[str, tuple[str, str]]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("A04P09_PORT_SOURCE_NOT_REGULAR")
    module = ast.parse(path.read_bytes(), filename=path.name)
    assignments = [n for n in module.body if isinstance(n, ast.AnnAssign)
                   and isinstance(n.target, ast.Name)
                   and n.target.id == "PORT_SIGNATURE"]
    if len(assignments) != 1 or not isinstance(
            assignments[0].value, ast.Dict):
        raise ValueError("A04P09_MISSING_EXACT_PORT_SIGNATURE")
    assignment = assignments[0].value
    result: dict[str, tuple[str, str]] = {}
    for key, pair in zip(assignment.keys, assignment.values):
        if key is None or not isinstance(pair, ast.Tuple) or len(pair.elts) != 2:
            raise ValueError("A04P09_INVALID_PORT_PAIR")
        role = _attr(key, "PluginKind")
        if role in result:
            raise ValueError("A04P09_DUPLICATE_PORT_ROLE")
        result[role] = (
            _attr(pair.elts[0], "PortSchema"),
            _attr(pair.elts[1], "PortSchema"),
        )
    if result != EXPECTED_PORTS or len(assignment.keys) != 4:
        raise ValueError("A04P09_FUTURE_PORT_SIGNATURE_DRIFT")
    return result


def _declared_fields(path: Path) -> dict[str, dict[str, tuple[str, ...]]]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("A04P09_SCHEMA_SOURCE_NOT_REGULAR")
    module = ast.parse(path.read_bytes(), filename=path.name)
    funcs = [x for x in module.body if isinstance(x, ast.FunctionDef)
             and x.name == "synthetic_baseline_contracts"]
    if len(funcs) != 1:
        raise ValueError("A04P09_MISSING_SYNTHETIC_SCHEMA_DECLARATION")
    assignments = [x for x in funcs[0].body if isinstance(x, ast.AnnAssign)
                   and isinstance(x.target, ast.Name)
                   and x.target.id == "fields"]
    if len(assignments) != 1 or not isinstance(
            assignments[0].value, ast.Tuple):
        raise ValueError("A04P09_EXPECT_STATIC_FIVE_PORT_FIELDS")
    output: dict[str, dict[str, tuple[str, ...]]] = {}
    declaration = assignments[0].value
    for row in declaration.elts:
        if not isinstance(row, ast.Tuple) or len(row.elts) != 3:
            raise ValueError("A04P09_INVALID_DECLARED_FIELD_ROW")
        name = _attr(row.elts[0], "PortSchema")
        if name in output:
            raise ValueError("A04P09_DUPLICATE_SCHEMA_FIELDS")
        required = _tuple_strings(row.elts[1])
        optional = _tuple_strings(row.elts[2])
        if not required or set(required) & set(optional):
            raise ValueError("A04P09_MALFORMED_REQUIRED_OPTIONAL_FIELDS")
        output[name] = {"required": required, "optional": optional}
    if len(output) != 5 or set(output) != {
            schema for pair in EXPECTED_PORTS.values() for schema in pair}:
        raise ValueError("A04P09_NOT_FIVE_DECLARED_SCHEMAS")
    return output


def _source_signature(
    path: Path, function: str, expected_sha: str, expected_ast_sha: str,
) -> dict[str, Any]:
    """Actual AST only. Do not execute/instantiate/trust third-party code."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("A04P09_SOURCE_FILE_NOT_REGULAR")
    data = path.read_bytes()
    if _sha(data) != expected_sha:
        raise ValueError("A04P09_FROZEN_SOURCE_BYTES_DRIFT")
    tree = ast.parse(data, filename=path.name)
    defs = [x for x in tree.body if isinstance(
        x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x.name == function]
    if len(defs) != 1 or _declaration_signature(defs[0]) != expected_ast_sha:
        raise ValueError("A04P09_SOURCE_FUNCTION_SIGNATURE_DRIFT")
    node = defs[0]
    args = node.args
    if args.vararg or args.kwarg or args.posonlyargs or isinstance(
            node, ast.AsyncFunctionDef):
        raise ValueError("A04P09_UNREVIEWED_CALLABLE_PARAMETER_MODE")
    pos_required = len(args.args) - len(args.defaults)
    if pos_required < 0 or len(args.kwonlyargs) != len(args.kw_defaults):
        raise ValueError("A04P09_MALFORMED_CALLABLE_DEFAULTS")
    params: list[dict[str, Any]] = []
    for idx, arg in enumerate(args.args):
        params.append({
            "name": arg.arg, "mode": "POSITIONAL_OR_KEYWORD",
            "required": idx < pos_required,
            "annotation": ast.unparse(arg.annotation)
            if arg.annotation is not None else None,
        })
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        params.append({
            "name": arg.arg, "mode": "KEYWORD_ONLY",
            "required": default is None,
            "annotation": ast.unparse(arg.annotation)
            if arg.annotation is not None else None,
        })
    if len(params) != len({p["name"] for p in params}):
        raise ValueError("A04P09_DUPLICATE_SOURCE_PARAMETER")
    return {
        "source_params": params,
        "source_return_annotation": ast.unparse(node.returns)
        if node.returns is not None else None,
        "source_ast_signature_sha256": expected_ast_sha,
        "source_file_sha256": expected_sha,
    }


def _ancestors() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    p02 = _read_json(ROOT / "docs/MFX_A04_P02_GOLDEN_GROUP_BASELINE.json")
    p03 = _read_json(ROOT / "docs/MFX_A04_P03_COMPAT_MATRIX_BASELINE.json")
    p06 = _read_json(ROOT / "docs/MFX_A04_P06_RUNTIME_SEAM_BASELINE.json")
    p07 = _read_json(ROOT / "docs/MFX_A04_P07_SOURCE_WRAPPER_BASELINE.json")
    p08 = _read_json(ROOT / "docs/MFX_A04_P08_SEAM_AUTHORITY_BASELINE.json")
    def observed(v: dict[str, Any], field: str) -> dict[str, Any]:
        x = v.get(field)
        if not isinstance(x, dict):
            raise ValueError("A04P09_MISSING_ANCESTOR_EVIDENCE")
        return x

    a, b, c, d, e = (
        observed(p02, "measured"), observed(p03, "observed"),
        observed(p06, "observed"), observed(p07, "observed"),
        observed(p08, "observed"),
    )
    if (p02.get("frozen_forex_source_commit") != FROZEN
            or p03.get("frozen_forex_commit") != FROZEN
            or p06.get("original_forex_source_commit") != FROZEN
            or p07.get("original_forex_source_commit") != FROZEN
            or p08.get("frozen_forex_source_commit") != FROZEN
            or a.get("frozen_golden_sha256") != P02_GOLDEN
            or a.get("adapter_graph_sha256") != P02_GRAPH
            or b.get("frozen_original_golden_sha256") != P02_GOLDEN
            or b.get("frozen_declared_graph_sha256") != P02_GRAPH
            or c.get("relative_import_graph_sha256") != P06_GRAPH
            or c.get("source_module_count") != 30
            or d.get("case_sha256") != P07_CASE
            or d.get("case_count") != 34
            or e.get("matrix_sha256") != P08_MATRIX
            or e.get("working_runtime_adapter_count") != 0):
        raise ValueError("A04P09_ANCESTOR_SOURCE_OR_ECONOMIC_LOCK_DRIFT")
    return c, a, e


def inspect_callable_gaps() -> dict[str, Any]:
    p06, _, _ = _ancestors()
    observed_files = p06.get("source_file_sha256")
    anchors = p06.get("verified_source_symbol_anchors")
    if not isinstance(observed_files, dict) or len(observed_files) != 30:
        raise ValueError("A04P09_MISSING_REAL_SOURCE_HASHES")
    if not isinstance(anchors, dict):
        raise ValueError("A04P09_MISSING_REAL_AST_SIGNATURES")
    signatures: dict[str, str] = {}
    for group in anchors.values():
        if not isinstance(group, list):
            raise ValueError("A04P09_BAD_AST_GROUP")
        for rec in group:
            if not isinstance(rec, dict):
                raise ValueError("A04P09_BAD_AST_ENTRY")
            key = str(rec.get("module")) + "." + str(rec.get("symbol"))
            sha = rec.get("signature_sha256")
            if key in signatures or not isinstance(sha, str) or len(sha) != 64:
                raise ValueError("A04P09_DUPLICATE_OR_INVALID_AST_SIGNATURE")
            signatures[key] = sha

    parsed_ports = _declared_ports(ROOT / "tools/a04_adapter_conformance.py")
    schemas = _declared_fields(ROOT / "tools/a04_contract_migration.py")
    rows: list[dict[str, Any]] = []
    for module, symbol, role in REFERENCE_ROLES:
        key = module + "." + symbol
        byte_sha = observed_files.get(module + ".py")
        ast_sha = signatures.get(key)
        if not isinstance(byte_sha, str) or not isinstance(ast_sha, str):
            raise ValueError("A04P09_SOURCE_PIN_UNAVAILABLE:" + key)
        source = _source_signature(
            SOURCE / (module + ".py"), symbol, byte_sha, ast_sha)
        incoming, outgoing = parsed_ports[role]
        accepted_fields = schemas[incoming]
        source_names = {x["name"] for x in source["source_params"]}
        required = set(accepted_fields["required"])
        optional = set(accepted_fields["optional"])
        rows.append({
            "reference_function": key,
            "role_vicinity_not_adapter": role,
            "future_input_schema": incoming,
            "future_output_schema": outgoing,
            "future_required_input_fields": sorted(required),
            "future_optional_input_fields": sorted(optional),
            "source_parameters": source["source_params"],
            "source_return_annotation": source["source_return_annotation"],
            "source_ast_signature_sha256": ast_sha,
            "source_file_sha256": byte_sha,
            "missing_required_port_input_fields": sorted(required - source_names),
            "source_only_parameter_names": sorted(source_names - required - optional),
            "return_port_schema_fields_not_proven": sorted(
                schemas[outgoing]["required"]),
            "direct_callable_port_compatible": False,
            "needs_separately_reviewed_explicit_mapper": True,
            "review_status": "A04P09_STATIC_GAP_ONLY_NO_RUNTIME_COMPATIBILITY",
        })
    if (len(rows) != 7 or
            {r["reference_function"] for r in rows} != {
                m + "." + f for m, f, _ in REFERENCE_ROLES}):
        raise ValueError("A04P09_SEVEN_ACTUAL_SOURCE_FUNCTIONS_REQUIRED")
    for row in rows:
        if not row["missing_required_port_input_fields"] or (
                not row["return_port_schema_fields_not_proven"]):
            raise ValueError("A04P09_UNEXPECTED_ZERO_GAP_REQUIRES_NEW_REVIEW")
    counts = {role: sum(x["role_vicinity_not_adapter"] == role
                        for x in rows) for role in EXPECTED_PORTS}
    if counts != {"PROVIDER": 3, "INDICATOR": 2,
                  "DETECTOR": 2, "TP_POLICY": 0}:
        raise ValueError("A04P09_UNREVIEWED_ROLE_COVERAGE")
    report: dict[str, Any] = {
        "kind": "MFX_A04_P09_ACTUAL_AST_VS_FUTURE_PORT_SHAPE_GAPS",
        "source_reference_count": len(rows),
        "declared_future_schema_count": len(schemas),
        "declared_future_port_kind_count": len(parsed_ports),
        "role_reference_counts": counts,
        "source_to_port_direct_compatible_count": 0,
        "required_mapper_review_count": len(rows),
        "missing_tp_policy_reference_count": 1,
        "rows_sha256": _sha(_canonical(rows)),
        "future_port_shapes_sha256": _sha(_canonical(schemas)),
        "future_port_routes_sha256": _sha(_canonical(parsed_ports)),
        "source_gap_rows": rows,
    }
    report.update({name: False for name in DENIED})
    report["no_source_imported_or_executed_during_ast_audit"] = True
    return report


def verify_pinned(report: dict[str, Any], baseline: dict[str, Any]) -> None:
    if (baseline.get("schema_version") != 1
            or baseline.get("kind") != "MFX_A04_P09_PINNED_CALLABLE_PORT_GAPS"
            or baseline.get("frozen_forex_source_commit") != FROZEN):
        raise ValueError("A04P09_PINNED_SOURCE_IDENTITY_DRIFT")
    expected = baseline.get("observed")
    if not isinstance(expected, dict):
        raise ValueError("A04P09_EXPECTED_AST_EVIDENCE_MISSING")
    for field in ("kind", "source_reference_count",
                  "declared_future_schema_count", "declared_future_port_kind_count",
                  "role_reference_counts", "source_to_port_direct_compatible_count",
                  "required_mapper_review_count", "missing_tp_policy_reference_count",
                  "rows_sha256", "future_port_shapes_sha256",
                  "future_port_routes_sha256", "source_gap_rows"):
        if report.get(field) != expected.get(field):
            raise ValueError("A04P09_FROZEN_CALLABLE_PORT_SHAPE_DRIFT:" + field)
    if (report.get("source_reference_count") != 7 or
            report.get("source_to_port_direct_compatible_count") != 0 or
            report.get("required_mapper_review_count") != 7 or
            report.get("missing_tp_policy_reference_count") != 1):
        raise ValueError("A04P09_UNAUTHORIZED_CALLABLE_COMPATIBILITY_CLAIM")
    if baseline.get("required_false_flags") != list(DENIED):
        raise ValueError("A04P09_BASELINE_AUTHORITY_WEAKENED")
    for flag in DENIED:
        if report.get(flag) is not False:
            raise ValueError("A04P09_FORBIDDEN_RUNTIME_AUTHORITY:" + flag)
    if report.get("no_source_imported_or_executed_during_ast_audit") is not True:
        raise ValueError("A04P09_SOURCE_EXECUTION_BOUNDARY_CHANGED")
