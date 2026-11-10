"""A04/P0.46-B2: SHA-sealed staged WARM UTC-day packing and promotion.

No provider calls, no arbitrary deletion/retention, no market signals or broker.
Hourly B1 originals remain immutable even after verified warm promotion.
The Drive adapter is single-writer/cooperative, NOT multi-object atomic CAS.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from mfx_cache.td_m5_codec import ClosedM5Bar, PROVIDER, SYMBOL, digest
from mfx_cache.v2_batch_commit import (
    PrivateObjectStore, _validate_chunk, _validate_manifest,
)
from mfx_cache.v2_engine import derive_intraday, validate_m5

VERSION = "MFX_A04_P46_B2_WARM_DAY_PROMOTION_V1"
WARM_PREFIX = "MFX_TD_EURUSD_M5_V2_warm_"
PROMOTION_PREFIX = "MFX_TD_EURUSD_M5_V2_promotion_"
MAX_SOURCE_MANIFESTS = 12000
MAX_HOURS_IN_DAY = 24
MIN_SOURCE_HOURS = 2


@dataclass(frozen=True, slots=True)
class WarmPlan:
    day_utc: str
    warm_name: str
    warm: dict[str, Any]
    warm_sha256: str
    promotion_name: str
    promotion: dict[str, Any]
    source_hour_count: int
    missing_hour_count: int


@dataclass(frozen=True, slots=True)
class WarmResult:
    status: str
    day_utc: str | None
    source_hour_count: int
    missing_hour_count: int
    expected_new_drive_objects: int
    recovered_unpromoted_warm: bool
    original_parent_objects_deleted: int = 0
    actual_vendor_api_calls: int = 0
    approved_source_numeric_signals: int = 0
    broker_orders: int = 0


def _utc(value: datetime) -> None:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P046_B2_EXPLICIT_UTC_NOW_REQUIRED")


def _target_day(now_utc: datetime) -> str | None:
    _utc(now_utc)
    if now_utc.hour < 1:
        return None
    return (now_utc - timedelta(days=1)).date().isoformat()


def _name(kind: str, day: str, sha: str) -> str:
    if kind not in ("warm", "promotion"):
        raise ValueError("P046_B2_UNKNOWN_OBJECT_KIND")
    if len(day) != 10 or day[4] != "-" or day[7] != "-":
        raise ValueError("P046_B2_INVALID_UTC_DAY")
    stamp = datetime.strptime(day, "%Y-%m-%d").strftime("%Y%m%d")
    prefix = WARM_PREFIX if kind == "warm" else PROMOTION_PREFIX
    return prefix + stamp + "_" + sha + ".json"


def _checked_day_name(kind: str, name: str, body: dict[str, Any]) -> str:
    day_value = body.get("day_utc") if type(body) is dict else None
    if (type(body) is not dict or body.get("schema") != VERSION
            or not isinstance(day_value, str)):
        raise ValueError("P046_B2_INVALID_OBJECT_SCHEMA")
    day = day_value
    if name != _name(kind, day, digest(body)):
        raise ValueError("P046_B2_CONTENT_HASH_NAME_MISMATCH")
    if (body.get("source") != PROVIDER or body.get("symbol") != SYMBOL
            or body.get("interval") != "M5"
            or body.get("side") != "MID" or body.get("timezone") != "UTC"
            or body.get("source_numeric_approved") is not False
            or type(body.get("broker_orders")) is not int
            or body["broker_orders"] != 0):
        raise ValueError("P046_B2_SOURCE_SCOPE_OR_SIGNAL_PROMOTION")
    return day


def _all_verified_source(
    store: PrivateObjectStore, *, now_utc: datetime,
) -> tuple[tuple[str, dict[str, Any], dict[str, Any]], ...]:
    """Read full B1 manifest history; every linked chunk must be verifiable.

    This is intentionally bounded/fail-closed; do NOT imply scalable unlimited
    20-pair history without an indexed manifest/partition rework.
    """
    names = tuple(sorted(store.list_names("manifest")))
    if len(names) > MAX_SOURCE_MANIFESTS or len(names) != len(set(names)):
        raise ValueError("P046_B2_UNBOUNDED_OR_DUPLICATE_SOURCE_MANIFESTS")
    observed: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    prior: dict[str, Any] | None = None
    prior_hour: str | None = None
    for name in names:
        m = store.read("manifest", name)
        hour = _validate_manifest(name, m)
        if prior_hour is not None and hour <= prior_hour:
            raise ValueError("P046_B2_FORK_OR_OUT_OF_ORDER_SOURCE_HOURS")
        if (m["parent_manifest_sha256"] !=
                (digest(prior) if prior is not None else None)
                or m["total_batches"] != len(observed) + 1):
            raise ValueError("P046_B2_BROKEN_FULL_SOURCE_MANIFEST_CHAIN")
        c = store.read("chunk", m["chunk_name"])
        _validate_chunk(m["chunk_name"], c)
        if (digest(c) != m["chunk_sha256"]
                or c["hour_utc"] != hour
                or c["parent_manifest_sha256"] != m["parent_manifest_sha256"]):
            raise ValueError("P046_B2_SOURCE_MANIFEST_CHUNK_LINK_FAILURE")
        raw = c["bars"]
        if (type(raw) is not list or len(raw) != 12
                or any(type(b) is not dict or set(b) != {
                    "start_utc", "open", "high", "low", "close",
                } for b in raw)):
            raise ValueError("P046_B2_BAD_CLOSED_SOURCE_BAR_SHAPE")
        bars = tuple(ClosedM5Bar(**row) for row in raw)
        validate_m5(bars, asof_utc=now_utc)
        expected = tuple((datetime.fromisoformat(hour) +
                          timedelta(minutes=5*i)).isoformat()
                         for i in range(12))
        if tuple(b.start_utc for b in bars) != expected:
            raise ValueError("P046_B2_INCOMPLETE_SOURCE_HOUR")
        for frame, size in (("M15", 4), ("M30", 2), ("H1", 1)):
            result = derive_intraday(bars, frame, asof_utc=now_utc)
            if (len(result.candles) != size
                    or [asdict(x) for x in result.candles] !=
                    c["derived"].get(frame)):
                raise ValueError("P046_B2_STALE_OR_FORGED_DERIVED_LINEAGE")
        observed.append((name, m, c))
        prior, prior_hour = m, hour
    return tuple(observed)


def _day_source(
    verified: tuple[tuple[str, dict[str, Any], dict[str, Any]], ...],
    day: str,
) -> tuple[tuple[str, dict[str, Any], dict[str, Any]], ...]:
    return tuple(row for row in verified if row[1]["hour_utc"][:10] == day)


def _plan_day(
    verified: tuple[tuple[str, dict[str, Any], dict[str, Any]], ...],
    *, day: str, now_utc: datetime,
) -> WarmPlan | None:
    rows = _day_source(verified, day)
    if not MIN_SOURCE_HOURS <= len(rows) <= MAX_HOURS_IN_DAY:
        return None
    # Each source manifest points to the exact B1 SHA-sealed hour.
    source_refs = [{
        "hour_utc": m["hour_utc"],
        "manifest_name": name, "manifest_sha256": digest(m),
        "chunk_name": m["chunk_name"],
        "chunk_sha256": m["chunk_sha256"],
    } for name, m, _ in rows]
    hours = [x["hour_utc"] for x in source_refs]
    if hours != sorted(set(hours)):
        raise ValueError("P046_B2_DUPLICATE_DAY_HOURS")
    missing_hours = tuple(
        (datetime.strptime(day, "%Y-%m-%d").replace(
            tzinfo=timezone.utc) + timedelta(hours=i)).isoformat()
        for i in range(MAX_HOURS_IN_DAY)
        if (datetime.strptime(day, "%Y-%m-%d").replace(
            tzinfo=timezone.utc) + timedelta(hours=i)).isoformat()
        not in hours
    )
    raw_bars: list[dict[str, str]] = []
    frames: dict[str, list[dict[str, Any]]] = {
        "M15": [], "M30": [], "H1": [],
    }
    for _, _, c in rows:
        raw_bars.extend(c["bars"])
        for frame in frames:
            frames[frame].extend(c["derived"][frame])
    warm: dict[str, Any] = {
        "schema": VERSION, "day_utc": day,
        "source": PROVIDER, "symbol": SYMBOL,
        "interval": "M5", "side": "MID", "timezone": "UTC",
        "source_manifest_refs": source_refs,
        "source_set_sha256": digest(source_refs),
        "closed_m5_bars": raw_bars,
        "derived": frames,
        "observed_utc_hours": len(rows),
        "missing_utc_hour_starts": list(missing_hours),
        "coverage": ("OBSERVED_24_UTC_HOURS_NOT_LICENSED_SESSION_PROOF"
                     if not missing_hours else
                     "PARTIAL_UTC_DAY_UNKNOWN_SESSION_OR_GAPS"),
        "source_asof_or_bidask_proven": False,
        "source_numeric_approved": False,
        "broker_orders": 0,
    }
    ws = digest(warm)
    wn = _name("warm", day, ws)
    receipt: dict[str, Any] = {
        "schema": VERSION, "day_utc": day,
        "source": PROVIDER, "symbol": SYMBOL,
        "interval": "M5", "side": "MID", "timezone": "UTC",
        "warm_name": wn, "warm_sha256": ws,
        "source_set_sha256": digest(source_refs),
        "observed_utc_hours": len(rows),
        "missing_utc_hours": len(missing_hours),
        "promotion_state": "WARM_VERIFIED_READBACK_NO_PARENT_DELETION",
        "source_numeric_approved": False, "broker_orders": 0,
    }
    pn = _name("promotion", day, digest(receipt))
    _checked_day_name("warm", wn, warm)
    _checked_day_name("promotion", pn, receipt)
    return WarmPlan(
        day_utc=day, warm_name=wn, warm=warm, warm_sha256=ws,
        promotion_name=pn, promotion=receipt,
        source_hour_count=len(rows), missing_hour_count=len(missing_hours),
    )


def _target_named(
    store: PrivateObjectStore, kind: str, day: str,
) -> tuple[str, ...]:
    names = store.list_names(kind)
    if len(names) > MAX_SOURCE_MANIFESTS or len(set(names)) != len(names):
        raise ValueError("P046_B2_DUPLICATE_OR_UNBOUNDED_WARM_OBJECTS")
    prefix = WARM_PREFIX if kind == "warm" else PROMOTION_PREFIX
    if any(not x.startswith(prefix) for x in names):
        raise ValueError("P046_B2_UNEXPECTED_WARM_BUCKET_FILENAME")
    stamp = day.replace("-", "")
    return tuple(x for x in names if x.startswith(prefix+stamp+"_"))


def promote_completed_utc_day(
    store: PrivateObjectStore, *, now_utc: datetime,
) -> WarmResult:
    """Idempotent additive warm object + promotion receipt with readback.

    No deletion. No unsafe claims of atomic Drive CAS or actual storage saving.
    Reject changes to full historic B1 manifest chain and selected day.
    """
    day = _target_day(now_utc)
    if day is None:
        return WarmResult("NOT_DUE_BEFORE_0100_UTC",None,0,0,0,False)
    verified = _all_verified_source(store, now_utc=now_utc)
    plan = _plan_day(verified, day=day, now_utc=now_utc)
    if plan is None:
        return WarmResult("INSUFFICIENT_CLOSED_SOURCE_HOURS",day,0,0,0,False)
    known_promotions = _target_named(store, "promotion", day)
    if len(known_promotions) > 1:
        raise ValueError("P046_B2_CONFLICTING_DAY_PROMOTIONS")
    if known_promotions:
        name = known_promotions[0]
        old = store.read("promotion", name)
        _checked_day_name("promotion", name, old)
        if old != plan.promotion:
            raise ValueError("P046_B2_PROMOTED_DAY_SOURCE_REVISION_CONFLICT")
        current_warm = store.read("warm", plan.warm_name)
        _checked_day_name("warm", plan.warm_name, current_warm)
        if current_warm != plan.warm:
            raise ValueError("P046_B2_PROMOTED_WARM_OBJECT_CHANGED")
        return WarmResult("ALREADY_PROMOTED",day,plan.source_hour_count,
                          plan.missing_hour_count,0,False)
    candidates = _target_named(store, "warm", day)
    if len(candidates) > 1:
        raise ValueError("P046_B2_COMPETING_WARM_OBJECTS")
    recovered = bool(candidates)
    if recovered:
        old_name = candidates[0]
        old_warm = store.read("warm", old_name)
        _checked_day_name("warm", old_name, old_warm)
        if old_name != plan.warm_name or old_warm != plan.warm:
            raise ValueError("P046_B2_ORPHAN_WARM_SOURCE_CHANGED")
    else:
        store.put_if_absent("warm",plan.warm_name,plan.warm)
    fetched = store.read("warm",plan.warm_name)
    _checked_day_name("warm",plan.warm_name,fetched)
    if fetched != plan.warm:
        raise ValueError("P046_B2_WARM_READBACK_MISMATCH")
    # Revalidate all original source manifests/chunks before promotion,
    # preventing cooperative stale commits after external source mutations.
    reread = _all_verified_source(store,now_utc=now_utc)
    if _day_source(reread,day) != _day_source(verified,day):
        raise ValueError("P046_B2_DAY_SOURCES_CHANGED_PREPROMOTION")
    if _target_named(store,"promotion",day):
        raise ValueError("P046_B2_CONCURRENT_PROMOTION_DETECTED")
    store.put_if_absent("promotion",plan.promotion_name,plan.promotion)
    stamped = store.read("promotion",plan.promotion_name)
    _checked_day_name("promotion",plan.promotion_name,stamped)
    if stamped != plan.promotion:
        raise ValueError("P046_B2_PROMOTION_READBACK_MISMATCH")
    if _target_named(store,"promotion",day) != (plan.promotion_name,):
        raise ValueError("P046_B2_FORKED_DAY_AFTER_PROMOTION")
    return WarmResult(
        status=("RECOVERED_WARM_AND_PROMOTED" if recovered else
                "WARM_PROMOTED"),
        day_utc=day,source_hour_count=plan.source_hour_count,
        missing_hour_count=plan.missing_hour_count,
        expected_new_drive_objects=1 if recovered else 2,
        recovered_unpromoted_warm=recovered,
    )
