"""A04/P0.3: bounded deterministic schema compatibility / rollback matrix.

Consumes the SHA-pinned A04/P0.2 golden baseline from this GitHub checkout;
replays ONLY immutable synthetic declaration bytes. Does not invoke plugins,
perform a Git rollback, access providers, persist cache or trade.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from tools.a04_contract_migration import (
    ContractSnapshot, SchemaClaim, assess_transition, decode_snapshot,
    encode_snapshot, replace_schema, review_declarative_rollback,
    synthetic_baseline_contracts,
)
from tools.a04_adapter_conformance import PortSchema

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_BASELINE = ROOT / "docs" / "MFX_A04_P02_GOLDEN_GROUP_BASELINE.json"


def _read_goldens() -> dict[str, Any]:
    if not GOLDEN_BASELINE.is_file() or GOLDEN_BASELINE.is_symlink():
        raise ValueError("A04P3_FROZEN_GOLDEN_FILE_UNAVAILABLE")
    contents = json.loads(GOLDEN_BASELINE.read_text(encoding="utf-8"))
    measured = contents.get("measured")
    if (contents.get("schema_version") != 1
            or contents.get("kind")
            != "MFX_A04_P02_PINNED_SYNTHETIC_GOLDEN_GROUP_BASELINE"
            or contents.get("frozen_forex_source_commit")
            != "7e1c1c012b1b189be5ad7b9d07756eac012a8309"
            or not isinstance(measured, dict)
            or measured.get("synthetic_scenario_count") != 50
            or measured.get("contract_group_count") != 8):
        raise ValueError("A04P3_FROZEN_GOLDEN_IDENTITY_DRIFT")
    return measured


def _edit(snap: ContractSnapshot, schema: PortSchema,
          **updates: Any) -> ContractSnapshot:
    old = next(x for x in snap.schemas if x.schema is schema)
    return replace_schema(snap, replace(old, **updates))


def run_matrix() -> dict[str, Any]:
    pinned = _read_goldens()
    before = synthetic_baseline_contracts(
        pinned["adapter_graph_sha256"], pinned["frozen_golden_sha256"],
    )
    snapshot_bytes = encode_snapshot(before)
    decoded = decode_snapshot(snapshot_bytes)
    if decoded.identity_sha256 != before.identity_sha256:
        raise ValueError("A04P3_BASELINE_REPLAY_IDENTITY_DRIFT")
    reference = next(x for x in before.schemas
                     if x.schema is PortSchema.PROVIDER_QUERY_V1)
    features = next(x for x in before.schemas
                    if x.schema is PortSchema.FEATURES_UNVERIFIED_V1)
    additive = _edit(
        before, reference.schema, minor=1,
        optional_fields=reference.optional_fields + ("synthetic_note",),
    )
    additive_two = _edit(
        additive, features.schema, minor=1,
        optional_fields=("analysis_note",),
    )
    cases: tuple[tuple[str, ContractSnapshot, str], ...] = (
        ("exact_noop", before, "A04P3_EXACT_DECLARATION_NOOP"),
        ("optional_minor_one", additive,
         "A04P3_ADDITIVE_SHAPE_REVIEW_ONLY_NOT_APPROVED"),
        ("optional_minor_two", additive_two,
         "A04P3_ADDITIVE_SHAPE_REVIEW_ONLY_NOT_APPROVED"),
        ("major_changed", _edit(before, reference.schema, major=2),
         "A04P3_SCHEMA_MAJOR_DRIFT"),
        ("semantic_changed", _edit(
            before, reference.schema, semantic_sha256_claim="b"*64),
         "A04P3_SEMANTIC_CLAIM_DRIFT"),
        ("required_added", _edit(before, reference.schema,
            required_fields=reference.required_fields + ("z_critical",)),
         "A04P3_REQUIRED_FIELDS_CHANGED"),
        ("required_removed", _edit(before, reference.schema,
            required_fields=reference.required_fields[:-1]),
         "A04P3_REQUIRED_FIELDS_CHANGED"),
        ("optional_removed", _edit(before, reference.schema,
            optional_fields=(), minor=1),
         "A04P3_OPTIONAL_FIELD_REMOVED"),
        ("unversioned_optional", _edit(before, reference.schema,
            optional_fields=reference.optional_fields + ("synthetic_note",)),
         "A04P3_UNVERSIONED_FIELD_DRIFT"),
        ("minor_no_change", _edit(before, reference.schema, minor=1),
         "A04P3_NON_ADDITIVE_MINOR"),
        ("minor_skip", _edit(before, reference.schema, minor=2,
            optional_fields=reference.optional_fields + ("synthetic_note",)),
         "A04P3_NON_ADDITIVE_MINOR"),
        ("minor_downgrade", _edit(before, reference.schema, minor=1,
            optional_fields=reference.optional_fields + ("synthetic_note",)),
         "A04P3_ADDITIVE_SHAPE_REVIEW_ONLY_NOT_APPROVED"),
        ("graph_drift", replace(before, graph_sha256="b"*64),
         "A04P3_PLUGIN_GRAPH_OR_ABI_DRIFT"),
        ("golden_drift", replace(before, golden_sha256="b"*64),
         "A04P3_FROZEN_GOLDEN_BASELINE_DRIFT"),
    )
    observed: list[dict[str, Any]] = []
    reasons: dict[str, int] = {}
    for case_id, proposed, expected in cases:
        outcome = assess_transition(before, proposed)
        if outcome.reason != expected:
            raise ValueError("A04P3_MATRIX_CASE_UNEXPECTED:" + case_id)
        reasons[outcome.reason] = reasons.get(outcome.reason, 0) + 1
        observed.append({
            "case": case_id,
            "before_sha256": outcome.before_sha256,
            "after_sha256": outcome.after_sha256,
            "reason": outcome.reason,
            "reviewable": outcome.declaration_reviewable,
            "exact_noop": outcome.exact_noop,
        })
    rollback_ok = review_declarative_rollback(
        before, additive, decode_snapshot(encode_snapshot(before)),
    )
    rollback_bad = review_declarative_rollback(before, additive, additive)
    if not rollback_ok.declaration_rollback_reproducible or (
            rollback_bad.declaration_rollback_reproducible):
        raise ValueError("A04P3_ROLLBACK_FIXTURE_INTEGRITY_FAILED")
    report = {
        "kind": "MFX_A04_P03_INERT_SCHEMA_COMPATIBILITY_MATRIX",
        "schema_family_count": len(before.schemas),
        "case_count": len(observed),
        "reviewable_count": sum(1 for c in observed if c["reviewable"]),
        "blocked_count": sum(1 for c in observed if not c["reviewable"]),
        "unchanged_count": sum(1 for c in observed if c["exact_noop"]),
        "declarative_rollback_exact_match": rollback_ok.declaration_rollback_reproducible,
        "declarative_rollback_wrong_target_rejected":
            not rollback_bad.declaration_rollback_reproducible,
        "frozen_original_golden_sha256": before.golden_sha256,
        "frozen_declared_graph_sha256": before.graph_sha256,
        "base_declaration_sha256": before.identity_sha256,
        "case_matrix_sha256": sha256(json.dumps(
            observed, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
        "reasons": {k: reasons[k] for k in sorted(reasons)},
        "schema_transform_executed": False,
        "plugin_runtime_executed": False,
        "git_rollback_performed": False,
        "real_data_used": False,
        "may_deploy_or_trade": False,
    }
    if (len(observed) != 14 or report["blocked_count"] < 9
            or report["reviewable_count"] < 3):
        raise ValueError("A04P3_MATRIX_BUDGET_REGRESSION")
    return report


def main() -> None:
    print("MFX_A04_P03_COMPAT_MATRIX_OBSERVED " + json.dumps(
        run_matrix(), sort_keys=True, separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
