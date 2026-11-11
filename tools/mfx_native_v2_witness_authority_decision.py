"""A04/P0.81: fail-closed, offline decision gate for a future GitHub witness.

Inputs are caller-supplied research observations, NOT live API receipts.
No GitHub/Drive HTTP, credentials, keys, ref/ruleset mutations, price data,
scheduler, trading or broker access. This does not activate native V2.
"""
from __future__ import annotations

from dataclasses import dataclass

SCHEMA = "MFX_A04_P81_WITNESS_AUTHORITY_DECISION_V1"
REPO = "ngluonghoa/MFX"
REF = "refs/heads/mfx-native-v2-witness"
MISSING_REF = "GITHUB_HTTP_404"
EXISTING_REF = "GITHUB_HTTP_200"
UNKNOWN_REF = "NOT_READ"
RULES_HTTP_200 = "GITHUB_HTTP_200"
RULES_BLOCKED = "CONNECTOR_ALLOWLIST_DENIED"
RULES_NOT_READ = "NOT_READ"
REQUIRED_RULES = frozenset(("deletion", "non_fast_forward"))
MAX_RULES = 64


@dataclass(frozen=True, slots=True)
class WitnessAuthorityResearch:
    repository: str
    candidate_ref: str
    main_ruleset_includes: tuple[str, ...]
    witness_ref_result: str
    witness_rules_result: str
    effective_branch_rules: tuple[str, ...]
    owner_selected_github_metadata_witness: bool = False
    owner_authorized_sandbox_mutation: bool = False
    independently_verified_signer: bool = False
    bypass_and_admin_threat_accepted: bool = False
    independent_append_only_backup_verified: bool = False
    genuine_cloud_concurrent_ff_probe_verified: bool = False
    independently_authenticated_monotonic_head_verified: bool = False
    externally_atomic_exact_head_cas_verified: bool = False


@dataclass(frozen=True, slots=True)
class WitnessAuthorityDecisionReceipt:
    schema: str
    status: str
    missing_evidence: tuple[str, ...]
    rules_readback_available: bool
    research_reviewable: bool
    # Source-only research cannot elevate caller observations to authority.
    independently_authenticated: bool = False
    durable_antirollback_verified: bool = False
    exact_head_cas_verified: bool = False
    native_v2_read_authorized: bool = False
    native_v2_write_authorized: bool = False
    production_witness_branch_created: bool = False
    github_mutations: int = 0
    drive_reads: int = 0
    drive_writes: int = 0
    vendor_calls: int = 0
    broker_orders: int = 0


def assess_witness_authority_decision(
    observed: WitnessAuthorityResearch,
) -> WitnessAuthorityDecisionReceipt:
    """Inventory missing proof; NEVER grant real witness/V2 authorization."""
    if type(observed) is not WitnessAuthorityResearch:
        raise ValueError("P081_WRONG_EVIDENCE_TYPE")
    if (observed.repository != REPO or observed.candidate_ref != REF
            or type(observed.main_ruleset_includes) is not tuple
            or any(type(v) is not str or not v
                   for v in observed.main_ruleset_includes)
            or observed.witness_ref_result not in
               (MISSING_REF, EXISTING_REF, UNKNOWN_REF)
            or observed.witness_rules_result not in
               (RULES_HTTP_200, RULES_BLOCKED, RULES_NOT_READ)
            or type(observed.effective_branch_rules) is not tuple
            or len(observed.effective_branch_rules) > MAX_RULES
            or any(type(v) is not str or not v
                   for v in observed.effective_branch_rules)
            or any(type(getattr(observed, field)) is not bool for field in (
                "owner_selected_github_metadata_witness",
                "owner_authorized_sandbox_mutation",
                "independently_verified_signer",
                "bypass_and_admin_threat_accepted",
                "independent_append_only_backup_verified",
                "genuine_cloud_concurrent_ff_probe_verified",
                "independently_authenticated_monotonic_head_verified",
                "externally_atomic_exact_head_cas_verified",
            ))):
        raise ValueError("P081_EVIDENCE_SCHEMA_INVALID")
    if (observed.witness_rules_result != RULES_HTTP_200
            and observed.effective_branch_rules):
        raise ValueError("P081_RULES_FABRICATED_WHEN_API_NOT_READ")
    if (observed.witness_rules_result == RULES_HTTP_200
            and len(set(observed.effective_branch_rules))
                != len(observed.effective_branch_rules)):
        raise ValueError("P081_DUPLICATED_RULE_TYPE")
    # GitHub /git/refs PATCH(force=false) checks ancestry, not exact-head
    # compare-and-swap. Claiming exact CAS from this provider is invalid.
    if observed.externally_atomic_exact_head_cas_verified:
        raise ValueError("P081_GITHUB_REF_IS_NOT_EXACT_HEAD_CAS")
    missing: list[str] = []
    if not observed.owner_selected_github_metadata_witness:
        missing.append("OWNER_TRUST_BOUNDARY_CHOICE")
    if not observed.owner_authorized_sandbox_mutation:
        missing.append("OWNER_TEST_ONLY_MUTATION_APPROVAL")
    if observed.witness_ref_result != EXISTING_REF:
        missing.append("REAL_WITNESS_REF_READBACK")
    if (observed.witness_rules_result != RULES_HTTP_200
            or not REQUIRED_RULES.issubset(
                frozenset(observed.effective_branch_rules))):
        missing.append("EFFECTIVE_EXACT_BRANCH_RULES_GET")
    if "~DEFAULT_BRANCH" in observed.main_ruleset_includes:
        # Default-branch coverage never proves dedicated witness coverage.
        if observed.witness_rules_result != RULES_HTTP_200:
            missing.append("MAIN_RULESET_DOES_NOT_COVER_WITNESS")
    if not observed.independently_verified_signer:
        missing.append("VERIFIED_SEPARATE_SIGNER_IDENTITY")
    if not observed.bypass_and_admin_threat_accepted:
        missing.append("ADMIN_BYPASS_RESIDUAL_RISK_DECISION")
    if not observed.independent_append_only_backup_verified:
        missing.append("INDEPENDENT_BACKUP_RESTORE_PROOF")
    if not observed.genuine_cloud_concurrent_ff_probe_verified:
        missing.append("REAL_SANDBOX_CONCURRENT_FF_TEST")
    if not observed.independently_authenticated_monotonic_head_verified:
        missing.append("INDEPENDENT_MONOTONIC_HEAD_PROOF")
    missing.append("SERVER_SIDE_EXACT_HEAD_CAS_NOT_PROVED")
    return WitnessAuthorityDecisionReceipt(
        schema=SCHEMA,
        status="BLOCKED_RESEARCH_ONLY",
        missing_evidence=tuple(missing),
        rules_readback_available=(
            observed.witness_rules_result == RULES_HTTP_200),
        research_reviewable=(
            observed.witness_rules_result == RULES_HTTP_200
            and observed.witness_ref_result == EXISTING_REF
            and observed.owner_selected_github_metadata_witness),
    )
