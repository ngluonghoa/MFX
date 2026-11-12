"""A04/P0.84: inert evidence reconciliation for an observed late M5 manifest.

All inputs come from a human-observed audit, GitHub Actions and Drive listing.
No network access, cloud writes, vendor requests or live trading. A Drive file
name and an Actions receipt are NOT cryptographic or historical attestations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

SCHEMA = "MFX_A04_P84_M5_SCHEDULE_RECONCILIATION_V1"
UTC = timezone.utc
AUDIT_MAX_AGE = timedelta(hours=2)
SOURCE = "TWELVE_DATA_COMPOSITE_MID"
SYMBOL = "EUR/USD"
_MANIFEST = re.compile(
    r"^MFX_TD_EURUSD_M5_V2_manifest_([0-9]{8}T[0-9]{4}Z)_([a-f0-9]{64})\.json$"
)


def _utc(value: datetime) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


def _hour(value: datetime) -> bool:
    return _utc(value) and value.minute == value.second == value.microsecond == 0


@dataclass(frozen=True, slots=True)
class M5TimelineObservation:
    audit_at_utc: datetime
    audit_last_manifest_hour_utc: datetime
    audit_reported_lag_hours: int
    audit_full_history_claim: bool
    writer_run_created_utc: datetime
    writer_run_completed_utc: datetime
    writer_committed_hour_utc: datetime
    writer_status: str
    drive_manifest_created_utc: datetime
    drive_manifest_name: str
    source: str = SOURCE
    symbol: str = SYMBOL


@dataclass(frozen=True, slots=True)
class M5TimelineReceipt:
    schema: str
    status: str
    observed_next_hour_manifest: bool
    seconds_after_earliest_hourly_tick: int
    manifest_filename_matches_slot: bool
    independently_verified_full_history: bool = False
    incident_cause_proven: bool = False
    github_scheduler_cause_proven: bool = False
    forex_session_calendar_verified: bool = False
    h4_source_substitution_authorized: bool = False
    live_v2_authorized: bool = False
    provider_calls: int = 0
    drive_writes: int = 0
    broker_orders: int = 0


def reconcile_m5_timeline(
    observed: M5TimelineObservation, *, as_of_utc: datetime
) -> M5TimelineReceipt:
    """Classify offline cross-system observation, never certify a full M5 chain."""
    if type(observed) is not M5TimelineObservation or not _utc(as_of_utc):
        raise ValueError("P084_INVALID_EVIDENCE")
    a = observed
    clocks = (a.audit_at_utc, a.writer_run_created_utc,
              a.writer_run_completed_utc, a.drive_manifest_created_utc)
    if (not all(_utc(t) for t in clocks)
            or not _hour(a.audit_last_manifest_hour_utc)
            or not _hour(a.writer_committed_hour_utc)
            or type(a.audit_reported_lag_hours) is not int
            or type(a.audit_full_history_claim) is not bool
            or a.audit_reported_lag_hours < 0
            or a.source != SOURCE or a.symbol != SYMBOL
            or a.writer_status not in {"BATCH_COMMITTED", "NO_COMMIT"}
            or type(a.drive_manifest_name) is not str
            or a.audit_at_utc > as_of_utc
            or a.writer_run_created_utc > a.writer_run_completed_utc
            or a.writer_run_completed_utc > as_of_utc
            or a.drive_manifest_created_utc > as_of_utc
            or a.audit_last_manifest_hour_utc > a.audit_at_utc
            or a.writer_committed_hour_utc > as_of_utc):
        raise ValueError("P084_INVALID_EVIDENCE")

    # Earliest theoretical GitHub hourly writer tick for this *closed* hour.
    # This is derived from existing :10 cron, NOT authenticated schedule origin.
    earliest_tick = a.writer_committed_hour_utc + timedelta(hours=1, minutes=10)
    delay = int((a.writer_run_created_utc - earliest_tick).total_seconds())
    name_match = _MANIFEST.fullmatch(a.drive_manifest_name)
    name_ok = bool(
        name_match
        and name_match.group(1) ==
        a.writer_committed_hour_utc.strftime("%Y%m%dT%H00Z")
    )
    if as_of_utc - a.audit_at_utc > AUDIT_MAX_AGE:
        status = "STALE_AUDIT_RECHECK_REQUIRED"
    elif (a.writer_run_created_utc < a.audit_at_utc
          or a.drive_manifest_created_utc < a.writer_run_created_utc
          or a.drive_manifest_created_utc > a.writer_run_completed_utc
          or delay < 0):
        status = "TIMELINE_ORDER_RECHECK_REQUIRED"
    elif a.writer_status != "BATCH_COMMITTED":
        status = "WRITER_RECEIPT_RECHECK_REQUIRED"
    elif not name_ok:
        status = "MANIFEST_IDENTITY_RECHECK_REQUIRED"
    elif a.writer_committed_hour_utc != (
            a.audit_last_manifest_hour_utc + timedelta(hours=1)):
        status = "NONCONTIGUOUS_NEXT_SLOT_RECHECK_REQUIRED"
    elif a.audit_reported_lag_hours != 1:
        status = "AUDIT_LAG_COUNTER_RECHECK_REQUIRED"
    else:
        status = "LATE_NEXT_SLOT_MANIFEST_OBSERVED"

    # Neither filename nor caller's full-history boolean is a signed proof.
    return M5TimelineReceipt(
        schema=SCHEMA, status=status,
        observed_next_hour_manifest=(status == "LATE_NEXT_SLOT_MANIFEST_OBSERVED"),
        seconds_after_earliest_hourly_tick=max(0, delay),
        manifest_filename_matches_slot=name_ok,
    )
