"""MFX A04/P0.46-B3 — CLOSED M5 HOT overlay, bounded and fail-closed.

Transient single-object Cloud HOT, not canonical append-only B1 hourly
archive. No live/approved Forex detector, no BID/ASK, no broker orders.
A mutable Drive object avoids per-poll NEW file proliferation but requires
independent readback; it does NOT provide vendor-signed revisions or CAS.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol
from dataclasses import asdict

from mfx_cache.td_m5_codec import ClosedM5Bar, PROVIDER, SYMBOL, digest
from mfx_cache.v2_engine import validate_m5

HOT_VERSION = "MFX_A04_P46_B3_HOT_OVERLAY_V1"
HOT_NAME = "MFX_TD_EURUSD_M5_V3_HOT_LATEST.json"
MAX_HOT_CANDLES = 24
MAX_VENDOR_WINDOW = 120
MAX_HOT_AGE_SECONDS = 390  # five minutes + 90 seconds safety; NOT freshness SLA
FIVE_MINUTES = timedelta(minutes=5)
GRACE = timedelta(seconds=15)


@dataclass(frozen=True, slots=True)
class HotFreshness:
    status: str
    age_seconds: int | None
    recent_closed_m5: int
    contiguous_recent: bool
    research_data_usable: bool
    live_buy_sell_authorized: bool = False
    broker_orders_authorized: bool = False


@dataclass(frozen=True, slots=True)
class HotUpdate:
    status: str
    new_state: dict[str, Any] | None
    new_closed_m5: int
    provider_requests: int = 0
    expected_drive_object_creates: int = 0
    expected_drive_object_updates: int = 0
    live_signals: int = 0
    broker_orders: int = 0


def _utc(dt: datetime) -> None:
    if (type(dt) is not datetime or dt.tzinfo is None
            or dt.utcoffset() != timedelta(0)):
        raise ValueError("P046_B3_EXPLICIT_UTC_REQUIRED")


def _stamp(s: str) -> datetime:
    if type(s) is not str or not s.endswith("+00:00"):
        raise ValueError("P046_B3_EXPLICIT_ISO_UTC_REQUIRED")
    try:
        value = datetime.fromisoformat(s)
    except ValueError as exc:
        raise ValueError("P046_B3_INVALID_UTC_CLOCK") from exc
    _utc(value)
    if value.second or value.microsecond or value.minute % 5:
        raise ValueError("P046_B3_NOT_ALIGNED_M5")
    return value


def _poll_slot(now: datetime) -> str:
    return now.replace(
        minute=(now.minute//5)*5, second=0, microsecond=0,
    ).isoformat()


def _bars(records: list[dict[str, str]]) -> tuple[ClosedM5Bar, ...]:
    return tuple(ClosedM5Bar(
        start_utc=x["start_utc"], open=x["open"], high=x["high"],
        low=x["low"], close=x["close"],
    ) for x in records)


def validate_hot(state: object, *, now_utc: datetime) -> dict[str, Any]:
    """Validate current HOT in full before trusting any read/overwrite."""
    _utc(now_utc)
    if type(state) is not dict:
        raise ValueError("P046_B3_HOT_STATE_DICT_REQUIRED")
    m = state
    if set(m) != {
        "schema", "provider", "symbol", "interval", "side", "timezone",
        "generation", "previous_hot_sha256", "first_created_utc",
        "last_updated_utc", "last_poll_slot_utc",
        "latest_closed_start_utc", "recent_bars", "recent_index_sha256",
        "source_gap_unverified", "source_revision_history_verified",
        "licensed_quote_retention_verified", "approved_original_numeric_signals",
        "broker_orders",
    }:
        raise ValueError("P046_B3_EXACT_HOT_SCHEMA_REQUIRED")
    if (m["schema"] != HOT_VERSION
            or m["provider"] != PROVIDER or m["symbol"] != SYMBOL
            or m["interval"] != "M5" or m["side"] != "MID"
            or m["timezone"] != "UTC"
            or m["source_revision_history_verified"] is not False
            or m["licensed_quote_retention_verified"] is not False
            or m["approved_original_numeric_signals"] is not False
            or type(m["broker_orders"]) is not int
            or m["broker_orders"] != 0):
        raise ValueError("P046_B3_HOT_PROVENANCE_OR_TRADE_PROMOTION")
    if type(m["generation"]) is not int or not 1 <= m["generation"] <= 10000000:
        raise ValueError("P046_B3_INVALID_HOT_GENERATION")
    p_sha = m["previous_hot_sha256"]
    if p_sha is not None and (type(p_sha) is not str or len(p_sha) != 64
                              or any(c not in "0123456789abcdef" for c in p_sha)):
        raise ValueError("P046_B3_INVALID_PREDECESSOR_SHA")
    if (m["generation"] == 1) != (p_sha is None):
        raise ValueError("P046_B3_HOT_GENERATION_PREDECESSOR_MISMATCH")
    created = m.get("first_created_utc")
    updated = m.get("last_updated_utc")
    if type(created) is not str or type(updated) is not str:
        raise ValueError("P046_B3_INVALID_UPDATE_CLOCK")
    try:
        first = datetime.fromisoformat(created)
        last = datetime.fromisoformat(updated)
    except ValueError as exc:
        raise ValueError("P046_B3_INVALID_UPDATE_CLOCK") from exc
    _utc(first)
    _utc(last)
    if first > last or last > now_utc:
        raise ValueError("P046_B3_FUTURE_OR_REVERSED_UPDATE_CLOCK")
    if (m["last_poll_slot_utc"] != _poll_slot(last)
            or type(m["source_gap_unverified"]) is not bool):
        raise ValueError("P046_B3_INVALID_POLL_OR_GAP_STATE")
    records = m["recent_bars"]
    if type(records) is not list or not 1 <= len(records) <= MAX_HOT_CANDLES:
        raise ValueError("P046_B3_BOUNDED_HOT_WINDOW_REQUIRED")
    for row in records:
        if type(row) is not dict or set(row) != {
            "start_utc", "open", "high", "low", "close",
            "first_seen_utc", "bar_sha256",
        }:
            raise ValueError("P046_B3_INVALID_HOT_BAR_SHAPE")
        if any(type(row[k]) is not str for k in row):
            raise ValueError("P046_B3_INVALID_HOT_BAR_TYPE")
        bar = ClosedM5Bar(
            start_utc=row["start_utc"],open=row["open"],high=row["high"],
            low=row["low"],close=row["close"],
        )
        if digest(asdict(bar)) != row["bar_sha256"]:
            raise ValueError("P046_B3_HOT_BAR_FINGERPRINT_CHANGED")
        seen = datetime.fromisoformat(row["first_seen_utc"])
        _utc(seen)
        if (seen < _stamp(row["start_utc"]) + FIVE_MINUTES + GRACE
                or seen > last):
            raise ValueError("P046_B3_IMPOSSIBLE_FIRST_SEEN_TIME")
    normalized = _bars(records)
    validate_m5(normalized, asof_utc=now_utc)
    if (m["latest_closed_start_utc"] != normalized[-1].start_utc
            or m["recent_index_sha256"] != digest(records)):
        raise ValueError("P046_B3_HOT_WINDOW_INDEX_MISMATCH")
    return m


def freshness(state: object, *, now_utc: datetime) -> HotFreshness:
    m = validate_hot(state,now_utc=now_utc)
    rec = m["recent_bars"]
    end = _stamp(rec[-1]["start_utc"]) + FIVE_MINUTES
    age = int((now_utc-end).total_seconds())
    gaps = any(
        _stamp(b["start_utc"]) -
        _stamp(a["start_utc"]) != FIVE_MINUTES
        for a,b in zip(rec,rec[1:])
    )
    continuous = (not gaps and not m["source_gap_unverified"])
    if age > MAX_HOT_AGE_SECONDS:
        state_label = "STALE_CLOSED_M5_NOT_FRESH"
    elif not continuous:
        state_label = "UNKNOWN_SOURCE_SESSION_OR_MISSING_M5"
    elif len(rec) < 3:
        state_label = "INSUFFICIENT_RECENT_M5"
    else:
        state_label = "FRESH_RECENT_M5_RESEARCH_ONLY"
    return HotFreshness(
        status=state_label, age_seconds=age,
        recent_closed_m5=len(rec), contiguous_recent=continuous,
        research_data_usable=state_label=="FRESH_RECENT_M5_RESEARCH_ONLY",
    )


def plan_hot(
    prior: dict[str, Any] | None,
    observed: tuple[ClosedM5Bar, ...], *, now_utc: datetime,
) -> HotUpdate:
    """Produce bounded newest CLOSED M5 overlay; never writes Drive itself.

    Revisions or older-outside-index returns hard failure, never silent
    overwrite. A single immutable B1 hourly archive remains authoritative.
    """
    _utc(now_utc)
    if (type(observed) is not tuple or not 1 <= len(observed) <= MAX_VENDOR_WINDOW
            or any(type(x) is not ClosedM5Bar for x in observed)):
        raise ValueError("P046_B3_BOUNDED_VENDOR_WINDOW_REQUIRED")
    validate_m5(observed,asof_utc=now_utc)
    old: dict[str, Any] | None = (
        validate_hot(prior,now_utc=now_utc) if prior is not None else None
    )
    last: str | None = old["latest_closed_start_utc"] if old else None
    seen: dict[str, dict[str, str]] = {
        x["start_utc"]: x for x in old["recent_bars"]
    } if old else {}
    if old is not None:
        assert last is not None
        for b in observed:
            known = seen.get(b.start_utc)
            if known is not None and known["bar_sha256"] != digest(asdict(b)):
                raise ValueError("P046_B3_REVISED_CLOSED_M5_QUARANTINE")
            if b.start_utc <= last and known is None:
                raise ValueError("P046_B3_UNRECONCILED_HISTORICAL_M5_NEEDS_AUDIT")
        if not any(b.start_utc in seen for b in observed):
            raise ValueError("P046_B3_LOST_SOURCE_OVERLAP_FAIL_CLOSED")
    new_bars = tuple(
        b for b in observed if last is None or b.start_utc > last
    )
    if not new_bars:
        return HotUpdate("UNCHANGED_NO_DRIVE_WRITE",None,0)
    if old and _poll_slot(now_utc) <= old["last_poll_slot_utc"]:
        raise ValueError("P046_B3_NEW_CLOSE_IN_ALREADY_PERSISTED_SLOT")
    appended: list[dict[str, str]] = list(old["recent_bars"]) if old else []
    for bar in new_bars:
        appended.append({
            **asdict(bar),
            "first_seen_utc":now_utc.isoformat(),
            "bar_sha256":digest(asdict(bar)),
        })
    appended = appended[-MAX_HOT_CANDLES:]
    has_gap = any(
        _stamp(next_["start_utc"]) -
        _stamp(prev["start_utc"]) != FIVE_MINUTES
        for prev,next_ in zip(appended,appended[1:])
    )
    state: dict[str, Any] = {
        "schema":HOT_VERSION,"provider":PROVIDER,"symbol":SYMBOL,
        "interval":"M5","side":"MID","timezone":"UTC",
        "generation":1 if old is None else old["generation"]+1,
        "previous_hot_sha256":None if old is None else digest(old),
        "first_created_utc":now_utc.isoformat() if old is None
                              else old["first_created_utc"],
        "last_updated_utc":now_utc.isoformat(),
        "last_poll_slot_utc":_poll_slot(now_utc),
        "latest_closed_start_utc":appended[-1]["start_utc"],
        "recent_bars":appended,"recent_index_sha256":digest(appended),
        # Conservative: a previous unknown gap is not auto-forgotten merely
        # because the rolling window evicted old evidence.
        "source_gap_unverified": bool(
            has_gap or (old is not None and old["source_gap_unverified"])
        ),
        "source_revision_history_verified":False,
        "licensed_quote_retention_verified":False,
        "approved_original_numeric_signals":False,"broker_orders":0,
    }
    validate_hot(state,now_utc=now_utc)
    return HotUpdate(
        status="NEW_CLOSED_M5_HOT_OVERLAY",
        new_state=state,new_closed_m5=len(new_bars),
        expected_drive_object_creates=1 if old is None else 0,
        expected_drive_object_updates=0 if old is None else 1,
    )


class HotStore(Protocol):
    """Single authorized Cloud writer contract, injected for offline QA."""

    def load(self) -> dict[str, Any] | None: ...

    def write(
        self, *, expected: dict[str, Any] | None,
        replacement: dict[str, Any],
    ) -> None: ...


def commit_hot(
    store: HotStore, observed: tuple[ClosedM5Bar, ...], *,
    now_utc: datetime,
) -> HotUpdate:
    """Read/revalidate/write/readback; never performs network by itself.

    Cooperative GitHub concurrency only. External races/Drive update
    semantics are NOT a trusted compare-and-swap or immutable witness.
    """
    current = store.load()
    decision = plan_hot(current, observed, now_utc=now_utc)
    if decision.new_state is None:
        return decision
    if store.load() != current:
        raise ValueError("P046_B3_HOT_STATE_CHANGED_AFTER_PLAN")
    store.write(expected=current, replacement=decision.new_state)
    if store.load() != decision.new_state:
        raise ValueError("P046_B3_HOT_FINAL_READBACK_MISMATCH")
    return decision
