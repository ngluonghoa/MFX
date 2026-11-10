"""A04/P0.46-B1 — bounded, deterministic CLOSED M5 hourly Drive batch commits.

Source and derived M15/M30/H1 are data lineage, NOT approved Forex
numeric trade signals. Two-phase append-only object commit, verified
readback, orphan replay; Drive does not provide a multi-file atomic CAS.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from mfx_cache.td_m5_codec import (
    ClosedM5Bar, PROVIDER, SYMBOL, digest,
)
from mfx_cache.v2_engine import (
    derive_intraday, validate_m5,
)

VERSION = "MFX_A04_P46_B1_HOURLY_DRIVE_BATCH_V1"
CHUNK_PREFIX = "MFX_TD_EURUSD_M5_V2_chunk_"
MANIFEST_PREFIX = "MFX_TD_EURUSD_M5_V2_manifest_"
MAX_LIST = 12000
HOUR = timedelta(hours=1)


class PrivateObjectStore(Protocol):
    """A single authorized writer; no local disk or implicit OAuth."""
    def list_names(self, bucket: str) -> tuple[str, ...]: ...
    def read(self, bucket: str, name: str) -> dict[str, Any]: ...
    def put_if_absent(
        self, bucket: str, name: str, body: dict[str, Any],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class BatchPlan:
    hour_utc: str
    chunk_name: str
    chunk_sha256: str
    chunk: dict[str, Any]
    manifest_name: str
    manifest_sha256: str
    manifest: dict[str, Any]
    new_closed_m5: int = 12
    real_user_signals: int = 0
    broker_orders: int = 0


@dataclass(frozen=True, slots=True)
class BatchResult:
    status: str
    committed_hour_utc: str | None
    new_closed_m5: int
    drive_object_writes_expected: int
    recovered_orphan: bool
    actual_twelve_data_calls: int = 0
    real_user_signals: int = 0
    broker_orders: int = 0


def _name(kind: str, hour: str, sha: str) -> str:
    if kind not in ("chunk", "manifest"):
        raise ValueError("P046_B1_OBJECT_KIND")
    stamp = datetime.fromisoformat(hour).strftime("%Y%m%dT%H%MZ")
    prefix = CHUNK_PREFIX if kind == "chunk" else MANIFEST_PREFIX
    return prefix + stamp + "_" + sha + ".json"


def _check_record(kind: str, name: str, body: dict[str, Any]) -> str:
    if type(body) is not dict or body.get("schema") != VERSION:
        raise ValueError("P046_B1_STRICT_OBJECT_SCHEMA")
    hour = body.get("hour_utc")
    if type(hour) is not str:
        raise ValueError("P046_B1_HOUR_STRING_REQUIRED")
    try:
        parsed = datetime.fromisoformat(hour)
    except ValueError as exc:
        raise ValueError("P046_B1_INVALID_HOUR") from exc
    if (parsed.tzinfo is None or parsed.utcoffset() != timedelta(0)
            or not hour.endswith("+00:00") or parsed.minute != 0
            or parsed.second != 0 or parsed.microsecond != 0):
        raise ValueError("P046_B1_EXACT_UTC_HOUR_REQUIRED")
    if name != _name(kind, hour, digest(body)):
        raise ValueError("P046_B1_OBJECT_NAME_CONTENT_SHA_MISMATCH")
    if (body.get("provider") != PROVIDER or body.get("symbol") != SYMBOL
            or body.get("source_interval") != "M5"
            or body.get("source_side") != "MID"
            or body.get("timezone") != "UTC"
            or body.get("approved_original_numeric_signals") is not False
            or body.get("broker_orders") != 0):
        raise ValueError("P046_B1_PROVENANCE_OR_SIGNAL_PROMOTION")
    return hour


def _validate_manifest(name: str, m: dict[str, Any]) -> str:
    hour = _check_record("manifest", name, m)
    if (set(m) != {
        "schema", "hour_utc", "provider", "symbol", "source_interval",
        "source_side", "timezone", "parent_manifest_sha256",
        "chunk_sha256", "chunk_name", "total_batches",
        "total_closed_m5", "gap_prior_hours_unverified",
        "continuity_status", "approved_original_numeric_signals",
        "broker_orders",
    } or type(m["total_batches"]) is not int
            or type(m["total_closed_m5"]) is not int
            or m["total_batches"] < 1 or m["total_closed_m5"] != 12*m["total_batches"]
            or type(m["gap_prior_hours_unverified"]) is not int
            or m["gap_prior_hours_unverified"] < 0
            or m["continuity_status"] not in (
                "BOOTSTRAP_HISTORY_UNVERIFIED",
                "CONTIGUOUS_WITH_PRIOR_BATCH",
                "MISSING_PRIOR_HOURS_UNVERIFIED",
            )
            or not isinstance(m["chunk_sha256"], str)
            or not isinstance(m["chunk_name"], str)):
        raise ValueError("P046_B1_INVALID_MANIFEST_SHAPE")
    if m["chunk_name"] != _name("chunk", hour, m["chunk_sha256"]):
        raise ValueError("P046_B1_BAD_CHUNK_MANIFEST_REFERENCE")
    return hour


def _validate_chunk(name: str, c: dict[str, Any]) -> str:
    hour = _check_record("chunk", name, c)
    if (set(c) != {
        "schema", "hour_utc", "provider", "symbol", "source_interval",
        "source_side", "timezone", "parent_manifest_sha256",
        "bars", "derived", "approved_original_numeric_signals",
        "broker_orders",
    } or type(c["bars"]) is not list or len(c["bars"]) != 12
            or not isinstance(c["derived"], dict)
            or set(c["derived"]) != {"M15", "M30", "H1"}):
        raise ValueError("P046_B1_INVALID_CHUNK_SHAPE")
    return hour


def _last_manifest(
    store: PrivateObjectStore,
) -> tuple[str | None, dict[str, Any] | None]:
    names = store.list_names("manifest")
    if len(names) > MAX_LIST or len(set(names)) != len(names):
        raise ValueError("P046_B1_MANIFEST_LIST_AMBIGUOUS_OR_UNBOUNDED")
    if not names:
        return None, None
    # Name has sortable UTC hour. Any competing hashes for the same hour
    # are rejected, even if one was written later.
    sorted_names = sorted(names)
    hours = [n[len(MANIFEST_PREFIX):len(MANIFEST_PREFIX)+13]
             for n in sorted_names]
    if (any(not n.startswith(MANIFEST_PREFIX) for n in names)
            or len(set(hours)) != len(hours)):
        raise ValueError("P046_B1_FORKED_MANIFEST_HOUR")
    latest_name = sorted_names[-1]
    latest = store.read("manifest", latest_name)
    _validate_manifest(latest_name, latest)
    if len(sorted_names) >= 2:
        parent_name = sorted_names[-2]
        parent = store.read("manifest", parent_name)
        _validate_manifest(parent_name, parent)
        if (latest["parent_manifest_sha256"] != digest(parent)
                or latest["total_batches"] != parent["total_batches"]+1):
            raise ValueError("P046_B1_BROKEN_PARENT_MANIFEST_CHAIN")
    elif (latest["parent_manifest_sha256"] is not None
          or latest["total_batches"] != 1):
        raise ValueError("P046_B1_INVALID_ROOT_MANIFEST")
    # Never trust a manifest whose referenced immutable raw+derived
    # chunk has been lost, mutated, or detached from the parent link.
    referenced = latest["chunk_name"]
    archived_chunk = store.read("chunk", referenced)
    _validate_chunk(referenced, archived_chunk)
    if (digest(archived_chunk) != latest["chunk_sha256"]
            or archived_chunk["hour_utc"] != latest["hour_utc"]
            or (archived_chunk["parent_manifest_sha256"] !=
                latest["parent_manifest_sha256"])):
        raise ValueError("P046_B1_MANIFEST_OR_CHUNK_LINK_BROKEN")
    return latest_name, latest


def _make_plan(
    previous: dict[str, Any] | None,
    *, hour_utc: str, bars: tuple[ClosedM5Bar, ...], now_utc: datetime,
) -> BatchPlan:
    source_hour = datetime.fromisoformat(hour_utc)
    expected = tuple((source_hour + timedelta(minutes=5*i)).isoformat()
                     for i in range(12))
    validate_m5(bars, asof_utc=now_utc)
    if len(bars) != 12 or tuple(b.start_utc for b in bars) != expected:
        raise ValueError("P046_B1_REQUIRE_EXACT_12_CLOSED_M5_UTC_HOUR")
    parent_sha = digest(previous) if previous is not None else None
    gap_hours = 0
    if previous is not None:
        previous_hour = datetime.fromisoformat(previous["hour_utc"])
        delta_hours = int((source_hour-previous_hour).total_seconds()//3600)
        if delta_hours <= 0:
            raise ValueError("P046_B1_CANNOT_REWRITE_PAST_COMMITTED_HOUR")
        gap_hours = delta_hours-1
    status = (
        "BOOTSTRAP_HISTORY_UNVERIFIED" if previous is None else
        "MISSING_PRIOR_HOURS_UNVERIFIED" if gap_hours else
        "CONTIGUOUS_WITH_PRIOR_BATCH"
    )
    derived = {}
    for frame, count in (("M15",4),("M30",2),("H1",1)):
        report = derive_intraday(bars, frame, asof_utc=now_utc)
        if len(report.candles) != count or report.skipped_incomplete_windows:
            raise ValueError("P046_B1_INCOMPLETE_DERIVED_HOUR")
        derived[frame] = [asdict(item) for item in report.candles]
    chunk: dict[str, Any] = {
        "schema": VERSION, "hour_utc": hour_utc, "provider": PROVIDER,
        "symbol": SYMBOL, "source_interval": "M5", "source_side": "MID",
        "timezone": "UTC", "parent_manifest_sha256": parent_sha,
        "bars": [asdict(b) for b in bars], "derived": derived,
        "approved_original_numeric_signals": False, "broker_orders": 0,
    }
    cs = digest(chunk)
    cn = _name("chunk", hour_utc, cs)
    prior_n = previous["total_batches"] if previous else 0
    manifest: dict[str, Any] = {
        "schema": VERSION, "hour_utc": hour_utc, "provider": PROVIDER,
        "symbol": SYMBOL, "source_interval": "M5", "source_side": "MID",
        "timezone": "UTC", "parent_manifest_sha256": parent_sha,
        "chunk_sha256": cs, "chunk_name": cn,
        "total_batches": prior_n+1,
        "total_closed_m5": (prior_n+1)*12,
        "gap_prior_hours_unverified": gap_hours,
        "continuity_status": status,
        "approved_original_numeric_signals": False,
        "broker_orders": 0,
    }
    ms = digest(manifest)
    mn = _name("manifest", hour_utc, ms)
    _validate_chunk(cn, chunk)
    _validate_manifest(mn, manifest)
    return BatchPlan(
        hour_utc=hour_utc, chunk_name=cn, chunk_sha256=cs, chunk=chunk,
        manifest_name=mn, manifest_sha256=ms, manifest=manifest,
    )


def plan_closed_hour(
    previous: dict[str, Any] | None,
    observed: tuple[ClosedM5Bar, ...],
    *, now_utc: datetime,
) -> BatchPlan | None:
    """Only the immediately previous full UTC hour, after +5m safety margin."""
    if (type(now_utc) is not datetime or now_utc.tzinfo is None
            or now_utc.utcoffset() != timedelta(0)):
        raise ValueError("P046_B1_UTC_NOW_REQUIRED")
    if now_utc.minute < 5:
        return None
    target_end = now_utc.replace(minute=0, second=0, microsecond=0)
    target_start = target_end-HOUR
    hour = target_start.isoformat()
    if previous is not None and (
            datetime.fromisoformat(previous["hour_utc"]) >= target_start):
        return None
    if not observed:
        return None
    validate_m5(observed, asof_utc=now_utc)
    selected = tuple(
        b for b in observed
        if target_start <= datetime.fromisoformat(b.start_utc) < target_end
    )
    if not selected:
        return None
    # A partial hour must not be published or passed to indicators/signals.
    if len(selected) != 12:
        return None
    return _make_plan(previous, hour_utc=hour, bars=selected,
                      now_utc=now_utc)


def _orphan_plan(
    store: PrivateObjectStore, previous: dict[str, Any] | None,
    now_utc: datetime,
) -> BatchPlan | None:
    names = store.list_names("chunk")
    if len(names) > MAX_LIST or len(set(names)) != len(names):
        raise ValueError("P046_B1_CHUNK_LIST_AMBIGUOUS_OR_UNBOUNDED")
    parent_sha = digest(previous) if previous is not None else None
    prior_hour = previous["hour_utc"] if previous is not None else ""
    pending: list[BatchPlan] = []
    for name in sorted(names):
        if not name.startswith(CHUNK_PREFIX):
            raise ValueError("P046_B1_UNKNOWN_CHUNK_NAME")
        # Prior/original chunks are already committed; do not fetch all raw.
        stamp = name[len(CHUNK_PREFIX):len(CHUNK_PREFIX)+13]
        prior_stamp = prior_hour[:16].replace("-", "").replace(":", "")
        if stamp < prior_stamp:
            continue
        if stamp == prior_stamp:
            if previous is not None and name != previous["chunk_name"]:
                raise ValueError("P046_B1_CONFLICTING_COMMITTED_HOUR_CHUNK")
            continue
        c = store.read("chunk", name)
        hour = _validate_chunk(name, c)
        if c["parent_manifest_sha256"] != parent_sha:
            # Other branch/orphan with stale parent must be investigated.
            raise ValueError("P046_B1_STALE_OR_CONFLICTING_CHUNK_PARENT")
        payload = c["bars"]
        if not isinstance(payload, list):
            raise ValueError("P046_B1_CHUNK_BARS_NOT_LIST")
        bars: list[ClosedM5Bar] = []
        for row in payload:
            if not isinstance(row, dict) or set(row) != {
                    "start_utc","open","high","low","close"}:
                raise ValueError("P046_B1_BAD_ORPHAN_BAR_FORMAT")
            bars.append(ClosedM5Bar(**row))
        plan = _make_plan(
            previous, hour_utc=hour, bars=tuple(bars), now_utc=now_utc,
        )
        if plan.chunk != c:
            raise ValueError("P046_B1_ORPHAN_DERIVATION_OR_SOURCE_DRIFT")
        pending.append(plan)
    if len(pending) > 1:
        raise ValueError("P046_B1_MULTIPLE_UNCOMMITTED_SIBLING_CHUNKS")
    return pending[0] if pending else None


def commit_hour(
    store: PrivateObjectStore,
    *, now_utc: datetime,
    observed: tuple[ClosedM5Bar, ...] | None = None,
) -> BatchResult:
    """Idempotent recovery-first two-object commit, no market/provider calls.

    A network adapter must authenticate to PRIVATE Drive and read back
    uploads. GitHub single-writer concurrency avoids cooperating conflicts,
    but Google Drive exposes no atomic multi-object compare-and-swap.
    """
    _, previous = _last_manifest(store)
    pending = _orphan_plan(store, previous, now_utc)
    recovered = pending is not None
    if pending is not None:
        plan = pending
    elif observed is None:
        return BatchResult("NO_ORPHAN_NEED_PROVIDER_DATA",None,0,0,False)
    else:
        plan = plan_closed_hour(previous, observed, now_utc=now_utc)
        if plan is None:
            return BatchResult("NOT_DUE_OR_INCOMPLETE_HOUR",None,0,0,False)
    current_name, current = _last_manifest(store)
    if current != previous:  # optimistic pre-write revalidation
        raise ValueError("P046_B1_PARENT_CHANGED_BEFORE_COMMIT")
    store.put_if_absent("chunk",plan.chunk_name,plan.chunk)
    if store.read("chunk",plan.chunk_name) != plan.chunk:
        raise ValueError("P046_B1_CHUNK_READBACK_MISMATCH")
    if _last_manifest(store)[0] != current_name:
        raise ValueError("P046_B1_MANIFEST_CHANGED_AFTER_CHUNK_WRITE")
    store.put_if_absent("manifest",plan.manifest_name,plan.manifest)
    if store.read("manifest",plan.manifest_name) != plan.manifest:
        raise ValueError("P046_B1_MANIFEST_READBACK_MISMATCH")
    latest_name, latest = _last_manifest(store)
    if latest_name != plan.manifest_name or latest != plan.manifest:
        raise ValueError("P046_B1_MANIFEST_NOT_UNIQUE_LATEST")
    return BatchResult(
        status="RECOVERED_UNCOMMITTED_CHUNK" if recovered else "BATCH_COMMITTED",
        committed_hour_utc=plan.hour_utc, new_closed_m5=12,
        drive_object_writes_expected=1 if recovered else 2,
        recovered_orphan=recovered,
    )
