"""A04/P0.82: offline classification of previously observed M5 audit lag.

All inputs are caller-provided; this module performs NO network, Drive, vendor,
GitHub or broker operations. A single lag observation cannot prove an outage.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

SCHEMA = "MFX_A04_P82_M5_LAG_EVIDENCE_V1"
UTC = timezone.utc
MAX_AUDIT_AGE = timedelta(hours=2)
PUBLISH_GRACE = timedelta(seconds=135)


@dataclass(frozen=True, slots=True)
class M5LagObservation:
    audit_at_utc: datetime
    last_closed_bar_open_utc: datetime
    expected_closed_bar_open_utc: datetime
    manifest_pairs: int
    closed_bars: int
    full_history_audited: bool


@dataclass(frozen=True, slots=True)
class M5LagReceipt:
    schema: str
    status: str
    observed_lag_bars: int
    evidence_is_current: bool
    complete_history_verified: bool
    outage_proven: bool = False
    source_substitution_authorized: bool = False
    live_v2_authorized: bool = False
    vendor_calls: int = 0
    drive_writes: int = 0
    broker_orders: int = 0


def _utc(value: datetime) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


def classify_m5_lag(
    observed: M5LagObservation, *, as_of_utc: datetime
) -> M5LagReceipt:
    """Classify one audit snapshot without claiming continuity or an outage."""
    if type(observed) is not M5LagObservation or not _utc(as_of_utc):
        raise ValueError("P082_INVALID_OBSERVATION")
    a, last, expected = (
        observed.audit_at_utc, observed.last_closed_bar_open_utc,
        observed.expected_closed_bar_open_utc
    )
    if (not all(_utc(x) for x in (a, last, expected))
            or any(x.second or x.microsecond or x.minute % 5
                   for x in (last, expected))
            or type(observed.manifest_pairs) is not int
            or type(observed.closed_bars) is not int
            or type(observed.full_history_audited) is not bool
            or observed.manifest_pairs < 0 or observed.closed_bars < 0
            or observed.closed_bars > observed.manifest_pairs * 12
            or a > as_of_utc or expected > a
            or last > expected or last > a
            or (expected - last) % timedelta(minutes=5)):
        raise ValueError("P082_INVALID_OBSERVATION")
    lag = int((expected - last) / timedelta(minutes=5))
    current = as_of_utc - a <= MAX_AUDIT_AGE
    # An audit at the close boundary may precede publication. Do not
    # misclassify that transient as a confirmed missing bar.
    publishing = a - (expected + timedelta(minutes=5)) < PUBLISH_GRACE
    # The expected tail is caller-supplied. Independently bound it to the
    # latest M5 bar whose close has cleared the 135-second publication grace.
    # Anchor due-tail to the AUDIT clock, not the later review clock.
    # A fresh but delayed audit must not be compared with future candles.
    latest_due = a - PUBLISH_GRACE - timedelta(minutes=5)
    latest_due = latest_due.replace(
        minute=(latest_due.minute // 5) * 5, second=0, microsecond=0
    )
    expected_is_stale = expected < latest_due
    # The UTC grid is not an FX trading calendar. Weekend observations
    # cannot establish a missing bar or a verified current tail.
    weekend_calendar_unknown = a.weekday() >= 5 or expected.weekday() >= 5
    if not current:
        status = "STALE_AUDIT_RECHECK_REQUIRED"
    elif weekend_calendar_unknown:
        status = "SESSION_CALENDAR_UNVERIFIED_RECHECK_REQUIRED"
    elif expected_is_stale:
        status = "STALE_EXPECTED_TAIL_RECHECK_REQUIRED"
    elif publishing and lag:
        status = "PUBLICATION_WINDOW_RECHECK_REQUIRED"
    elif lag:
        status = "LAG_OBSERVED_NOT_OUTAGE_PROOF"
    else:
        status = "TAIL_MATCH_ONLY"
    # Caller-provided full_history_audited cannot attest complete history.
    return M5LagReceipt(
        schema=SCHEMA, status=status, observed_lag_bars=lag,
        evidence_is_current=current,
        complete_history_verified=False,
    )
