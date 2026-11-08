"""Causal bid/ask bar evidence contracts. No market feed, trade or licensed access.

These typed records are caller-supplied claims; even VERIFIED quality from a
fixture does not prove an external broker/data vendor authorization.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from re import fullmatch
from typing import Sequence

from .quotes import ensure_utc


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"


class BarSide(str, Enum):
    BID = "BID"
    ASK = "ASK"
    MID = "MID"  # analysis/reference only, NOT broker-executable


class BarLifecycle(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class BarCoverage(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    SPARSE_UNVERIFIED = "SPARSE_UNVERIFIED"
    UNKNOWN = "UNKNOWN"
    INVALID = "INVALID"


class SourceQuality(str, Enum):
    VERIFIED = "VERIFIED"
    WARN = "WARN"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class Observation:
    """A raw-observation provenance claim; licence/identity NOT independently verified."""
    provider_id: str
    stream_id: str
    endpoint: str
    revision_id: str
    raw_sha256: str
    first_known_utc: datetime
    retrieved_at_utc: datetime
    source_timezone_policy: str
    license_scope_claim: str

    def __post_init__(self) -> None:
        for key in ("provider_id", "stream_id", "endpoint", "revision_id",
                    "source_timezone_policy", "license_scope_claim"):
            val = getattr(self, key)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{key} required")
        if not isinstance(self.raw_sha256, str) or not fullmatch(r"[a-f0-9]{64}", self.raw_sha256):
            raise ValueError("raw_sha256 must be lowercase 64-character hex")
        ensure_utc(self.first_known_utc, "first_known_utc")
        ensure_utc(self.retrieved_at_utc, "retrieved_at_utc")
        if self.retrieved_at_utc < self.first_known_utc:
            raise ValueError("retrieval before first-known is inconsistent")


@dataclass(frozen=True, slots=True)
class MarketBarKey:
    instrument_version: str
    timeframe: Timeframe
    bar_start_utc: datetime
    bar_end_utc: datetime
    calendar_version: str
    aggregation_version: str
    side: BarSide

    def __post_init__(self) -> None:
        if any(not isinstance(v, str) or not v.strip() for v in
               (self.instrument_version, self.calendar_version, self.aggregation_version)):
            raise ValueError("instrument/calendar/aggregation versions required")
        if not isinstance(self.timeframe, Timeframe) or not isinstance(self.side, BarSide):
            raise TypeError("Explicit timeframe and price side required")
        ensure_utc(self.bar_start_utc, "bar_start_utc")
        ensure_utc(self.bar_end_utc, "bar_end_utc")
        if self.bar_end_utc <= self.bar_start_utc:
            raise ValueError("bar end must be after bar start")
        lengths = {Timeframe.M1: 1, Timeframe.M5: 5, Timeframe.M15: 15, Timeframe.M30: 30}
        if self.timeframe in lengths and (
            self.bar_end_utc - self.bar_start_utc != timedelta(minutes=lengths[self.timeframe])
        ):
            raise ValueError("intraday M1/M5/M15/M30 bar duration mismatch")
        # H1/H4/D1/W1 clocks require SOURCE calendar, session & DST policy;
        # no universal New-York-close or holiday calendar is invented.


@dataclass(frozen=True, slots=True)
class MarketBar:
    key: MarketBarKey
    observation: Observation
    revision_number: int
    first_known_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    lifecycle: BarLifecycle
    coverage: BarCoverage
    quality: SourceQuality

    def __post_init__(self) -> None:
        if not isinstance(self.key, MarketBarKey) or not isinstance(self.observation, Observation):
            raise TypeError("typed key and provenance required")
        if type(self.revision_number) is not int or self.revision_number < 1:
            raise ValueError("positive integer revision number required")
        ensure_utc(self.first_known_utc, "first_known_utc")
        if self.first_known_utc < self.observation.first_known_utc:
            raise ValueError("bar revision cannot be known before its observation")
        if any(not isinstance(v, Decimal) or not v.is_finite() or v <= 0
               for v in (self.open, self.high, self.low, self.close)):
            raise ValueError("OHLC must be positive finite Decimal values")
        if not (self.low <= min(self.open, self.close) and
                self.high >= max(self.open, self.close) and self.low <= self.high):
            raise ValueError("inconsistent OHLC")
        if not isinstance(self.lifecycle, BarLifecycle) or not isinstance(self.coverage, BarCoverage) or not isinstance(self.quality, SourceQuality):
            raise TypeError("lifecycle, coverage and quality must be typed")
        if self.lifecycle is BarLifecycle.CLOSED and self.first_known_utc < self.key.bar_end_utc:
            raise ValueError("CLOSED bar cannot first be known before its cutoff")


@dataclass(frozen=True, slots=True)
class ReadOnlyBarGate:
    usable_for_technical_features: bool
    eligible_for_early_phase_input: bool
    confirmed_phase_authorized: bool
    executable_quote_basis: bool
    permission_to_trade: bool
    reason: str


def select_asof_revision(revisions: Sequence[MarketBar], decision_utc: datetime) -> MarketBar | None:
    """Only inspect records already known at decision_utc; never peek at future corrections.

    Identity/revision checks apply to the KNOWN prefix, never future revisions.
    """
    ensure_utc(decision_utc, "decision_utc")
    known = [r for r in revisions if isinstance(r, MarketBar) and r.first_known_utc <= decision_utc]
    if not known:
        return None
    identity = {(r.key, r.observation.provider_id, r.observation.stream_id) for r in known}
    if len(identity) != 1:
        raise ValueError("mixed identity or provider in known revision history")
    by_number = sorted(known, key=lambda r: r.revision_number)
    if len({r.revision_number for r in by_number}) != len(by_number):
        raise ValueError("duplicate revision number in known prefix")
    if any(next_.first_known_utc <= prev.first_known_utc
           for prev, next_ in zip(by_number, by_number[1:])):
        raise ValueError("revisions cannot arrive out of causal order")
    return by_number[-1]


def evaluate_closed_bar(
    bar: MarketBar | None,
    decision_utc: datetime,
    *,
    conditional_m5_early_enabled: bool = False,
    htf_context_first_known_utc: datetime | None = None,
) -> ReadOnlyBarGate:
    """Time/quality gate only: never promotes to CONFIRMED_SIGNAL or broker eligibility."""
    ensure_utc(decision_utc, "decision_utc")
    def blocked(reason: str) -> ReadOnlyBarGate:
        return ReadOnlyBarGate(False, False, False, False, False, reason)

    if bar is None:
        return blocked("MISSING_BAR_NOT_ZERO_VOLUME")
    if not isinstance(bar, MarketBar):
        raise TypeError("expected MarketBar")
    if bar.first_known_utc > decision_utc:
        return blocked("FUTURE_REVISION_NOT_KNOWN")
    if bar.lifecycle is not BarLifecycle.CLOSED:
        return blocked("OPEN_PROVISIONAL_BAR")
    if bar.coverage is not BarCoverage.COMPLETE:
        return blocked("INCOMPLETE_COVERAGE")
    if bar.quality is not SourceQuality.VERIFIED:
        return blocked("SOURCE_QUALITY_UNVERIFIED")
    if bar.key.timeframe is Timeframe.M5:
        if not conditional_m5_early_enabled:
            return blocked("M5_CONDITIONAL_ARM_DISABLED")
        if htf_context_first_known_utc is None:
            return blocked("M5_REQUIRES_PRIOR_HTF_CONTEXT")
        ensure_utc(htf_context_first_known_utc, "htf_context_first_known_utc")
        if htf_context_first_known_utc > bar.first_known_utc or htf_context_first_known_utc > decision_utc:
            return blocked("M5_HTF_CONTEXT_FUTURE_KNOWN")
    if bar.key.timeframe is not Timeframe.M5 and conditional_m5_early_enabled:
        return blocked("M5_ARM_USED_WITH_WRONG_TIMEFRAME")

    # MID may be a fully validated technical reference, not a tradeable fill side.
    quote_basis_ok = bar.key.side in (BarSide.BID, BarSide.ASK)
    early_input = bar.key.timeframe in (Timeframe.M15, Timeframe.M5)
    return ReadOnlyBarGate(True, early_input, False, quote_basis_ok, False,
                           "READ_ONLY_CLOSED_BAR_CAUSAL_QUALITY_PASS")
