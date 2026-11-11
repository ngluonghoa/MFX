"""A04/P0.80: pure READ-ONLY GitHub witness-ref preflight contract.

No HTTP client, auth, ref creation, commit, ruleset mutation, Drive access,
vendor access or broker code. All observations are caller-supplied and
cannot prove an independently trusted, fresh or durable CAS authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.mfx_native_v2_github_witness_policy import (
    GithubWitnessCommitPlan, REF, SCHEMA as P079_SCHEMA,
    STATUS as P079_STATUS, _sha40, _sha64, assess_github_ref_readback,
)

SCHEMA = "MFX_A04_P80_WITNESS_REF_READONLY_PREFLIGHT_V1"
TARGET = "refs/heads/mfx-native-v2-witness"
GITHUB_BRANCH_RULES_ENDPOINT = (
    "GET /repos/ngluonghoa/MFX/rules/branches/mfx-native-v2-witness"
)
REQUIRED_RULE_TYPES = frozenset((
    "deletion", "non_fast_forward",
))
MAX_RULES = 64


@dataclass(frozen=True, slots=True)
class GitBranchRulesObservation:
    """A purported branch-specific active-rules API result; NOT authenticated."""

    branch_ref: str
    endpoint: str
    http_status: int
    active_rules: tuple[tuple[int, str], ...]
    # Neither presence nor absence of an API bypass list is proved by
    # GET /rules/branches/...; never claim admin or identity assurance.
    bypass_visibility_verified: bool = False


@dataclass(frozen=True, slots=True)
class GitRefObservation:
    ref: str
    http_status: int
    git_sha: str | None
    object_type: str | None


@dataclass(frozen=True, slots=True)
class GitCommitObservation:
    git_sha: str
    parents: tuple[str, ...]
    witness_payload_sha256: str
    github_signature_verified: bool


@dataclass(frozen=True, slots=True)
class GithubWitnessSandboxPreflightReceipt:
    status: str
    target_ref: str
    before_after_rules_equal: bool
    required_branch_rules_reported: bool
    expected_parent_sha: str
    observed_head_sha: str | None
    head_matches_candidate: bool
    caller_observation_consistent: bool
    independently_authenticated_head: bool = False
    durable_monotonic_antirollback_verified: bool = False
    real_exact_head_atomic_cas_verified: bool = False
    ruleset_bypass_protection_verified: bool = False
    live_v2_authorized: bool = False
    github_mutations: int = 0
    drive_writes: int = 0
    provider_requests: int = 0
    broker_orders: int = 0


def _validate_rules(observation: GitBranchRulesObservation) -> None:
    if (type(observation) is not GitBranchRulesObservation
            or observation.branch_ref != TARGET
            or observation.endpoint != GITHUB_BRANCH_RULES_ENDPOINT
            or type(observation.http_status) is not int
            or observation.http_status != 200
            or type(observation.active_rules) is not tuple
            or len(observation.active_rules) > MAX_RULES
            or any(type(record) is not tuple or len(record) != 2
                   or type(record[0]) is not int or record[0] <= 0
                   or type(record[1]) is not str or not record[1]
                   for record in observation.active_rules)
            or observation.bypass_visibility_verified is not False):
        raise ValueError("P080_RULES_OBSERVATION_INVALID")


def _validate_ref(snapshot: GitRefObservation) -> None:
    if (type(snapshot) is not GitRefObservation
            or snapshot.ref != TARGET
            or type(snapshot.http_status) is not int
            or (
                snapshot.http_status == 404
                and (snapshot.git_sha is not None
                     or snapshot.object_type is not None)
            )
            or (
                snapshot.http_status == 200
                and (not _sha40(snapshot.git_sha)
                     or snapshot.object_type != "commit")
            )
            or snapshot.http_status not in (200, 404)):
        raise ValueError("P080_GIT_REF_OBSERVATION_INVALID")


def _validate_candidate(snapshot: GitCommitObservation) -> None:
    if (type(snapshot) is not GitCommitObservation
            or not _sha40(snapshot.git_sha)
            or type(snapshot.parents) is not tuple
            or len(snapshot.parents) != 1
            or not _sha40(snapshot.parents[0])
            or not _sha64(snapshot.witness_payload_sha256)
            or type(snapshot.github_signature_verified) is not bool):
        raise ValueError("P080_CANDIDATE_GIT_COMMIT_INVALID")


def assess_github_witness_sandbox_readonly(
    plan: GithubWitnessCommitPlan, *,
    rules_before: GitBranchRulesObservation,
    rules_after: GitBranchRulesObservation,
    ref_before: GitRefObservation,
    ref_after: GitRefObservation,
    candidate: GitCommitObservation | None,
) -> GithubWitnessSandboxPreflightReceipt:
    """Evaluate caller-supplied read-only snapshots. Never mutate GitHub.

    The stronger branch-scoped API is documented by GitHub but may not
    be accessible through the installed connector. If not retrieved,
    DO NOT substitute a default-branch ruleset or forge the response.
    """
    if (type(plan) is not GithubWitnessCommitPlan
            or plan.schema != P079_SCHEMA or plan.status != P079_STATUS
            or plan.target_ref != TARGET
            or REF.fullmatch(plan.target_ref) is None
            or not _sha40(plan.expected_parent_git_sha)
            or not _sha64(plan.candidate_payload_sha256)
            or not _sha64(plan.previous_witness_sha256)
            or not _sha64(plan.proposed_witness_sha256)
            or type(plan.witness_generation) is not int
            or plan.witness_generation < 1
            or type(plan.epoch) is not int or plan.epoch < 1
            or type(plan.fence_token) is not int or plan.fence_token < 1
            or plan.symbol != "EUR/USD"
            or plan.interval not in ("4h", "1day")
            or plan.private_key_or_token_used is not False
            or plan.published_github_commit is not False
            or plan.authenticated_external_cas_verified is not False
            or plan.live_v2_enabled is not False
            or plan.drive_writes != 0
            or plan.provider_requests != 0
            or plan.broker_orders != 0):
        raise ValueError("P080_GIT_WITNESS_PLAN_UNSAFE")
    _validate_rules(rules_before)
    _validate_rules(rules_after)
    _validate_ref(ref_before)
    _validate_ref(ref_after)
    if rules_before != rules_after:
        raise ValueError("P080_BRANCH_RULES_CHANGED_DURING_READBACK")
    names = frozenset(t for _,t in rules_before.active_rules)
    if not REQUIRED_RULE_TYPES.issubset(names):
        raise ValueError("P080_BRANCH_REF_NOT_PROTECTED")
    if ref_before.http_status == 404 or ref_after.http_status == 404:
        if (ref_before.http_status != 404
                or ref_after.http_status != 404
                or candidate is not None):
            raise ValueError("P080_WITNESS_REF_APPEARED_OR_DISAPPEARED")
        return GithubWitnessSandboxPreflightReceipt(
            status="NO_WITNESS_REF_READONLY_RESEARCH_ONLY",
            target_ref=TARGET,
            before_after_rules_equal=True,
            required_branch_rules_reported=True,
            expected_parent_sha=plan.expected_parent_git_sha,
            observed_head_sha=None,
            head_matches_candidate=False,
            caller_observation_consistent=True,
        )
    if ref_before.git_sha != plan.expected_parent_git_sha:
        raise ValueError("P080_INITIAL_REF_HEAD_NOT_EXPECTED_PARENT")
    if candidate is None:
        if ref_after.git_sha != ref_before.git_sha:
            raise ValueError("P080_REF_CHANGED_WITHOUT_CANDIDATE")
        return GithubWitnessSandboxPreflightReceipt(
            status="NO_CANDIDATE_NO_PUBLICATION",
            target_ref=TARGET, before_after_rules_equal=True,
            required_branch_rules_reported=True,
            expected_parent_sha=plan.expected_parent_git_sha,
            observed_head_sha=ref_after.git_sha,
            head_matches_candidate=False,
            caller_observation_consistent=True,
        )
    _validate_candidate(candidate)
    readback = assess_github_ref_readback(
        plan,
        observed_ref_git_sha=ref_after.git_sha,
        candidate_git_sha=candidate.git_sha,
        candidate_parent_git_sha=candidate.parents[0],
        candidate_payload_sha256=candidate.witness_payload_sha256,
    )
    if ref_after.git_sha == ref_before.git_sha:
        status="CANDIDATE_NOT_PUBLISHED_OR_STALE_HEAD"
    elif not candidate.github_signature_verified:
        raise ValueError("P080_CANDIDATE_SIGNATURE_NOT_VERIFIED")
    else:
        status="CALLER_READBACK_CONSISTENT_NOT_EXTERNAL_AUTHORITY"
    return GithubWitnessSandboxPreflightReceipt(
        status=status, target_ref=TARGET,
        before_after_rules_equal=True,
        required_branch_rules_reported=True,
        expected_parent_sha=plan.expected_parent_git_sha,
        observed_head_sha=ref_after.git_sha,
        head_matches_candidate=readback.exact_candidate_sha_matched,
        caller_observation_consistent=True,
    )
