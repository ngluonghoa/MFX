"""A04/P0.4 — declaration-only canary readiness, never runtime promotion.

Stages name synthetic review gates, NOT percent traffic, production rollout
or trading. No adapter import, provider call, cache write or order execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from re import fullmatch


class SyntheticCanaryStage(IntEnum):
    BASELINE = 0
    DECLARATION_SHADOW = 1
    SYNTHETIC_REPLAY_SMALL = 2
    SYNTHETIC_REPLAY_EXTENDED = 3


@dataclass(frozen=True, slots=True)
class CanaryEvidence:
    project_id: str
    frozen_forex_sha: str
    graph_sha256: str
    golden_sha256: str
    schema_matrix_sha256: str
    snapshot_restored_exact: bool
    git_drill_restored_exact: bool
    original_source_parity_passed: bool
    golden_50_passed: bool
    matrix_14_passed: bool
    security_gates_passed: bool
    replay_budget_cases: int = 50
    blocked_migration_cases: int = 11
    runtime_activation_requested: bool = False
    real_data_requested: bool = False
    automatic_provider_failover: bool = False
    broker_order_requested: bool = False


@dataclass(frozen=True, slots=True)
class CanaryReview:
    structural_reviewable: bool
    reason: str
    from_stage: SyntheticCanaryStage
    to_stage: SyntheticCanaryStage
    may_activate_runtime: bool = False
    may_use_live_provider: bool = False
    may_change_protected_main: bool = False
    may_deploy_or_trade: bool = False


def _sha256(value: object) -> bool:
    return (isinstance(value, str)
            and fullmatch(r"[0-9a-f]{64}", value) is not None)


def assess_synthetic_canary(
    before: SyntheticCanaryStage,
    after: SyntheticCanaryStage,
    evidence: CanaryEvidence,
    *,
    expected_graph_sha256: str,
    expected_golden_sha256: str,
    expected_schema_matrix_sha256: str,
) -> CanaryReview:
    """Strictly staged *review*, no real rollout/permission even on PASS."""
    if not isinstance(before, SyntheticCanaryStage) or not isinstance(
            after, SyntheticCanaryStage):
        raise TypeError("A04P4_TYPED_STAGES_REQUIRED")
    if not isinstance(evidence, CanaryEvidence):
        raise TypeError("A04P4_TYPED_EVIDENCE_REQUIRED")

    def result(ok: bool, reason: str) -> CanaryReview:
        return CanaryReview(ok, reason, before, after)

    if evidence.project_id != "MFX" or evidence.frozen_forex_sha != (
            "7e1c1c012b1b189be5ad7b9d07756eac012a8309"):
        return result(False, "A04P4_FROZEN_SOURCE_OR_PROJECT_MISMATCH")
    if not all(_sha256(s) for s in (
            expected_graph_sha256, expected_golden_sha256,
            expected_schema_matrix_sha256)):
        raise ValueError("A04P4_UNTYPED_PINNED_SHA")
    if (evidence.graph_sha256 != expected_graph_sha256
            or evidence.golden_sha256 != expected_golden_sha256
            or evidence.schema_matrix_sha256 != expected_schema_matrix_sha256):
        return result(False, "A04P4_GOLDEN_GRAPH_OR_MATRIX_DRIFT")
    if not all(v is True for v in (
            evidence.snapshot_restored_exact,
            evidence.git_drill_restored_exact,
            evidence.original_source_parity_passed,
            evidence.golden_50_passed,
            evidence.matrix_14_passed,
            evidence.security_gates_passed)):
        return result(False, "A04P4_MISSING_REQUIRED_GATE")
    if (type(evidence.replay_budget_cases) is not int
            or evidence.replay_budget_cases != 50
            or type(evidence.blocked_migration_cases) is not int
            or evidence.blocked_migration_cases != 11):
        return result(False, "A04P4_SYNTHETIC_EVIDENCE_BUDGET_DRIFT")
    if any(v is not False for v in (
            evidence.runtime_activation_requested,
            evidence.real_data_requested,
            evidence.automatic_provider_failover,
            evidence.broker_order_requested)):
        return result(False, "A04P4_FORBIDDEN_REAL_OPERATION")
    if after.value != before.value + 1:
        return result(False, "A04P4_STAGE_SKIP_REPLAY_OR_REVERSE")
    return result(True, "A04P4_SYNTHETIC_STRUCTURAL_REVIEW_ONLY_NOT_APPROVAL")
