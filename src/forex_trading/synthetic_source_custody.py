"""Causal synthetic source-receipt custody — no signature or vendor trust.

The *first seen by our fixture* clock must not be backdated to a provider's
claimed publication clock. Hash-chain validation helps spot local changes
but without trusted external anchoring it is NOT tamper-proof or licensed data.
"""
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from json import dumps
from re import fullmatch

from .quotes import ensure_utc


def _required(x: str, label: str) -> None:
    if not isinstance(x, str) or not x.strip():
        raise ValueError(f"{label} required")


def _digest(payload: tuple[object, ...]) -> str:
    return sha256(dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SyntheticSourceReceipt:
    partition_fingerprint: str
    vendor_revision_claim: str
    vendor_event_utc_claim: datetime
    observed_at_utc: datetime
    first_seen_by_us_utc: datetime
    payload_sha256_claim: str
    ordinal: int
    previous_receipt_sha256: str | None
    receipt_sha256: str

    def __post_init__(self) -> None:
        for field in ("partition_fingerprint", "vendor_revision_claim"):
            _required(getattr(self, field), field)
        for field in ("vendor_event_utc_claim", "observed_at_utc",
                      "first_seen_by_us_utc"):
            ensure_utc(getattr(self, field), field)
        if self.vendor_event_utc_claim > self.observed_at_utc:
            raise ValueError("VENDOR_EVENT_CANNOT_BE_FUTURE_OF_OBSERVATION")
        if self.first_seen_by_us_utc < self.observed_at_utc:
            raise ValueError("LOCAL_FIRST_SEEN_CANNOT_PREDATE_OBSERVATION")
        if type(self.ordinal) is not int or self.ordinal < 1:
            raise ValueError("SOURCE_RECEIPT_SEQUENCE_INVALID")
        for d in (self.payload_sha256_claim, self.receipt_sha256):
            if not isinstance(d, str) or not fullmatch(r"[0-9a-f]{64}", d):
                raise ValueError("RECEIPT_SHA256_INVALID")
        if self.previous_receipt_sha256 is not None and not fullmatch(
            r"[0-9a-f]{64}", self.previous_receipt_sha256
        ):
            raise ValueError("RECEIPT_PARENT_SHA256_INVALID")


def _canonical(r: SyntheticSourceReceipt) -> tuple[object, ...]:
    return (r.partition_fingerprint, r.vendor_revision_claim,
            r.vendor_event_utc_claim.isoformat(), r.observed_at_utc.isoformat(),
            r.first_seen_by_us_utc.isoformat(), r.payload_sha256_claim,
            r.ordinal, r.previous_receipt_sha256)


def make_synthetic_source_receipt(
    partition_fingerprint: str,
    vendor_revision_claim: str,
    vendor_event_utc_claim: datetime,
    observed_at_utc: datetime,
    first_seen_by_us_utc: datetime,
    payload_sha256_claim: str,
    *,
    previous: SyntheticSourceReceipt | None = None,
) -> SyntheticSourceReceipt:
    if previous is not None and not isinstance(previous, SyntheticSourceReceipt):
        raise TypeError("Typed previous receipt required")
    # Construct a self-validating candidate using the digest of its real fields.
    seq = (previous.ordinal + 1) if previous is not None else 1
    parent = previous.receipt_sha256 if previous is not None else None
    skeleton = SyntheticSourceReceipt(
        partition_fingerprint, vendor_revision_claim, vendor_event_utc_claim,
        observed_at_utc, first_seen_by_us_utc, payload_sha256_claim,
        seq, parent, "0"*64,
    )
    if previous is not None:
        if previous.partition_fingerprint != partition_fingerprint:
            raise ValueError("CROSS_PARTITION_CUSTODY_CHAIN")
        if observed_at_utc < previous.observed_at_utc:
            raise ValueError("SOURCE_OBSERVATION_CLOCK_ROLLBACK")
        if first_seen_by_us_utc < previous.first_seen_by_us_utc:
            raise ValueError("SOURCE_FIRST_SEEN_CLOCK_ROLLBACK")
        if (vendor_revision_claim == previous.vendor_revision_claim
                and payload_sha256_claim != previous.payload_sha256_claim):
            raise ValueError("SAME_VENDOR_REVISION_CONFLICTING_PAYLOAD")
    from dataclasses import replace
    return replace(skeleton, receipt_sha256=_digest(_canonical(skeleton)))


def validate_synthetic_source_custody(
    current: SyntheticSourceReceipt,
    previous: SyntheticSourceReceipt | None = None,
) -> bool:
    if not isinstance(current, SyntheticSourceReceipt):
        raise TypeError("Typed receipt required")
    if previous is None:
        if current.ordinal != 1 or current.previous_receipt_sha256 is not None:
            raise ValueError("RECEIPT_GENESIS_CONFLICT")
    else:
        if not isinstance(previous, SyntheticSourceReceipt):
            raise TypeError("Typed previous receipt required")
        if current.partition_fingerprint != previous.partition_fingerprint:
            raise ValueError("RECEIPT_PARTITION_CONFLICT")
        if current.ordinal != previous.ordinal + 1:
            raise ValueError("RECEIPT_ORDINAL_ROLLBACK_OR_GAP")
        if current.previous_receipt_sha256 != previous.receipt_sha256:
            raise ValueError("RECEIPT_PARENT_MISMATCH")
        if current.observed_at_utc < previous.observed_at_utc:
            raise ValueError("SOURCE_OBSERVATION_CLOCK_ROLLBACK")
        if current.first_seen_by_us_utc < previous.first_seen_by_us_utc:
            raise ValueError("SOURCE_FIRST_SEEN_CLOCK_ROLLBACK")
        if (current.vendor_revision_claim == previous.vendor_revision_claim
                and current.payload_sha256_claim != previous.payload_sha256_claim):
            raise ValueError("SAME_VENDOR_REVISION_CONFLICTING_PAYLOAD")
    if _digest(_canonical(current)) != current.receipt_sha256:
        raise ValueError("SOURCE_CUSTODY_DIGEST_MISMATCH")
    return True


def select_synthetic_receipt_asof(
    receipts: tuple[SyntheticSourceReceipt, ...], decision_utc: datetime,
) -> SyntheticSourceReceipt | None:
    """Use LOCAL first-seen, not backdated vendor publication. No real source IO."""
    ensure_utc(decision_utc, "decision_utc")
    if not isinstance(receipts, tuple) or any(
        not isinstance(x, SyntheticSourceReceipt) for x in receipts
    ):
        raise TypeError("Immutable typed receipts required")
    prior: SyntheticSourceReceipt | None = None
    eligible: SyntheticSourceReceipt | None = None
    for receipt in receipts:
        validate_synthetic_source_custody(receipt, prior)
        prior = receipt
        if receipt.first_seen_by_us_utc <= decision_utc:
            eligible = receipt
    return eligible


@dataclass(frozen=True, slots=True)
class SyntheticCustodyVerdict:
    local_chain_consistent: bool
    independently_signed_by_vendor: bool = False
    data_retention_rights_verified: bool = False
    may_replay_for_real_backtest: bool = False


def assess_synthetic_custody(
    receipt: SyntheticSourceReceipt,
    previous: SyntheticSourceReceipt | None = None,
) -> SyntheticCustodyVerdict:
    return SyntheticCustodyVerdict(validate_synthetic_source_custody(receipt, previous))
