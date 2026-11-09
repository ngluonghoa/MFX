"""A04/P0.6 — measured AST inventory of the REAL frozen MFX source tree.

This audits checked-out source bytes without importing forex_trading, calling
provider APIs, modifying src/, constructing signals or executing any plugin.
Source SHA256 is a byte digest, NOT evidence of vendor entitlement.
"""
from __future__ import annotations

import ast
from hashlib import sha256
import json
from pathlib import Path
import tomllib
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "forex_trading"
PROJECT = ROOT / "pyproject.toml"
PIN_FILE = ROOT / "docs" / "MFX_A04_P06_RUNTIME_SEAM_BASELINE.json"

# Verified against real source, these are existing READ-ONLY functions/types,
# not plugin insertion points. Detector and TP runtime implementations absent.
ROLE_ANCHORS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "provider_review_only": (
        ("market_data", "select_asof_revision", "function"),
        ("market_data", "evaluate_closed_bar", "function"),
        ("source_qualification", "assess_source_for_m2_review", "function"),
        ("source_stream_binding", "qualify_snapshot_binding", "function"),
        ("side_pair", "assess_bid_ask_side_pair", "function"),
        ("quotes", "indicative_price", "function"),
    ),
    "indicator_ema_only": (
        ("cache_indicators", "ema_full", "function"),
        ("cache_indicators", "ema_recompute", "function"),
    ),
    "detector_catalog_or_synthetic_only": (
        ("catalog", "validate_catalog", "function"),
        ("catalog", "catalog_counts", "function"),
        ("model", "SignalDisplay", "class"),
        ("scan_selection", "run_selected_synthetic_scan", "function"),
    ),
    "tp_policy_release_review_only": (
        ("release_readiness", "review_release_candidate", "function"),
        ("release_readiness", "preview_full_profile_rollback", "function"),
    ),
}

NO_RUNTIME_AUTHORITY: tuple[str, ...] = (
    "dynamic_plugin_loader_used",
    "a04_tool_imported_by_source",
    "new_runtime_adapter_wired",
    "native_bid_ask_vendor_entitlement_verified",
    "numeric_18_zone_detector_verified",
    "executable_tp_sl_policy_verified",
    "provider_io_performed",
    "trades_or_release_authorized",
)


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _json_hash(value: Any) -> str:
    return _sha(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8"))


def _declaration_signature(node: ast.AST) -> str:
    info: object
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        info = (ast.dump(node.args, include_attributes=False),
                ast.dump(node.returns, include_attributes=False)
                if node.returns is not None else None,
                tuple(ast.dump(x, include_attributes=False) for x in
                      node.decorator_list))
    elif isinstance(node, ast.ClassDef):
        info = (tuple(ast.dump(x, include_attributes=False)
                      for x in node.bases),
                tuple(ast.dump(x, include_attributes=False)
                      for x in node.keywords),
                tuple(ast.dump(x, include_attributes=False)
                      for x in node.decorator_list))
    else:
        raise TypeError("A04P06_ONLY_TYPED_DECLARATIONS")
    return _json_hash(info)


def _direct_names(tree: ast.Module) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            if name in entries:
                raise ValueError("A04P06_DUPLICATED_TOP_LEVEL_DEF:" + name)
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            entries[name] = (kind, _declaration_signature(node))
    return entries


def _dependencies(tree: ast.Module, module: str) -> tuple[str, ...]:
    edges: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            target = node.module or ""
            if node.level:
                if node.level != 1:
                    edges.add("relative-level-" + str(node.level) + ":" + target)
                elif target:
                    edges.add("forex_trading." + target)
                else:
                    for item in node.names:
                        edges.add("forex_trading." + item.name)
            elif target == "tools" or target.startswith("tools."):
                edges.add("UNAUTHORIZED-TOOLS:" + target)
            elif target.startswith("forex_trading"):
                edges.add(target)
        elif isinstance(node, ast.Import):
            for item in node.names:
                if item.name == "tools" or item.name.startswith("tools."):
                    edges.add("UNAUTHORIZED-TOOLS:" + item.name)
                elif item.name.startswith("forex_trading"):
                    edges.add(item.name)
    if any(edge.startswith("UNAUTHORIZED-TOOLS:") for edge in edges):
        raise ValueError("A04P06_SOURCE_IMPORTS_A04_OR_TOOLS:" + module)
    return tuple(sorted(edges))


def _exports(tree: ast.Module) -> tuple[str, ...]:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(x, ast.Name) and x.id == "__all__"
                   for x in node.targets):
                try:
                    x = ast.literal_eval(node.value)
                except (ValueError, TypeError) as exc:
                    raise ValueError("A04P06_PUBLIC_EXPORTS_NOT_STATIC") from exc
                if (not isinstance(x, (list, tuple))
                        or any(not isinstance(t, str) for t in x)):
                    raise ValueError("A04P06_PUBLIC_EXPORTS_NOT_STRINGS")
                return tuple(x)
    raise ValueError("A04P06_NO_PUBLIC_EXPORTS")


def inspect_source(source: Path, pyproject: Path) -> dict[str, Any]:
    """Static inspection only; does not import or instantiate MFX runtime."""
    if source.is_symlink() or not source.is_dir():
        raise ValueError("A04P06_INVALID_SOURCE_DIRECTORY")
    paths = sorted(source.glob("*.py"))
    if len(paths) != 30 or any(p.is_symlink() or not p.is_file() for p in paths):
        raise ValueError("A04P06_EXPECT_EXACTLY_30_UNMODIFIED_CORE_FILES")

    details: dict[str, dict[str, Any]] = {}
    names: dict[str, dict[str, tuple[str, str]]] = {}
    dependencies: dict[str, tuple[str, ...]] = {}
    for path in paths:
        raw = path.read_bytes()
        module = path.stem
        parsed = ast.parse(raw, filename=path.name)
        definitions = _direct_names(parsed)
        names[module] = definitions
        imports = _dependencies(parsed, module)
        dependencies[module] = imports
        details[path.name] = {
            "source_bytes_sha256": _sha(raw),
            "definition_count": len(definitions),
            "relative_source_imports": imports,
        }

    anchors: dict[str, list[dict[str, str]]] = {}
    for role, symbols in ROLE_ANCHORS.items():
        anchors[role] = []
        for module, symbol, expected_kind in symbols:
            found = names.get(module, {}).get(symbol)
            if found is None or found[0] != expected_kind:
                raise ValueError("A04P06_MISSING_REAL_SOURCE_SYMBOL:" +
                                 module + "." + symbol)
            anchors[role].append({
                "module": module,
                "symbol": symbol,
                "declaration_kind": expected_kind,
                "signature_sha256": found[1],
            })

    package_init = ast.parse((source / "__init__.py").read_bytes())
    exported = _exports(package_init)
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    if (project.get("project", {}).get("name") != "mfx-forex-core"
            or project.get("tool", {}).get("setuptools", {})
            .get("packages", {}).get("find", {}).get("where") != ["src"]):
        raise ValueError("A04P06_PACKAGING_OWNERSHIP_CHANGED")
    project_public = project["project"]
    if "scripts" in project_public or "entry-points" in project_public:
        raise ValueError("A04P06_UNREVIEWED_RUNTIME_ENTRYPOINT")
    if any("UNAUTHORIZED-TOOLS:" in dep for v in dependencies.values()
           for dep in v):
        raise ValueError("A04P06_UNAUTHORIZED_SRC_TOOLING_IMPORT")
    return {
        "kind": "MFX_A04_P06_REAL_SRC_AST_SEAM_INVENTORY",
        "source_module_count": len(paths),
        "source_file_sha256": {p: details[p]["source_bytes_sha256"]
                               for p in sorted(details)},
        "all_source_metadata_sha256": _json_hash(details),
        "relative_import_graph_sha256": _json_hash(dependencies),
        "package_name": project_public["name"],
        "pyproject_bytes_sha256": _sha(pyproject.read_bytes()),
        "public_export_count": len(exported),
        "public_export_names": list(exported),
        "candidate_readonly_symbol_count": sum(len(v) for v in anchors.values()),
        "verified_source_symbol_anchors": anchors,
        "role_landing_status": {
            "provider": "READ_ONLY_SOURCE_REVIEW_FUNCTIONS_EXIST_NO_ADAPTER",
            "indicator": "EMA_NUMERIC_HELPERS_EXIST_NO_PLUGIN_INTERFACE",
            "detector": "CATALOG_AND_SYNTHETIC_SCAN_ONLY_NO_18_ZONE_ENGINE_PROOF",
            "tp_policy": "RELEASE_AND_ROLLBACK_REVIEW_ONLY_NO_TP_SL_ENGINE_PROOF",
        },
        "dynamic_plugin_loader_used": False,
        "a04_tool_imported_by_source": False,
        "new_runtime_adapter_wired": False,
        "native_bid_ask_vendor_entitlement_verified": False,
        "numeric_18_zone_detector_verified": False,
        "executable_tp_sl_policy_verified": False,
        "provider_io_performed": False,
        "trades_or_release_authorized": False,
        "no_source_executed_during_inventory": True,
        "ast_only_no_dynamic_reachability_proof": True,
    }


def verify_inventory(report: dict[str, Any],
                     baseline: dict[str, Any]) -> None:
    if (baseline.get("schema_version") != 1 or baseline.get("kind")
            != "MFX_A04_P06_PINNED_REAL_SOURCE_AST_INVENTORY"
            or baseline.get("original_forex_source_commit")
            != "7e1c1c012b1b189be5ad7b9d07756eac012a8309"):
        raise ValueError("A04P06_UNRECOGNIZED_PINNED_SOURCE_IDENTITY")
    expected = baseline.get("observed")
    if not isinstance(expected, dict):
        raise ValueError("A04P06_MISSING_EXPECTED_SOURCE_AUDIT")
    for field in (
        "source_module_count", "source_file_sha256",
        "all_source_metadata_sha256", "relative_import_graph_sha256",
        "package_name", "pyproject_bytes_sha256", "public_export_count",
        "public_export_names", "candidate_readonly_symbol_count",
        "verified_source_symbol_anchors", "role_landing_status",
    ):
        if report.get(field) != expected.get(field):
            raise ValueError("A04P06_PINNED_CORE_INTERFACE_DRIFT:" + field)
    if (report.get("source_module_count") != 30
            or report.get("candidate_readonly_symbol_count") != 14):
        raise ValueError("A04P06_SOURCE_AUDIT_BUDGET_DRIFT")
    denied = baseline.get("required_false_flags")
    if denied != list(NO_RUNTIME_AUTHORITY):
        raise ValueError("A04P06_UNAUTHORIZED_BASELINE_FLAG_CHANGE")
    for key in NO_RUNTIME_AUTHORITY:
        if report.get(key) is not False:
            raise ValueError("A04P06_UNAUTHORIZED_RUNTIME_CLAIM:" + key)
    if (report.get("no_source_executed_during_inventory") is not True
            or report.get("ast_only_no_dynamic_reachability_proof") is not True):
        raise ValueError("A04P06_AST_READONLY_BOUNDARY_LOST")
