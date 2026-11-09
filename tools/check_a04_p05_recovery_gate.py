"""A04/P0.5 deterministic offline schema selection/recovery policy matrix.

No Git mutation or app/provider import beyond inert schema declarations.
Run on GitHub-hosted CI after independently pinned A04/P0.4 gates.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from tools.a04_adapter_conformance import PortSchema
from tools.a04_contract_migration import (
    ContractSnapshot, replace_schema, synthetic_baseline_contracts,
)
from tools.a04_p05_recovery_selection import (
    IntegrationFacts, RecoveryFacts, review_integration_readiness,
    review_protected_recovery, select_exact_schema_declaration,
)

ROOT = Path(__file__).resolve().parents[1]
P03 = ROOT / "docs" / "MFX_A04_P03_COMPAT_MATRIX_BASELINE.json"
P04 = ROOT / "docs" / "MFX_A04_P04_CANARY_GIT_DRILL_BASELINE.json"
BASELINE_FILE = ROOT / "docs" / "MFX_A04_P05_RECOVERY_SELECTION_BASELINE.json"


def _json_file(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("A04P5_PINNED_FILE_NOT_AVAILABLE")
    v = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(v, dict):
        raise ValueError("A04P5_PINNED_FILE_NOT_OBJECT")
    return v


def _seed() -> tuple[ContractSnapshot, ContractSnapshot, dict[str, str]]:
    p3, p4 = _json_file(P03), _json_file(P04)
    p3o, p4o = p3.get("observed"), p4.get("observed")
    if not isinstance(p3o, dict) or not isinstance(p4o, dict):
        raise ValueError("A04P5_MISSING_OBSERVED_ANCESTOR")
    p4g, p4c = p4o.get("git"), p4o.get("canary")
    if not isinstance(p4g, dict) or not isinstance(p4c, dict):
        raise ValueError("A04P5_MISSING_GIT_AND_CANARY_EVIDENCE")
    if (
        p3.get("kind") != "MFX_A04_P03_PINNED_DECLARATIVE_SCHEMA_MATRIX"
        or p4.get("kind") != "MFX_A04_P04_PINNED_DISPOSABLE_GIT_CANARY"
        or p3.get("frozen_forex_commit")
           != "7e1c1c012b1b189be5ad7b9d07756eac012a8309"
        or p4.get("original_forex_commit")
           != "7e1c1c012b1b189be5ad7b9d07756eac012a8309"
        or p3o.get("case_count") != 14
        or p3o.get("blocked_count") != 11
        or p4c.get("case_count") != 19
        or p4c.get("blocked_count") != 16
        or p4g.get("isolated_baseline_tree_sha")
           != p4g.get("isolated_restored_tree_sha")
        or p4o.get("frozen_schema_matrix_sha256")
           != p3o.get("case_matrix_sha256")
    ):
        raise ValueError("A04P5_PREVIOUS_PINNED_GATES_DRIFT")
    graph = p3o.get("frozen_declared_graph_sha256")
    golden = p3o.get("frozen_original_golden_sha256")
    if not isinstance(graph, str) or not isinstance(golden, str):
        raise ValueError("A04P5_INVALID_PREVIOUS_DIGEST")
    previous = synthetic_baseline_contracts(graph, golden)
    if previous.identity_sha256 != p3o.get("base_declaration_sha256"):
        raise ValueError("A04P5_SCHEMA_IDENTITY_NOT_FROZEN")
    target_schema = next(
        s for s in previous.schemas if s.schema is PortSchema.PROVIDER_QUERY_V1
    )
    changed = replace_schema(
        previous, replace(
            target_schema, minor=1,
            optional_fields=target_schema.optional_fields + ("synthetic_note",),
        ),
    )
    return previous, changed, {
        "golden": golden,
        "graph": graph,
        "matrix": p3o["case_matrix_sha256"],
        "canary": p4c["case_matrix_sha256"],
        "initial": previous.identity_sha256,
    }


def run_matrix() -> dict[str, Any]:
    previous, changed, hashes = _seed()
    base = RecoveryFacts(
        "ngluonghoa/MFX",
        "a"*40, "a"*40, "b"*40, "c"*40,
        True, True, True, True, True,
    )
    evidence = IntegrationFacts(True, True, True, True, True, True)
    schema = PortSchema.PROVIDER_QUERY_V1

    cases: list[tuple[str, bool, str]] = []
    def record(name: str, good: bool, reason: str) -> None:
        cases.append((name, good, reason))

    recovery = [
        ("recovery_new_branch_review", base),
        ("recovery_main_moved", replace(base, observed_main_sha="f"*40)),
        ("recovery_wrong_repository", replace(base, project_repository="other/MFX")),
        ("recovery_unprotected", replace(base, protected_main=False)),
        ("recovery_competing_pr", replace(base, zero_competing_prs=False)),
        ("recovery_unreviewed_dependency", replace(base, dependency_revert_reviewed=False)),
        ("recovery_source_unfrozen", replace(base, original_102_blob_source_frozen=False)),
        ("recovery_ci_missing", replace(base, previous_ci_three_of_three=False)),
        ("recovery_force_push", replace(base, force_push_requested=True)),
        ("recovery_direct_main_write", replace(base, direct_main_write_requested=True)),
        ("recovery_production_redeploy", replace(base, production_redeploy_requested=True)),
    ]
    for name, facts in recovery:
        result = review_protected_recovery(facts)
        if any((
            result.may_write_remote_git, result.may_reset_or_force_main,
            result.may_redeploy_production, result.may_release_or_trade,
        )):
            raise ValueError("A04P5_RECOVERY_WRONGLY_GRANTED_AUTHORITY")
        record(name, result.new_branch_pr_reviewable, result.reason)

    selections = [
        ("schema_exact_baseline", (previous,), 1, 0, False),
        ("schema_exact_additive", (changed,), 1, 1, False),
        ("schema_unlisted_minor", (previous,), 1, 1, False),
        ("schema_implicit_fallback", (previous,), 1, 0, True),
        ("schema_ambiguous", (previous, previous), 1, 0, False),
        ("schema_major_mismatch", (previous,), 2, 0, False),
        ("schema_older_minor_fallback", (changed,), 1, 0, False),
        ("schema_mixed_declared", (previous, changed), 1, 1, False),
    ]
    for name, options, major, minor, fallback in selections:
        choice = select_exact_schema_declaration(
            previous, options, schema, major, minor,
            allow_implicit_fallback=fallback,
        )
        if (choice.runtime_schema_applied or choice.automatic_fallback_performed
                or choice.may_import_plugin or choice.may_trade):
            raise ValueError("A04P5_SCHEMA_SELECTOR_GRANTED_RUNTIME_AUTHORITY")
        record(name, choice.structural_reviewable, choice.reason)

    decisions = [
        ("architecture_doc_only", evidence),
        ("integration_golden_missing", replace(evidence, frozen_golden_50=False)),
        ("integration_security_missing", replace(evidence, source_security_gates=False)),
        ("integration_unverified_source_delta", replace(evidence, source_delta_approved=True)),
        ("integration_unverified_rights", replace(evidence, provider_rights_qualified=True)),
        ("integration_broker_semantics_claim", replace(evidence, real_execution_semantics_verified=True)),
        ("integration_request_activate", replace(evidence, runtime_plugin_activation_requested=True)),
        ("integration_request_real_feed", replace(evidence, actual_market_data_requested=True)),
        ("integration_request_broker", replace(evidence, broker_orders_requested=True)),
    ]
    for name, integration_facts in decisions:
        integration_result = review_integration_readiness(integration_facts)
        if (integration_result.runtime_integration_authorized
                or integration_result.production_canary_authorized
                or integration_result.may_fetch_real_data
                or integration_result.may_execute_orders):
            raise ValueError("A04P5_INTEGRATION_WRONGLY_GRANTED_AUTHORITY")
        record(name, integration_result.documentation_reviewable,
               integration_result.reason)

    passed = sum(1 for _, x, _ in cases if x)
    if len(cases) != 28 or passed != 5:
        raise ValueError("A04P5_MATRIX_SCOPE_REGRESSION")
    row_dicts = [
        {"case": name, "reviewable": reviewable, "reason": reason}
        for name, reviewable, reason in cases
    ]
    fingerprint = sha256(json.dumps(
        row_dicts, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        "kind": "MFX_A04_P05_PROTECTED_RECOVERY_SCHEMA_SELECTION_GATE",
        "cases": len(cases),
        "review_only": passed,
        "blocked": len(cases)-passed,
        "case_matrix_sha256": fingerprint,
        "previous_pinned_shas": hashes,
        "synthetic_candidate_version": "1.1",
        "no_real_git_write": True,
        "no_runtime_plugin_execution": True,
        "no_automatic_schema_fallback": True,
        "no_source_changes": True,
        "no_real_provider_io": True,
        "no_trades_or_release": True,
    }


def verify_pinned_report(report: dict[str, Any],
                         baseline: dict[str, Any]) -> None:
    if baseline.get("schema_version") != 1 or baseline.get("kind") != (
            "MFX_A04_P05_PINNED_PROTECTED_RECOVERY_SCHEMA_GATE"):
        raise ValueError("A04P5_INVALID_BASELINE_IDENTITY")
    expected = baseline.get("observed")
    if not isinstance(expected, dict):
        raise ValueError("A04P5_MISSING_PINNED_OBSERVATION")
    for key in ("cases", "review_only", "blocked", "case_matrix_sha256",
                "previous_pinned_shas", "synthetic_candidate_version"):
        if report.get(key) != expected.get(key):
            raise ValueError("A04P5_PINNED_MATRIX_DRIFT:" + key)
    if report.get("kind") != (
            "MFX_A04_P05_PROTECTED_RECOVERY_SCHEMA_SELECTION_GATE"
    ) or report.get("cases") != 28 or report.get("review_only") != 5 or (
            report.get("blocked") != 23):
        raise ValueError("A04P5_PINNED_MATRIX_BUDGET")
    fields = baseline.get("required_true_flags")
    if fields != [
        "no_real_git_write", "no_runtime_plugin_execution",
        "no_automatic_schema_fallback", "no_source_changes",
        "no_real_provider_io", "no_trades_or_release",
    ]:
        raise ValueError("A04P5_UNAUTHORIZED_BASELINE_POLICY")
    for key in fields:
        if report.get(key) is not True:
            raise ValueError("A04P5_UNAUTHORIZED_OPERATION:" + key)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-measure", action="store_true")
    args = parser.parse_args()
    report = run_matrix()
    if args.bootstrap_measure:
        print("MFX_A04_P05_BOOTSTRAP_UNPINNED " + json.dumps(
            report, sort_keys=True, separators=(",", ":"),
        ))
        return
    baseline = _json_file(BASELINE_FILE)
    verify_pinned_report(report, baseline)
    print("MFX_A04_P05_PINNED_NO_RUNTIME_GATE_PASS")
    print("MFX_A04_P05_RECEIPT " + json.dumps(
        report, sort_keys=True, separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
