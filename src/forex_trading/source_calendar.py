"""Provider-declared Forex session/DST clocks, as-of evidence: READ-ONLY contracts.

An IANA zone name and tzdb revision reference DO NOT independently attest a
data vendor's actual calendar, broker rollover, or installed tzdb contents.
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .market_data import MarketBar, Timeframe
from .quotes import ensure_utc


@dataclass(frozen=True, slots=True)
class SourceCalendarPolicy:
    provider_id: str
    calendar_version: str
    timezone_policy_id: str
    iana_timezone: str
    tzdb_revision_claim: str
    daily_rollover_local: time
    first_known_utc: datetime

    def __post_init__(self) -> None:
        for key in ("provider_id", "calendar_version", "timezone_policy_id",
                    "iana_timezone", "tzdb_revision_claim"):
            v = getattr(self, key)
            if not isinstance(v, str) or not v.strip():
                raise ValueError(f"{key} required")
        if not isinstance(self.daily_rollover_local, time) or self.daily_rollover_local.tzinfo is not None:
            raise ValueError("daily_rollover_local must be a naive wall-clock time")
        ensure_utc(self.first_known_utc, "calendar_first_known_utc")
        self.zone()  # reject invalid/absent IANA names without inventing UTC fallback

    def zone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.iana_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("IANA_TIMEZONE_UNAVAILABLE") from exc


def resolve_local_wall_time(
    wall: datetime, iana_timezone: str, *, fold: int | None = None
) -> datetime:
    """Require explicit fold for overlap; reject non-existent spring-gap time.

    Only naive wall timestamps are accepted. Returns a timezone-aware UTC
    instant. A tzdb version claim alone is not a locked runtime dependency.
    """
    if not isinstance(wall, datetime) or wall.tzinfo is not None:
        raise ValueError("LOCAL_WALL_MUST_BE_NAIVE")
    if fold is not None and (type(fold) is not int or fold not in (0, 1)):
        raise ValueError("FOLD_MUST_BE_0_OR_1")
    try:
        tz = ZoneInfo(iana_timezone)
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise ValueError("IANA_TIMEZONE_UNAVAILABLE") from exc
    valid: dict[int, datetime] = {}
    for candidate in (0, 1):
        aware = wall.replace(tzinfo=tz, fold=candidate)
        utc_instant = aware.astimezone(timezone.utc)
        back = utc_instant.astimezone(tz).replace(tzinfo=None)
        if back == wall:
            valid[candidate] = utc_instant
    if not valid:
        raise ValueError("NONEXISTENT_DST_WALL_TIME")
    if len(set(valid.values())) > 1:
        if fold is None:
            raise ValueError("AMBIGUOUS_DST_WALL_TIME_REQUIRES_FOLD")
        return valid[fold]
    if fold == 1:
        raise ValueError("FOLD_1_NOT_APPLICABLE")
    return valid[0]


@dataclass(frozen=True, slots=True)
class SessionEvidence:
    """An announced session time window, NOT proof that FX quotes were present."""
    session_id: str
    provider_id: str
    calendar_version: str
    source_revision: str
    opens_utc: datetime
    closes_utc: datetime
    first_known_utc: datetime

    def __post_init__(self) -> None:
        for key in ("session_id", "provider_id", "calendar_version", "source_revision"):
            val = getattr(self, key)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{key} required")
        for key in ("opens_utc", "closes_utc", "first_known_utc"):
            ensure_utc(getattr(self, key), key)
        if self.closes_utc <= self.opens_utc:
            raise ValueError("session must have positive duration")


def validate_session_ledger(sessions: tuple[SessionEvidence, ...]) -> None:
    """Fail closed if an explicit same-provider/calendar schedule overlaps."""
    if any(not isinstance(s, SessionEvidence) for s in sessions):
        raise TypeError("typed session evidence required")
    if len({(s.provider_id, s.calendar_version, s.session_id) for s in sessions}) != len(sessions):
        raise ValueError("DUPLICATE_SESSION_ID")
    groups: dict[tuple[str, str], list[SessionEvidence]] = {}
    for session in sessions:
        groups.setdefault((session.provider_id, session.calendar_version), []).append(session)
    for group in groups.values():
        ordered = sorted(group, key=lambda s: s.opens_utc)
        for previous, current in zip(ordered, ordered[1:]):
            if previous.closes_utc > current.opens_utc:
                raise ValueError("OVERLAPPING_SOURCE_SESSIONS")


class CalendarDisposition(str, Enum):
    VERIFIED_CONTRACT_INPUT = "VERIFIED_CONTRACT_INPUT"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class CalendarGate:
    disposition: CalendarDisposition
    use_for_calendar_aware_features: bool
    permission_to_trade: bool
    reason: str


def assess_bar_source_calendar(
    bar: MarketBar | None,
    decision_utc: datetime,
    policy: SourceCalendarPolicy | None,
    session: SessionEvidence | None,
) -> CalendarGate:
    """Additional temporal/source gate; does NOT replace bar-quality gate.

    Even a PASS is only a check of supplied metadata, not provider/broker
    proof, actual market-open evidence, or trading authorization.
    """
    ensure_utc(decision_utc, "decision_utc")

    def blocked(reason: str) -> CalendarGate:
        return CalendarGate(CalendarDisposition.UNVERIFIED, False, False, reason)

    if bar is None or policy is None or session is None:
        return blocked("MISSING_CALENDAR_OR_SESSION_EVIDENCE")
    if not isinstance(bar, MarketBar) or not isinstance(policy, SourceCalendarPolicy) or not isinstance(session, SessionEvidence):
        raise TypeError("typed bar, policy and session required")
    if any(t > decision_utc for t in (bar.first_known_utc, policy.first_known_utc,
                                     session.first_known_utc)):
        return blocked("CALENDAR_OR_BAR_NOT_KNOWN_AS_OF")
    if bar.key.calendar_version != policy.calendar_version or session.calendar_version != policy.calendar_version:
        return blocked("CALENDAR_VERSION_MISMATCH")
    if bar.observation.provider_id != policy.provider_id or session.provider_id != policy.provider_id:
        return blocked("PROVIDER_CALENDAR_MISMATCH")
    if bar.observation.source_timezone_policy != policy.timezone_policy_id:
        return blocked("SOURCE_TIMEZONE_POLICY_MISMATCH")
    if bar.key.bar_start_utc < session.opens_utc or bar.key.bar_end_utc > session.closes_utc:
        return blocked("BAR_OUTSIDE_EXPLICIT_SESSION")
    if bar.key.timeframe is Timeframe.D1:
        z = policy.zone()
        if (bar.key.bar_start_utc.astimezone(z).time() != policy.daily_rollover_local
                or bar.key.bar_end_utc.astimezone(z).time() != policy.daily_rollover_local):
            return blocked("DAILY_ROLLOVER_BOUNDARY_MISMATCH")
    elif bar.key.timeframe is Timeframe.W1:
        return blocked("WEEKLY_BOUNDARY_POLICY_NOT_SPECIFIED")
    return CalendarGate(CalendarDisposition.VERIFIED_CONTRACT_INPUT, True, False,
                        "PROVIDER_DECLARED_SESSION_CLOCKS_CONSISTENT_NOT_ATTESTED")
