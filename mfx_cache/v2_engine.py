"""A04/P0.46 — deterministic Cloud-only Cache V2 RESEARCH core.

Pure planning/transformation: NO network, no Google Drive writes, no broker,
no original Forex source detector parity, no production BUY/SELL publication.
The existing P045 REST→Drive writer stays disabled until separately adapted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from typing import Any, Literal
import re

from mfx_cache.td_m5_codec import (
    ClosedM5Bar, PROVIDER, canonical, digest,
)

VERSION = "MFX_A04_P46_CACHE_V2_CORE_V1"
SOURCE_TIMEZONE = "UTC"
SOURCE_SIDE = "MID"
SOURCE_INTERVAL = "M5"
CALENDAR = "UTC_INTRADAY_WINDOW_V1"
MAX_M5_BARS = 10_000
DERIVATION_SIZES = {"M15": 3, "M30": 6, "H1": 12}
FRAME_MINUTES = {"M5": 5, "M15": 15, "M30": 30, "H1": 60,
                 "H4": 240, "D1": 1440}


def _utc_now(value: datetime) -> None:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P046_UTC_ASOF_REQUIRED")


def _ts(text: str) -> datetime:
    if type(text) is not str:
        raise ValueError("P046_TIMESTAMP_EXPLICIT_UTC_REQUIRED")
    try:
        result = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("P046_INVALID_UTC_TIMESTAMP") from exc
    if (result.tzinfo is None or result.utcoffset() != timedelta(0)
            or not text.endswith("+00:00") or result.second != 0
            or result.microsecond != 0 or result.minute % 5 != 0):
        raise ValueError("P046_EXACT_M5_UTC_ALIGNMENT_REQUIRED")
    return result


def _price(value: str) -> Decimal:
    if type(value) is not str:
        raise ValueError("P046_DECIMAL_STRING_REQUIRED")
    try:
        d = Decimal(value)
    except Exception as exc:
        raise ValueError("P046_DECIMAL_PARSE_FAILURE") from exc
    if not d.is_finite() or d <= 0:
        raise ValueError("P046_FINITE_POSITIVE_PRICE_REQUIRED")
    return d


def _bar_object(bar: ClosedM5Bar) -> dict[str, str]:
    return {"start_utc": bar.start_utc, "open": bar.open,
            "high": bar.high, "low": bar.low, "close": bar.close}


def validate_m5(
    bars: tuple[ClosedM5Bar, ...], *, asof_utc: datetime,
) -> tuple[ClosedM5Bar, ...]:
    _utc_now(asof_utc)
    if (type(bars) is not tuple or not 1 <= len(bars) <= MAX_M5_BARS
            or any(type(x) is not ClosedM5Bar for x in bars)):
        raise ValueError("P046_BOUNDED_M5_BAR_INPUT_REQUIRED")
    last: datetime | None = None
    for b in bars:
        start = _ts(b.start_utc)
        if last is not None and start <= last:
            raise ValueError("P046_DUPLICATE_OR_UNORDERED_M5")
        if start + timedelta(minutes=5) > asof_utc - timedelta(seconds=15):
            raise ValueError("P046_FUTURE_OPEN_OR_NOT_SETTLED_M5")
        o, high, low, close = map(
            _price, (b.open, b.high, b.low, b.close),
        )
        if low > min(o, close) or high < max(o, close) or high < low:
            raise ValueError("P046_INVALID_M5_OHLC")
        last = start
    return bars


def source_fingerprint(bars: tuple[ClosedM5Bar, ...]) -> str:
    return digest({"schema": VERSION, "provider": PROVIDER, "side": SOURCE_SIDE,
                   "timeframe": SOURCE_INTERVAL, "timezone": SOURCE_TIMEZONE,
                   "calendar": CALENDAR,
                   "bars": [_bar_object(b) for b in bars]})


@dataclass(frozen=True, slots=True)
class DerivedCandle:
    frame: str
    start_utc: str
    end_utc: str
    open: str
    high: str
    low: str
    close: str
    source_interval: str
    source_count: int
    source_sha256: str
    derivation_version: str = VERSION
    calendar_version: str = CALENDAR
    source_provider: str = PROVIDER
    price_side: str = SOURCE_SIDE
    is_source_native: bool = False
    source_numeric_strategy_approved: bool = False


@dataclass(frozen=True, slots=True)
class DerivationReport:
    frame: str
    candles: tuple[DerivedCandle, ...]
    skipped_incomplete_windows: tuple[str, ...]
    source_bar_count: int
    provider_calls: int = 0
    broker_orders: int = 0


def derive_intraday(
    bars: tuple[ClosedM5Bar, ...], frame: str, *, asof_utc: datetime,
) -> DerivationReport:
    """Only M15/M30/H1, aligned UTC, exact N CLOSED native M5 bars.

    H4 and D1 MUST come from native provider: never derive those here.
    """
    if frame not in DERIVATION_SIZES:
        raise ValueError("P046_H4_D1_MUST_BE_PROVIDER_NATIVE")
    validate_m5(bars, asof_utc=asof_utc)
    count = DERIVATION_SIZES[frame]
    width = FRAME_MINUTES[frame]
    windows: dict[datetime, list[ClosedM5Bar]] = {}
    for b in bars:
        start = _ts(b.start_utc)
        minute_of_day = start.hour * 60 + start.minute
        anchor = start - timedelta(minutes=minute_of_day % width)
        windows.setdefault(anchor, []).append(b)
    result: list[DerivedCandle] = []
    incomplete: list[str] = []
    for anchor, group in sorted(windows.items()):
        expected = tuple(anchor + timedelta(minutes=5*i)
                         for i in range(count))
        actual = tuple(_ts(b.start_utc) for b in group)
        if len(group) != count or actual != expected:
            incomplete.append(anchor.isoformat())
            continue
        # Data is pre-validated and the entire N-group is CLOSED by asof.
        op, end = group[0].open, group[-1].close
        high = max(_price(b.high) for b in group)
        low = min(_price(b.low) for b in group)
        result.append(DerivedCandle(
            frame=frame, start_utc=anchor.isoformat(),
            end_utc=(anchor + timedelta(minutes=width)).isoformat(),
            open=op, high=str(high), low=str(low), close=end,
            source_interval="M5", source_count=count,
            source_sha256=source_fingerprint(tuple(group)),
        ))
    return DerivationReport(frame=frame, candles=tuple(result),
                            skipped_incomplete_windows=tuple(incomplete),
                            source_bar_count=len(bars))


@dataclass(frozen=True, slots=True)
class Hole:
    after_utc: str
    before_utc: str
    missing_m5_slots: int
    classification: Literal["POSSIBLE_SOURCE_HOLE", "SESSION_UNKNOWN"]
    auto_backfill_allowed: bool = False


def detect_missing(
    bars: tuple[ClosedM5Bar, ...], *, asof_utc: datetime,
    max_holes: int = 256,
) -> tuple[Hole, ...]:
    """Mark gaps; weekend/rollover/session calendar are NOT guessed."""
    validate_m5(bars, asof_utc=asof_utc)
    if type(max_holes) is not int or not 1 <= max_holes <= 256:
        raise ValueError("P046_BOUNDED_GAP_REPORT_REQUIRED")
    gaps: list[Hole] = []
    for prior, current in zip(bars, bars[1:]):
        seconds = int((_ts(current.start_utc) -
                       _ts(prior.start_utc)).total_seconds())
        if seconds == 300:
            continue
        if seconds < 300 or seconds % 300:
            raise ValueError("P046_NON_M5_ALIGNED_HISTORY_GAP")
        if len(gaps) >= max_holes:
            raise ValueError("P046_GAP_REPORT_TOO_LARGE")
        gaps.append(Hole(
            after_utc=prior.start_utc, before_utc=current.start_utc,
            missing_m5_slots=(seconds // 300) - 1,
            classification=("SESSION_UNKNOWN" if seconds > 8*3600
                            else "POSSIBLE_SOURCE_HOLE"),
        ))
    return tuple(gaps)


@dataclass(frozen=True, slots=True)
class RawChunk:
    """Pinned digest of exact canonical source bytes plus closed bars."""
    bars: tuple[ClosedM5Bar, ...]
    sha256: str
    source: str = PROVIDER
    side: str = SOURCE_SIDE
    timezone: str = SOURCE_TIMEZONE


def make_chunk(bars: tuple[ClosedM5Bar, ...], *,
               asof_utc: datetime) -> RawChunk:
    validate_m5(bars, asof_utc=asof_utc)
    return RawChunk(bars=bars, sha256=source_fingerprint(bars))


@dataclass(frozen=True, slots=True)
class CompactedPartition:
    utc_day: str
    parent_chunk_sha256: tuple[str, ...]
    canonical_bars: tuple[ClosedM5Bar, ...]
    compacted_sha256: str
    storage_tier: str = "WARM"
    parent_deletion_authorized: bool = False
    drive_verified_readback: bool = False


def compact_utc_days(
    chunks: tuple[RawChunk, ...], *, asof_utc: datetime,
    min_parent_chunks: int = 4,
) -> tuple[CompactedPartition, ...]:
    """Dry-run additive compaction; independent Drive readback required.

    The returned immutable partition is a content-addressed *proposal*.
    Do not remove parents until an external verified commit/CAS/retention.
    """
    _utc_now(asof_utc)
    if (type(chunks) is not tuple or not 1 <= len(chunks) <= 1440
            or type(min_parent_chunks) is not int
            or not 2 <= min_parent_chunks <= 100):
        raise ValueError("P046_BOUNDED_CHUNK_COMPACTION_REQUIRED")
    parts: dict[str, dict[str, Any]] = {}
    seen_chunks: set[str] = set()
    for chunk in chunks:
        if (type(chunk) is not RawChunk or
                chunk.source != PROVIDER or chunk.side != SOURCE_SIDE
                or chunk.timezone != SOURCE_TIMEZONE):
            raise ValueError("P046_COMPACTION_PROVENANCE_MISMATCH")
        validate_m5(chunk.bars, asof_utc=asof_utc)
        if chunk.sha256 != source_fingerprint(chunk.bars):
            raise ValueError("P046_CHUNK_CONTENT_SHA_MISMATCH")
        if chunk.sha256 in seen_chunks:
            continue
        seen_chunks.add(chunk.sha256)
        for b in chunk.bars:
            day = b.start_utc[:10]
            state = parts.setdefault(day, {"bars": {}, "parents": set()})
            state["parents"].add(chunk.sha256)
            existing = state["bars"].get(b.start_utc)
            if existing is not None and existing != b:
                raise ValueError("P046_OVERLAPPING_REVISED_CLOSED_BAR_QUARANTINE")
            state["bars"][b.start_utc] = b
    proposals: list[CompactedPartition] = []
    for day, state in sorted(parts.items()):
        parents = tuple(sorted(state["parents"]))
        if len(parents) < min_parent_chunks:
            continue
        bars = tuple(b for _, b in sorted(state["bars"].items()))
        validate_m5(bars, asof_utc=asof_utc)
        if len(bars) > 288:
            raise ValueError("P046_OVERFILLED_UTC_DAY_PARTITION")
        document = {
            "schema": VERSION, "tier": "WARM", "day": day,
            "source": PROVIDER, "side": SOURCE_SIDE,
            "timezone": SOURCE_TIMEZONE, "calendar": CALENDAR,
            "parents": parents,
            "bars": [_bar_object(b) for b in bars],
        }
        proposals.append(CompactedPartition(
            utc_day=day, parent_chunk_sha256=parents,
            canonical_bars=bars, compacted_sha256=digest(document),
        ))
    return tuple(proposals)


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    algorithm: str
    period: int
    source_sha256: str
    ema_close: str
    atr_wilder: str
    last_close_utc: str
    numerical_strategy_approved: bool = False
    publishable_signal: bool = False


@dataclass(frozen=True, slots=True)
class IndicatorDecision:
    snapshot: IndicatorSnapshot
    reused: bool
    provider_calls: int = 0


def indicator_cache(
    bars: tuple[ClosedM5Bar, ...], *, period: int,
    asof_utc: datetime, cached: IndicatorSnapshot | None = None,
) -> IndicatorDecision:
    """Deterministic WINDOW-SCOPED EMA and Wilder ATR, not original signals."""
    validate_m5(bars, asof_utc=asof_utc)
    if type(period) is not int or not 2 <= period <= 100:
        raise ValueError("P046_EXPLICIT_RESEARCH_INDICATOR_PERIOD_REQUIRED")
    if len(bars) < period + 1:
        raise ValueError("P046_INSUFFICIENT_CLOSED_INDICATOR_HISTORY")
    if detect_missing(bars, asof_utc=asof_utc):
        raise ValueError("P046_INDICATOR_REQUIRES_CONTIGUOUS_INPUT")
    signature = source_fingerprint(bars)
    algo = "MFX_P046_EMA_AND_WILDER_ATR_RESEARCH_V1"
    if cached is not None and (
            cached.algorithm == algo and cached.period == period
            and cached.source_sha256 == signature and
            cached.last_close_utc == bars[-1].start_utc
            and not cached.numerical_strategy_approved
            and not cached.publishable_signal):
        return IndicatorDecision(snapshot=cached, reused=True)
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_EVEN
        closes = [_price(b.close) for b in bars]
        highs = [_price(b.high) for b in bars]
        lows = [_price(b.low) for b in bars]
        coefficient = Decimal(2) / Decimal(period + 1)
        ema = sum(closes[:period], Decimal(0)) / Decimal(period)
        for close in closes[period:]:
            ema = (close - ema) * coefficient + ema
        true_ranges: list[Decimal] = []
        for i, (hi, lo) in enumerate(zip(highs, lows)):
            true_ranges.append(hi - lo if i == 0 else
                               max(hi-lo, abs(hi-closes[i-1]),
                                   abs(lo-closes[i-1])))
        atr = sum(true_ranges[:period], Decimal(0)) / Decimal(period)
        for tr in true_ranges[period:]:
            atr = ((atr * Decimal(period - 1)) + tr) / Decimal(period)
    snap = IndicatorSnapshot(
        algorithm=algo, period=period, source_sha256=signature,
        ema_close=str(ema), atr_wilder=str(atr),
        last_close_utc=bars[-1].start_utc,
    )
    return IndicatorDecision(snapshot=snap, reused=False)


@dataclass(frozen=True, slots=True)
class FetchCandidate:
    symbol: str
    frame: Literal["M5", "H4", "D1"]
    last_closed_start_utc: str | None
    last_polled_utc: str | None
    priority: int  # 0=highest; policy quality only, not source trading signal.
    request_credits: int = 1


@dataclass(frozen=True, slots=True)
class SmartFetchPlan:
    selected: tuple[FetchCandidate, ...]
    not_due: tuple[str, ...]
    due_but_deferred: tuple[str, ...]
    credits_reserved: int
    market_api_calls: int = 0
    drive_file_writes: int = 0


def plan_fetch(
    candidates: tuple[FetchCandidate, ...], *, now_utc: datetime,
    minute_credits_remaining: int, day_credits_remaining: int,
    max_requests: int = 7,
) -> SmartFetchPlan:
    """Quota-admission plan only; 0 external calls, deterministic priority."""
    _utc_now(now_utc)
    if (type(candidates) is not tuple or len(candidates) > 100
            or any(type(x) is not FetchCandidate for x in candidates)
            or any(type(x) is not int or x < 0 for x in
                   (minute_credits_remaining, day_credits_remaining,
                    max_requests))
            or max_requests > 7):
        raise ValueError("P046_BOUNDED_FETCH_ADMISSION_REQUIRED")
    due: list[tuple[int, int, str, FetchCandidate]] = []
    reuse: list[str] = []
    keys: set[tuple[str, str]] = set()
    for c in candidates:
        if (re.fullmatch("[A-Z]{3}/[A-Z]{3}", c.symbol) is None
                or c.frame not in ("M5", "H4", "D1")
                or type(c.priority) is not int or not 0 <= c.priority <= 10
                or type(c.request_credits) is not int
                or not 1 <= c.request_credits <= 8
                or (c.symbol, c.frame) in keys):
            raise ValueError("P046_INVALID_SYMBOL_FRAME_OR_COST")
        keys.add((c.symbol, c.frame))
        label = c.symbol + ":" + c.frame
        # A candle already closed, but current polling slot was requested:
        # avoid duplicate vendor calls. Recover missing data separately.
        if c.last_polled_utc is not None:
            polled = _ts(c.last_polled_utc)
            if polled > now_utc:
                raise ValueError("P046_FUTURE_LAST_POLL")
            if polled >= now_utc.replace(second=0, microsecond=0) - timedelta(
                    minutes=now_utc.minute % 5):
                reuse.append(label)
                continue
        if c.last_closed_start_utc is not None:
            last = _ts(c.last_closed_start_utc)
            if last > now_utc:
                raise ValueError("P046_FUTURE_LAST_CLOSED")
            length = timedelta(minutes=FRAME_MINUTES[c.frame])
            if now_utc < last + length*2 + timedelta(seconds=15):
                reuse.append(label)
                continue
            overdue = int((now_utc - last - length).total_seconds())
        else:
            overdue = 10**12
        due.append((c.priority, -overdue, label, c))
    due.sort()
    admitted: list[FetchCandidate] = []
    deferred: list[str] = []
    left = min(minute_credits_remaining, day_credits_remaining)
    for _, _, label, c in due:
        if len(admitted) >= max_requests or left < c.request_credits:
            deferred.append(label)
        else:
            admitted.append(c)
            left -= c.request_credits
    return SmartFetchPlan(
        selected=tuple(admitted),
        not_due=tuple(sorted(reuse)),
        due_but_deferred=tuple(deferred),
        credits_reserved=sum(c.request_credits for c in admitted),
    )


def modeled_write_pressure(
    *, polls_per_day: int, flushes_per_day: int,
    days: int,
) -> dict[str, int | str]:
    """Model only; NEVER claim actual measured vendor or Drive improvement."""
    for val in (polls_per_day, flushes_per_day, days):
        if type(val) is not int or not 1 <= val <= 365:
            raise ValueError("P046_EXPLICIT_BOUNDED_PRESSURE_SCENARIO_REQUIRED")
    if flushes_per_day > polls_per_day:
        raise ValueError("P046_FLUSHES_CANNOT_EXCEED_POLL_CYCLES")
    p45 = 2 * polls_per_day * days  # assumes 1 chunk and 1 manifest/poll
    p46 = 2 * flushes_per_day * days
    return {
        "classification": "SCENARIO_ONLY_NOT_MEASURED_DRIVE_IO",
        "p045_max_two_files_per_poll_scenario": p45,
        "p046_two_files_per_flush_scenario": p46,
        "potential_files_avoided_scenario": p45-p46,
    }
