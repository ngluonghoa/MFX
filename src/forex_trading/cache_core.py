"""Forex-specific, in-memory, synthetic-only incremental candle cache contract.

No HTTP adapter, persistent store, entitlement grant or market-data ingestion is
provided. Source receipts are caller claims and NEVER unlock real data use.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256
from json import dumps
from typing import Sequence

from .market_data import (
    BarCoverage, BarLifecycle, BarSide, MarketBar, SourceQuality, Timeframe,
)
from .quotes import ensure_utc


def _nonblank(x: str, label: str) -> None:
    if not isinstance(x, str) or not x.strip():
        raise ValueError(f"{label} is required")


@dataclass(frozen=True, slots=True)
class CachePartition:
    """Do not mix provider, broker product, pair, side, timeframe or data versions."""
    provider_id: str
    broker_product_ref: str  # opaque NON-SECRET reference, not account number
    instrument_version: str
    side: BarSide
    timeframe: Timeframe
    calendar_version: str
    aggregation_version: str
    source_timezone_policy: str
    rights_policy_ref: str  # audit reference, NOT a grant
    schema_version: str

    def __post_init__(self) -> None:
        for label in ("provider_id", "broker_product_ref", "instrument_version",
                      "calendar_version", "aggregation_version",
                      "source_timezone_policy", "rights_policy_ref",
                      "schema_version"):
            _nonblank(getattr(self, label), label)
        if not isinstance(self.side, BarSide) or not isinstance(self.timeframe, Timeframe):
            raise TypeError("Typed side and timeframe required")

    @property
    def fingerprint(self) -> str:
        fields = (
            self.provider_id, self.broker_product_ref, self.instrument_version,
            self.side.value, self.timeframe.value, self.calendar_version,
            self.aggregation_version, self.source_timezone_policy,
            self.rights_policy_ref, self.schema_version,
        )
        return sha256(dumps(fields, separators=(",", ":")).encode()).hexdigest()


def _validate_bar(partition: CachePartition, bar: MarketBar, as_of_utc: datetime) -> None:
    if not isinstance(bar, MarketBar):
        raise TypeError("Only typed MarketBar records accepted")
    k = bar.key
    if (k.instrument_version != partition.instrument_version
            or k.timeframe is not partition.timeframe or k.side is not partition.side
            or k.calendar_version != partition.calendar_version
            or k.aggregation_version != partition.aggregation_version
            or bar.observation.provider_id != partition.provider_id
            or bar.observation.source_timezone_policy != partition.source_timezone_policy):
        raise ValueError("CACHE_PARTITION_SOURCE_IDENTITY_CONFLICT")
    if bar.lifecycle is not BarLifecycle.CLOSED:
        raise ValueError("PROVISIONAL_BAR_CANNOT_BE_CACHED_AS_CLOSED")
    if bar.coverage is not BarCoverage.COMPLETE or bar.quality is not SourceQuality.VERIFIED:
        raise ValueError("BAR_QUALITY_NOT_CACHEABLE")
    if bar.first_known_utc > as_of_utc or k.bar_end_utc > as_of_utc:
        raise ValueError("FUTURE_BAR_CANNOT_BE_CACHED")
    # A synthetic VERIFIED flag still cannot certify outside-provider rights.


def _bar_row(bar: MarketBar) -> tuple[str, ...]:
    k, o = bar.key, bar.observation
    return (
        k.bar_start_utc.isoformat(), k.bar_end_utc.isoformat(),
        str(bar.revision_number), bar.first_known_utc.isoformat(),
        o.stream_id, o.revision_id, o.raw_sha256,
        str(bar.open), str(bar.high), str(bar.low), str(bar.close),
        bar.lifecycle.value, bar.coverage.value, bar.quality.value,
    )


@dataclass(frozen=True, slots=True)
class CandleSnapshot:
    partition: CachePartition
    closed_bars: tuple[MarketBar, ...]
    checked_at_utc: datetime
    source_head_claim: str

    def __post_init__(self) -> None:
        if not isinstance(self.partition, CachePartition):
            raise TypeError("Expected CachePartition")
        ensure_utc(self.checked_at_utc, "checked_at_utc")
        _nonblank(self.source_head_claim, "source_head_claim")
        if not isinstance(self.closed_bars, tuple):
            raise TypeError("Closed bars must be an immutable tuple")
        last_end = None
        keys = set()
        for bar in self.closed_bars:
            _validate_bar(self.partition, bar, self.checked_at_utc)
            k = bar.key.bar_start_utc
            if k in keys:
                raise ValueError("DUPLICATE_CANDLE_START")
            keys.add(k)
            if last_end is not None and k < last_end:
                raise ValueError("OVERLAPPING_OR_UNSORTED_CANDLE_WINDOW")
            last_end = bar.key.bar_end_utc
        # Gaps are NOT assumed to be missing bars without a verified Forex session.

    @property
    def fingerprint(self) -> str:
        payload = (self.partition.fingerprint,
                   tuple(_bar_row(b) for b in self.closed_bars))
        return sha256(dumps(payload, separators=(",", ":")).encode()).hexdigest()

    @property
    def last_closed_end_utc(self) -> datetime | None:
        return self.closed_bars[-1].key.bar_end_utc if self.closed_bars else None


@dataclass(frozen=True, slots=True)
class SourceHeadClaim:
    """Claim to be externally authenticated by a FUTURE source adapter."""
    partition_fingerprint: str
    source_head_id: str
    complete_through_utc: datetime
    observed_at_utc: datetime

    def __post_init__(self) -> None:
        _nonblank(self.partition_fingerprint, "partition_fingerprint")
        _nonblank(self.source_head_id, "source_head_id")
        ensure_utc(self.complete_through_utc, "complete_through_utc")
        ensure_utc(self.observed_at_utc, "observed_at_utc")
        if self.complete_through_utc > self.observed_at_utc:
            raise ValueError("SOURCE_HEAD_FUTURE_CUTOFF")


@dataclass(frozen=True, slots=True)
class IncrementalPolicy:
    overlap_closed_bars: int
    max_head_age: timedelta

    def __post_init__(self) -> None:
        if (type(self.overlap_closed_bars) is not int
                or not 1 <= self.overlap_closed_bars <= 100):
            raise ValueError("overlap_closed_bars must be between 1 and 100")
        if not isinstance(self.max_head_age, timedelta) or not (
            timedelta(0) < self.max_head_age <= timedelta(days=1)
        ):
            raise ValueError("max_head_age must be positive and at most one day")


class RefreshMode(str, Enum):
    BOOTSTRAP_NEEDED = "BOOTSTRAP_NEEDED"
    DELTA_WINDOW = "DELTA_WINDOW"
    REUSE_HEAD_CLAIM = "REUSE_HEAD_CLAIM"
    RANGE_ENDPOINT_REQUIRED = "RANGE_ENDPOINT_REQUIRED"


@dataclass(frozen=True, slots=True)
class RefreshPlan:
    mode: RefreshMode
    from_utc: datetime | None
    previous_fingerprint: str
    source_claim_authenticated: bool
    may_fetch_real_data: bool
    reason: str


def plan_incremental_refresh(
    snapshot: CandleSnapshot,
    policy: IncrementalPolicy,
    decision_utc: datetime,
    *,
    supports_bounded_range: bool,
    head: SourceHeadClaim | None = None,
) -> RefreshPlan:
    """A pure plan; never invokes source APIs, and always denies real-data IO.

    A matching *claimed* remote head can avoid historical re-fetch only after
    an independent adapter authenticates the receipt. This local planner does
    not perform such verification and cannot grant IO authorization.
    """
    if not isinstance(snapshot, CandleSnapshot) or not isinstance(policy, IncrementalPolicy):
        raise TypeError("Typed snapshot and policy required")
    ensure_utc(decision_utc, "decision_utc")
    if type(supports_bounded_range) is not bool:
        raise TypeError("supports_bounded_range must be bool")
    if decision_utc < snapshot.checked_at_utc:
        raise ValueError("DECISION_PREDATES_CACHE_SNAPSHOT")
    if head is not None and not isinstance(head, SourceHeadClaim):
        raise TypeError("Expected SourceHeadClaim")
    fp = snapshot.fingerprint
    def result(mode: RefreshMode, start: datetime | None, reason: str) -> RefreshPlan:
        return RefreshPlan(mode, start, fp, False, False, reason)

    if not snapshot.closed_bars:
        return result(RefreshMode.BOOTSTRAP_NEEDED, None, "NO_QUALIFIED_HISTORY")
    if not supports_bounded_range:
        return result(RefreshMode.RANGE_ENDPOINT_REQUIRED, None,
                      "NO_VERIFIED_BOUNDED_DELTA_INTERFACE")
    if head is not None:
        if head.partition_fingerprint != snapshot.partition.fingerprint:
            raise ValueError("SOURCE_HEAD_WRONG_PARTITION")
        if head.observed_at_utc > decision_utc:
            raise ValueError("SOURCE_HEAD_FUTURE_OBSERVED")
        if (head.source_head_id == snapshot.source_head_claim
                and head.complete_through_utc >= snapshot.last_closed_end_utc
                and head.observed_at_utc >= snapshot.checked_at_utc
                and decision_utc - head.observed_at_utc <= policy.max_head_age):
            return result(RefreshMode.REUSE_HEAD_CLAIM, None,
                          "CLAIMED_HEAD_IDENTICAL_EXTERNAL_AUTH_REQUIRED")
    start = snapshot.closed_bars[-min(
        policy.overlap_closed_bars, len(snapshot.closed_bars)
    )].key.bar_start_utc
    return result(RefreshMode.DELTA_WINDOW, start,
                  "REQUEST_BOUNDED_OVERLAP_AND_NEW_CLOSED_BARS_ONLY")


class ChangeKind(str, Enum):
    NO_CHANGE = "NO_CHANGE"
    APPEND = "APPEND"
    REVISE = "REVISE"
    APPEND_AND_REVISE = "APPEND_AND_REVISE"


@dataclass(frozen=True, slots=True)
class DeltaReconciliation:
    snapshot: CandleSnapshot
    change: ChangeKind
    appended: int
    revised: int
    first_dirty_utc: datetime | None
    # This is not independent evidence that a provider has no corrections.
    source_verified_externally: bool = False
    may_persist_real_data: bool = False


def reconcile_closed_delta(
    existing: CandleSnapshot,
    delta: tuple[MarketBar, ...],
    decision_utc: datetime,
    *,
    new_source_head_claim: str,
    max_total_bars: int = 100_000,
) -> DeltaReconciliation:
    """Reconcile append/late revision against immutable prior snapshot.

    No deletion inferred from missing rows in a response: range may be partial.
    No silent replacement without a strictly newer revision and first-known.
    """
    if not isinstance(existing, CandleSnapshot) or not isinstance(delta, tuple):
        raise TypeError("Expected snapshot and immutable delta tuple")
    ensure_utc(decision_utc, "decision_utc")
    if decision_utc < existing.checked_at_utc:
        raise ValueError("DECISION_PREDATES_CACHE_SNAPSHOT")
    _nonblank(new_source_head_claim, "new_source_head_claim")
    if type(max_total_bars) is not int or max_total_bars <= 0:
        raise ValueError("max_total_bars must be positive integer")
    by_start: dict[datetime, MarketBar] = {
        b.key.bar_start_utc: b for b in existing.closed_bars
    }
    seen: set[datetime] = set()
    append = revise = 0
    first_dirty = None
    for incoming in delta:
        _validate_bar(existing.partition, incoming, decision_utc)
        start = incoming.key.bar_start_utc
        if start in seen:
            raise ValueError("DUPLICATE_DELTA_BAR")
        seen.add(start)
        old = by_start.get(start)
        if old is None:
            by_start[start] = incoming
            append += 1
            first_dirty = start if first_dirty is None else min(first_dirty, start)
        elif _bar_row(old) == _bar_row(incoming):
            continue
        else:
            if (old.key.bar_end_utc != incoming.key.bar_end_utc
                    or old.observation.stream_id != incoming.observation.stream_id):
                raise ValueError("REVISION_CHANGE_REQUIRES_NEW_PARTITION_OR_REPLAY")
            if (incoming.revision_number <= old.revision_number
                    or incoming.first_known_utc <= old.first_known_utc):
                raise ValueError("OLDER_OR_SAME_REVISION_CONFLICT")
            by_start[start] = incoming
            revise += 1
            first_dirty = start if first_dirty is None else min(first_dirty, start)
    if len(by_start) > max_total_bars:
        raise ValueError("CACHE_CAPACITY_EXCEEDED_NO_SILENT_EVICTION")
    ordered = tuple(by_start[k] for k in sorted(by_start))
    updated = CandleSnapshot(existing.partition, ordered, decision_utc, new_source_head_claim)
    kind = (ChangeKind.APPEND_AND_REVISE if append and revise else
            ChangeKind.APPEND if append else
            ChangeKind.REVISE if revise else ChangeKind.NO_CHANGE)
    return DeltaReconciliation(updated, kind, append, revise, first_dirty)
