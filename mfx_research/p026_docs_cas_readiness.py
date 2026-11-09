"""A04/P0.26 -- read-only Docs revision-CAS decision matrix (SIM ONLY).

This module models published API behavior but NEVER calls Google Docs/Drive,
creates a document, caches OHLC, publishes a signal, or executes a trade.
All revision strings and CAS transactions here are mock values.
Actual Drive files.update remains NO_GO as an atomic lock via this connector.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from mfx_research.p025_mock_cloud_journal import SimMetadataEvent


class ContractOutcome(str, Enum):
    SIM_CAS_APPENDED = "SIM_CAS_APPENDED_NOT_PUBLISHED"
    STALE_REVISION = "STALE_REQUIRED_REVISION_DENIED"
    DUPLICATE_EVENT = "DUPLICATE_EVENT_DENIED"
    BAD_CONTROL = "NO_GO_UNSAFE_OR_MISSING_WRITE_CONTROL"
    RIGHTS_STOP = "NO_GO_METADATA_RIGHTS"
    FUTURE_KNOWN = "FUTURE_OBSERVATION_DENIED"
    QUOTA_STOP = "NO_GO_SIM_QUOTA_BUDGET"
    AMBIGUOUS_STOP = "MANUAL_RECONCILE_AMBIGUOUS"
    NO_GO_DRIVE = "NO_GO_GENERIC_DRIVE_FILES_UPDATE"
    NO_GO_REAL = "NO_GO_REAL_JOURNAL_OR_VERIFIED_FX_SIGNAL"


class ErrorHandling(str, Enum):
    FETCH_LATEST_NO_ALERT = "RE_READ_LATEST_NO_ALERT"
    DENY_INVALID_REQUEST = "STOP_INVALID_REQUEST"
    DENY_RIGHTS = "STOP_RIGHTS_REVOKED"
    BOUNDED_BACKOFF_READ = "BACKOFF_METADATA_READ_ONLY"
    MANUAL_COMMIT_RECONCILIATION = "UNKNOWN_COMMIT_MANUAL_RECONCILE"
    STOP_NOT_FOUND = "STOP_DOCUMENT_NOT_FOUND"


@dataclass(frozen=True, slots=True)
class SimDocsSnapshot:
    """Strictly modeled mock Docs revision, never a connected document."""

    epoch: int = 0
    revision_id: str = "SIM:REV-0000"
    event_ids: tuple[str, ...] = ()
    ambiguous_event_ids: tuple[str, ...] = ()
    document_type: str = "application/vnd.google-apps.document"

    def __post_init__(self) -> None:
        if (type(self.epoch) is not int or not 0 <= self.epoch <= 32
                or self.revision_id != f"SIM:REV-{self.epoch:04d}"
                or not isinstance(self.event_ids, tuple)
                or len(self.event_ids) > 32
                or len(set(self.event_ids)) != len(self.event_ids)
                or not all(isinstance(x, str) and len(x) == 64
                           for x in self.event_ids)
                or not isinstance(self.ambiguous_event_ids, tuple)
                or len(set(self.ambiguous_event_ids)) != len(
                    self.ambiguous_event_ids
                ) or not set(self.ambiguous_event_ids).issubset(
                    self.event_ids
                )):
            raise ValueError("P026_MOCK_REVISION_HISTORY_INVALID")
        if self.document_type != "application/vnd.google-apps.document":
            raise ValueError("P026_MOCK_ONLY_NATIVE_DOCS_TYPE")


@dataclass(frozen=True, slots=True)
class SimRevisionWriteIntent:
    captured_revision_id: str
    event: SimMetadataEvent
    write_control: str = "requiredRevisionId"
    metadata_storage_reviewed: bool = False
    access_revoked: bool = False
    real_drive_write_authorized: bool = False
    notification_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.event, SimMetadataEvent):
            raise TypeError("P026_TYPED_PRICE_FREE_EVENT_REQUIRED")
        for x in ("metadata_storage_reviewed", "access_revoked",
                  "real_drive_write_authorized", "notification_authorized"):
            if type(getattr(self, x)) is not bool:
                raise TypeError("P026_TYPED_POLICY_FLAGS")
        if self.real_drive_write_authorized or self.notification_authorized:
            raise ValueError("P026_MOCK_CANNOT_GRANT_REAL_AUTHORITY")


@dataclass(frozen=True, slots=True)
class SimDocsCASResult:
    outcome: ContractOutcome
    snapshot: SimDocsSnapshot
    reason: str
    simulated_only: bool = True
    real_docs_journal_writes: int = 0
    real_drive_quote_cache_writes: int = 0
    forex_provider_calls: int = 0
    verified_buy_sell_alerts: int = 0
    broker_orders: int = 0
    release_ready: bool = False


class MockDocsRequiredRevisionServer:
    """Deterministic in-memory contract oracle, NOT a Google Docs API client."""

    def __init__(self, initial: SimDocsSnapshot | None = None) -> None:
        self._state = initial if initial is not None else SimDocsSnapshot()

    def read(self) -> SimDocsSnapshot:
        return self._state

    def append(
        self, intent: SimRevisionWriteIntent, asof_utc: datetime,
        *,
        user_writes_this_minute: int = 0,
        project_writes_this_minute: int = 0,
    ) -> SimDocsCASResult:
        if not isinstance(intent, SimRevisionWriteIntent):
            raise TypeError("P026_TYPED_DOCS_CAS_INTENT")
        if asof_utc.tzinfo is None or asof_utc.utcoffset() is None:
            raise ValueError("P026_UTC_ASOF_REQUIRED")
        if asof_utc.utcoffset() != timezone.utc.utcoffset(asof_utc):
            raise ValueError("P026_UTC_ASOF_REQUIRED")
        before = self._state

        def denied(status: ContractOutcome, reason: str) -> SimDocsCASResult:
            return SimDocsCASResult(status, before, reason)

        if (not intent.metadata_storage_reviewed or intent.access_revoked):
            return denied(ContractOutcome.RIGHTS_STOP,
                          "P026_STORAGE_REVIEW_MISSING_OR_ACCESS_REVOKED")
        if (intent.write_control != "requiredRevisionId"
                or not intent.captured_revision_id
                or not intent.captured_revision_id.startswith("SIM:REV-")):
            return denied(ContractOutcome.BAD_CONTROL,
                          "P026_TARGET_REVISION_OR_UNGUARDED_WRITE_UNSAFE")
        if intent.captured_revision_id != before.revision_id:
            return denied(ContractOutcome.STALE_REVISION,
                          "P026_MOCK_HTTP_400_STALE_REQUIRED_REVISION")
        if asof_utc < intent.event.retrieved_at_utc:
            return denied(ContractOutcome.FUTURE_KNOWN,
                          "P026_FUTURE_RETRIEVED_METADATA")
        if intent.event.event_id in before.ambiguous_event_ids:
            return denied(ContractOutcome.AMBIGUOUS_STOP,
                          "P026_AMBIGUOUS_DELIVERY_NEEDS_MANUAL_RECONCILIATION")
        if intent.event.event_id in before.event_ids:
            return denied(ContractOutcome.DUPLICATE_EVENT,
                          "P026_IMMUTABLE_EVENT_REPLAY_NO_ALERT")
        if (type(user_writes_this_minute) is not int
                or type(project_writes_this_minute) is not int
                or user_writes_this_minute < 0
                or project_writes_this_minute < 0):
            raise ValueError("P026_INVALID_SIM_RATE_COUNTER")
        if user_writes_this_minute >= 60 or project_writes_this_minute >= 600:
            return denied(ContractOutcome.QUOTA_STOP,
                          "P026_CONSERVATIVE_GOOGLE_DOCS_WRITE_BUDGET_STOP")
        if len(before.event_ids) >= 32:
            return denied(ContractOutcome.QUOTA_STOP,
                          "P026_MOCK_APPEND_HISTORY_BOUNDED")
        updated = SimDocsSnapshot(
            epoch=before.epoch + 1,
            revision_id=f"SIM:REV-{before.epoch+1:04d}",
            event_ids=before.event_ids + (intent.event.event_id,),
            ambiguous_event_ids=before.ambiguous_event_ids,
        )
        self._state = updated
        return SimDocsCASResult(
            ContractOutcome.SIM_CAS_APPENDED, updated,
            "P026_MOCK_DOCS_REQUIRED_REVISION_ACCEPTED_NOT_REAL_WRITE",
        )


def unsafe_generic_drive_file_update_verdict(
    *, has_file_version: bool, has_modified_time: bool,
    has_server_enforced_precondition_in_connector: bool = False,
) -> ContractOutcome:
    """Current connector exposes no typed expected revision for Drive write.

    Version / modifiedTime readbacks alone do not implement a CAS mutation.
    """
    if has_server_enforced_precondition_in_connector:
        raise ValueError("P026_UNVERIFIED_DRIVE_CAS_CAPABILITY_CLAIM")
    if type(has_file_version) is not bool or type(has_modified_time) is not bool:
        raise TypeError("P026_TYPED_DRIVE_METADATA_FLAGS")
    return ContractOutcome.NO_GO_DRIVE


def classify_docs_api_failure(
    status_code: int | None,
    *,
    explicit_stale_revision: bool = False,
    timeout_after_write: bool = False,
) -> ErrorHandling:
    """Conservative pure error map, NOT an HTTP adapter."""
    if type(explicit_stale_revision) is not bool:
        raise TypeError("P026_TYPED_STALE_EVIDENCE")
    if type(timeout_after_write) is not bool:
        raise TypeError("P026_TYPED_TIMEOUT_EVIDENCE")
    if timeout_after_write:
        return ErrorHandling.MANUAL_COMMIT_RECONCILIATION
    if status_code is None:
        return ErrorHandling.MANUAL_COMMIT_RECONCILIATION
    if type(status_code) is not int or not 100 <= status_code <= 599:
        raise ValueError("P026_INVALID_HTTP_STATUS")
    if status_code == 400:
        return (ErrorHandling.FETCH_LATEST_NO_ALERT
                if explicit_stale_revision
                else ErrorHandling.DENY_INVALID_REQUEST)
    if status_code in (401, 403):
        return ErrorHandling.DENY_RIGHTS
    if status_code == 404:
        return ErrorHandling.STOP_NOT_FOUND
    if status_code in (409, 412):
        return ErrorHandling.FETCH_LATEST_NO_ALERT
    if status_code == 429:
        return ErrorHandling.BOUNDED_BACKOFF_READ
    if 500 <= status_code <= 599:
        return ErrorHandling.MANUAL_COMMIT_RECONCILIATION
    return ErrorHandling.DENY_INVALID_REQUEST


@dataclass(frozen=True, slots=True)
class SourceRightsGate:
    """Independent source rights still blocked, regardless of Docs API."""

    original_numeric_entry_rules_approved: int = 0
    b2_s2_numeric_obligations_approved: int = 0
    licensed_market_source_verified: bool = False
    real_drive_market_cache_rights_verified: bool = False
    metadata_journal_storage_approved: bool = False
    receiver_ack_contract_verified: bool = False
    actual_docs_race_verified: bool = False
    independently_trusted_highwater_verified: bool = False

    def __post_init__(self) -> None:
        if (type(self.original_numeric_entry_rules_approved) is not int
                or not 0 <= self.original_numeric_entry_rules_approved <= 15
                or type(self.b2_s2_numeric_obligations_approved) is not int
                or not 0 <= self.b2_s2_numeric_obligations_approved <= 36):
            raise ValueError("P026_SOURCE_NUMERIC_EVIDENCE_COUNTS_INVALID")
        for x in ("licensed_market_source_verified",
                  "real_drive_market_cache_rights_verified",
                  "metadata_journal_storage_approved",
                  "receiver_ack_contract_verified",
                  "actual_docs_race_verified",
                  "independently_trusted_highwater_verified"):
            if type(getattr(self, x)) is not bool:
                raise TypeError("P026_TYPED_SOURCE_PERMISSION_FLAGS")


def go_no_go_for_real_journal(rights: SourceRightsGate) -> ContractOutcome:
    if not isinstance(rights, SourceRightsGate):
        raise TypeError("P026_TYPED_RELEASE_GATE")
    # Assertions inside a mock are not independent evidence or authorization.
    return ContractOutcome.NO_GO_REAL
