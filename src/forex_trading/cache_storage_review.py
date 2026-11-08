"""Read-only durable-cache design review. NEVER authorizes market-data storage.

These declarations specify future controls: rights, encryption, atomic writes,
recovery and revocation. Neither a self-asserted StorageProposal nor a synthetically
successful test substitutes for approval of a particular provider or runtime.
No files, databases or network are opened by this module.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256
from json import dumps
from re import fullmatch

from .cache_core import CachePartition, CandleSnapshot
from .quotes import ensure_utc
from .source_qualification import SourceQualification


class StorageKind(str, Enum):
    MEMORY_SYNTHETIC = "MEMORY_SYNTHETIC"
    ENCRYPTED_LOCAL_PROPOSED = "ENCRYPTED_LOCAL_PROPOSED"
    ENCRYPTED_REMOTE_PROPOSED = "ENCRYPTED_REMOTE_PROPOSED"


@dataclass(frozen=True, slots=True)
class DurableStorageProposal:
    """Non-sensitive storage-class reference; NEVER an active storage URL."""
    location_ref: str
    storage_kind: StorageKind
    schema_version: str
    encrypted_at_rest_claim: bool
    atomic_commit_claim: bool
    digest_verification_claim: bool
    restart_recovery_claim: bool
    append_only_audit_claim: bool
    retention_days_proposed: int
    revocation_purge_process_documented: bool

    def __post_init__(self) -> None:
        if not isinstance(self.storage_kind, StorageKind):
            raise TypeError("Explicit StorageKind required")
        for name in ("location_ref", "schema_version"):
            val = getattr(self, name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{name} required")
            if any(s in val for s in ("@", "://", "\\n", "\\r")):
                raise ValueError("NO_CREDENTIALS_OR_RAW_STORAGE_URLS_IN_MANIFEST")
        flags = (
            self.encrypted_at_rest_claim, self.atomic_commit_claim,
            self.digest_verification_claim, self.restart_recovery_claim,
            self.append_only_audit_claim, self.revocation_purge_process_documented,
        )
        if any(type(f) is not bool for f in flags):
            raise TypeError("Storage control claims must be booleans")
        if type(self.retention_days_proposed) is not int or not 1 <= self.retention_days_proposed <= 3650:
            raise ValueError("PROPOSED_RETENTION_OUT_OF_BOUNDS")


@dataclass(frozen=True, slots=True)
class StorageReview:
    control_claims_complete: bool
    outstanding: tuple[str, ...]
    provider_retention_right_independently_verified: bool
    host_security_approved: bool
    may_write_real_data: bool
    may_restore_real_data: bool


def assess_durable_cache_proposal(
    proposal: DurableStorageProposal, source: SourceQualification,
) -> StorageReview:
    if not isinstance(proposal, DurableStorageProposal) or not isinstance(
        source, SourceQualification
    ):
        raise TypeError("Typed proposal and SourceQualification required")
    reasons = []
    if proposal.storage_kind is StorageKind.MEMORY_SYNTHETIC:
        reasons.append("NOT_DURABLE_STORAGE")
    for name in (
        "encrypted_at_rest_claim", "atomic_commit_claim",
        "digest_verification_claim", "restart_recovery_claim",
        "append_only_audit_claim", "revocation_purge_process_documented",
    ):
        if not getattr(proposal, name):
            reasons.append(f"STORAGE_CONTROL_MISSING:{name}")
    if not source.may_cache_or_store_real_data:
        reasons.append("PROVIDER_STORAGE_AND_CACHE_RIGHT_NOT_VERIFIED")
    if not source.vendor_entitlement_independently_verified:
        reasons.append("SOURCE_CONTRACT_NOT_INDEPENDENTLY_ATTESTED")
    reasons.extend((
        "HOST_ACL_KEY_MANAGEMENT_AND_RECOVERY_NOT_APPROVED",
        "REAL_RETENTION_REVOCATION_TEST_NOT_RUN",
        "NO_PRODUCTION_IO_BACKEND_PRESENT",
    ))
    claims = (
        proposal.storage_kind is not StorageKind.MEMORY_SYNTHETIC and
        all(getattr(proposal, n) for n in (
            "encrypted_at_rest_claim", "atomic_commit_claim",
            "digest_verification_claim", "restart_recovery_claim",
            "append_only_audit_claim", "revocation_purge_process_documented",
        ))
    )
    return StorageReview(claims, tuple(sorted(set(reasons))),
                         False, False, False, False)


@dataclass(frozen=True, slots=True)
class SyntheticGenerationManifest:
    """Deterministic metadata-only generation; no OHLC stored in this object."""
    partition_fingerprint: str
    cache_fingerprint: str
    schema_version: str
    source_revision_claim: str
    generation: int
    created_at_utc: datetime
    previous_manifest_sha256: str | None
    manifest_sha256: str

    def __post_init__(self) -> None:
        for key in ("partition_fingerprint", "cache_fingerprint", "schema_version",
                    "source_revision_claim"):
            val = getattr(self, key)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{key} required")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("GENERATION_MUST_BE_POSITIVE")
        ensure_utc(self.created_at_utc, "created_at_utc")
        if not fullmatch(r"[a-f0-9]{64}", self.manifest_sha256):
            raise ValueError("INVALID_MANIFEST_DIGEST")
        if self.previous_manifest_sha256 is not None and not fullmatch(
            r"[a-f0-9]{64}", self.previous_manifest_sha256
        ):
            raise ValueError("INVALID_PARENT_MANIFEST_DIGEST")


def _manifest_digest(payload: tuple[object, ...]) -> str:
    return sha256(dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()


def make_synthetic_generation(
    snapshot: CandleSnapshot, created_at_utc: datetime,
    previous: SyntheticGenerationManifest | None = None,
) -> SyntheticGenerationManifest:
    """Plan an immutable manifest. Does NOT commit a file or retain data."""
    if not isinstance(snapshot, CandleSnapshot):
        raise TypeError("CandleSnapshot required")
    ensure_utc(created_at_utc, "created_at_utc")
    if snapshot.checked_at_utc > created_at_utc:
        raise ValueError("MANIFEST_PREDATES_SNAPSHOT")
    if previous is not None and not isinstance(previous, SyntheticGenerationManifest):
        raise TypeError("SyntheticGenerationManifest previous required")
    if previous is not None:
        # Schema change is a migration even though it also changes partition SHA.
        # Report the more actionable SAFE_MODE reason before generic mismatch.
        if previous.schema_version != snapshot.partition.schema_version:
            raise ValueError("SCHEMA_MIGRATION_REQUIRES_EXPLICIT_REVIEW")
        if previous.partition_fingerprint != snapshot.partition.fingerprint:
            raise ValueError("CROSS_PARTITION_GENERATION_CHAIN")
        if previous.created_at_utc > created_at_utc:
            raise ValueError("GENERATION_CLOCK_ROLLBACK")
    generation = 1 if previous is None else previous.generation + 1
    parent = previous.manifest_sha256 if previous is not None else None
    payload = (snapshot.partition.fingerprint, snapshot.fingerprint,
               snapshot.partition.schema_version, snapshot.source_head_claim,
               generation, created_at_utc.isoformat(), parent)
    digest = _manifest_digest(payload)
    return SyntheticGenerationManifest(
        snapshot.partition.fingerprint, snapshot.fingerprint,
        snapshot.partition.schema_version, snapshot.source_head_claim,
        generation, created_at_utc, parent, digest,
    )


def validate_synthetic_generation_chain(
    current: SyntheticGenerationManifest,
    previous: SyntheticGenerationManifest | None = None,
) -> bool:
    """Tamper/rollback metadata guard, not trusted storage or source proof."""
    if not isinstance(current, SyntheticGenerationManifest):
        raise TypeError("Expected generation manifest")
    if previous is None:
        if current.generation != 1 or current.previous_manifest_sha256 is not None:
            raise ValueError("GENESIS_CHAIN_CONFLICT")
    else:
        if not isinstance(previous, SyntheticGenerationManifest):
            raise TypeError("Previous generation manifest required")
        if current.generation != previous.generation + 1:
            raise ValueError("GENERATION_SEQUENCE_GAP_OR_ROLLBACK")
        if current.previous_manifest_sha256 != previous.manifest_sha256:
            raise ValueError("GENERATION_PARENT_MISMATCH")
        if (current.partition_fingerprint != previous.partition_fingerprint
                or current.schema_version != previous.schema_version):
            raise ValueError("GENERATION_PARTITION_OR_SCHEMA_CHANGE")
        if current.created_at_utc < previous.created_at_utc:
            raise ValueError("GENERATION_CLOCK_ROLLBACK")
    payload = (current.partition_fingerprint, current.cache_fingerprint,
               current.schema_version, current.source_revision_claim,
               current.generation, current.created_at_utc.isoformat(),
               current.previous_manifest_sha256)
    if current.manifest_sha256 != _manifest_digest(payload):
        raise ValueError("GENERATION_CHECKSUM_MISMATCH")
    return True
