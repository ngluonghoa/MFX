"""M2/P0.5: fail-closed source/account-rights and storage residency review.

No user supplied contract/status/receipt can authenticate itself. Public documents,
an API token, account plan, signed-looking SHA, and a filled questionnaire do NOT
prove entitlement. This module has NO network, disk or trading side effects; all
real-data grants are intentionally False until a separately approved independent
vendor/legal/host verification workflow exists.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from re import fullmatch

from .cache_storage_review import (
    DurableStorageProposal, StorageKind, assess_durable_cache_proposal,
)
from .quotes import ensure_utc
from .source_qualification import (
    LicensedUse, PublicCapabilityClaim, SourceQualification, UseRightsClaim,
    assess_source_for_m2_review,
)


def _ref(value: str, field: str) -> None:
    """Opaque and nonsecret; do not store account numbers, tokens or URLs."""
    if (not isinstance(value, str) or
            not fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{1,63}", value) or
            "token" in value.lower() or "secret" in value.lower()):
        raise ValueError(f"{field} requires an opaque nonsecret reference")


@dataclass(frozen=True, slots=True)
class AccountContractClaim:
    """Account-specific review metadata, NOT a legal permission."""
    provider_id: str
    product_id: str
    jurisdiction_code: str
    account_scope_ref: str
    plan_ref: str
    contract_revision_ref: str
    effective_from_utc: datetime
    expires_utc: datetime | None
    first_seen_by_us_utc: datetime

    def __post_init__(self) -> None:
        for name in (
            "provider_id", "product_id", "jurisdiction_code",
            "account_scope_ref", "plan_ref", "contract_revision_ref",
        ):
            _ref(getattr(self, name), name)
        ensure_utc(self.effective_from_utc, "effective_from_utc")
        ensure_utc(self.first_seen_by_us_utc, "first_seen_by_us_utc")
        if self.expires_utc is not None:
            ensure_utc(self.expires_utc, "expires_utc")
            if self.expires_utc <= self.effective_from_utc:
                raise ValueError("CONTRACT_EXPIRES_BEFORE_EFFECTIVE")


@dataclass(frozen=True, slots=True)
class DataRetentionClaim:
    """Contract duration/regions claimed by applicant, not vendor verified."""
    maximum_days_claimed: int | None
    allowed_storage_regions_claimed: frozenset[str]
    derived_indicators_may_be_retained_claimed: bool

    def __post_init__(self) -> None:
        if self.maximum_days_claimed is not None and (
            type(self.maximum_days_claimed) is not int or
            not 1 <= self.maximum_days_claimed <= 3650
        ):
            raise ValueError("INVALID_VENDOR_RETENTION_CLAIM")
        if not isinstance(self.allowed_storage_regions_claimed, frozenset):
            raise TypeError("Storage regions must be an immutable set")
        for region in self.allowed_storage_regions_claimed:
            _ref(region, "storage_region")
        if type(self.derived_indicators_may_be_retained_claimed) is not bool:
            raise TypeError("Explicit derived-retention flag required")


@dataclass(frozen=True, slots=True)
class CandidateStorageLocation:
    """A candidate only; no hostname, filesystem path, IP or actual endpoint."""
    location_class_ref: str
    region_ref: str
    proposal: DurableStorageProposal

    def __post_init__(self) -> None:
        _ref(self.location_class_ref, "location_class_ref")
        _ref(self.region_ref, "region_ref")
        if not isinstance(self.proposal, DurableStorageProposal):
            raise TypeError("Typed DurableStorageProposal required")


@dataclass(frozen=True, slots=True)
class RevocationNoticeClaim:
    """Recorded first-seen UTC must not be mistaken for retroactive knowledge."""
    first_seen_by_us_utc: datetime
    effective_utc: datetime
    evidence_sha256_claim: str

    def __post_init__(self) -> None:
        ensure_utc(self.first_seen_by_us_utc, "revocation_first_seen_by_us_utc")
        ensure_utc(self.effective_utc, "revocation_effective_utc")
        if not isinstance(self.evidence_sha256_claim, str) or not fullmatch(
            r"[a-f0-9]{64}", self.evidence_sha256_claim
        ):
            raise ValueError("REVOCATION_DIGEST_CLAIM_INVALID")


@dataclass(frozen=True, slots=True)
class AccountDataReviewPacket:
    account: AccountContractClaim
    public_capability: PublicCapabilityClaim | None
    rights: tuple[UseRightsClaim, ...]
    retention: DataRetentionClaim
    storage: CandidateStorageLocation
    revocation: RevocationNoticeClaim | None

    def __post_init__(self) -> None:
        if not isinstance(self.account, AccountContractClaim):
            raise TypeError("AccountContractClaim required")
        if self.public_capability is not None and not isinstance(
            self.public_capability, PublicCapabilityClaim
        ):
            raise TypeError("Typed public capability required")
        if not isinstance(self.rights, tuple) or any(
            not isinstance(x, UseRightsClaim) for x in self.rights
        ):
            raise TypeError("Immutable typed rights required")
        if not isinstance(self.retention, DataRetentionClaim):
            raise TypeError("DataRetentionClaim required")
        if not isinstance(self.storage, CandidateStorageLocation):
            raise TypeError("CandidateStorageLocation required")
        if self.revocation is not None and not isinstance(
            self.revocation, RevocationNoticeClaim
        ):
            raise TypeError("Typed revocation notice required")


class ReviewState(str, Enum):
    BLOCKED_MISSING_EVIDENCE = "BLOCKED_MISSING_EVIDENCE"
    READY_FOR_INDEPENDENT_REVIEW = "READY_FOR_INDEPENDENT_REVIEW"
    SUSPEND_AND_REVIEW_RETENTION = "SUSPEND_AND_REVIEW_RETENTION"


@dataclass(frozen=True, slots=True)
class AccountDataReviewResult:
    state: ReviewState
    account_specific_claims_consistent: bool
    proposed_storage_controls_complete: bool
    requires_cessation_and_retention_review: bool
    source_qualification: SourceQualification
    reasons: tuple[str, ...]
    account_entitlement_independently_verified: bool = False
    storage_host_approved: bool = False
    may_fetch_real_fx_data: bool = False
    may_cache_real_fx_data: bool = False
    may_retain_derived_indicators: bool = False
    may_run_real_backtests: bool = False


def review_account_data_packet(
    packet: AccountDataReviewPacket,
    as_of_utc: datetime,
    *,
    requested_cache_retention_days: int,
    max_review_age: timedelta = timedelta(days=90),
) -> AccountDataReviewResult:
    """Review stated paperwork only; ALL operational permissions remain False.

    Revocation/expiry prepares a *non-executing* stop/retention review, not a
    deletion procedure (which itself may be restricted or subject to holds).
    """
    if not isinstance(packet, AccountDataReviewPacket):
        raise TypeError("Typed AccountDataReviewPacket required")
    ensure_utc(as_of_utc, "as_of_utc")
    if type(requested_cache_retention_days) is not int or not (
        1 <= requested_cache_retention_days <= 3650
    ):
        raise ValueError("INVALID_REQUESTED_RETENTION")
    if not isinstance(max_review_age, timedelta) or not (
        timedelta(0) < max_review_age <= timedelta(days=365)
    ):
        raise ValueError("INVALID_MAX_REVIEW_AGE")

    source = assess_source_for_m2_review(
        packet.public_capability, packet.rights, as_of_utc
    )
    storage = assess_durable_cache_proposal(
        packet.storage.proposal, source
    )
    r: set[str] = set(source.reasons)
    account = packet.account
    if packet.public_capability is None or (
        account.provider_id != packet.public_capability.provider_id or
        account.product_id != packet.public_capability.product_id
    ):
        r.add("ACCOUNT_PRODUCT_OR_PROVIDER_MISMATCH")
    if account.effective_from_utc > as_of_utc:
        r.add("ACCOUNT_CONTRACT_NOT_YET_EFFECTIVE")
    if account.first_seen_by_us_utc > as_of_utc:
        r.add("ACCOUNT_EVIDENCE_FUTURE_KNOWN")
    elif as_of_utc - account.first_seen_by_us_utc > max_review_age:
        r.add("ACCOUNT_ENTITLEMENT_REVIEW_STALE")
    if not packet.rights:
        r.add("NO_ACCOUNT_RIGHTS_DOCUMENTS")
    if packet.storage.proposal.storage_kind is StorageKind.MEMORY_SYNTHETIC:
        r.add("NOT_PERSISTENT_CACHE_ARCHITECTURE")

    allowed_max = packet.retention.maximum_days_claimed
    if allowed_max is None:
        r.add("VENDOR_RETENTION_LIMIT_NOT_ESTABLISHED")
    elif requested_cache_retention_days > allowed_max:
        r.add("REQUESTED_RETENTION_EXCEEDS_VENDOR_CLAIM")
    if packet.storage.region_ref not in packet.retention.allowed_storage_regions_claimed:
        r.add("STORAGE_RESIDENCY_NOT_COVERED_BY_CLAIM")
    if not packet.retention.derived_indicators_may_be_retained_claimed:
        r.add("DERIVED_INDICATOR_RETENTION_NOT_ESTABLISHED")
    if (requested_cache_retention_days >
            packet.storage.proposal.retention_days_proposed):
        r.add("CACHE_RETENTION_EXCEEDS_STORAGE_PROPOSAL")

    stop = False
    if account.expires_utc is not None and account.expires_utc <= as_of_utc:
        r.add("CONTRACT_EXPIRED_REVIEW_RETENTION")
        stop = True
    for right in packet.rights:
        if right.expires_utc is not None and right.expires_utc <= as_of_utc:
            stop = True

    if packet.revocation is not None:
        notice = packet.revocation
        if notice.first_seen_by_us_utc > as_of_utc:
            r.add("REVOCATION_NOTICE_FUTURE_KNOWN")
        elif notice.effective_utc <= as_of_utc:
            r.add("REVOCATION_NOTICED_STOP_ACCESS_AND_REVIEW_RETENTION")
            stop = True
        else:
            r.add("REVOCATION_SCHEDULED_NOT_YET_EFFECTIVE")
            # Acknowledged impending revocation: do not finalize new storage.
    if stop:
        r.add("STOP_FETCH_AND_WRITES_PRESERVE_AUDIT_PENDING_REVIEW")
        r.add("ACTUAL_QUARANTINE_OR_PURGE_NOT_IMPLEMENTED")

    # Keep operational terms outside this reviewer's control.
    if not storage.control_claims_complete:
        r.add("STORAGE_CONTROLS_NOT_COMPLETE")
    non_blocking_source = {
        "CLAIMED_PERMISSIONS_NEED_INDEPENDENT_CONTRACT_VALIDATION",
        "NO_QUALIFIED_NATIVE_BID_ASK_SAMPLE_OR_REPLAY_EVIDENCE",
    }
    has_source_blocker = any(x not in non_blocking_source for x in source.reasons)
    non_blocking_notice = {"REVOCATION_SCHEDULED_NOT_YET_EFFECTIVE"}
    packet_claims_ok = (
        not has_source_blocker and source.review_packet_ready and
        storage.control_claims_complete and not stop and
        not (r - set(source.reasons) - non_blocking_notice)
    )
    if packet_claims_ok:
        r.add("READY_PAPERWORK_ONLY_EXTERNAL_LEGAL_AND_VENDOR_CHECK_REQUIRED")
    state = (
        ReviewState.SUSPEND_AND_REVIEW_RETENTION if stop
        else ReviewState.READY_FOR_INDEPENDENT_REVIEW if packet_claims_ok
        else ReviewState.BLOCKED_MISSING_EVIDENCE
    )
    return AccountDataReviewResult(
        state, packet_claims_ok,
        storage.control_claims_complete,
        stop, source, tuple(sorted(r)),
    )
