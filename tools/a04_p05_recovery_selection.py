"""A04/P0.5: synthetic protected-main recovery and exact schema selection.

Every return value is an offline architecture review, NEVER a GitHub
permission, schema migration execution, real-data entitlement, plugin loader,
production canary or trading authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from re import fullmatch

from tools.a04_adapter_conformance import PortSchema
from tools.a04_contract_migration import (
    ContractSnapshot, assess_transition,
)


def _sha40(value: object) -> bool:
    return isinstance(value, str) and fullmatch(r"[0-9a-f]{40}", value) is not None


@dataclass(frozen=True, slots=True)
class RecoveryFacts:
    """Claims for planning only; GitHub status is NOT authenticated here."""

    project_repository: str
    observed_main_sha: str
    expected_main_sha: str
    candidate_squash_sha: str
    documented_parent_sha: str
    protected_main: bool
    zero_competing_prs: bool
    dependency_revert_reviewed: bool
    original_102_blob_source_frozen: bool
    previous_ci_three_of_three: bool
    force_push_requested: bool = False
    direct_main_write_requested: bool = False
    production_redeploy_requested: bool = False


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    new_branch_pr_reviewable: bool
    reason: str
    may_write_remote_git: bool = False
    may_reset_or_force_main: bool = False
    may_redeploy_production: bool = False
    may_release_or_trade: bool = False


def review_protected_recovery(facts: RecoveryFacts) -> RecoveryDecision:
    """Only approve drafting a recovery PR; never execute a remote action."""
    if not isinstance(facts, RecoveryFacts):
        raise TypeError("A04P5_TYPED_RECOVERY_FACTS_REQUIRED")

    def done(reviewable: bool, reason: str) -> RecoveryDecision:
        return RecoveryDecision(reviewable, reason)

    if facts.project_repository != "ngluonghoa/MFX":
        return done(False, "A04P5_WRONG_REPOSITORY")
    if not all(_sha40(v) for v in (
            facts.observed_main_sha, facts.expected_main_sha,
            facts.candidate_squash_sha, facts.documented_parent_sha)):
        return done(False, "A04P5_INVALID_COMMIT_IDENTITY")
    if (facts.observed_main_sha != facts.expected_main_sha or
            facts.candidate_squash_sha == facts.documented_parent_sha):
        return done(False, "A04P5_MAIN_MOVED_OR_IMPOSSIBLE_TARGET")
    if (facts.protected_main is not True
            or facts.zero_competing_prs is not True
            or facts.dependency_revert_reviewed is not True
            or facts.original_102_blob_source_frozen is not True
            or facts.previous_ci_three_of_three is not True):
        return done(False, "A04P5_PROTECTION_OR_EVIDENCE_MISSING")
    if any(v is not False for v in (
            facts.force_push_requested, facts.direct_main_write_requested,
            facts.production_redeploy_requested)):
        return done(False, "A04P5_FORBIDDEN_RECOVERY_ACTION")
    return done(True, "A04P5_NEW_BRANCH_REVERT_PR_REVIEW_ONLY")


@dataclass(frozen=True, slots=True)
class SchemaSelection:
    structural_reviewable: bool
    selected_snapshot_sha256: str | None
    reason: str
    runtime_schema_applied: bool = False
    automatic_fallback_performed: bool = False
    may_import_plugin: bool = False
    may_trade: bool = False


def select_exact_schema_declaration(
    baseline: ContractSnapshot,
    options: tuple[ContractSnapshot, ...],
    schema: PortSchema,
    major: int,
    minor: int,
    *,
    allow_implicit_fallback: bool = False,
) -> SchemaSelection:
    """Do not silently downgrade versions or select another provider/schema."""
    if (not isinstance(baseline, ContractSnapshot)
            or not isinstance(options, tuple)
            or any(not isinstance(o, ContractSnapshot) for o in options)
            or not isinstance(schema, PortSchema)):
        raise TypeError("A04P5_TYPED_SELECTION_REQUIRED")
    if (type(major) is not int or major < 1
            or type(minor) is not int or minor < 0):
        raise ValueError("A04P5_INVALID_VERSION_REQUEST")

    def done(ok: bool, sha: str | None, reason: str) -> SchemaSelection:
        return SchemaSelection(ok, sha, reason)

    if allow_implicit_fallback is not False:
        return done(False, None, "A04P5_NO_IMPLICIT_SCHEMA_FALLBACK")
    if not options or len(options) > 8:
        return done(False, None, "A04P5_BOUNDED_CANDIDATE_SET_REQUIRED")
    current = {s.schema: s for s in baseline.schemas}
    matches: list[ContractSnapshot] = []
    for candidate in options:
        if (candidate.project_id != "MFX"
                or candidate.graph_sha256 != baseline.graph_sha256
                or candidate.golden_sha256 != baseline.golden_sha256):
            return done(False, None, "A04P5_FOREX_SOURCE_OR_GRAPH_DRIFT")
        versions = {s.schema: s for s in candidate.schemas}
        if any(versions[k] != current[k] for k in current if k is not schema):
            return done(False, None, "A04P5_UNREQUESTED_SCHEMA_CHANGED")
        if versions[schema].major == major and versions[schema].minor == minor:
            matches.append(candidate)
    if not matches:
        return done(False, None, "A04P5_EXACT_VERSION_NOT_DECLARED_NO_FALLBACK")
    if len(matches) != 1:
        return done(False, None, "A04P5_AMBIGUOUS_EXACT_SCHEMA_VERSION")
    selected = matches[0]
    compatibility = assess_transition(baseline, selected)
    if not compatibility.declaration_reviewable:
        return done(False, None, "A04P5_INCOMPATIBLE_DECLARATION:" + compatibility.reason)
    return done(True, selected.identity_sha256,
                "A04P5_EXACT_SCHEMA_STRUCTURAL_REVIEW_ONLY_NOT_RUNTIME")


@dataclass(frozen=True, slots=True)
class IntegrationFacts:
    original_forex_parity: bool
    frozen_golden_50: bool
    schema_matrix_pinned: bool
    disposable_revert_verified: bool
    source_security_gates: bool
    protected_main_ci_verified: bool
    source_delta_approved: bool = False
    provider_rights_qualified: bool = False
    real_execution_semantics_verified: bool = False
    runtime_plugin_activation_requested: bool = False
    actual_market_data_requested: bool = False
    broker_orders_requested: bool = False


@dataclass(frozen=True, slots=True)
class IntegrationDecision:
    documentation_reviewable: bool
    reason: str
    runtime_integration_authorized: bool = False
    production_canary_authorized: bool = False
    may_fetch_real_data: bool = False
    may_execute_orders: bool = False


def review_integration_readiness(facts: IntegrationFacts) -> IntegrationDecision:
    """Stop before implementation: even a healthy synthetic gate is NOT GO."""
    if not isinstance(facts, IntegrationFacts):
        raise TypeError("A04P5_TYPED_INTEGRATION_FACTS_REQUIRED")

    def done(ok: bool, reason: str) -> IntegrationDecision:
        return IntegrationDecision(ok, reason)

    if not all(v is True for v in (
            facts.original_forex_parity, facts.frozen_golden_50,
            facts.schema_matrix_pinned, facts.disposable_revert_verified,
            facts.source_security_gates, facts.protected_main_ci_verified)):
        return done(False, "A04P5_MISSING_SYNTHETIC_SAFETY_EVIDENCE")
    if any(v is not False for v in (
            facts.runtime_plugin_activation_requested,
            facts.actual_market_data_requested, facts.broker_orders_requested)):
        return done(False, "A04P5_FORBIDDEN_RUNTIME_ACTION")
    if any(v is not False for v in (
            facts.source_delta_approved, facts.provider_rights_qualified,
            facts.real_execution_semantics_verified)):
        return done(False, "A04P5_UNVERIFIED_EXTERNAL_APPROVAL_CLAIM")
    return done(True, "A04P5_ARCHITECTURE_DOC_REVIEW_ONLY_RUNTIME_STOP")
