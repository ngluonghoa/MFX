"""Immutable versioned experiment identity and rollback assessment (never executes)."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from json import dumps


@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    code_ref: str
    dependency_ref: str
    rule_ref: str
    parameter_ref: str
    provider_ref: str
    data_revision_ref: str
    calendar_ref: str
    bid_ask_basis_ref: str
    cost_fill_ref: str
    risk_ref: str
    persistence_schema_ref: str
    report_schema_ref: str

    def __post_init__(self) -> None:
        if any(not isinstance(x, str) or not x.strip() for x in asdict(self).values()):
            raise ValueError("Every profile component must be identified")

    @property
    def fingerprint(self) -> str:
        payload = dumps(asdict(self), sort_keys=True, ensure_ascii=True,
                        separators=(",", ":")).encode("utf-8")
        return sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class RollbackAssessment:
    compatible_in_read_only_replay: bool
    requires_external_review: bool
    reasons: tuple[str, ...]


def assess_rollback(current: ExecutionProfile, target: ExecutionProfile) -> RollbackAssessment:
    """Conservative preview; does not restore DB, undo broker fills or switch code."""
    reasons = []
    if current.persistence_schema_ref != target.persistence_schema_ref:
        reasons.append("PERSISTENCE_SCHEMA_MISMATCH")
    if current.bid_ask_basis_ref != target.bid_ask_basis_ref:
        reasons.append("QUOTE_BASIS_MISMATCH")
    if current.provider_ref != target.provider_ref:
        reasons.append("SOURCE_ADAPTER_MISMATCH")
    if current.data_revision_ref != target.data_revision_ref:
        reasons.append("SOURCE_REVISION_RECONCILIATION_REQUIRED")
    # Even matching references cannot prove real-world state/positions are safe.
    return RollbackAssessment(not reasons, True, tuple(reasons))
