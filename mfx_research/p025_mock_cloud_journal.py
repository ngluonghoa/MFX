"""A04/P0.25: deterministic metadata-only MOCK Cloud CAS journal research.

No actual Google Drive writes, market-price payloads, provider calls, broker
orders or real BUY/SELL notifications. Hash chains are checksums, NOT trusted
digital signatures or proof of exactly-once external delivery.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256
import json

from forex_trading.quotes import ensure_utc

_GENESIS = sha256(b"SIM:MFX_P025_METADATA_ONLY_GENESIS_V1").hexdigest()
_MAX_HISTORY = 128
_MAX_EVENTS = 32


def _sim(value: str, field: str) -> None:
    if (not isinstance(value, str) or
            not 5 <= len(value) <= 128 or
            not value.startswith("SIM:") or
            any(x.isspace() for x in value)):
        raise ValueError("P025_SIM_ONLY_" + field)


def _sha(value: object) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SimMetadataEvent:
    instrument_version: str
    rule_id: str
    policy_version: str
    origin_event_id: str
    provider_id: str
    stream_id: str
    calendar_version: str
    aggregation_version: str
    candle_end_utc: datetime
    first_known_utc: datetime
    retrieved_at_utc: datetime
    quote_side: str = "MID"
    license_scope_claim: str = "SYNTHETIC_ONLY"
    original_numeric_approved: bool = False
    raw_market_bar: object | None = None

    def __post_init__(self) -> None:
        for field in ("instrument_version", "policy_version",
                      "origin_event_id", "provider_id", "stream_id",
                      "calendar_version", "aggregation_version"):
            _sim(getattr(self, field), field)
        if self.rule_id not in ("B2", "S2"):
            raise ValueError("P025_ONLY_SIM_B2_S2")
        if (self.quote_side != "MID"
                or self.license_scope_claim != "SYNTHETIC_ONLY"
                or type(self.original_numeric_approved) is not bool
                or self.original_numeric_approved
                or self.raw_market_bar is not None):
            raise ValueError("P025_REJECT_REAL_QUOTES_OR_SOURCE_APPROVAL")
        for name in ("candle_end_utc", "first_known_utc", "retrieved_at_utc"):
            ensure_utc(getattr(self, name), name)
        if not (
            self.candle_end_utc <= self.first_known_utc
            <= self.retrieved_at_utc
        ):
            raise ValueError("P025_BAD_OBSERVABLE_CLOCK_ORDER")

    @property
    def event_id(self) -> str:
        return _sha({
            "pair": self.instrument_version, "rule": self.rule_id,
            "policy": self.policy_version, "origin": self.origin_event_id,
            "provider": self.provider_id, "stream": self.stream_id,
            "calendar": self.calendar_version,
            "aggregation": self.aggregation_version,
            "candle_end": self.candle_end_utc.isoformat(),
            "first_known": self.first_known_utc.isoformat(),
            "retrieved": self.retrieved_at_utc.isoformat(),
            "side": self.quote_side,
            "permission": self.license_scope_claim,
        })


@dataclass(frozen=True, slots=True)
class SimJournalPolicy:
    version: str
    ttl_seconds: int = 600
    lease_seconds: int = 60
    metadata_storage_reviewed: bool = False
    metadata_access_revoked: bool = False
    source_numeric_approved: bool = False
    allow_real_drive_writes: bool = False
    allow_notifications: bool = False

    def __post_init__(self) -> None:
        _sim(self.version, "JOURNAL_POLICY")
        if (type(self.ttl_seconds) is not int
                or not 1 <= self.ttl_seconds <= 86400
                or type(self.lease_seconds) is not int
                or not 1 <= self.lease_seconds <= 600):
            raise ValueError("P025_INVALID_SIM_TTL_OR_LEASE")
        for field in ("metadata_storage_reviewed",
                      "metadata_access_revoked", "source_numeric_approved",
                      "allow_real_drive_writes", "allow_notifications"):
            if type(getattr(self, field)) is not bool:
                raise TypeError("P025_TYPED_EXPLICIT_POLICY_FLAGS")
        if (self.source_numeric_approved or self.allow_real_drive_writes
                or self.allow_notifications):
            raise ValueError("P025_FORGED_REAL_PERMISSION")


class MockPhase(str, Enum):
    QUEUED = "QUEUED_SIM"
    LEASED = "LEASED_SIM"
    AMBIGUOUS = "DELIVERY_AMBIGUOUS_SIM"


class MockOutcome(str, Enum):
    JOURNALED = "RESEARCH_JOURNALED"
    DUPLICATE_DENIED = "DUPLICATE_DENIED"
    EXPIRED_DENIED = "EXPIRED_DENIED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CAP_DENIED = "CAP_DENIED"
    CLAIMED = "CLAIMED_SIM_ONLY"
    LEASE_BUSY = "LEASE_BUSY"
    FENCE_DENIED = "STALE_FENCE_DENIED"
    RELEASED = "RELEASED_SIM_ONLY"
    ATTEMPT_AMBIGUOUS = "DELIVERY_AMBIGUOUS_SIM_ONLY"
    AMBIGUOUS_DENIED = "NO_AUTOMATIC_RETRY_AMBIGUOUS"
    RECEIVER_ACK_REQUIRED = "EXTERNAL_ACK_UNPROVABLE"


@dataclass(frozen=True, slots=True)
class MockEventRecord:
    event: SimMetadataEvent
    expires_utc: datetime
    phase: MockPhase = MockPhase.QUEUED
    fence: int = 0
    worker_id: str | None = None
    lease_until_utc: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event, SimMetadataEvent):
            raise TypeError("P025_TYPED_METADATA_EVENT")
        ensure_utc(self.expires_utc, "expires_utc")
        if self.expires_utc < self.event.retrieved_at_utc:
            raise ValueError("P025_EXPIRY_BEFORE_OBSERVABLE")
        if type(self.fence) is not int or self.fence < 0:
            raise ValueError("P025_BAD_FENCE_EPOCH")
        if not isinstance(self.phase, MockPhase):
            raise TypeError("P025_TYPED_EVENT_PHASE")
        if self.phase is MockPhase.LEASED:
            if (self.worker_id is None or self.lease_until_utc is None
                    or self.fence < 1):
                raise ValueError("P025_LEASE_REQUIRES_FENCE_AND_WORKER")
            _sim(self.worker_id, "WORKER_ID")
            ensure_utc(self.lease_until_utc, "lease_until_utc")
        elif self.worker_id is not None or self.lease_until_utc is not None:
            raise ValueError("P025_NONLEASED_HAS_ACTIVE_OWNER")


def _record_payload(r: MockEventRecord) -> dict[str, object]:
    return {
        "event": r.event.event_id, "expires": r.expires_utc.isoformat(),
        "phase": r.phase.value, "fence": r.fence,
        "worker": r.worker_id,
        "lease": (r.lease_until_utc.isoformat()
                  if r.lease_until_utc is not None else None),
    }


def _state_hash(records: tuple[MockEventRecord, ...]) -> str:
    return _sha(sorted(
        (_record_payload(r) for r in records),
        key=lambda r: str(r["event"]),
    ))


@dataclass(frozen=True, slots=True)
class MockJournalEntry:
    revision: int
    action: str
    event_id: str
    at_utc: datetime
    previous_hash: str
    state_hash: str
    digest: str

    def __post_init__(self) -> None:
        ensure_utc(self.at_utc, "at_utc")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("P025_BAD_ENTRY_REVISION")
        if self.action not in ("OFFER", "CLAIM", "RELEASE", "ATTEMPT_INTENT"):
            raise ValueError("P025_UNREGISTERED_JOURNAL_TRANSITION")
        if not (len(self.event_id) == 64
                and len(self.previous_hash) == 64
                and len(self.state_hash) == 64
                and len(self.digest) == 64):
            raise ValueError("P025_BAD_EVENT_OR_HASH_LENGTH")
        if self.digest != self.expected_digest():
            raise ValueError("P025_TAMPERED_JOURNAL_ENTRY_DIGEST")

    def expected_digest(self) -> str:
        return _sha({
            "revision": self.revision, "action": self.action,
            "event": self.event_id, "at": self.at_utc.isoformat(),
            "previous": self.previous_hash, "state": self.state_hash,
        })


@dataclass(frozen=True, slots=True)
class MockJournalSnapshot:
    schema: str = "SIM:P025-METADATA-V1"
    revision: int = 0
    records: tuple[MockEventRecord, ...] = ()
    entries: tuple[MockJournalEntry, ...] = ()

    @property
    def head_hash(self) -> str:
        return self.entries[-1].digest if self.entries else _GENESIS

    def __post_init__(self) -> None:
        if self.schema != "SIM:P025-METADATA-V1":
            raise ValueError("P025_SCHEMA_MIGRATION_NEEDS_APPROVAL")
        if (type(self.revision) is not int or self.revision < 0
                or not isinstance(self.records, tuple)
                or not isinstance(self.entries, tuple)
                or len(self.records) > _MAX_EVENTS
                or len(self.entries) > _MAX_HISTORY
                or len(self.entries) != self.revision):
            raise ValueError("P025_BOUNDED_APPEND_ONLY_HISTORY")
        if not all(isinstance(r, MockEventRecord) for r in self.records):
            raise TypeError("P025_TYPED_RECORDS")
        if not all(isinstance(e, MockJournalEntry) for e in self.entries):
            raise TypeError("P025_TYPED_CHAIN_ENTRIES")
        if len({r.event.event_id for r in self.records}) != len(self.records):
            raise ValueError("P025_IMMUTABLE_EVENT_ID_REUSE")
        prev = _GENESIS
        for i, entry in enumerate(self.entries):
            if entry.revision != i + 1 or entry.previous_hash != prev:
                raise ValueError("P025_CHAIN_REORDER_OR_TAMPER")
            prev = entry.digest
        if self.entries and self.entries[-1].state_hash != _state_hash(
            self.records
        ):
            raise ValueError("P025_SNAPSHOT_STATE_TAMPER")
        if not self.entries and self.records:
            raise ValueError("P025_UNJOURNALED_RECORDS")


@dataclass(frozen=True, slots=True)
class MockJournalDecision:
    outcome: MockOutcome
    snapshot: MockJournalSnapshot
    reason: str
    can_publish: bool = False
    source_numeric_approved: bool = False
    real_drive_writes: int = 0
    provider_calls: int = 0
    broker_orders: int = 0


def _new_snapshot(
    before: MockJournalSnapshot,
    records: tuple[MockEventRecord, ...],
    action: str,
    event_id: str,
    at_utc: datetime,
) -> MockJournalSnapshot:
    ensure_utc(at_utc, "at_utc")
    if before.revision >= _MAX_HISTORY:
        raise ValueError("P025_NO_SILENT_COMPACTION")
    base = {
        "revision": before.revision + 1, "action": action,
        "event": event_id, "at": at_utc.isoformat(),
        "previous": before.head_hash, "state": _state_hash(records),
    }
    entry = MockJournalEntry(
        revision=before.revision + 1, action=action,
        event_id=event_id, at_utc=at_utc,
        previous_hash=before.head_hash,
        state_hash=_state_hash(records), digest=_sha(base),
    )
    return MockJournalSnapshot(
        schema=before.schema, revision=before.revision + 1,
        records=records, entries=before.entries + (entry,),
    )


def _deny(
    original: MockJournalSnapshot, outcome: MockOutcome, reason: str,
) -> MockJournalDecision:
    return MockJournalDecision(outcome=outcome, snapshot=original,
                               reason=reason)


def _permission(policy: SimJournalPolicy) -> bool:
    if not isinstance(policy, SimJournalPolicy):
        raise TypeError("P025_TYPED_MOCK_STORAGE_POLICY")
    return policy.metadata_storage_reviewed and not policy.metadata_access_revoked


def _record_at(
    snapshot: MockJournalSnapshot, event_id: str,
) -> tuple[int, MockEventRecord]:
    for i, r in enumerate(snapshot.records):
        if r.event.event_id == event_id:
            return i, r
    raise ValueError("P025_UNKNOWN_EVENT_ID")


def offer_sim_event(
    snapshot: MockJournalSnapshot, event: SimMetadataEvent,
    now_utc: datetime, policy: SimJournalPolicy,
) -> MockJournalDecision:
    ensure_utc(now_utc, "now_utc")
    if (not isinstance(snapshot, MockJournalSnapshot)
            or not isinstance(event, SimMetadataEvent)):
        raise TypeError("P025_TYPED_SIM_JOURNAL_OFFER")
    if not _permission(policy):
        return _deny(snapshot, MockOutcome.PERMISSION_DENIED,
                     "P025_SIM_METADATA_RIGHTS_UNREVIEWED_OR_REVOKED")
    if now_utc < event.retrieved_at_utc:
        raise ValueError("P025_FUTURE_KNOWN_OR_RETRIEVED_METADATA")
    if any(r.event.event_id == event.event_id for r in snapshot.records):
        return _deny(snapshot, MockOutcome.DUPLICATE_DENIED,
                     "P025_EVENT_ID_NEVER_RECYCLED")
    expires = event.retrieved_at_utc + timedelta(seconds=policy.ttl_seconds)
    if now_utc > expires:
        return _deny(snapshot, MockOutcome.EXPIRED_DENIED,
                     "P025_NEVER_SEEN_EVENT_TTL_EXPIRED")
    if len(snapshot.records) >= _MAX_EVENTS:
        return _deny(snapshot, MockOutcome.CAP_DENIED,
                     "P025_NO_SILENT_RECORD_COMPACTION")
    record = MockEventRecord(event=event, expires_utc=expires)
    updated = _new_snapshot(
        snapshot, snapshot.records + (record,),
        "OFFER", event.event_id, now_utc,
    )
    return MockJournalDecision(
        outcome=MockOutcome.JOURNALED, snapshot=updated,
        reason="P025_SIM_METADATA_RESEARCH_JOURNAL_ONLY",
    )


def claim_sim_event(
    snapshot: MockJournalSnapshot, event_id: str, worker_id: str,
    now_utc: datetime, policy: SimJournalPolicy,
) -> MockJournalDecision:
    ensure_utc(now_utc, "now_utc")
    _sim(worker_id, "WORKER_ID")
    if not _permission(policy):
        return _deny(snapshot, MockOutcome.PERMISSION_DENIED,
                     "P025_SIM_METADATA_RIGHTS_UNREVIEWED_OR_REVOKED")
    index, record = _record_at(snapshot, event_id)
    if now_utc < record.event.retrieved_at_utc:
        raise ValueError("P025_FUTURE_RESEARCH_EVENT")
    if record.phase is MockPhase.AMBIGUOUS:
        return _deny(snapshot, MockOutcome.AMBIGUOUS_DENIED,
                     "P025_EXTERNAL_DELIVERY_OUTCOME_UNKNOWN")
    if now_utc > record.expires_utc:
        return _deny(snapshot, MockOutcome.EXPIRED_DENIED,
                     "P025_EVENT_TTL_EXPIRED_BEFORE_CLAIM")
    if (record.phase is MockPhase.LEASED
            and record.lease_until_utc is not None
            and now_utc < record.lease_until_utc):
        return _deny(snapshot, MockOutcome.LEASE_BUSY,
                     "P025_ACTIVE_FENCED_CLOUD_LEASE")
    altered = replace(
        record, phase=MockPhase.LEASED, fence=record.fence + 1,
        worker_id=worker_id,
        lease_until_utc=now_utc + timedelta(seconds=policy.lease_seconds),
    )
    records = snapshot.records[:index] + (altered,) + snapshot.records[index+1:]
    return MockJournalDecision(
        outcome=MockOutcome.CLAIMED,
        snapshot=_new_snapshot(snapshot, records, "CLAIM", event_id, now_utc),
        reason="P025_MOCK_CLAIM_NO_SIGNAL_PUBLICATION",
    )


def _owned(
    snapshot: MockJournalSnapshot,
    event_id: str, worker_id: str, fence: int, now_utc: datetime,
) -> tuple[int, MockEventRecord] | None:
    ensure_utc(now_utc, "now_utc")
    _sim(worker_id, "WORKER_ID")
    if type(fence) is not int or fence < 1:
        raise ValueError("P025_INVALID_FENCE_TOKEN")
    index, record = _record_at(snapshot, event_id)
    if (record.phase is not MockPhase.LEASED
            or record.worker_id != worker_id
            or record.fence != fence
            or record.lease_until_utc is None
            or now_utc > record.lease_until_utc
            or now_utc > record.expires_utc):
        return None
    return index, record


def release_sim_lease(
    snapshot: MockJournalSnapshot, event_id: str,
    worker_id: str, fence: int,
    now_utc: datetime, policy: SimJournalPolicy,
) -> MockJournalDecision:
    if not _permission(policy):
        return _deny(snapshot, MockOutcome.PERMISSION_DENIED,
                     "P025_SIM_ACCESS_REVOKED")
    own = _owned(snapshot, event_id, worker_id, fence, now_utc)
    if own is None:
        return _deny(snapshot, MockOutcome.FENCE_DENIED,
                     "P025_STALE_OR_EXPIRED_WORKER_FENCE")
    index, record = own
    released = replace(record, phase=MockPhase.QUEUED,
                       worker_id=None, lease_until_utc=None)
    records = snapshot.records[:index] + (released,) + snapshot.records[index+1:]
    return MockJournalDecision(
        outcome=MockOutcome.RELEASED,
        snapshot=_new_snapshot(snapshot, records, "RELEASE", event_id, now_utc),
        reason="P025_RELEASED_MOCK_METADATA_ONLY",
    )


def mark_sim_attempt_intent(
    snapshot: MockJournalSnapshot, event_id: str,
    worker_id: str, fence: int,
    now_utc: datetime, policy: SimJournalPolicy,
) -> MockJournalDecision:
    """Records *intent*, never invokes a real notification provider."""
    if not _permission(policy):
        return _deny(snapshot, MockOutcome.PERMISSION_DENIED,
                     "P025_SIM_ACCESS_REVOKED")
    own = _owned(snapshot, event_id, worker_id, fence, now_utc)
    if own is None:
        return _deny(snapshot, MockOutcome.FENCE_DENIED,
                     "P025_STALE_OR_EXPIRED_WORKER_FENCE")
    index, record = own
    uncertain = replace(
        record, phase=MockPhase.AMBIGUOUS,
        worker_id=None, lease_until_utc=None,
    )
    records = snapshot.records[:index] + (uncertain,) + snapshot.records[index+1:]
    return MockJournalDecision(
        outcome=MockOutcome.ATTEMPT_AMBIGUOUS,
        snapshot=_new_snapshot(
            snapshot, records, "ATTEMPT_INTENT", event_id, now_utc,
        ),
        reason="P025_MOCK_INTENT_NOT_RECEIVER_ACK_OR_DELIVERY",
    )


def confirm_external_delivery_without_receiver_ack(
    snapshot: MockJournalSnapshot,
) -> MockJournalDecision:
    """No external sender/receiver exists. Exactly-once cannot be asserted."""
    if not isinstance(snapshot, MockJournalSnapshot):
        raise TypeError("P025_TYPED_JOURNAL_RECEIPT")
    return _deny(snapshot, MockOutcome.RECEIVER_ACK_REQUIRED,
                 "P025_NO_PROVABLE_EXTERNAL_DELIVERY_OR_ACK")


@dataclass(frozen=True, slots=True)
class TrustedMockCheckpoint:
    revision: int
    head_hash: str

    def __post_init__(self) -> None:
        if (type(self.revision) is not int or self.revision < 0
                or not isinstance(self.head_hash, str)
                or len(self.head_hash) != 64):
            raise ValueError("P025_INVALID_EXTERNALLY_TRUSTED_CHECKPOINT")


class MockCloudCASStore:
    """IN-MEMORY test double only; not Google Drive and not durable storage."""

    def __init__(
        self, snapshot: MockJournalSnapshot | None = None,
        trusted_checkpoint: TrustedMockCheckpoint | None = None,
    ) -> None:
        self._snapshot = (
            MockJournalSnapshot() if snapshot is None else snapshot
        )
        if not isinstance(self._snapshot, MockJournalSnapshot):
            raise TypeError("P025_TYPED_MOCK_CLOUD_SNAPSHOT")
        check = (
            TrustedMockCheckpoint(
                self._snapshot.revision, self._snapshot.head_hash,
            )
            if trusted_checkpoint is None else trusted_checkpoint
        )
        if (self._snapshot.revision != check.revision
                or self._snapshot.head_hash != check.head_hash):
            raise ValueError("P025_TRUSTED_HIGHWATER_ANTI_ROLLBACK")
        self._trusted_checkpoint = check

    def read(self) -> MockJournalSnapshot:
        return self._snapshot

    def checkpoint(self) -> TrustedMockCheckpoint:
        return self._trusted_checkpoint

    def cas(
        self, expected_revision: int, expected_head_hash: str,
        candidate: MockJournalSnapshot,
        *,
        metadata_permission_active: bool,
    ) -> MockJournalSnapshot:
        if not metadata_permission_active:
            raise ValueError("P025_CLOUD_PERMISSION_REVOKED_OR_UNREVIEWED")
        if not isinstance(candidate, MockJournalSnapshot):
            raise TypeError("P025_TYPED_CAS_CANDIDATE")
        now = self._snapshot
        if (expected_revision != now.revision
                or expected_head_hash != now.head_hash):
            raise ValueError("P025_CAS_STALE_REVISION_OR_HEAD")
        if (now.revision != self._trusted_checkpoint.revision
                or now.head_hash != self._trusted_checkpoint.head_hash):
            raise ValueError("P025_TRUSTED_HIGHWATER_ANTI_ROLLBACK")
        if (candidate.schema != now.schema
                or candidate.revision != now.revision + 1
                or candidate.entries[:-1] != now.entries
                or candidate.entries[-1].previous_hash != now.head_hash):
            raise ValueError("P025_CAS_NOT_SINGLE_APPEND_FROM_EXPECTED_PARENT")
        self._snapshot = candidate
        self._trusted_checkpoint = TrustedMockCheckpoint(
            candidate.revision, candidate.head_hash,
        )
        return self._snapshot
