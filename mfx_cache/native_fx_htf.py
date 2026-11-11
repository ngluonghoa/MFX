"""A04/P0.52 — strictly native Twelve Data H4/D1 Forex OHLC envelopes.

Offline parse/validation ONLY: no HTTP, Google Drive write, broker, or signal.
D1 uses exchange-local date; Twelve Data ignores timezone=UTC for daily.
H4 requires the upstream intraday REST request to specify timezone=UTC.
Never derive provider-native H4/D1 from M5 or claim UTC daily anchoring.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mfx_cache.td_m5_codec import PROVIDER, digest

NATIVE_INTERVALS = frozenset(("4h", "1day"))
PAIR_PATTERN = re.compile(r"^[A-Z]{3}/[A-Z]{3}$")
H4_TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
D1_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_NATIVE_RECORDS = 120
H4_CLOSE_GRACE = timedelta(seconds=15)
# The D1 provider defines its own exchange-local session calendar. Require
# that the whole reported local date has passed; no UTC midnight inference.


@dataclass(frozen=True, slots=True)
class NativeFXBar:
    symbol: str
    interval: str
    native_open_label: str
    time_reference: str
    exchange_timezone: str
    open: str
    high: str
    low: str
    close: str
    source: str = PROVIDER
    price_side: str = "MID"
    is_provider_native: bool = True
    exchange_timezone_origin: str = "PROVIDER_META"
    source_numeric_strategy_approved: bool = False
    broker_orders: int = 0

    def sha256(self) -> str:
        return digest(asdict(self))


@dataclass(frozen=True, slots=True)
class NativeFXBatch:
    symbol: str
    interval: str
    exchange_timezone: str
    time_reference: str
    closed_bars: tuple[NativeFXBar, ...]
    incomplete_excluded: int
    source: str = PROVIDER
    is_provider_native: bool = True
    vendor_calls_made_by_parser: int = 0
    google_drive_writes: int = 0
    confirmed_buy_sell_signals: int = 0
    broker_orders: int = 0


def native_request_contract(*, symbol: str, interval: str) -> dict[str, str]:
    """Cloud HTTP caller parameter envelope, not an HTTP request.

    The daily timezone key is deliberately absent: vendor ignores it for
    1day and labels daily candles in exchange-local time.
    """
    _check_symbol_and_interval(symbol, interval)
    request = {"symbol": symbol, "interval": interval,
               "format": "JSON", "outputsize": "120"}
    if interval == "4h":
        request["timezone"] = "UTC"
    return request


def _check_symbol_and_interval(symbol: str, interval: str) -> None:
    if (type(symbol) is not str or not PAIR_PATTERN.fullmatch(symbol)
            or symbol.split("/")[0] == symbol.split("/")[1]):
        raise ValueError("P052_INVALID_FOREX_SYMBOL")
    if interval not in NATIVE_INTERVALS:
        raise ValueError("P052_ONLY_PROVIDER_NATIVE_H4_D1")


def _positive_decimal(text: Any, name: str) -> Decimal:
    if type(text) is not str:
        raise ValueError("P052_INVALID_PRICE_TYPE:" + name)
    try:
        val = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("P052_INVALID_PRICE_DECIMAL:" + name) from exc
    if not val.is_finite() or val <= 0:
        raise ValueError("P052_INVALID_PRICE_VALUE:" + name)
    return val


def parse_native_forex(
    payload: Any, *, symbol: str, interval: str,
    now_utc: datetime, requested_timezone: str | None,
) -> NativeFXBatch:
    """Pure conservative parser; retain H4 UTC vs D1 local-date provenance.

    For H4, an actual REST caller must send timezone=UTC. For D1 the API
    ignores timezone and returns exchange-local dates, so NEVER give D1
    candles a synthetic UTC open timestamp.
    """
    _check_symbol_and_interval(symbol, interval)
    if (type(now_utc) is not datetime or now_utc.tzinfo is None
            or now_utc.utcoffset() != timedelta(0)):
        raise ValueError("P052_EXACT_UTC_NOW_REQUIRED")
    if ((interval == "4h" and requested_timezone != "UTC")
            or (interval == "1day" and requested_timezone is not None)):
        raise ValueError("P052_REQUEST_TIMEZONE_CONTRACT_VIOLATION")
    if not isinstance(payload, dict) or payload.get("status") == "error":
        raise ValueError("P052_INVALID_VENDOR_PAYLOAD")
    meta, values = payload.get("meta"), payload.get("values")
    if (not isinstance(meta, dict) or meta.get("symbol") != symbol
            or meta.get("interval") != interval
            or meta.get("type") not in ("Physical Currency", "Forex")
            or type(values) is not list
            or not 1 <= len(values) <= MAX_NATIVE_RECORDS):
        raise ValueError("P052_VENDOR_META_INTERVAL_OR_ROWS_MISMATCH")

    exchange_timezone = meta.get("exchange_timezone")
    timezone_origin = "PROVIDER_META"
    if exchange_timezone is None or exchange_timezone == "":
        # Twelve Data documents Australia/Sydney as the default Forex
        # exchange timezone. Its real EUR/USD response can omit the field.
        # This narrow EUR/USD-only fallback is explicitly provenance-marked
        # in the SHA-covered native candle, NOT represented as vendor meta.
        if (symbol == "EUR/USD" and meta.get("type") in
                ("Physical Currency", "Forex")):
            exchange_timezone = "Australia/Sydney"
            timezone_origin = "DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT"
        else:
            raise ValueError("P052_EXCHANGE_TIMEZONE_REQUIRED")
    elif type(exchange_timezone) is not str:
        raise ValueError("P052_EXCHANGE_TIMEZONE_REQUIRED")
    try:
        local_zone = ZoneInfo(exchange_timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("P052_INVALID_EXCHANGE_TIMEZONE") from exc

    axis = ("UTC_INTRADAY_OPEN" if interval == "4h" else
            "EXCHANGE_LOCAL_SESSION_DATE")
    seen: set[str] = set()
    closed: list[NativeFXBar] = []
    incomplete = 0
    for raw in values:
        if type(raw) is not dict or type(raw.get("datetime")) is not str:
            raise ValueError("P052_INVALID_NATIVE_ROW")
        label = raw["datetime"]
        if label in seen:
            raise ValueError("P052_DUPLICATE_NATIVE_OPEN_LABEL")
        seen.add(label)
        if interval == "4h":
            if not H4_TIME_PATTERN.fullmatch(label):
                raise ValueError("P052_H4_UTC_DATETIME_FORMAT")
            try:
                started = datetime.strptime(
                    label, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError as exc:
                raise ValueError("P052_H4_UTC_DATETIME_FORMAT") from exc
            if started.minute or started.second:
                raise ValueError("P052_H4_NOT_HOUR_ALIGNED")
            is_closed = started + timedelta(hours=4) <= (
                now_utc - H4_CLOSE_GRACE)
        else:
            if not D1_DATE_PATTERN.fullmatch(label):
                raise ValueError("P052_D1_LOCAL_DATE_FORMAT")
            try:
                local_date = date.fromisoformat(label)
            except ValueError as exc:
                raise ValueError("P052_D1_LOCAL_DATE_FORMAT") from exc
            is_closed = local_date < now_utc.astimezone(local_zone).date()
        if not is_closed:
            incomplete += 1
            continue
        o = _positive_decimal(raw.get("open"), "open")
        hi = _positive_decimal(raw.get("high"), "high")
        lo = _positive_decimal(raw.get("low"), "low")
        c = _positive_decimal(raw.get("close"), "close")
        if lo > min(o, c) or hi < max(o, c) or hi < lo:
            raise ValueError("P052_INVALID_NATIVE_OHLC_ORDER")
        closed.append(NativeFXBar(
            symbol=symbol, interval=interval, native_open_label=label,
            time_reference=axis, exchange_timezone=exchange_timezone,
            open=str(o), high=str(hi), low=str(lo), close=str(c),
            exchange_timezone_origin=timezone_origin,
        ))
    closed.sort(key=lambda bar: bar.native_open_label)
    return NativeFXBatch(
        symbol=symbol, interval=interval,
        exchange_timezone=exchange_timezone, time_reference=axis,
        closed_bars=tuple(closed), incomplete_excluded=incomplete,
    )
