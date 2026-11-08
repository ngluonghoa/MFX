"""M2/P0.6: synthetic-only rights invalidation and crash recovery decisions.

This module operates on nonsecret fingerprints and manifests, not price data.
It does not read/write a disk, make vendor requests, enable a host, or grant
data entitlement. Any durable pointer or generation floor is an UNTRUSTED
fixture claim, not an independently anchored anti-rollback proof.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from re import fullmatch

from .account_data_review import (
    AccountDataReviewPacket, AccountDataReviewResult, ReviewState,
    review_account_data_packet,
)
from .cache_storage_review import (
    SyntheticGenerationManifest, validate_synthetic_generation_chain,
)
from .quotes import ensure_utc


LAYERS = ("L1", "L2", "L3", "L4", "L5")


class SyntheticRightsAction(str, Enum):
    PAPERWORK_ONLY = "PAPERWORK_ONLY"
    INVALIDATE_AND_REVIEW = "INVALIDATE_AND_REVIEW"
    BLOCK_UNVERIFIED = "BLOCK_UNVERIFIED"


@dataclass(frozen=True, slots=True)
class SyntheticRightsCachePlan:
    action: SyntheticRightsAction
    account_review: AccountDataReviewResult
    partition_fingerprints: tuple[str, ...]
    invalidated_layers: tuple[str, ...]
    # These clocks are for audit visibility, not automatic retrospective edits.
    observed_revocation_first_seen_utc: datetime | None
    observed_revocation_effective_utc: datetime | None
    reasons: tuple[str, ...]
    may_fetch_real_data: bool = False
    may_reuse_real_cache: bool = False
    may_purge_or_restore_real_data: bool = False


def plan_synthetic_rights_cache_transition(
    packet: AccountDataReviewPacket,
    as_of_utc: datetime,
    partition_fingerprints: tuple[str, ...],
    *,
    requested_cache_retention_days: int,
) -> SyntheticRightsCachePlan:
    """Model selective partition invalidation, never execute it.

    Every affected partition is an opaque 64-hex SHA-256 fingerprint. A future
    observed revocation must NOT appear as an earlier known revocation event.
    Expiry/denial blocks new use without deleting lawful audit evidence.
    """
    if not isinstance(packet, AccountDataReviewPacket):
        raise TypeError("Typed account packet required")
    ensure_utc(as_of_utc, "as_of_utc")
    if not isinstance(partition_fingerprints, tuple) or not partition_fingerprints:
        raise TypeError("Nonempty immutable partition fingerprint tuple required")
    if len(partition_fingerprints) > 200:
        raise ValueError("SYNTHETIC_SCOPE_TOO_LARGE")
    if any(not isinstance(x, str) or not fullmatch(r"[a-f0-9]{64}", x)
           for x in partition_fingerprints):
        raise ValueError("INVALID_PARTITION_FINGERPRINT")
    if len(set(partition_fingerprints)) != len(partition_fingerprints):
        raise ValueError("DUPLICATE_PARTITION_FINGERPRINT")

    review = review_account_data_packet(
        packet, as_of_utc,
        requested_cache_retention_days=requested_cache_retention_days,
    )
    if review.state is ReviewState.SUSPEND_AND_REVIEW_RETENTION:
        action = SyntheticRightsAction.INVALIDATE_AND_REVIEW
    elif review.state is ReviewState.BLOCKED_MISSING_EVIDENCE:
        action = SyntheticRightsAction.BLOCK_UNVERIFIED
    else:
        action = SyntheticRightsAction.PAPERWORK_ONLY

    seen = effective = None
    notice = packet.revocation
    if notice is not None and notice.first_seen_by_us_utc <= as_of_utc:
        seen = notice.first_seen_by_us_utc
        effective = notice.effective_utc

    reasons = set(review.reasons)
    reasons.add("SYNTHETIC_ONLY_NO_VENDOR_OR_HOST_APPROVAL")
    if action is SyntheticRightsAction.INVALIDATE_AND_REVIEW:
        reasons.add("PROPOSE_INVALIDATE_L1_TO_L5_PRESERVE_AUDIT")
    elif action is SyntheticRightsAction.BLOCK_UNVERIFIED:
        reasons.add("UNVERIFIED_RIGHTS_BLOCK_CACHE_REUSE")
    return SyntheticRightsCachePlan(
        action=action,
        account_review=review,
        partition_fingerprints=partition_fingerprints,
        invalidated_layers=LAYERS if action is not SyntheticRightsAction.PAPERWORK_ONLY else (),
        observed_revocation_first_seen_utc=seen,
        observed_revocation_effective_utc=effective,
        reasons=tuple(sorted(reasons)),
    )


class SyntheticRecoveryState(str, Enum):
    STABLE_GENERATION = "STABLE_GENERATION"
    COMMITTED_NEW_GENERATION = "COMMITTED_NEW_GENERATION"
    FAIL_CLOSED = "FAIL_CLOSED"


@dataclass(frozen=True, slots=True)
class SyntheticRecoveryVerdict:
    state: SyntheticRecoveryState
    selected_manifest: SyntheticGenerationManifest | None
    reasons: tuple[str, ...]
    may_restore_real_data: bool = False
    may_write_real_data: bool = False


def evaluate_synthetic_atomic_recovery(
    stable: SyntheticGenerationManifest,
    staged: SyntheticGenerationManifest | None,
    committed_pointer_sha256: str | None,
    policy: SyntheticRightsCachePlan,
    *,
    stable_parent: SyntheticGenerationManifest | None = None,
    minimum_expected_generation_claim: int = 1,
) -> SyntheticRecoveryVerdict:
    """Evaluate simulated commit-marker crash windows; no physical recovery.

    A marker pointing to stable ignores an orphan staged generation. A marker
    pointing to staged requires a valid parent link and full checksum. A torn
    marker, unexpected pointer, checksum failure or rollback floor fails closed.
    A claim supplied by a caller is NOT a trusted external rollback anchor.
    """
    if not isinstance(stable, SyntheticGenerationManifest):
        raise TypeError("Stable synthetic generation required")
    if staged is not None and not isinstance(staged, SyntheticGenerationManifest):
        raise TypeError("Staged synthetic generation must be typed")
    if not isinstance(policy, SyntheticRightsCachePlan):
        raise TypeError("Typed synthetic rights plan required")
    if type(minimum_expected_generation_claim) is not int or minimum_expected_generation_claim < 1:
        raise ValueError("INVALID_GENERATION_FLOOR")

    def blocked(reason: str) -> SyntheticRecoveryVerdict:
        return SyntheticRecoveryVerdict(SyntheticRecoveryState.FAIL_CLOSED, None, (reason,))

    if policy.action is not SyntheticRightsAction.PAPERWORK_ONLY:
        return blocked("RIGHTS_REVIEW_BLOCKS_SYNTHETIC_REUSE")
    try:
        # A claimed parent also needs its own checksum checked. This bounded
        # reference evaluator only accepts a verified genesis parent; deeper
        # chains require an explicit, independently audited ancestor walk.
        if stable_parent is not None:
            validate_synthetic_generation_chain(stable_parent)
        validate_synthetic_generation_chain(stable, stable_parent)
    except (ValueError, TypeError) as exc:
        return blocked("STABLE_MANIFEST_INVALID:" + str(exc))

    if not isinstance(committed_pointer_sha256, str) or not fullmatch(
        r"[a-f0-9]{64}", committed_pointer_sha256
    ):
        return blocked("COMMIT_POINTER_MISSING_OR_TORN")

    if committed_pointer_sha256 == stable.manifest_sha256:
        selected = stable
        state = SyntheticRecoveryState.STABLE_GENERATION
        reasons = ("ORPHAN_STAGE_NOT_PROMOTED",) if staged is not None else ()
    elif staged is not None and committed_pointer_sha256 == staged.manifest_sha256:
        try:
            validate_synthetic_generation_chain(staged, stable)
        except (ValueError, TypeError) as exc:
            return blocked("STAGED_MANIFEST_INVALID:" + str(exc))
        selected = staged
        state = SyntheticRecoveryState.COMMITTED_NEW_GENERATION
        reasons = ()
    else:
        return blocked("COMMIT_POINTER_UNKNOWN_OR_ROLLBACK")

    if selected.generation < minimum_expected_generation_claim:
        return blocked("GENERATION_BELOW_CLAIMED_FLOOR")
    return SyntheticRecoveryVerdict(state, selected, reasons)
