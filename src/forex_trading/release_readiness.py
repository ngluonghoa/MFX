"""RE1: immutable *read-only* release evidence and conservative recovery preview.

All evidence here is caller-declared and must be checked against independent
GitHub/Drive/provider records outside this module. In particular, matching
hashes/CI claims do not imply an approved release, LKG, rollback, source right
or permission to trade. No API call, filesystem write or process execution.
"""
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from json import dumps
from re import fullmatch

from .versioning import ExecutionProfile, assess_rollback


class ReleaseGate(str, Enum):
    CODE_CI = "CODE_CI"
    REPRODUCIBLE_BUILD = "REPRODUCIBLE_BUILD"
    SOURCE_ENTITLEMENT = "SOURCE_ENTITLEMENT"
    CAUSAL_HISTORICAL_DATA = "CAUSAL_HISTORICAL_DATA"
    OOS_BACKTEST = "OOS_BACKTEST"
    COST_AND_RISK = "COST_AND_RISK"
    SECURITY_AND_KEY_CUSTODY = "SECURITY_AND_KEY_CUSTODY"
    RESTORE_DRILL = "RESTORE_DRILL"
    OWNER_SIGNOFF = "OWNER_SIGNOFF"


class EvidenceState(str, Enum):
    MISSING = "MISSING"
    BLOCKED = "BLOCKED"
    CLAIMED_PASS = "CLAIMED_PASS"


@dataclass(frozen=True, slots=True)
class GateEvidence:
    gate: ReleaseGate
    state: EvidenceState
    evidence_ref: str | None = None
    code_sha: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.gate, ReleaseGate) or not isinstance(
            self.state, EvidenceState
        ):
            raise TypeError("TYPED_RELEASE_GATE_AND_STATE_REQUIRED")
        if self.state is EvidenceState.CLAIMED_PASS:
            if not isinstance(self.evidence_ref, str) or not self.evidence_ref.strip():
                raise ValueError("PASS_CLAIM_REQUIRES_INDEPENDENT_EVIDENCE_REFERENCE")
        if self.code_sha is not None and not _is_sha(self.code_sha):
            raise ValueError("INVALID_GATE_CODE_SHA")


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and fullmatch(r"[0-9a-f]{40}", value) is not None


@dataclass(frozen=True, slots=True)
class ReleaseCandidate:
    """A proposed release manifest, never a release/tag or activation."""

    version: str
    code_sha: str
    package_sha256: str
    profile: ExecutionProfile
    receipts: tuple[GateEvidence, ...]

    def __post_init__(self) -> None:
        # Strict SemVer, no ambiguous 0-prefixes; releases are NOT created here.
        version = (
            r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
            r"(?:-(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
            r"(?:\+(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
        )
        if not isinstance(self.version, str) or fullmatch(version, self.version) is None:
            raise ValueError("INVALID_CANDIDATE_SEMVER")
        if not _is_sha(self.code_sha):
            raise ValueError("INVALID_CANDIDATE_CODE_SHA")
        if not isinstance(self.package_sha256, str) or fullmatch(
            r"[0-9a-f]{64}", self.package_sha256
        ) is None:
            raise ValueError("INVALID_PACKAGE_SHA256")
        if not isinstance(self.profile, ExecutionProfile):
            raise TypeError("TYPED_EXECUTION_PROFILE_REQUIRED")
        if not isinstance(self.receipts, tuple) or any(
            not isinstance(x, GateEvidence) for x in self.receipts
        ):
            raise TypeError("TYPED_IMMUTABLE_GATE_RECEIPTS_REQUIRED")
        if len({x.gate for x in self.receipts}) != len(self.receipts):
            raise ValueError("DUPLICATE_RELEASE_GATE_RECEIPT")

    @property
    def fingerprint(self) -> str:
        payload = {
            "format": "FX_READ_ONLY_CANDIDATE_V1",
            "version": self.version,
            "code_sha": self.code_sha,
            "package_sha256": self.package_sha256,
            "profile_fingerprint": self.profile.fingerprint,
            "receipts": [
                (x.gate.value, x.state.value, x.evidence_ref, x.code_sha)
                for x in sorted(self.receipts, key=lambda y: y.gate.value)
            ],
        }
        return sha256(dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ReleaseReview:
    missing_gates: tuple[ReleaseGate, ...]
    blocked_gates: tuple[ReleaseGate, ...]
    claimed_pass_unverified_gates: tuple[ReleaseGate, ...]
    mismatched_code_gates: tuple[ReleaseGate, ...]
    ready_for_independent_evidence_review: bool
    has_independently_verified_evidence: bool = False
    release_approved: bool = False
    may_publish_release: bool = False
    may_assign_lkg: bool = False
    may_activate: bool = False
    may_trade: bool = False


def review_release_candidate(candidate: ReleaseCandidate) -> ReleaseReview:
    """Evaluate claim completeness, not authenticity; NEVER approve release."""
    if not isinstance(candidate, ReleaseCandidate):
        raise TypeError("TYPED_RELEASE_CANDIDATE_REQUIRED")
    items = {e.gate: e for e in candidate.receipts}
    missing = tuple(g for g in ReleaseGate if g not in items or
                    items[g].state is EvidenceState.MISSING)
    blocked = tuple(g for g in ReleaseGate if g in items and
                    items[g].state is EvidenceState.BLOCKED)
    mismatched = tuple(g for g, e in items.items() if e.code_sha is not None and
                       e.code_sha != candidate.code_sha)
    claimed = tuple(g for g in ReleaseGate if g in items and
                    items[g].state is EvidenceState.CLAIMED_PASS)
    # Even a complete candidate is only ready for *external* evidence review.
    return ReleaseReview(
        missing, blocked, claimed, mismatched,
        not (missing or blocked or mismatched),
    )


@dataclass(frozen=True, slots=True)
class ReadOnlyRollbackPreview:
    changed_profile_fields: tuple[str, ...]
    incompatible_fields: tuple[str, ...]
    reasons: tuple[str, ...]
    limited_replay_compatible: bool
    requires_external_review: bool = True
    can_restore_runtime: bool = False
    can_undo_broker_fills: bool = False
    can_revert_cache_data: bool = False
    can_activate_lkg: bool = False
    may_trade: bool = False


def preview_full_profile_rollback(
    current: ExecutionProfile, target: ExecutionProfile,
) -> ReadOnlyRollbackPreview:
    """All 12 refs compared; no destructive or operational rollback action."""
    if not isinstance(current, ExecutionProfile) or not isinstance(
        target, ExecutionProfile
    ):
        raise TypeError("TYPED_ROLLBACK_PROFILES_REQUIRED")
    a, b = asdict(current), asdict(target)
    changed = tuple(k for k in a if a[k] != b[k])
    check = assess_rollback(current, target)
    # A change in ANY release-profile component requires separate review.
    # Schema/provider/revision/side mismatches are additionally incompatible
    # for naive read-only replay under the legacy conservative assessment.
    mismatched = tuple(k for k in changed if k in (
        "persistence_schema_ref", "provider_ref", "data_revision_ref",
        "bid_ask_basis_ref",
    ))
    reasons = check.reasons + (
        ("EXTERNAL_BROKER_CACHE_SECURITY_RECONCILIATION_REQUIRED",)
        if changed else ("NO_DEPLOYED_STATE_EVIDENCE",)
    )
    return ReadOnlyRollbackPreview(
        changed, mismatched, reasons, check.compatible_in_read_only_replay,
    )
