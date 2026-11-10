"""A04/P0.45 Twelve Data M5 UTC CLOSED-MID cache: pure, offline contracts.

The Forex original 1:1 model is frozen and untouched. MID is non-executable.
Never infer authenticated source strategy numeric approvals from valid cache.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import re
from typing import Any

VERSION = "MFX_A04_P45_TD_M5_DRIVE_INCREMENTAL_V1"
PROVIDER = "TWELVE_DATA_COMPOSITE_MID"
SYMBOL = "EUR/USD"
INTERVAL = "5min"
TF = timedelta(minutes=5)
BAR_PATTERN = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")


@dataclass(frozen=True, slots=True)
class ClosedM5Bar:
    start_utc: str
    open: str
    high: str
    low: str
    close: str

    def digest(self) -> str:
        return digest(asdict(self))


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: object) -> str:
    return sha256(canonical(value)).hexdigest()


def _price(value: object, name: str) -> Decimal:
    if type(value) is not str:
        raise ValueError("P045_PRICE_MUST_BE_STRING:" + name)
    try:
        result = Decimal(value)
    except Exception as exc:
        raise ValueError("P045_PRICE_NOT_DECIMAL:" + name) from exc
    if not result.is_finite() or result <= 0:
        raise ValueError("P045_PRICE_NOT_FINITE_POSITIVE:" + name)
    return result


def _datetime(value: str) -> datetime:
    if not isinstance(value, str) or not BAR_PATTERN.fullmatch(value):
        raise ValueError("P045_UTC_BAR_TIMESTAMP_FORMAT")
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc,
    )
    if parsed.second or parsed.microsecond or parsed.minute % 5:
        raise ValueError("P045_M5_NOT_UTC_ALIGNED")
    return parsed


def parse_closed_utc_m5(
    payload: object, *, now_utc: datetime,
) -> tuple[ClosedM5Bar, ...]:
    """Accept only an explicitly timezone=UTC REST response.

    The caller MUST request timezone=UTC, because Twelve Data Forex otherwise
    defaults to Australia/Sydney. A raw connector table without timezone
    evidence is NOT eligible to call this parser.
    """
    if (not isinstance(now_utc, datetime)
            or now_utc.tzinfo is None
            or now_utc.utcoffset() != timedelta(0)):
        raise ValueError("P045_EXACT_UTC_NOW_REQUIRED")
    if not isinstance(payload, dict) or payload.get("status") == "error":
        raise ValueError("P045_VENDOR_ERROR_OR_INVALID_PAYLOAD")
    meta, values = payload.get("meta"), payload.get("values")
    if (not isinstance(meta, dict) or meta.get("symbol") != SYMBOL
            or meta.get("interval") != INTERVAL
            or not isinstance(values, list) or not values):
        raise ValueError("P045_VENDOR_SYMBOL_TF_OR_VALUES_MISMATCH")
    if meta.get("type") not in ("Physical Currency", "Forex", None):
        raise ValueError("P045_NON_FOREX_SOURCE")
    # meta.exchange_timezone describes the exchange, NOT necessarily the
    # caller-selected output timezone. The network client pins timezone=UTC.
    bars: list[ClosedM5Bar] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, dict):
            raise ValueError("P045_TYPED_OHLC_REQUIRED")
        start_text = raw.get("datetime")
        if type(start_text) is not str:
            raise ValueError("P045_UTC_BAR_TIMESTAMP_MUST_BE_STRING")
        start = _datetime(start_text)
        if start_text in seen:
            raise ValueError("P045_DUPLICATE_VENDOR_BAR")
        seen.add(start_text)
        # Vendor's newest entry may be still forming; exclude rather than
        # storing/inferencing it. Require 15 seconds bar-close grace.
        if start + TF > now_utc - timedelta(seconds=15):
            continue
        o, h, low, c = (_price(raw.get(k), k)
                         for k in ("open", "high", "low", "close"))
        if low > min(o, c) or h < max(o, c) or h < low:
            raise ValueError("P045_INVALID_OHLC_ORDER")
        bars.append(ClosedM5Bar(
            start_utc=start.isoformat(),
            open=str(o), high=str(h), low=str(low), close=str(c),
        ))
    bars.sort(key=lambda x: x.start_utc)
    return tuple(bars)


def initial_manifest(now_utc: datetime) -> dict[str, Any]:
    if now_utc.tzinfo is None or now_utc.utcoffset() != timedelta(0):
        raise ValueError("P045_EXACT_UTC_NOW_REQUIRED")
    return {
        "schema": VERSION, "source": PROVIDER, "symbol": SYMBOL,
        "interval": INTERVAL, "side": "MID", "timezone": "UTC",
        "last_start_utc": None, "recent_bars": [],
        "last_poll_slot_utc": None, "credit_day_utc": now_utc.date().isoformat(),
        "credits_reserved_today": 0,
        "total_closed_bars_archived": 0,
        "total_chunks": 0, "last_chunk_sha256": None,
        "previous_manifest_sha256": None,
        "may_confirm_user_buy_sell": False, "broker_orders": 0,
    }


def check_manifest(m: object) -> dict[str, Any]:
    if not isinstance(m, dict):
        raise ValueError("P045_MANIFEST_MAPPING_REQUIRED")
    expected = initial_manifest(datetime(2026, 11, 10, tzinfo=timezone.utc))
    if set(m) != set(expected):
        raise ValueError("P045_MANIFEST_EXACT_SCHEMA")
    for k in ("schema", "source", "symbol", "interval", "side", "timezone"):
        if m.get(k) != expected[k]:
            raise ValueError("P045_MANIFEST_SOURCE_OR_SCHEMA_DRIFT:" + k)
    if m.get("may_confirm_user_buy_sell") is not False or m.get("broker_orders") != 0:
        raise ValueError("P045_NO_TRADE_OR_SOURCE_APPROVAL_PROMOTION")
    recent = m.get("recent_bars")
    if (not isinstance(recent, list) or len(recent) > 120
            or any(not isinstance(x, dict) or set(x) != {"start", "sha256"}
                   or not isinstance(x["start"], str)
                   or not isinstance(x["sha256"], str)
                   or re.fullmatch("[a-f0-9]{64}", x["sha256"]) is None
                   for x in recent)):
        raise ValueError("P045_INVALID_RECENT_BAR_INDEX")
    stamps = [x["start"] for x in recent]
    if stamps != sorted(set(stamps)):
        raise ValueError("P045_DUPLICATE_OR_REORDERED_RECENT_INDEX")
    if (not isinstance(m.get("credits_reserved_today"), int)
            or isinstance(m.get("credits_reserved_today"), bool)
            or m["credits_reserved_today"] < 0
            or any(type(m.get(k)) is not int or m[k] < 0
                   for k in ("total_closed_bars_archived", "total_chunks"))):
        raise ValueError("P045_INVALID_QUOTA_OR_ARCHIVE_COUNT")
    if (not isinstance(m.get("credit_day_utc"), str)
            or not isinstance(m.get("last_start_utc"), (str, type(None)))
            or not isinstance(m.get("last_poll_slot_utc"), (str, type(None)))):
        raise ValueError("P045_INVALID_MANIFEST_CLOCK")
    if m["last_start_utc"] != (stamps[-1] if stamps else None) and m["total_closed_bars_archived"] <= 120:
        raise ValueError("P045_LAST_BAR_INDEX_MISMATCH")
    for key in ("last_chunk_sha256", "previous_manifest_sha256"):
        val = m.get(key)
        if val is not None and (type(val) is not str
                                or re.fullmatch("[a-f0-9]{64}", val) is None):
            raise ValueError("P045_MANIFEST_LINK_SHA_INVALID")
    return m


@dataclass(frozen=True, slots=True)
class DeltaDecision:
    new_bars: tuple[ClosedM5Bar, ...]
    previous_latest: str | None
    newest: str | None
    gaps_detected: int
    no_change: bool


def compute_delta(
    prior: object, observed: tuple[ClosedM5Bar, ...],
) -> DeltaDecision:
    m = check_manifest(prior)
    if not isinstance(observed, tuple) or any(
            not isinstance(x, ClosedM5Bar) for x in observed):
        raise ValueError("P045_BOUNDED_TYPED_CLOSED_BAR_TUPLE")
    if len(observed) > 500:
        raise ValueError("P045_MAX_FETCH_BARS_500")
    if tuple(sorted({x.start_utc for x in observed})) != tuple(
            x.start_utc for x in observed):
        raise ValueError("P045_DUPLICATE_OR_UNSORTED_OBSERVATIONS")
    prior_index = {x["start"]: x["sha256"] for x in m["recent_bars"]}
    last = m["last_start_utc"]
    for bar in observed:
        _datetime(bar.start_utc.replace("T", " ").replace("+00:00", ""))
        # Recompute and reject edited historical overlap, rather than silently
        # overriding previous values. Archive reprocessing needs review.
        if bar.start_utc in prior_index and bar.digest() != prior_index[bar.start_utc]:
            raise ValueError("P045_HISTORICAL_CLOSED_BAR_REVISION_QUARANTINE")
        if last is not None and bar.start_utc <= last and bar.start_utc not in prior_index:
            raise ValueError("P045_OLDER_THAN_RECENT_INDEX_REQUIRES_AUDIT")
    new = tuple(b for b in observed if last is None or b.start_utc > last)
    gaps = 0
    previous = last
    for b in new:
        if previous is not None:
            delta_seconds = (
                datetime.fromisoformat(b.start_utc) -
                datetime.fromisoformat(previous)
            ).total_seconds()
            if delta_seconds != 300:
                gaps += 1  # weekend/provider gaps are explicit, not fabricated.
        previous = b.start_utc
    return DeltaDecision(
        new_bars=new, previous_latest=last,
        newest=new[-1].start_utc if new else last,
        gaps_detected=gaps, no_change=not new,
    )


def next_manifest(
    prior: dict[str, Any], decision: DeltaDecision, *,
    now_utc: datetime,
    new_chunk_sha256: str | None,
) -> dict[str, Any]:
    old = check_manifest(prior)
    if now_utc.tzinfo is None or now_utc.utcoffset() != timedelta(0):
        raise ValueError("P045_EXACT_UTC_NOW_REQUIRED")
    if bool(decision.new_bars) != bool(new_chunk_sha256):
        raise ValueError("P045_CHUNK_REQUIRED_ONLY_FOR_NEW_BARS")
    today = now_utc.date().isoformat()
    recent = {x["start"]: x["sha256"] for x in old["recent_bars"]}
    for b in decision.new_bars:
        recent[b.start_utc] = b.digest()
    items = [{"start": k, "sha256": v}
             for k, v in sorted(recent.items())[-120:]]
    return check_manifest({
        **old,
        "recent_bars": items, "last_start_utc": decision.newest,
        "last_poll_slot_utc": now_utc.replace(
            minute=now_utc.minute//5*5, second=0, microsecond=0,
        ).isoformat(),
        "credit_day_utc": today,
        "credits_reserved_today": (
            old["credits_reserved_today"]+1
            if today == old["credit_day_utc"] else 1
        ),
        "total_closed_bars_archived":
            old["total_closed_bars_archived"] + len(decision.new_bars),
        "total_chunks": old["total_chunks"] + int(bool(decision.new_bars)),
        "last_chunk_sha256": new_chunk_sha256 or old["last_chunk_sha256"],
        "previous_manifest_sha256": digest(old),
    })


def content_chunk(decision: DeltaDecision, now_utc: datetime) -> dict[str, Any]:
    if not decision.new_bars:
        raise ValueError("P045_NO_EMPTY_RAW_CHUNK")
    return {
        "schema": VERSION, "source": PROVIDER,
        "symbol": SYMBOL, "interval": INTERVAL, "side": "MID",
        "timezone": "UTC",
        "gaps_from_previous": decision.gaps_detected,
        "bars": [{"start_utc": b.start_utc,
                  "open": b.open, "high": b.high,
                  "low": b.low, "close": b.close}
                 for b in decision.new_bars],
        "confirmed_user_signals": 0, "may_trade": False,
    }
