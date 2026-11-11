"""A04/P0.54 — pure isolated immutable H4/D1 Forex archival contracts.

No network/Drive calls and no trading. Content-addressed one-chunk +
one-manifest planning, idempotent overlap and exact per-symbol/TF boundaries.
The live M5 writer remains completely unchanged.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mfx_cache.native_fx_htf import (
    NativeFXBar, NativeFXBatch, PAIR_PATTERN, PROVIDER,
)
from mfx_cache.td_m5_codec import digest

SCHEMA = "MFX_A04_P54_NATIVE_HTF_SEALED_V1"
MAX_BATCH_BARS = 120
RECENT_INDEX_LIMIT = 16
SHA_DIGITS = set("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class NativeSealedPlan:
    symbol: str
    interval: str
    chunk_name: str
    chunk_sha256: str
    chunk: dict[str, Any]
    manifest_name: str
    manifest_sha256: str
    manifest: dict[str, Any]
    newly_closed_bars: int
    drive_writes_performed: int = 0
    provider_requests_performed: int = 0
    broker_orders: int = 0


def _scope(symbol: str, interval: str) -> str:
    if (type(symbol) is not str or PAIR_PATTERN.fullmatch(symbol) is None
            or symbol[:3] == symbol[-3:]):
        raise ValueError("P054_INVALID_PAIR")
    if interval not in ("4h", "1day"):
        raise ValueError("P054_UNSUPPORTED_NATIVE_INTERVAL")
    return f"MFX_TD_{symbol.replace('/', '')}_{'H4' if interval == '4h' else 'D1'}_NATIVE_V1"


def _axis(interval: str) -> str:
    return "UTC_INTRADAY_OPEN" if interval == "4h" else "EXCHANGE_LOCAL_SESSION_DATE"


def _sha(text: Any) -> bool:
    return type(text) is str and len(text) == 64 and all(c in SHA_DIGITS for c in text)


def _bar_valid(bar: NativeFXBar, *, symbol: str, interval: str, zone: str) -> None:
    if type(bar) is not NativeFXBar or (
            bar.symbol != symbol or bar.interval != interval
            or bar.exchange_timezone != zone
            or bar.time_reference != _axis(interval)
            or bar.source != PROVIDER
            or bar.price_side != "MID"
            or bar.is_provider_native is not True
            or bar.source_numeric_strategy_approved is not False
            or bar.broker_orders != 0):
        raise ValueError("P054_BAR_SCOPE_OR_PROVENANCE_MISMATCH")
    if (bar.exchange_timezone_origin not in (
            "PROVIDER_META", "DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT")
            or (bar.exchange_timezone_origin ==
                "DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT"
                and (symbol != "EUR/USD" or zone != "Australia/Sydney"))):
        raise ValueError("P056_NATIVE_TIMEZONE_PROVENANCE_INVALID")
    try:
        if interval == "4h":
            timestamp = datetime.strptime(
                bar.native_open_label, "%Y-%m-%d %H:%M:%S")
            if (timestamp.strftime("%Y-%m-%d %H:%M:%S") !=
                    bar.native_open_label or timestamp.minute or timestamp.second):
                raise ValueError("P054_BAD_H4_LABEL")
        else:
            d = date.fromisoformat(bar.native_open_label)
            if d.isoformat() != bar.native_open_label:
                raise ValueError("P054_BAD_D1_LABEL")
    except (ValueError, TypeError) as exc:
        raise ValueError("P054_BAD_NATIVE_LABEL") from exc
    values: list[Decimal] = []
    for val in (bar.open, bar.high, bar.low, bar.close):
        if type(val) is not str:
            raise ValueError("P054_NATIVE_PRICE_NOT_STRING")
        try:
            d = Decimal(val)
        except InvalidOperation as exc:
            raise ValueError("P054_INVALID_NATIVE_PRICE") from exc
        if not d.is_finite() or d <= 0:
            raise ValueError("P054_INVALID_NATIVE_PRICE")
        values.append(d)
    op, high, low, close = values
    if low > min(op, close) or high < max(op, close) or high < low:
        raise ValueError("P054_INVALID_NATIVE_OHLC")


def _stamp(label: str, interval: str) -> str:
    if interval == "4h":
        return datetime.strptime(label, "%Y-%m-%d %H:%M:%S").strftime("%Y%m%dT%H%MUTC")
    return date.fromisoformat(label).strftime("%Y%m%dLOCAL")


def _name(kind: str, symbol: str, interval: str, label: str, sha: str) -> str:
    if kind not in ("chunk", "manifest") or not _sha(sha):
        raise ValueError("P054_INVALID_KIND_OR_SHA")
    return f"{_scope(symbol, interval)}_{kind}_{_stamp(label, interval)}_{sha}.json"


def check_native_manifest(m: dict[str, Any], *, symbol: str, interval: str,
                          zone: str) -> None:
    _scope(symbol, interval)
    required = {
        "schema","symbol","interval","exchange_timezone",
        "time_reference","source","source_side","provider_native",
        "parent_manifest_sha256","chunk_name","chunk_sha256",
        "last_native_open_label","batch_count","total_closed_native_bars",
        "recent_native_bar_index","approved_numeric_signals","broker_orders",
    }
    if (type(m) is not dict or set(m) != required
            or m["schema"] != SCHEMA or m["symbol"] != symbol
            or m["interval"] != interval or m["exchange_timezone"] != zone
            or m["time_reference"] != _axis(interval)
            or m["source"] != PROVIDER or m["source_side"] != "MID"
            or m["provider_native"] is not True
            or m["approved_numeric_signals"] is not False
            or m["broker_orders"] != 0
            or type(m["batch_count"]) is not int or m["batch_count"] < 1
            or type(m["total_closed_native_bars"]) is not int
            or m["total_closed_native_bars"] < m["batch_count"]
            or not _sha(m["chunk_sha256"])
            or type(m["last_native_open_label"]) is not str):
        raise ValueError("P054_INVALID_MANIFEST_SCHEMA_OR_PROVENANCE")
    parent = m["parent_manifest_sha256"]
    if parent is not None and not _sha(parent):
        raise ValueError("P054_INVALID_PARENT_SHA")
    if (m["batch_count"] == 1) != (parent is None):
        raise ValueError("P054_INVALID_ROOT_OR_PARENT")
    try:
        _stamp(m["last_native_open_label"], interval)
    except ValueError as exc:
        raise ValueError("P054_INVALID_MANIFEST_LAST_LABEL") from exc
    if m["chunk_name"] != _name(
            "chunk", symbol, interval, m["last_native_open_label"],
            m["chunk_sha256"]):
        raise ValueError("P054_MANIFEST_CHUNK_REFERENCE_MISMATCH")
    recent = m["recent_native_bar_index"]
    if (type(recent) is not list or not 1 <= len(recent) <= RECENT_INDEX_LIMIT
            or any(type(x) is not dict or set(x) != {"label", "sha256"}
                   or type(x["label"]) is not str or not _sha(x["sha256"])
                   for x in recent)):
        raise ValueError("P054_INVALID_RECENT_NATIVE_INDEX")
    labels = [x["label"] for x in recent]
    if (labels != sorted(set(labels)) or
            labels[-1] != m["last_native_open_label"]
            or any(not _valid_stamp(x, interval) for x in labels)):
        raise ValueError("P054_RECENT_INDEX_ORDER_OR_LAST_LABEL")


def _valid_stamp(label: str, interval: str) -> bool:
    try:
        _stamp(label, interval)
        return True
    except (ValueError, TypeError):
        return False


def plan_native_sealed(
    batch: NativeFXBatch, *,
    previous: dict[str, Any] | None,
) -> NativeSealedPlan | None:
    """One immutable append-only batch from a prevalidated native provider envelope.

    Existing recent labels are checked by SHA. Old overlap beyond the recent
    index is not reread, so historical revision detection is bounded.
    """
    if type(batch) is not NativeFXBatch:
        raise ValueError("P054_NATIVE_BATCH_REQUIRED")
    symbol, interval, zone = (
        batch.symbol,batch.interval,batch.exchange_timezone)
    _scope(symbol, interval)
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValueError("P054_NATIVE_IANA_ZONE_INVALID") from exc
    if (batch.time_reference != _axis(interval)
            or batch.source != PROVIDER
            or batch.is_provider_native is not True
            or batch.vendor_calls_made_by_parser != 0
            or batch.google_drive_writes != 0
            or batch.confirmed_buy_sell_signals != 0
            or batch.broker_orders != 0
            or type(batch.closed_bars) is not tuple
            or len(batch.closed_bars) > MAX_BATCH_BARS):
        raise ValueError("P054_NATIVE_BATCH_SCOPE_INVALID")
    if previous is not None:
        check_native_manifest(previous,symbol=symbol,interval=interval,zone=zone)
    seen: set[str] = set()
    for bar in batch.closed_bars:
        _bar_valid(bar,symbol=symbol,interval=interval,zone=zone)
        if bar.native_open_label in seen:
            raise ValueError("P054_DUPLICATE_NATIVE_LABEL")
        seen.add(bar.native_open_label)
    if tuple(sorted(seen)) != tuple(bar.native_open_label for bar in batch.closed_bars):
        raise ValueError("P054_NATIVE_BATCH_NOT_SORTED")
    index = {
        x["label"]:x["sha256"]
        for x in previous["recent_native_bar_index"]
    } if previous is not None else {}
    for bar in batch.closed_bars:
        if bar.native_open_label in index and index[bar.native_open_label] != bar.sha256():
            raise ValueError("P054_HISTORICAL_NATIVE_REVISION_QUARANTINE")
    prior_last = previous["last_native_open_label"] if previous is not None else None
    new = tuple(bar for bar in batch.closed_bars
                if prior_last is None or bar.native_open_label > prior_last)
    if not new:
        return None
    combined = {**index}
    for bar in new:
        combined[bar.native_open_label] = bar.sha256()
    recent = [{"label":label,"sha256":sha}
              for label,sha in sorted(combined.items())[-RECENT_INDEX_LIMIT:]]
    parent = digest(previous) if previous is not None else None
    last_label = new[-1].native_open_label
    chunk: dict[str, Any] = {
        "schema":SCHEMA,"symbol":symbol,"interval":interval,
        "exchange_timezone":zone,"time_reference":_axis(interval),
        "source":PROVIDER,"source_side":"MID","provider_native":True,
        "parent_manifest_sha256":parent,
        "bars":[asdict(b) for b in new],
        "approved_numeric_signals":False,"broker_orders":0,
    }
    chunk_sha = digest(chunk)
    chunk_name = _name("chunk",symbol,interval,last_label,chunk_sha)
    manifest: dict[str, Any] = {
        "schema":SCHEMA,"symbol":symbol,"interval":interval,
        "exchange_timezone":zone,"time_reference":_axis(interval),
        "source":PROVIDER,"source_side":"MID","provider_native":True,
        "parent_manifest_sha256":parent,
        "chunk_name":chunk_name,"chunk_sha256":chunk_sha,
        "last_native_open_label":last_label,
        "batch_count":1 if previous is None else previous["batch_count"]+1,
        "total_closed_native_bars":len(new) if previous is None else
            previous["total_closed_native_bars"]+len(new),
        "recent_native_bar_index":recent,
        "approved_numeric_signals":False,"broker_orders":0,
    }
    check_native_manifest(manifest,symbol=symbol,interval=interval,zone=zone)
    manifest_sha = digest(manifest)
    return NativeSealedPlan(
        symbol=symbol,interval=interval,chunk_name=chunk_name,
        chunk_sha256=chunk_sha,chunk=chunk,
        manifest_name=_name("manifest",symbol,interval,last_label,manifest_sha),
        manifest_sha256=manifest_sha,manifest=manifest,
        newly_closed_bars=len(new),
    )


def verify_native_sealed(
    plan: NativeSealedPlan, *, previous: dict[str, Any] | None,
) -> None:
    """Pure full canonical recomputation of an in-memory candidate pair."""
    if type(plan) is not NativeSealedPlan:
        raise ValueError("P054_PLAN_TYPE_REQUIRED")
    symbol,interval = plan.symbol,plan.interval
    chunk,manifest = plan.chunk,plan.manifest
    if (type(chunk) is not dict or type(manifest) is not dict
            or type(chunk.get("bars")) is not list
            or not 1 <= len(chunk["bars"]) <= MAX_BATCH_BARS
            or not all(type(row) is dict for row in chunk["bars"])
            or not _sha(plan.chunk_sha256)
            or not _sha(plan.manifest_sha256)):
        raise ValueError("P054_INVALID_SEALED_PAIR_SHAPE")
    try:
        native = NativeFXBatch(
            symbol=symbol,interval=interval,
            exchange_timezone=manifest["exchange_timezone"],
            time_reference=manifest["time_reference"],
            closed_bars=tuple(NativeFXBar(**row) for row in chunk["bars"]),
            incomplete_excluded=0,
        )
    except (TypeError, KeyError) as exc:
        raise ValueError("P054_SEALED_BAR_PARSE_FAILED") from exc
    rebuilt = plan_native_sealed(native,previous=previous)
    if (rebuilt is None or rebuilt.chunk != chunk
            or rebuilt.manifest != manifest
            or rebuilt.chunk_name != plan.chunk_name
            or rebuilt.manifest_name != plan.manifest_name
            or rebuilt.chunk_sha256 != plan.chunk_sha256
            or rebuilt.manifest_sha256 != plan.manifest_sha256
            or plan.newly_closed_bars != rebuilt.newly_closed_bars
            or plan.provider_requests_performed != 0
            or plan.drive_writes_performed != 0
            or plan.broker_orders != 0):
        raise ValueError("P054_IMMUTABLE_NATIVE_PAIR_INCONSISTENT")
