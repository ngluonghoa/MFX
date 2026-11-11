"""A04/P0.65: M5 -> H4 shadow research; no native-source replacement.

This is an offline, deterministic contrast with independently sourced H4.
It does not read/write Drive, call Twelve Data, approve signals or trade.
The P0.46 production derivation contract (M15/M30/H1 ONLY) is unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from mfx_cache.native_fx_htf import NativeFXBar
from mfx_cache.td_m5_codec import ClosedM5Bar, PROVIDER
from mfx_cache.v2_engine import (
    DerivationReport, DerivedCandle, source_fingerprint, validate_m5,
)

VERSION = "MFX_A04_P65_M5_H4_SHADOW_RESEARCH_V1"
CALENDAR = "UTC_4H_OPEN_V1"
M5_PER_H4 = 48
H4_SPAN = timedelta(hours=4)
M5_SPAN = timedelta(minutes=5)
Status = Literal["MATCH", "MISMATCH", "NATIVE_MISSING"]


@dataclass(frozen=True, slots=True)
class H4ParityRow:
    start_utc: str
    status: Status
    differing_fields: tuple[str, ...]
    m5_window_sha256: str
    native_bar_sha256: str | None


@dataclass(frozen=True, slots=True)
class H4ParityReport:
    rows: tuple[H4ParityRow, ...]
    matches: int
    mismatches: int
    missing_native: int
    fully_verified: bool = False
    source_numeric_strategy_approved: bool = False
    provider_calls: int = 0
    drive_writes: int = 0
    broker_orders: int = 0


def derive_h4_shadow(
    bars: tuple[ClosedM5Bar, ...], *, asof_utc: datetime,
) -> DerivationReport:
    """Aggregate ONLY complete, 48x CLOSED 5-minute UTC H4 windows.

    A hole, duplicate, misalignment or future M5 candle never yields H4.
    The returned SHA fingerprints the 48 bars, not a verified Drive parent.
    """
    validate_m5(bars, asof_utc=asof_utc)
    windows: dict[datetime, list[ClosedM5Bar]] = {}
    for bar in bars:
        ts = datetime.fromisoformat(bar.start_utc)
        anchor = ts.replace(hour=4 * (ts.hour // 4), minute=0,
                            second=0, microsecond=0)
        windows.setdefault(anchor, []).append(bar)

    candles: list[DerivedCandle] = []
    incomplete: list[str] = []
    for anchor, group in sorted(windows.items()):
        actual = tuple(datetime.fromisoformat(x.start_utc) for x in group)
        expected = tuple(anchor + i * M5_SPAN for i in range(M5_PER_H4))
        if actual != expected:
            incomplete.append(anchor.isoformat())
            continue
        # No rounding: source MID price strings are interpreted as Decimals.
        high = max(Decimal(x.high) for x in group)
        low = min(Decimal(x.low) for x in group)
        candles.append(DerivedCandle(
            frame="H4",
            start_utc=anchor.isoformat(),
            end_utc=(anchor + H4_SPAN).isoformat(),
            open=group[0].open,
            high=str(high),
            low=str(low),
            close=group[-1].close,
            source_interval="M5",
            source_count=M5_PER_H4,
            source_sha256=source_fingerprint(tuple(group)),
            derivation_version=VERSION,
            calendar_version=CALENDAR,
            source_provider=PROVIDER,
            price_side="MID",
            is_source_native=False,
            source_numeric_strategy_approved=False,
        ))
    return DerivationReport(
        frame="H4", candles=tuple(candles),
        skipped_incomplete_windows=tuple(incomplete),
        source_bar_count=len(bars),
    )


def _native_index(bars: tuple[NativeFXBar, ...]) -> dict[str, NativeFXBar]:
    if type(bars) is not tuple or any(type(x) is not NativeFXBar for x in bars):
        raise ValueError("P065_NATIVE_TYPED_TUPLE_REQUIRED")
    result: dict[str, NativeFXBar] = {}
    previous: str | None = None
    for bar in bars:
        if (bar.symbol != "EUR/USD" or bar.interval != "4h"
                or bar.time_reference != "UTC_INTRADAY_OPEN"
                or bar.exchange_timezone != "Australia/Sydney"
                or bar.exchange_timezone_origin not in (
                    "PROVIDER_META", "DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT")
                or bar.source != PROVIDER or bar.price_side != "MID"
                or bar.is_provider_native is not True
                or bar.source_numeric_strategy_approved is not False
                or bar.broker_orders != 0):
            raise ValueError("P065_NATIVE_SCOPE_OR_PROVENANCE_INVALID")
        try:
            stamp = datetime.strptime(bar.native_open_label, "%Y-%m-%d %H:%M:%S")
            if (stamp.strftime("%Y-%m-%d %H:%M:%S") != bar.native_open_label
                    or stamp.hour % 4):
                raise ValueError("P065_NATIVE_H4_UTC_GRID_INVALID")
            vals = tuple(Decimal(getattr(bar, f)) for f in
                         ("open", "high", "low", "close"))
            o, hi, lo, c = vals
            if (any(not x.is_finite() or x <= 0 for x in vals)
                    or lo > min(o, c) or hi < max(o, c) or hi < lo):
                raise ValueError("P065_NATIVE_OHLC_INVALID")
        except (TypeError, ValueError, ArithmeticError) as exc:
            raise ValueError("P065_NATIVE_LABEL_OR_OHLC_INVALID") from exc
        if previous is not None and bar.native_open_label <= previous:
            raise ValueError("P065_DUPLICATE_OR_UNSORTED_NATIVE_H4")
        result[bar.native_open_label] = bar
        previous = bar.native_open_label
    return result


def compare_shadow_to_native(
    shadow: DerivationReport, native: tuple[NativeFXBar, ...],
) -> H4ParityReport:
    """Conservative equality audit, NEVER permission to replace H4 native."""
    if (type(shadow) is not DerivationReport or shadow.frame != "H4"
            or shadow.provider_calls != 0 or shadow.broker_orders != 0):
        raise ValueError("P065_SHADOW_REPORT_INVALID")
    indexed = _native_index(native)
    rows: list[H4ParityRow] = []
    previous: str | None = None
    for candle in shadow.candles:
        if (type(candle) is not DerivedCandle or candle.frame != "H4"
                or candle.source_interval != "M5"
                or candle.source_count != M5_PER_H4
                or candle.derivation_version != VERSION
                or candle.calendar_version != CALENDAR
                or candle.source_provider != PROVIDER
                or candle.price_side != "MID"
                or candle.is_source_native is not False
                or candle.source_numeric_strategy_approved is not False
                or len(candle.source_sha256) != 64):
            raise ValueError("P065_UNTRUSTED_SHADOW_CANDLE")
        try:
            anchor = datetime.fromisoformat(candle.start_utc)
            if (anchor.utcoffset() != timedelta(0) or anchor.hour % 4
                    or anchor.minute or anchor.second or anchor.microsecond
                    or candle.end_utc != (anchor + H4_SPAN).isoformat()):
                raise ValueError("P065_SHADOW_UTC_WINDOW_INVALID")
            derived_prices = tuple(Decimal(getattr(candle, field))
                                   for field in ("open", "high", "low", "close"))
        except (TypeError, ValueError, ArithmeticError) as exc:
            raise ValueError("P065_SHADOW_CANDLE_MALFORMED") from exc
        if previous is not None and candle.start_utc <= previous:
            raise ValueError("P065_DUPLICATE_OR_UNSORTED_SHADOW")
        previous = candle.start_utc
        key = anchor.strftime("%Y-%m-%d %H:%M:%S")
        reference = indexed.get(key)
        diffs: tuple[str, ...] = ()
        status: Status = "NATIVE_MISSING"
        if reference is not None:
            names = ("open", "high", "low", "close")
            diffs = tuple(name for name, price in zip(names, derived_prices)
                          if price != Decimal(getattr(reference, name)))
            status = "MISMATCH" if diffs else "MATCH"
        rows.append(H4ParityRow(
            start_utc=candle.start_utc, status=status,
            differing_fields=diffs,
            m5_window_sha256=candle.source_sha256,
            native_bar_sha256=reference.sha256() if reference else None,
        ))
    return H4ParityReport(
        rows=tuple(rows),
        matches=sum(x.status == "MATCH" for x in rows),
        mismatches=sum(x.status == "MISMATCH" for x in rows),
        missing_native=sum(x.status == "NATIVE_MISSING" for x in rows),
        # Even all equal is only numerical parity; NOT full Drive/source proof.
        fully_verified=False,
    )
