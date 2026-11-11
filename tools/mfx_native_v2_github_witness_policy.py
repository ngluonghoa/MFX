"""MFX A04/P0.79: INERT GitHub protected-ref witness policy and commit contract.

GitHub can be a separate *domain* from Google Drive price archives, but a
fast-forward-only ref update is not a signature, a head-bound exact CAS,
a durable monotonic timestamp or an immutable admin-proof authority.
All inputs and ruleset observations here are caller-supplied. No HTTP,
git push, permissions update, credentials, secrets, or Drive writes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from mfx_cache.td_m5_codec import digest
from tools.mfx_native_v2_cas_recovery_contract import (
    SCHEMA as P078_SCHEMA, STATUS as P078_STATUS, V2FencedCASProposal,
)
from tools.mfx_native_v2_witness_draft import witness_sha256

SCHEMA = "MFX_A04_P79_GITHUB_REF_WITNESS_RESEARCH_V1"
STATUS = "OFFLINE_WITNESS_COMMIT_PLAN_UNAUTHENTICATED"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REF = re.compile(r"^refs/heads/[a-z][a-z0-9-]{0,79}$")
REQUIRED_RULES = frozenset(("deletion", "non_fast_forward"))
NO_ACTIVE_AUTH = "POLICY_NOT_PROVEN_NO_WITNESS_AUTHORITY"


@dataclass(frozen=True, slots=True)
class GithubWitnessPolicyReview:
    target_ref: str
    matched_ruleset: bool
    mandatory_rules_seen: bool
    ruleset_active: bool
    no_bypass_claimed: bool
    required_checks_present: bool
    identity_control_proven: bool = False
    cryptographic_external_witness_proven: bool = False
    safe_to_activate_v2: bool = False
    status: str = NO_ACTIVE_AUTH


@dataclass(frozen=True, slots=True)
class GithubWitnessCommitPlan:
    schema: str
    status: str
    target_ref: str
    expected_parent_git_sha: str
    candidate_payload_sha256: str
    previous_witness_sha256: str
    proposed_witness_sha256: str
    witness_generation: int
    epoch: int
    fence_token: int
    symbol: str
    interval: str
    private_key_or_token_used: bool = False
    published_github_commit: bool = False
    authenticated_external_cas_verified: bool = False
    live_v2_enabled: bool = False
    drive_writes: int = 0
    provider_requests: int = 0
    broker_orders: int = 0


@dataclass(frozen=True, slots=True)
class GithubWitnessReadbackAssessment:
    status: str
    expected_parent_git_sha: str
    observed_ref_git_sha: str
    exact_candidate_sha_matched: bool
    real_git_ref_readback_verified: bool = False
    durable_authenticated_antirollback_verified: bool = False
    live_v2_enabled: bool = False
    drive_writes: int = 0
    broker_orders: int = 0


def _sha40(value: Any) -> bool:
    return type(value) is str and HEX40.fullmatch(value) is not None


def _sha64(value: Any) -> bool:
    return type(value) is str and HEX64.fullmatch(value) is not None


def review_witness_ruleset(
    *, target_ref: str, default_branch: str,
    enforced: bool, include_patterns: tuple[str, ...],
    rule_types: tuple[str, ...], bypass_actor_count: int,
    trusted_identity_verification_available: bool,
) -> GithubWitnessPolicyReview:
    """Fail closed: only exact GitHub ref or ~DEFAULT_BRANCH matching.

    This is NOT a general GitHub glob/ruleset precedence parser. Patterns
    other than an exact ref or ~DEFAULT_BRANCH remain UNVERIFIED.
    Even a complete caller-reported ruleset is not authenticated by us.
    """
    if (type(target_ref) is not str or REF.fullmatch(target_ref) is None
            or type(default_branch) is not str
            or REF.fullmatch("refs/heads/"+default_branch) is None
            or type(enforced) is not bool
            or type(include_patterns) is not tuple
            or any(type(x) is not str for x in include_patterns)
            or type(rule_types) is not tuple
            or any(type(x) is not str for x in rule_types)
            or type(bypass_actor_count) is not int
            or bypass_actor_count < 0
            or type(trusted_identity_verification_available) is not bool):
        raise ValueError("P079_RULESET_INPUTS_INVALID")
    covered = target_ref in include_patterns or (
        "~DEFAULT_BRANCH" in include_patterns
        and target_ref == "refs/heads/"+default_branch
    )
    present = REQUIRED_RULES.issubset(rule_types)
    checks = "required_status_checks" in rule_types
    no_bypass = bypass_actor_count == 0
    return GithubWitnessPolicyReview(
        target_ref=target_ref,matched_ruleset=covered,
        mandatory_rules_seen=present,ruleset_active=enforced,
        no_bypass_claimed=no_bypass,
        required_checks_present=checks,
        # This is an input claim, NEVER independent proof.
        identity_control_proven=False,
        cryptographic_external_witness_proven=False,
        safe_to_activate_v2=False,
    )


def plan_git_ref_witness_commit(
    prepared: V2FencedCASProposal, *,
    target_ref: str, expected_parent_git_sha: str,
) -> GithubWitnessCommitPlan:
    """Plan a single-parent payload; DO NOT compute/fake a Git commit ID.

    Git commit OIDs depend on exact tree/author/committer metadata and must
    be obtained from an authenticated Git object create/readback.
    """
    if (type(prepared) is not V2FencedCASProposal
            or prepared.status != P078_STATUS
            or prepared.expected_head.schema != P078_SCHEMA
            or prepared.proposed_head.schema != P078_SCHEMA
            or prepared.external_atomic_cas_required is not True
            or prepared.independent_external_authority_verified is not False
            or prepared.live_drive_writer_authorized is not False
            or prepared.real_drive_writes != 0
            or prepared.provider_requests != 0
            or prepared.broker_orders != 0
            or not _sha64(prepared.previous_witness_sha256)
            or not _sha64(prepared.next_witness_sha256)
            or prepared.previous_witness_sha256 !=
            prepared.expected_head.witness_sha256
            or prepared.next_witness_sha256 !=
            prepared.proposed_head.witness_sha256
            or witness_sha256(prepared.next_witness) !=
            prepared.next_witness_sha256
            or prepared.next_witness.parent_witness_sha256 !=
            prepared.previous_witness_sha256
            or prepared.proposed_head.symbol !=
            prepared.expected_head.symbol
            or prepared.proposed_head.interval !=
            prepared.expected_head.interval
            or prepared.proposed_head.epoch !=
            prepared.expected_head.epoch
            or prepared.proposed_head.generation !=
            prepared.expected_head.generation + 1
            or type(prepared.proposed_head.fence_token) is not int
            or prepared.proposed_head.fence_token <=
            prepared.expected_head.fence_token
            or type(target_ref) is not str
            or REF.fullmatch(target_ref) is None
            or target_ref == "refs/heads/main"
            or not _sha40(expected_parent_git_sha)):
        raise ValueError("P079_WITNESS_COMMIT_INPUTS_INVALID")
    payload = {
        "schema": SCHEMA,
        "target_ref": target_ref,
        "expected_parent_git_sha": expected_parent_git_sha,
        "previous_witness_sha256": prepared.previous_witness_sha256,
        "proposed_witness_sha256": prepared.next_witness_sha256,
        "witness_generation": prepared.proposed_head.generation,
        "epoch": prepared.proposed_head.epoch,
        "fence_token": prepared.proposed_head.fence_token,
        "symbol": prepared.expected_head.symbol,
        "interval": prepared.expected_head.interval,
        "no_live_v2_authority": True,
    }
    return GithubWitnessCommitPlan(
        schema=SCHEMA, status=STATUS,target_ref=target_ref,
        expected_parent_git_sha=expected_parent_git_sha,
        candidate_payload_sha256=digest(payload),
        previous_witness_sha256=prepared.previous_witness_sha256,
        proposed_witness_sha256=prepared.next_witness_sha256,
        witness_generation=prepared.proposed_head.generation,
        epoch=prepared.proposed_head.epoch,
        fence_token=prepared.proposed_head.fence_token,
        symbol=prepared.expected_head.symbol,
        interval=prepared.expected_head.interval,
    )


def assess_github_ref_readback(
    plan: GithubWitnessCommitPlan, *,
    observed_ref_git_sha: str,
    candidate_git_sha: str,
    candidate_parent_git_sha: str,
    candidate_payload_sha256: str,
) -> GithubWitnessReadbackAssessment:
    """Check caller-supplied readback against the plan, not Github itself.

    'force:false' enforces fast-forward ancestry, NOT exact expected-ref
    compare-and-swap and NOT an independent authenticated freshness pin.
    An attacker with rule-bypass rights may rewrite/delete this history.
    """
    if (type(plan) is not GithubWitnessCommitPlan
            or plan.schema != SCHEMA or plan.status != STATUS
            or plan.private_key_or_token_used is not False
            or plan.published_github_commit is not False
            or plan.authenticated_external_cas_verified is not False
            or plan.live_v2_enabled is not False
            or plan.drive_writes != 0
            or plan.provider_requests != 0
            or plan.broker_orders != 0
            or not _sha40(plan.expected_parent_git_sha)
            or not _sha64(plan.candidate_payload_sha256)
            or not all(_sha40(x) for x in (
                observed_ref_git_sha,candidate_git_sha,
                candidate_parent_git_sha))
            or not _sha64(candidate_payload_sha256)):
        raise ValueError("P079_READBACK_SHAPE_OR_FLAGS_INVALID")
    if candidate_parent_git_sha != plan.expected_parent_git_sha:
        raise ValueError("P079_PARENT_COMMIT_CHANGED")
    if candidate_payload_sha256 != plan.candidate_payload_sha256:
        raise ValueError("P079_COMMIT_PAYLOAD_SHA_MISMATCH")
    if observed_ref_git_sha == plan.expected_parent_git_sha:
        status="NOT_PUBLISHED_OR_REF_STALE"
        matched=False
    elif observed_ref_git_sha == candidate_git_sha:
        status="CALLER_READBACK_MATCH_NO_INDEPENDENT_ATTESTATION"
        matched=True
    else:
        raise ValueError("P079_GITHUB_REF_FORK_OR_UNEXPECTED_HEAD")
    return GithubWitnessReadbackAssessment(
        status=status,
        expected_parent_git_sha=plan.expected_parent_git_sha,
        observed_ref_git_sha=observed_ref_git_sha,
        exact_candidate_sha_matched=matched,
    )
