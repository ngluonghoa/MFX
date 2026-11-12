"""MFX 1.0 SIGNAL-FIRST — real source-contract six-timeframe read-only slice.

Pure composition of existing P0.45 M5, P0.46 3/6/12 aggregation and P0.52
native H4 / Sydney-local D1 parsers. Input is *caller-supplied*, NOT an
authenticated Google Drive cache, vendor subscription or historical as-of
snapshot. Current public action is always NO_SIGNAL. No numerical strategy,
SL/TP, R:R, broker, cache/network call or source Forex 1:1 modification.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.td_m5_codec import ClosedM5Bar, PROVIDER, SYMBOL, digest
from mfx_cache.v2_engine import (
    DERIVATION_SIZES, DerivedCandle, derive_intraday,
    validate_m5,
)

VERSION = "MFX_V1_SIX_TF_READONLY_CAUSAL_CONTEXT_V1"
FRAMES = ("M5", "M15", "M30", "H1", "H4", "D1")
GRACE = timedelta(seconds=15)
SYDNEY = "Australia/Sydney"
SOURCE_MID_ONLY = "MID"
MAX_H4_AGE = timedelta(hours=8)
MAX_D1_SESSION_DATE_AGE = 3
MAX_NATIVE_BARS = 120
EXPECTED_REFERENCE = {
    "4h": "UTC_INTRADAY_OPEN",
    "1day": "EXCHANGE_LOCAL_SESSION_DATE",
}


def _utc(value: datetime) -> None:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("V1_SIX_TF_EXACT_UTC_ASOF_REQUIRED")


def _positive(text: str) -> Decimal:
    if type(text) is not str:
        raise ValueError("V1_SIX_TF_PRICE_NOT_DECIMAL_STRING")
    try:
        n = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("V1_SIX_TF_PRICE_NOT_NUMERIC") from exc
    if not n.is_finite() or n <= 0:
        raise ValueError("V1_SIX_TF_PRICE_NOT_POSITIVE_FINITE")
    return n


def _verify_ohlc(open_: str, high: str, low: str, close: str) -> None:
    o, h, lo, c = (_positive(x) for x in (open_, high, low, close))
    if not (lo <= min(o, c) and h >= max(o, c) and lo <= h):
        raise ValueError("V1_SIX_TF_NATIVE_OHLC_INVALID")


def _expected_last_closed(asof: datetime, width: int) -> datetime:
    """UTC-aligned latest interval end that has passed 15s close grace."""
    clock = asof - GRACE
    minutes = clock.hour * 60 + clock.minute
    anchor = clock.replace(hour=0, minute=0, second=0, microsecond=0)
    return anchor + timedelta(minutes=(minutes // width) * width)


def _native_utc_start(label: str) -> datetime:
    if type(label) is not str:
        raise ValueError("V1_SIX_TF_NATIVE_H4_UTC_LABEL_REQUIRED")
    try:
        started = datetime.strptime(label, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc,
        )
    except ValueError as exc:
        raise ValueError("V1_SIX_TF_NATIVE_H4_UTC_LABEL_REQUIRED") from exc
    if (started.strftime("%Y-%m-%d %H:%M:%S") != label
            or started.hour % 4 or started.minute or started.second):
        raise ValueError("V1_SIX_TF_NATIVE_H4_UTC_4H_GRID")
    return started


def _native_local_date(label: str) -> date:
    if type(label) is not str:
        raise ValueError("V1_SIX_TF_NATIVE_D1_DATE_REQUIRED")
    try:
        value = date.fromisoformat(label)
    except ValueError as exc:
        raise ValueError("V1_SIX_TF_NATIVE_D1_DATE_REQUIRED") from exc
    if value.isoformat() != label:
        raise ValueError("V1_SIX_TF_NATIVE_D1_DATE_REQUIRED")
    return value


def _validate_native(
    batch: NativeFXBatch, interval: str, *, asof: datetime,
) -> tuple[NativeFXBar, ...]:
    if (type(batch) is not NativeFXBatch
            or batch.symbol != SYMBOL or batch.interval != interval
            or batch.exchange_timezone != SYDNEY
            or batch.time_reference != EXPECTED_REFERENCE[interval]
            or batch.source != PROVIDER or batch.is_provider_native is not True
            or type(batch.closed_bars) is not tuple
            or len(batch.closed_bars) > MAX_NATIVE_BARS
            or type(batch.incomplete_excluded) is not int
            or batch.incomplete_excluded < 0
            or batch.vendor_calls_made_by_parser != 0
            or batch.google_drive_writes != 0
            or batch.confirmed_buy_sell_signals != 0
            or batch.broker_orders != 0):
        raise ValueError("V1_SIX_TF_NATIVE_BATCH_SCOPE_OR_PRIVILEGE_INVALID")
    prev = ""
    local_today = asof.astimezone(ZoneInfo(SYDNEY)).date()
    for bar in batch.closed_bars:
        if (type(bar) is not NativeFXBar
                or bar.symbol != SYMBOL or bar.interval != interval
                or bar.exchange_timezone != SYDNEY
                or bar.time_reference != EXPECTED_REFERENCE[interval]
                or bar.source != PROVIDER or bar.price_side != SOURCE_MID_ONLY
                or bar.is_provider_native is not True
                or bar.source_numeric_strategy_approved is not False
                or bar.broker_orders != 0
                or bar.exchange_timezone_origin not in (
                    "PROVIDER_META",
                    "DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT",
                )):
            raise ValueError("V1_SIX_TF_NATIVE_BAR_SCOPE_OR_PRIVILEGE_INVALID")
        label = bar.native_open_label
        if type(label) is not str:
            raise ValueError("V1_SIX_TF_NATIVE_LABEL_TYPE_REQUIRED")
        if label <= prev:
            raise ValueError("V1_SIX_TF_DUPLICATE_OR_UNSORTED_NATIVE")
        prev = label
        _verify_ohlc(bar.open, bar.high, bar.low, bar.close)
        if interval == "4h":
            if _native_utc_start(label) + timedelta(hours=4) > asof - GRACE:
                raise ValueError("V1_SIX_TF_NATIVE_H4_OPEN_OR_FUTURE")
        elif _native_local_date(label) >= local_today:
            raise ValueError("V1_SIX_TF_NATIVE_D1_LOCAL_DATE_NOT_CLOSED")
    return batch.closed_bars


@dataclass(frozen=True, slots=True)
class ReadonlyTimeframeEvidence:
    frame: str
    source_provider: str
    source_price_side: str
    time_basis: str
    source_label: str
    end_utc: str | None
    open: str
    high: str
    low: str
    close: str
    source_bar_count: int
    evidence_sha256: str
    native: bool
    verified_feed_subscription: bool = False
    independently_verified_archive_custody: bool = False
    source_numeric_strategy_approved: bool = False


@dataclass(frozen=True, slots=True)
class SixTimeframeResearchReceipt:
    version: str
    action: str
    stage: str
    status: str
    asof_utc: str
    instrument: str
    source_provider: str
    input_m5_sha256: str
    frames: tuple[ReadonlyTimeframeEvidence, ...]
    missing_or_stale_frames: tuple[str, ...]
    total_frames: int
    research_technical_context_complete: bool
    historical_asof_replay_proven: bool = False
    source_feed_subscription_verified: bool = False
    archive_sha_independently_verified: bool = False
    forex_1to1_numerical_parity_verified: bool = False
    entry_sl_tp_net_rr_approved: bool = False
    may_publish_verified_buy_sell: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_market_cache_writes: int = 0
    broker_orders: int = 0


def _from_derived(candle: DerivedCandle) -> ReadonlyTimeframeEvidence:
    if (candle.source_interval != "M5"
            or candle.source_count != DERIVATION_SIZES[candle.frame]
            or candle.source_provider != PROVIDER
            or candle.price_side != SOURCE_MID_ONLY
            or candle.is_source_native
            or candle.source_numeric_strategy_approved):
        raise ValueError("V1_SIX_TF_DERIVED_MUST_BE_MID_RESEARCH")
    return ReadonlyTimeframeEvidence(
        frame=candle.frame, source_provider=PROVIDER,
        source_price_side="MID", time_basis="UTC_INTRADAY_WINDOW",
        source_label=candle.start_utc, end_utc=candle.end_utc,
        open=candle.open, high=candle.high, low=candle.low,
        close=candle.close, source_bar_count=candle.source_count,
        evidence_sha256=candle.source_sha256, native=False,
    )


def _from_native(bar: NativeFXBar, frame: str) -> ReadonlyTimeframeEvidence:
    return ReadonlyTimeframeEvidence(
        frame=frame, source_provider=PROVIDER,
        source_price_side="MID", time_basis=bar.time_reference,
        source_label=bar.native_open_label,
        end_utc=((
            _native_utc_start(bar.native_open_label) + timedelta(hours=4)
        ).isoformat() if frame == "H4" else None),
        open=bar.open, high=bar.high, low=bar.low,
        close=bar.close, source_bar_count=1,
        evidence_sha256=bar.sha256(), native=True,
    )


def build_six_timeframe_readonly_context(
    m5_bars: tuple[ClosedM5Bar, ...], h4: NativeFXBatch,
    d1: NativeFXBatch, *, asof_utc: datetime,
) -> SixTimeframeResearchReceipt:
    """Run a REAL deterministic 6TF technical source composition, no signal.

    The *objects* came from existing offline vendor parser contracts. They do
    not carry authenticated retrieval time, external SHA witness or legal
    entitlement; no historical point-in-time or live claims can be inferred.
    """
    _utc(asof_utc)
    validate_m5(m5_bars, asof_utc=asof_utc)
    h4_rows = _validate_native(h4, "4h", asof=asof_utc)
    d1_rows = _validate_native(d1, "1day", asof=asof_utc)
    evidence: dict[str, ReadonlyTimeframeEvidence] = {}
    missing: list[str] = []

    last_m5 = m5_bars[-1]
    m5_start = datetime.fromisoformat(last_m5.start_utc)
    m5_end = m5_start + timedelta(minutes=5)
    if m5_end == _expected_last_closed(asof_utc, 5):
        evidence["M5"] = ReadonlyTimeframeEvidence(
            frame="M5", source_provider=PROVIDER,
            source_price_side="MID", time_basis="UTC_NATIVE_M5_OPEN",
            source_label=last_m5.start_utc, end_utc=m5_end.isoformat(),
            open=last_m5.open, high=last_m5.high, low=last_m5.low,
            close=last_m5.close, source_bar_count=1,
            evidence_sha256=last_m5.digest(), native=True,
        )
    else:
        missing.append("M5")
    for frame, width in (("M15", 15), ("M30", 30), ("H1", 60)):
        report = derive_intraday(m5_bars, frame, asof_utc=asof_utc)
        target_end = _expected_last_closed(asof_utc, width).isoformat()
        newest = report.candles[-1] if report.candles else None
        if newest is None or newest.end_utc != target_end:
            missing.append(frame)
        else:
            evidence[frame] = _from_derived(newest)

    if h4_rows:
        h4_end = _native_utc_start(
            h4_rows[-1].native_open_label,
        ) + timedelta(hours=4)
        if asof_utc - h4_end <= MAX_H4_AGE:
            evidence["H4"] = _from_native(h4_rows[-1], "H4")
        else:
            missing.append("H4")
    else:
        missing.append("H4")

    if d1_rows:
        last_date = _native_local_date(d1_rows[-1].native_open_label)
        today = asof_utc.astimezone(ZoneInfo(SYDNEY)).date()
        if (today - last_date).days <= MAX_D1_SESSION_DATE_AGE:
            evidence["D1"] = _from_native(d1_rows[-1], "D1")
        else:
            missing.append("D1")
    else:
        missing.append("D1")

    ready = len(evidence) == len(FRAMES) and not missing
    # Digest is a deterministic fingerprint of the caller's typed M5 bars,
    # NOT an externally authenticated raw Drive manifest/chunk SHA.
    m5_sha = digest({
        "version": VERSION,
        "provider": PROVIDER, "instrument": SYMBOL,
        "side": SOURCE_MID_ONLY,
        "m5_sha256": [b.digest() for b in m5_bars],
    })
    return SixTimeframeResearchReceipt(
        version=VERSION, action="NO_SIGNAL", stage="UNVERIFIED",
        status=("SIX_TF_TECHNICAL_RESEARCH_READY_NO_SIGNAL" if ready
                else "SIX_TF_MISSING_OR_STALE_NO_SIGNAL"),
        asof_utc=asof_utc.isoformat(),
        instrument=SYMBOL, source_provider=PROVIDER,
        input_m5_sha256=m5_sha,
        frames=tuple(evidence[x] for x in FRAMES if x in evidence),
        missing_or_stale_frames=tuple(missing),
        total_frames=len(evidence),
        research_technical_context_complete=ready,
    )
