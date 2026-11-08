"""OANDA v20-shaped, synthetic-only, read-only delta response contract.

The payload is an UNTRUSTED fixture, not a licensed vendor quote, signed source
revision, provider authorization, or an executable broker price. No network IO.
This module never promotes parsed candles into a VERIFIED MarketBar/cache.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from hashlib import sha256
from json import dumps
from re import fullmatch
from typing import Mapping, cast

from .cache_core import CachePartition, RefreshMode, RefreshPlan
from .market_data import BarSide, Timeframe
from .quotes import ensure_utc

_SUPPORTED_MINUTES = {Timeframe.M1: 1, Timeframe.M5: 5, Timeframe.M15: 15,
                      Timeframe.M30: 30, Timeframe.H1: 60}
_WIRE_GRANULARITY = {Timeframe.M1: "M1", Timeframe.M5: "M5",
                     Timeframe.M15: "M15", Timeframe.M30: "M30", Timeframe.H1: "H1"}


def _str(x: object, label: str) -> str:
    if not isinstance(x, str) or not x.strip():
        raise ValueError(f"{label} required")
    return x


@dataclass(frozen=True, slots=True)
class OandaUtcStamp:
    """Explicit RFC3339 Z with up to 9 decimals; NEVER silently round ns."""
    utc: datetime
    nanosecond_remainder: int

    @property
    def exact(self) -> bool:
        return self.nanosecond_remainder == 0


def parse_oanda_utc(value: str) -> OandaUtcStamp:
    if not isinstance(value, str):
        raise TypeError("OANDA timestamp must be a string")
    m = fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z", value)
    if not m:
        raise ValueError("INVALID_OANDA_RFC3339_UTC")
    from datetime import datetime as _datetime
    try:
        base = _datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise ValueError("INVALID_OANDA_CLOCK_FIELDS") from exc
    ns = int((m.group(2) or "").ljust(9, "0"))
    return OandaUtcStamp(base.replace(microsecond=ns // 1000, tzinfo=timezone.utc),
                         ns % 1000)


@dataclass(frozen=True, slots=True)
class SyntheticOandaRequest:
    """No URL, token, account ID, network method or source entitlement."""
    partition: CachePartition
    wire_instrument: str
    from_utc: datetime
    to_utc: datetime
    include_first: bool = True
    wire_price: str = "BA"
    smooth: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.partition, CachePartition):
            raise TypeError("CachePartition required")
        if self.partition.side is not BarSide.BID:
            raise ValueError("PAIRED_BID_ASK_REQUEST_REQUIRES_BID_BASE_PARTITION")
        if self.partition.timeframe not in _SUPPORTED_MINUTES:
            raise ValueError("SOURCE_ALIGNED_DAILY_WEEKLY_POLICY_NOT_IMPLEMENTED")
        if not isinstance(self.wire_instrument, str) or not fullmatch(
            r"[A-Z]{3}_[A-Z]{3}", self.wire_instrument
        ):
            raise ValueError("INVALID_WIRE_INSTRUMENT")
        ensure_utc(self.from_utc, "from_utc")
        ensure_utc(self.to_utc, "to_utc")
        if self.from_utc >= self.to_utc:
            raise ValueError("EMPTY_OR_REVERSED_DELTA_RANGE")
        if self.include_first is not True or self.wire_price != "BA" or self.smooth is not False:
            raise ValueError("LOSSY_OR_UNPAIRED_CANDLE_REQUEST")
        # This is deliberately not a usable network client request.


@dataclass(frozen=True, slots=True)
class SyntheticRequestPlan:
    request: SyntheticOandaRequest | None
    may_issue_network_call: bool
    may_store_real_data: bool
    reason: str


def plan_synthetic_oanda_delta(
    refresh: RefreshPlan, partition: CachePartition, wire_instrument: str,
    decision_utc: datetime,
) -> SyntheticRequestPlan:
    ensure_utc(decision_utc, "decision_utc")
    if not isinstance(refresh, RefreshPlan) or not isinstance(partition, CachePartition):
        raise TypeError("Typed cache plan and partition required")
    if refresh.mode is not RefreshMode.DELTA_WINDOW or refresh.from_utc is None:
        return SyntheticRequestPlan(None, False, False, "NO_BOUNDED_DELTA_WINDOW")
    if refresh.from_utc >= decision_utc:
        return SyntheticRequestPlan(None, False, False, "NO_CLOSED_DELTA_TO_REQUEST")
    request = SyntheticOandaRequest(partition, wire_instrument, refresh.from_utc,
                                    decision_utc)
    return SyntheticRequestPlan(
        request, False, False, "SYNTHETIC_BA_WINDOW_ONLY_RIGHTS_NOT_VERIFIED"
    )


def _price(value: object, name: str) -> Decimal:
    if not isinstance(value, str) or not fullmatch(r"\d+(?:\.\d+)?", value):
        raise ValueError(f"INVALID_{name}_PRICE")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"INVALID_{name}_PRICE") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError(f"INVALID_{name}_PRICE")
    return result


@dataclass(frozen=True, slots=True)
class StagedQuoteBar:
    side: BarSide
    start_utc: datetime
    end_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    synthetic_record_digest: str  # not signed or bound to licensed vendor bytes

    def __post_init__(self) -> None:
        if self.side not in (BarSide.BID, BarSide.ASK):
            raise ValueError("NEEDS_NATIVE_BID_ASK")
        ensure_utc(self.start_utc, "start_utc")
        ensure_utc(self.end_utc, "end_utc")
        if self.start_utc >= self.end_utc:
            raise ValueError("INVALID_BAR_INTERVAL")
        if not (self.low <= min(self.open, self.close)
                and self.high >= max(self.open, self.close)
                and self.low <= self.high):
            raise ValueError("INCONSISTENT_NATIVE_SIDE_OHLC")


@dataclass(frozen=True, slots=True)
class StagedCandlePair:
    start_utc: datetime
    end_utc: datetime
    bid: StagedQuoteBar
    ask: StagedQuoteBar
    synthetic_volume_count: int


@dataclass(frozen=True, slots=True)
class SyntheticDeltaResponse:
    pairs: tuple[StagedCandlePair, ...]
    open_candle_count_skipped: int
    observed_at_utc: datetime
    response_sha256_claim: str
    vendor_response_verified: bool = False
    provider_rights_verified: bool = False
    may_commit_real_cache: bool = False


def parse_synthetic_oanda_candles(
    payload: Mapping[str, object], request: SyntheticOandaRequest,
    observed_at_utc: datetime, *,
    max_rows: int = 5000,
) -> SyntheticDeltaResponse:
    """Accept an OANDA-v20-shaped test JSON mapping. No external fetch.

    A source's 'complete' boolean is not proof of full coverage, correct
    first-known time, source reliability, historical pricing parity or rights.
    """
    ensure_utc(observed_at_utc, "observed_at_utc")
    if not isinstance(request, SyntheticOandaRequest):
        raise TypeError("SyntheticOandaRequest required")
    if observed_at_utc < request.to_utc:
        raise ValueError("OBSERVED_BEFORE_REQUEST_CUTOFF")
    if not isinstance(payload, Mapping):
        raise TypeError("Mapping response expected")
    if payload.get("instrument") != request.wire_instrument:
        raise ValueError("RESPONSE_INSTRUMENT_MISMATCH")
    if payload.get("granularity") != _WIRE_GRANULARITY[request.partition.timeframe]:
        raise ValueError("RESPONSE_TIMEFRAME_MISMATCH")
    rows = payload.get("candles")
    if not isinstance(rows, list) or len(rows) > max_rows or max_rows < 1:
        raise ValueError("INVALID_CANDLE_PAGE_SIZE")
    pairs: list[StagedCandlePair] = []
    provisional = 0
    last_start: datetime | None = None
    duration = timedelta(minutes=_SUPPORTED_MINUTES[request.partition.timeframe])
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("Candle record must be a mapping")
        stamp = parse_oanda_utc(cast(str, row.get("time")))
        if not stamp.exact:
            raise ValueError("SUBMICROSECOND_CANDLE_START_REQUIRES_EXACT_CLOCK")
        start = stamp.utc
        end = start + duration
        if start < request.from_utc or start >= request.to_utc:
            raise ValueError("BAR_OUTSIDE_BOUNDED_QUERY")
        if last_start is not None and start <= last_start:
            raise ValueError("DUPLICATE_OR_UNSORTED_CANDLE_TIME")
        last_start = start
        if type(row.get("complete")) is not bool:
            raise ValueError("CANDLE_COMPLETE_FLAG_REQUIRED")
        if not row["complete"]:
            provisional += 1
            continue
        if end > request.to_utc or end > observed_at_utc:
            raise ValueError("COMPLETE_BEFORE_BAR_END_NOT_CAUSAL")
        volume = row.get("volume")
        if type(volume) is not int or volume < 0:
            raise ValueError("INVALID_CANDLE_PRICE_COUNT")
        sides: dict[BarSide, StagedQuoteBar] = {}
        for side, wire in ((BarSide.BID, "bid"), (BarSide.ASK, "ask")):
            quote = row.get(wire)
            if not isinstance(quote, Mapping):
                raise ValueError("BID_ASK_BOTH_REQUIRED")
            o, h, low, c = (_price(quote.get(key), f"{wire.upper()}_{key.upper()}")
                             for key in ("o", "h", "l", "c"))
            serialized = dumps(
                {"start": row["time"], "side": side.value,
                 "ohlc": [str(o), str(h), str(low), str(c)], "volume": volume},
                sort_keys=True, separators=(",", ":"),
            )
            digest = sha256(serialized.encode("utf-8")).hexdigest()
            sides[side] = StagedQuoteBar(side, start, end, o, h, low, c, digest)
        pairs.append(StagedCandlePair(start, end, sides[BarSide.BID],
                                      sides[BarSide.ASK], volume))
    serialized_response = dumps(payload, sort_keys=True, separators=(",", ":"))
    return SyntheticDeltaResponse(
        tuple(pairs), provisional, observed_at_utc,
        sha256(serialized_response.encode("utf-8")).hexdigest()
    )


class DeltaChange(str, Enum):
    UNCHANGED = "UNCHANGED"
    APPENDED = "APPENDED"
    CORRECTED = "CORRECTED"


@dataclass(frozen=True, slots=True)
class SyntheticDeltaDiff:
    appended: int
    corrected: int
    unchanged: int
    first_dirty_utc: datetime | None
    missing_previous_rows_not_deleted: bool
    may_persist_real_prices: bool = False


def diff_synthetic_delta(
    previous: tuple[StagedCandlePair, ...],
    current: SyntheticDeltaResponse,
) -> SyntheticDeltaDiff:
    """Pure overlap diff: missing prior rows aren't provider deletions."""
    if not isinstance(previous, tuple) or not isinstance(current, SyntheticDeltaResponse):
        raise TypeError("Typed previous and current record sets required")
    old = {r.start_utc: r for r in previous}
    if len(old) != len(previous):
        raise ValueError("DUPLICATE_PREVIOUS_CANDLES")
    inserted = corrected = identical = 0
    dirty: datetime | None = None
    for item in current.pairs:
        prior = old.get(item.start_utc)
        if prior is None:
            inserted += 1
        elif (prior.bid.synthetic_record_digest == item.bid.synthetic_record_digest
              and prior.ask.synthetic_record_digest == item.ask.synthetic_record_digest):
            identical += 1
            continue
        else:
            if prior.end_utc != item.end_utc:
                raise ValueError("CANDLE_INTERVAL_CHANGE_REQUIRES_NEW_VERSION")
            corrected += 1
        if dirty is None or item.start_utc < dirty:
            dirty = item.start_utc
    return SyntheticDeltaDiff(inserted, corrected, identical, dirty, True)
