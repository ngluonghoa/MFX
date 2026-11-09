"""A04/P0.4 — GitHub-hosted isolated *real git revert* rehearsal.

Runs git init/commit/revert ONLY in a fresh no-remotes temporary repository.
The checked-out MFX project (especially protected main) is read-only.
Never publish, push, fetch, call providers or trade.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any

from tools.a04_canary_contract import (
    CanaryEvidence, SyntheticCanaryStage, assess_synthetic_canary,
)
from tools.a04_adapter_conformance import PortSchema
from tools.a04_contract_migration import (
    ContractSnapshot, assess_transition, decode_snapshot, encode_snapshot,
    replace_schema, synthetic_baseline_contracts,
)

ROOT = Path(__file__).resolve().parents[1]
P02 = ROOT / "docs" / "MFX_A04_P02_GOLDEN_GROUP_BASELINE.json"
P03 = ROOT / "docs" / "MFX_A04_P03_COMPAT_MATRIX_BASELINE.json"
PIN = ROOT / "docs" / "MFX_A04_P04_CANARY_GIT_DRILL_BASELINE.json"
FOREX_SHA = "7e1c1c012b1b189be5ad7b9d07756eac012a8309"


def _json_file(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("A04P4_FROZEN_PINNED_FILE_MISSING")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("A04P4_PINNED_NOT_MAPPING")
    return data


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args), cwd=cwd, capture_output=True, text=True,
        check=True, timeout=20,
    )
    return result.stdout.strip()


def _observed_inputs() -> tuple[ContractSnapshot, ContractSnapshot, dict[str, Any]]:
    p2, p3 = _json_file(P02), _json_file(P03)
    a, b = p2.get("measured"), p3.get("observed")
    if not isinstance(a, dict) or not isinstance(b, dict):
        raise ValueError("A04P4_MISSING_OBSERVED_PINNED_EVIDENCE")
    if (
        p2.get("frozen_forex_source_commit") != FOREX_SHA
        or p2.get("kind") != "MFX_A04_P02_PINNED_SYNTHETIC_GOLDEN_GROUP_BASELINE"
        or p3.get("frozen_forex_commit") != FOREX_SHA
        or p3.get("kind") != "MFX_A04_P03_PINNED_DECLARATIVE_SCHEMA_MATRIX"
        or a.get("synthetic_scenario_count") != 50
        or b.get("case_count") != 14
        or b.get("blocked_count") != 11
        or b.get("declarative_rollback_exact_match") is not True
    ):
        raise ValueError("A04P4_FROZEN_ORIGINAL_PINNED_GATES_DRIFT")
    before = synthetic_baseline_contracts(
        a["adapter_graph_sha256"], a["frozen_golden_sha256"],
    )
    if before.identity_sha256 != b.get("base_declaration_sha256"):
        raise ValueError("A04P4_SCHEMA_SOURCE_SHA_DRIFT")
    ref = next(
        s for s in before.schemas if s.schema is PortSchema.PROVIDER_QUERY_V1
    )
    candidate = replace_schema(
        before, replace(
            ref, minor=1,
            optional_fields=ref.optional_fields + ("synthetic_note",),
        ),
    )
    decision = assess_transition(before, candidate)
    if (not decision.declaration_reviewable or decision.exact_noop
            or decision.reason !=
            "A04P3_ADDITIVE_SHAPE_REVIEW_ONLY_NOT_APPROVED"):
        raise ValueError("A04P4_ADDITIVE_PROPOSAL_NOT_REVIEWABLE")
    return before, candidate, {
        "graph_sha256": a["adapter_graph_sha256"],
        "golden_sha256": a["frozen_golden_sha256"],
        "matrix_sha256": b["case_matrix_sha256"],
    }


def run_disposable_git_revert(
    before: ContractSnapshot,
    candidate: ContractSnapshot,
) -> dict[str, Any]:
    """Actual Git commit/revert in *new* no-remotes repo; NEVER project main."""
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("GITHUB_REPOSITORY") != "ngluonghoa/MFX"):
        raise ValueError("A04P4_GITHUB_HOSTED_ONLY")
    home = ROOT.resolve()
    before_git_head = _git(home, "rev-parse", "HEAD")
    before_git_status = _git(home, "status", "--porcelain")
    before_bytes = encode_snapshot(before)
    candidate_bytes = encode_snapshot(candidate)
    if before_bytes == candidate_bytes:
        raise ValueError("A04P4_MISSING_REAL_DECLARATION_CHANGE")

    with tempfile.TemporaryDirectory(prefix="mfx-a04p4-no-remote-") as tmp:
        path = Path(tmp).resolve()
        if path == home or home in path.parents or path in home.parents:
            raise ValueError("A04P4_DRILL_PATH_NOT_ISOLATED")
        _git(path, "init", "-q", "--initial-branch=drill-main")
        _git(path, "config", "--local", "user.name", "MFX Synthetic CI")
        _git(path, "config", "--local", "user.email", "synthetic-ci@invalid.test")
        if _git(path, "remote"):
            raise ValueError("A04P4_DISPOSABLE_REPO_HAS_REMOTES")
        target = path / "declared-contract.json"
        target.write_bytes(before_bytes)
        _git(path, "add", "--", "declared-contract.json")
        _git(path, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "synthetic-baseline")
        original_tree = _git(path, "rev-parse", "HEAD^{tree}")
        target.write_bytes(candidate_bytes)
        _git(path, "add", "--", "declared-contract.json")
        _git(path, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "synthetic-change")
        mutation_tree = _git(path, "rev-parse", "HEAD^{tree}")
        if mutation_tree == original_tree:
            raise ValueError("A04P4_DISPOSABLE_CHANGE_HAS_NO_TREE_DELTA")
        _git(path, "-c", "commit.gpgsign=false", "revert", "--no-edit", "HEAD")
        restored_tree = _git(path, "rev-parse", "HEAD^{tree}")
        restored_bytes = target.read_bytes()
        if (
            restored_tree != original_tree
            or restored_bytes != before_bytes
            or _git(path, "status", "--porcelain") != ""
            or _git(path, "remote") != ""
            or _git(path, "rev-list", "--count", "HEAD") != "3"
        ):
            raise ValueError("A04P4_DISPOSABLE_GIT_REVERT_MISMATCH")
        if decode_snapshot(restored_bytes).identity_sha256 != before.identity_sha256:
            raise ValueError("A04P4_DECLARATION_IDENTITY_NOT_RESTORED")
    if (_git(home, "rev-parse", "HEAD") != before_git_head
            or _git(home, "status", "--porcelain") != before_git_status):
        raise ValueError("A04P4_PROJECT_CHECKOUT_WAS_MUTATED")
    return {
        "git_drill_executed": True,
        "disposable_git_repo_has_no_remotes": True,
        "git_history_commit_count": 3,
        "isolated_baseline_tree_sha": original_tree,
        "isolated_changed_tree_sha": mutation_tree,
        "isolated_restored_tree_sha": restored_tree,
        "baseline_contract_bytes_sha256": _sha(before_bytes),
        "restored_contract_bytes_sha256": _sha(restored_bytes),
        "project_checkout_head_preserved": True,
        "project_checkout_status_preserved": True,
        "protected_main_reverted": False,
        "remote_git_write_performed": False,
    }


def _evidence(pinned: dict[str, Any]) -> CanaryEvidence:
    return CanaryEvidence(
        project_id="MFX", frozen_forex_sha=FOREX_SHA,
        graph_sha256=pinned["graph_sha256"],
        golden_sha256=pinned["golden_sha256"],
        schema_matrix_sha256=pinned["matrix_sha256"],
        snapshot_restored_exact=True, git_drill_restored_exact=True,
        original_source_parity_passed=True, golden_50_passed=True,
        matrix_14_passed=True, security_gates_passed=True,
    )


def run_canary_matrix(pinned: dict[str, Any]) -> dict[str, Any]:
    good = _evidence(pinned)
    stages = tuple(SyntheticCanaryStage)
    cases: list[tuple[str, SyntheticCanaryStage, SyntheticCanaryStage,
                      CanaryEvidence, str]] = [
        ("baseline_to_shadow", stages[0], stages[1], good,
         "A04P4_SYNTHETIC_STRUCTURAL_REVIEW_ONLY_NOT_APPROVAL"),
        ("shadow_to_small", stages[1], stages[2], good,
         "A04P4_SYNTHETIC_STRUCTURAL_REVIEW_ONLY_NOT_APPROVAL"),
        ("small_to_extended", stages[2], stages[3], good,
         "A04P4_SYNTHETIC_STRUCTURAL_REVIEW_ONLY_NOT_APPROVAL"),
        ("skipped_stage", stages[0], stages[3], good,
         "A04P4_STAGE_SKIP_REPLAY_OR_REVERSE"),
        ("same_stage", stages[2], stages[2], good,
         "A04P4_STAGE_SKIP_REPLAY_OR_REVERSE"),
        ("reverse_stage", stages[3], stages[1], good,
         "A04P4_STAGE_SKIP_REPLAY_OR_REVERSE"),
        ("bad_project", stages[0], stages[1], replace(good, project_id="FOREX"),
         "A04P4_FROZEN_SOURCE_OR_PROJECT_MISMATCH"),
        ("wrong_frozen_source", stages[0], stages[1],
         replace(good, frozen_forex_sha="0"*40),
         "A04P4_FROZEN_SOURCE_OR_PROJECT_MISMATCH"),
        ("graph_drift", stages[0], stages[1],
         replace(good, graph_sha256="a"*64),
         "A04P4_GOLDEN_GRAPH_OR_MATRIX_DRIFT"),
        ("golden_drift", stages[0], stages[1],
         replace(good, golden_sha256="a"*64),
         "A04P4_GOLDEN_GRAPH_OR_MATRIX_DRIFT"),
        ("matrix_drift", stages[0], stages[1],
         replace(good, schema_matrix_sha256="a"*64),
         "A04P4_GOLDEN_GRAPH_OR_MATRIX_DRIFT"),
        ("missing_git_revert", stages[0], stages[1],
         replace(good, git_drill_restored_exact=False),
         "A04P4_MISSING_REQUIRED_GATE"),
        ("missing_security", stages[0], stages[1],
         replace(good, security_gates_passed=False),
         "A04P4_MISSING_REQUIRED_GATE"),
        ("missing_parity", stages[0], stages[1],
         replace(good, original_source_parity_passed=False),
         "A04P4_MISSING_REQUIRED_GATE"),
        ("budget_drift", stages[0], stages[1],
         replace(good, blocked_migration_cases=10),
         "A04P4_SYNTHETIC_EVIDENCE_BUDGET_DRIFT"),
        ("real_activation", stages[0], stages[1],
         replace(good, runtime_activation_requested=True),
         "A04P4_FORBIDDEN_REAL_OPERATION"),
        ("real_data", stages[0], stages[1],
         replace(good, real_data_requested=True),
         "A04P4_FORBIDDEN_REAL_OPERATION"),
        ("provider_fallback", stages[0], stages[1],
         replace(good, automatic_provider_failover=True),
         "A04P4_FORBIDDEN_REAL_OPERATION"),
        ("broker_order", stages[0], stages[1],
         replace(good, broker_order_requested=True),
         "A04P4_FORBIDDEN_REAL_OPERATION"),
    ]
    observed: list[dict[str, Any]] = []
    for name, from_stage, to_stage, evidence, reason in cases:
        decision = assess_synthetic_canary(
            from_stage, to_stage, evidence,
            expected_graph_sha256=pinned["graph_sha256"],
            expected_golden_sha256=pinned["golden_sha256"],
            expected_schema_matrix_sha256=pinned["matrix_sha256"],
        )
        if (decision.reason != reason or decision.may_deploy_or_trade
                or decision.may_change_protected_main
                or decision.may_activate_runtime or decision.may_use_live_provider):
            raise ValueError("A04P4_CANARY_CASE_DRIFT:" + name)
        observed.append({
            "case": name, "from": from_stage.name, "to": to_stage.name,
            "reviewable": decision.structural_reviewable, "reason": reason,
        })
    allowed = sum(1 for o in observed if o["reviewable"])
    blocked = len(observed) - allowed
    if len(observed) != 19 or allowed != 3 or blocked != 16:
        raise ValueError("A04P4_CANARY_REVIEW_MATRIX_BUDGET")
    receipt: dict[str, Any] = {
        "case_count": len(observed),
        "structural_review_only_count": allowed,
        "blocked_count": blocked,
        "stage_count": len(stages),
        "case_matrix_sha256": _sha(json.dumps(
            observed, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")),
        "all_stages_declarative_only": True,
        "real_traffic_shifted": False,
        "provider_adapter_invoked": False,
        "may_deploy_or_trade": False,
    }
    return receipt


def run_drill() -> dict[str, Any]:
    before, candidate, pinned = _observed_inputs()
    git = run_disposable_git_revert(before, candidate)
    canary = run_canary_matrix(pinned)
    return {
        "kind": "MFX_A04_P04_ISOLATED_CLOUD_GIT_REVERT_AND_INERT_CANARY",
        "frozen_original_source_commit": FOREX_SHA,
        "frozen_golden_sha256": pinned["golden_sha256"],
        "frozen_graph_sha256": pinned["graph_sha256"],
        "frozen_schema_matrix_sha256": pinned["matrix_sha256"],
        "git": git,
        "canary": canary,
        "any_real_plugin_executed": False,
        "real_market_data_called": False,
        "real_cache_written": False,
        "protected_main_changed": False,
        "live_release_or_trade_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-measure", action="store_true")
    args = parser.parse_args()
    measured = run_drill()
    if args.bootstrap_measure:
        print("MFX_A04_P04_BOOTSTRAP_MEASURE_NO_PIN " + json.dumps(
            measured, sort_keys=True, separators=(",", ":"),
        ))
        return
    baseline = _json_file(PIN)
    verify_pinned_a04_p04_receipt(measured, baseline)
    print("MFX_A04_P04_PINNED_CLOUD_GIT_REVERT_CANARY_PASS")
    print("MFX_A04_P04_RECEIPT " + json.dumps(
        measured, sort_keys=True, separators=(",", ":"),
    ))


def verify_pinned_a04_p04_receipt(
    measured: dict[str, Any], baseline: dict[str, Any],
) -> None:
    """Pin measured stable rollback tree and 19 synthetic cases, not commit IDs."""
    if (baseline.get("schema_version") != 1
            or baseline.get("kind")
            != "MFX_A04_P04_PINNED_DISPOSABLE_GIT_CANARY"):
        raise ValueError("A04P4_UNRECOGNIZED_PINNED_BASELINE")
    expected = baseline.get("observed")
    if not isinstance(expected, dict):
        raise ValueError("A04P4_PINNED_OBSERVATION_MISSING")
    if measured.get("kind") != (
            "MFX_A04_P04_ISOLATED_CLOUD_GIT_REVERT_AND_INERT_CANARY"):
        raise ValueError("A04P4_INVALID_RECEIPT_KIND")
    for field in (
        "frozen_original_source_commit", "frozen_golden_sha256",
        "frozen_graph_sha256", "frozen_schema_matrix_sha256",
    ):
        if measured.get(field) != expected.get(field):
            raise ValueError("A04P4_PINNED_SOURCE_DRIFT:" + field)
    canary = measured.get("canary")
    git = measured.get("git")
    wanted_c, wanted_g = expected.get("canary"), expected.get("git")
    if (
        not isinstance(canary, dict)
        or not isinstance(git, dict)
        or not isinstance(wanted_c, dict)
        or not isinstance(wanted_g, dict)
    ):
        raise ValueError("A04P4_PINNED_COMPONENT_UNTYPED")
    for key in (
        "case_count", "structural_review_only_count", "blocked_count",
        "stage_count", "case_matrix_sha256",
    ):
        if canary.get(key) != wanted_c.get(key):
            raise ValueError("A04P4_PINNED_CANARY_MATRIX_DRIFT:" + key)
    for key in (
        "git_history_commit_count", "isolated_baseline_tree_sha",
        "isolated_changed_tree_sha", "isolated_restored_tree_sha",
        "baseline_contract_bytes_sha256", "restored_contract_bytes_sha256",
    ):
        if git.get(key) != wanted_g.get(key):
            raise ValueError("A04P4_PINNED_GIT_REVERT_DRIFT:" + key)
    if (canary.get("case_count") != 19
            or canary.get("structural_review_only_count") != 3
            or canary.get("blocked_count") != 16
            or git.get("git_history_commit_count") != 3
            or git.get("isolated_baseline_tree_sha")
            != git.get("isolated_restored_tree_sha")
            or git.get("baseline_contract_bytes_sha256")
            != git.get("restored_contract_bytes_sha256")):
        raise ValueError("A04P4_DISPOSABLE_REVERT_INTEGRITY_FAILED")
    expected_true = baseline.get("required_true_paths")
    expected_false = baseline.get("required_false_paths")
    if expected_true != [
        "git.git_drill_executed",
        "git.disposable_git_repo_has_no_remotes",
        "git.project_checkout_head_preserved",
        "git.project_checkout_status_preserved",
        "canary.all_stages_declarative_only",
    ] or expected_false != [
        "git.protected_main_reverted", "git.remote_git_write_performed",
        "canary.real_traffic_shifted", "canary.provider_adapter_invoked",
        "canary.may_deploy_or_trade", "any_real_plugin_executed",
        "real_market_data_called", "real_cache_written",
        "protected_main_changed", "live_release_or_trade_performed",
    ]:
        raise ValueError("A04P4_PINNED_AUTHORITY_PATHS_CHANGED")
    for path, expected_value in (
        *((x, True) for x in expected_true),
        *((x, False) for x in expected_false),
    ):
        obj: Any = measured
        for part in path.split("."):
            if not isinstance(obj, dict):
                raise ValueError("A04P4_PINNED_AUTHORITY_NESTING_MISSING")
            obj = obj.get(part)
        if obj is not expected_value:
            raise ValueError("A04P4_UNAUTHORIZED_AUTHORITY:" + path)


if __name__ == "__main__":
    main()
