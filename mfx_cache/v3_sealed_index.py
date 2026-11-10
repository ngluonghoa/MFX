"""A04/P0.46-B3-B: bounded sealed B1 index and HOT-vs-B1 source anchor.

Index is a *mutable pointer*, not a new immutable source truth. Every use
re-reads the exact SHA-addressed B1 Manifest and raw hourly chunk. Index
latestness against external writers cannot be proved without a scoped list:
the hourly reconciliation scan does that; HOT reads are bounded O(1).

No provider calls, no original Forex numeric approvals, no broker orders.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import re
from typing import Any, Protocol

from mfx_cache.td_m5_codec import (
    ClosedM5Bar, PROVIDER, SYMBOL, digest,
)
from mfx_cache.v2_batch_commit import (
    MANIFEST_PREFIX, PrivateObjectStore, _validate_manifest, _validate_chunk,
)
from mfx_cache.v2_engine import derive_intraday, validate_m5
from mfx_cache.v3_hot_overlay import validate_hot

VERSION = "MFX_A04_P46_B3B_B1_SEALED_INDEX_V1"
INDEX_NAME = "MFX_TD_EURUSD_M5_V3_B1_SEALED_INDEX_LATEST.json"
MAX_MANIFEST_NAMES = 12000
SHA_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class IndexPort(Protocol):
    def load(self) -> dict[str, Any] | None: ...
    def write(
        self, *, expected: dict[str, Any] | None,
        replacement: dict[str, Any],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class IndexReceipt:
    status: str
    source_hour_utc: str | None
    generation: int
    verified_manifest_reads: int
    verified_chunk_reads: int
    new_index_file_expected: int
    index_updates_expected: int
    full_history_scans: int = 0
    actual_provider_requests: int = 0
    original_source_objects_deleted: int = 0
    source_numeric_signals_approved: bool = False
    broker_orders: int = 0


@dataclass(frozen=True, slots=True)
class HotAnchor:
    status: str
    overlap_bars: int
    hour_utc: str
    canonical_source_matches: bool
    authoritative_signal_allowed: bool = False
    broker_orders_allowed: bool = False


def _check_utc(now: datetime) -> None:
    if (type(now) is not datetime or now.tzinfo is None
            or now.utcoffset() != timedelta(0)):
        raise ValueError("P046_B3B_EXACT_UTC_REQUIRED")


def _hour(text: object) -> datetime:
    if type(text) is not str or not text.endswith("+00:00"):
        raise ValueError("P046_B3B_UTC_HOUR_STRING")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("P046_B3B_INVALID_HOUR") from exc
    _check_utc(dt)
    if dt.minute or dt.second or dt.microsecond:
        raise ValueError("P046_B3B_NOT_HOUR_ALIGNED")
    return dt


def _sha(value: object) -> bool:
    return type(value) is str and SHA_PATTERN.fullmatch(value) is not None


def validate_index(raw: object, *, now_utc: datetime) -> dict[str, Any]:
    _check_utc(now_utc)
    if type(raw) is not dict:
        raise ValueError("P046_B3B_INDEX_MAPPING_REQUIRED")
    m = raw
    if set(m) != {
        "schema", "provider", "symbol", "side", "timezone", "interval",
        "generation", "previous_index_sha256", "index_mode",
        "index_first_created_utc", "index_updated_utc",
        "source_hour_utc", "manifest_name", "manifest_sha256",
        "chunk_name", "chunk_sha256", "source_parent_manifest_sha256",
        "source_total_batches", "source_closed_m5_count",
        "source_continuity_status", "history_completeness_claimed",
        "owner_approved_numeric_signals", "broker_orders",
    }:
        raise ValueError("P046_B3B_EXACT_INDEX_SCHEMA_REQUIRED")
    if (m["schema"] != VERSION or m["provider"] != PROVIDER
            or m["symbol"] != SYMBOL or m["side"] != "MID"
            or m["timezone"] != "UTC" or m["interval"] != "M5"
            or m["history_completeness_claimed"] is not False
            or m["owner_approved_numeric_signals"] is not False
            or type(m["broker_orders"]) is not int
            or m["broker_orders"] != 0):
        raise ValueError("P046_B3B_SOURCE_PROVENANCE_NOT_APPROVAL")
    if (type(m["generation"]) is not int
            or not 1 <= m["generation"] <= 10000000):
        raise ValueError("P046_B3B_INVALID_GENERATION")
    if (m["index_mode"] not in ("ROOT_FULL_B1_CHAIN_READ",
                              "NEXT_B1_SEALED_CHILD")
            or (m["generation"] == 1) != (
                m["previous_index_sha256"] is None)
            or (m["generation"] > 1 and
                not _sha(m["previous_index_sha256"]))):
        raise ValueError("P046_B3B_INDEX_PREDECESSOR_INVALID")
    if m["generation"] == 1 and m["index_mode"] != "ROOT_FULL_B1_CHAIN_READ":
        raise ValueError("P046_B3B_INDEX_BOOTSTRAP_NOT_SCANNED")
    if m["generation"] > 1 and m["index_mode"] != "NEXT_B1_SEALED_CHILD":
        raise ValueError("P046_B3B_INDEX_MODE_DRIFT")
    if (not _sha(m["manifest_sha256"]) or not _sha(m["chunk_sha256"])
            or (m["source_parent_manifest_sha256"] is not None and
                not _sha(m["source_parent_manifest_sha256"]))):
        raise ValueError("P046_B3B_INVALID_B1_HASH")
    if (type(m["manifest_name"]) is not str
            or not m["manifest_name"].startswith(MANIFEST_PREFIX)
            or type(m["chunk_name"]) is not str):
        raise ValueError("P046_B3B_INVALID_IMMUTABLE_OBJECT_NAMES")
    source_hour = _hour(m["source_hour_utc"])
    if source_hour + timedelta(hours=1) > now_utc:
        raise ValueError("P046_B3B_FUTURE_UNCLOSED_B1_HOUR")
    try:
        created = datetime.fromisoformat(m["index_first_created_utc"])
        updated = datetime.fromisoformat(m["index_updated_utc"])
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("P046_B3B_INVALID_INDEX_CLOCK") from exc
    _check_utc(created)
    _check_utc(updated)
    if not (source_hour < created <= updated <= now_utc):
        raise ValueError("P046_B3B_IMPOSSIBLE_INDEX_CLOCK")
    if (type(m["source_total_batches"]) is not int
            or m["source_total_batches"] < 1
            or type(m["source_closed_m5_count"]) is not int
            or m["source_closed_m5_count"] !=
            m["source_total_batches"] * 12
            or m["source_continuity_status"] not in (
                "BOOTSTRAP_HISTORY_UNVERIFIED",
                "CONTIGUOUS_WITH_PRIOR_BATCH",
                "MISSING_PRIOR_HOURS_UNVERIFIED",
            )):
        raise ValueError("P046_B3B_INVALID_SOURCE_ORDINAL")
    return m


def _source(
    store: PrivateObjectStore, name: str,
    *, now_utc: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        m = store.read("manifest", name)
        hour = _validate_manifest(name, m)
        c = store.read("chunk", m["chunk_name"])
        _validate_chunk(m["chunk_name"], c)
    except (KeyError, FileNotFoundError) as exc:
        raise ValueError("P046_B3B_MISSING_SEALED_SOURCE") from exc
    if (c["hour_utc"] != hour
            or c["parent_manifest_sha256"] != m["parent_manifest_sha256"]
            or digest(c) != m["chunk_sha256"]):
        raise ValueError("P046_B3B_B1_MANIFEST_CHUNK_SHA_LINK_BROKEN")
    raw = c["bars"]
    if (type(raw) is not list or len(raw) != 12
            or any(type(x) is not dict or set(x) != {
                "start_utc", "open", "high", "low", "close",
            } for x in raw)):
        raise ValueError("P046_B3B_INVALID_HOURLY_BAR_SET")
    bars = tuple(ClosedM5Bar(**x) for x in raw)
    validate_m5(bars, asof_utc=now_utc)
    start = _hour(m["hour_utc"])
    expected = tuple((start+timedelta(minutes=5*i)).isoformat()
                     for i in range(12))
    if tuple(b.start_utc for b in bars) != expected:
        raise ValueError("P046_B3B_B1_INCOMPLETE_CLOSED_HOUR")
    for frame, count in (("M15", 4), ("M30", 2), ("H1", 1)):
        derived = derive_intraday(bars, frame, asof_utc=now_utc)
        if (len(derived.candles) != count
                or [asdict(x) for x in derived.candles] !=
                c["derived"].get(frame)):
            raise ValueError("P046_B3B_B1_DERIVED_SOURCE_SHA_LINEAGE_BROKEN")
    return m, c


def _read_index_source(
    store: PrivateObjectStore, index: dict[str, Any],
    *, now_utc: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    indexed = validate_index(index, now_utc=now_utc)
    manifest, chunk = _source(
        store, indexed["manifest_name"], now_utc=now_utc,
    )
    if (digest(manifest) != indexed["manifest_sha256"]
            or digest(chunk) != indexed["chunk_sha256"]
            or manifest["hour_utc"] != indexed["source_hour_utc"]
            or manifest["parent_manifest_sha256"] !=
            indexed["source_parent_manifest_sha256"]
            or manifest["total_batches"] != indexed["source_total_batches"]
            or manifest["total_closed_m5"] != indexed["source_closed_m5_count"]
            or manifest["continuity_status"] !=
            indexed["source_continuity_status"]
            or manifest["chunk_name"] != indexed["chunk_name"]):
        raise ValueError("P046_B3B_INDEX_REFERENCE_MISMATCH")
    return manifest, chunk


def _new_index(
    prior: dict[str, Any] | None,
    manifest_name: str,
    manifest: dict[str, Any], chunk: dict[str, Any],
    *, now_utc: datetime,
) -> dict[str, Any]:
    hour = _hour(manifest["hour_utc"])
    if prior is not None:
        validate_index(prior, now_utc=now_utc)
        if (hour <= _hour(prior["source_hour_utc"])
                or manifest["parent_manifest_sha256"] !=
                prior["manifest_sha256"]
                or manifest["total_batches"] !=
                prior["source_total_batches"] + 1):
            raise ValueError("P046_B3B_INDEX_FORK_OR_SOURCE_SKIP")
    index: dict[str, Any] = {
        "schema": VERSION, "provider": PROVIDER, "symbol": SYMBOL,
        "side": "MID", "timezone": "UTC", "interval": "M5",
        "generation": prior["generation"] + 1 if prior else 1,
        "previous_index_sha256": digest(prior) if prior else None,
        "index_mode": ("NEXT_B1_SEALED_CHILD" if prior else
                       "ROOT_FULL_B1_CHAIN_READ"),
        "index_first_created_utc": (
            prior["index_first_created_utc"] if prior else
            now_utc.isoformat()),
        "index_updated_utc": now_utc.isoformat(),
        "source_hour_utc": hour.isoformat(),
        "manifest_name": manifest_name,
        "manifest_sha256": digest(manifest),
        "chunk_name": manifest["chunk_name"],
        "chunk_sha256": digest(chunk),
        "source_parent_manifest_sha256":
            manifest["parent_manifest_sha256"],
        "source_total_batches": manifest["total_batches"],
        "source_closed_m5_count": manifest["total_closed_m5"],
        "source_continuity_status": manifest["continuity_status"],
        "history_completeness_claimed": False,
        "owner_approved_numeric_signals": False,
        "broker_orders": 0,
    }
    return validate_index(index,now_utc=now_utc)


def reconcile_sealed_index(
    source: PrivateObjectStore, pointer: IndexPort, *,
    now_utc: datetime,
) -> IndexReceipt:
    """One hourly bounded list; HOT lookups never list archive objects."""
    _check_utc(now_utc)
    original = pointer.load()
    if original is not None:
        _read_index_source(source, original, now_utc=now_utc)
    names = tuple(sorted(source.list_names("manifest")))
    if (len(names) > MAX_MANIFEST_NAMES
            or len(set(names)) != len(names)
            or any(not x.startswith(MANIFEST_PREFIX) for x in names)):
        raise ValueError("P046_B3B_INVALID_OR_UNBOUNDED_MANIFEST_LIST")
    if not names:
        if original is not None:
            raise ValueError("P046_B3B_INDEX_ORPHANED_NO_SOURCE_LIST")
        return IndexReceipt("NO_SEALED_B1_HOUR",None,0,0,0,0,0)
    if original is None:
        # One-time bootstrap must scan the full manifest chain and every
        # immutable chunk. Not O(1); subsequent HOT reads remain O(1).
        previous: dict[str, Any] | None = None
        for i, name in enumerate(names):
            m, _ = _source(source,name,now_utc=now_utc)
            if (m["parent_manifest_sha256"] !=
                    (digest(previous) if previous else None)
                    or m["total_batches"] != i+1
                    or (previous is not None and
                        m["hour_utc"] <= previous["hour_utc"])):
                raise ValueError("P046_B3B_BOOTSTRAP_B1_CHAIN_BROKEN")
            previous = m
        latest_name = names[-1]
        manifest, chunk = _source(source,latest_name,now_utc=now_utc)
        next_index = _new_index(
            None,latest_name,manifest,chunk,now_utc=now_utc,
        )
        full_scans = 1
    else:
        previous_name = original["manifest_name"]
        if previous_name not in names:
            raise ValueError("P046_B3B_POINTER_NOT_IN_SOURCE_LIST")
        pos = names.index(previous_name)
        if pos == len(names)-1:
            # Index can only prove currently observed archive listing,
            # not absence of unlisted external revisions.
            return IndexReceipt(
                "UNCHANGED_B1_SEALED_INDEX",
                original["source_hour_utc"],original["generation"],
                1,1,0,0,
            )
        if pos != len(names)-2:
            raise ValueError("P046_B3B_MULTIPLE_UNINDEXED_B1_HOURS")
        latest_name = names[-1]
        manifest, chunk = _source(source,latest_name,now_utc=now_utc)
        next_index = _new_index(
            original,latest_name,manifest,chunk,now_utc=now_utc,
        )
        full_scans = 0
    if pointer.load()!=original:
        raise ValueError("P046_B3B_POINTER_CHANGED_DURING_PLAN")
    pointer.write(expected=original,replacement=next_index)
    if pointer.load()!=next_index:
        raise ValueError("P046_B3B_POINTER_READBACK_MISMATCH")
    _read_index_source(source,next_index,now_utc=now_utc)
    if tuple(sorted(source.list_names("manifest"))) != names:
        raise ValueError("P046_B3B_B1_MANIFEST_LIST_CHANGED_DURING_INDEX_WRITE")
    return IndexReceipt(
        "BOOTSTRAP_INDEX_COMMITTED" if original is None else
        "NEXT_B1_SEALED_INDEX_COMMITTED",
        next_index["source_hour_utc"],next_index["generation"],
        1 if original else len(names)+1,1 if original else len(names)+1,
        1 if original is None else 0,
        0 if original is None else 1,
        full_history_scans=full_scans,
    )


def check_hot_against_sealed_index(
    source: PrivateObjectStore, index: dict[str, Any],
    hot: dict[str, Any], *, now_utc: datetime,
) -> HotAnchor:
    """Two direct immutable B1 reads, zero historical listing operations."""
    _, sealed = _read_index_source(source,index,now_utc=now_utc)
    current = validate_hot(hot,now_utc=now_utc)
    b1 = {x["start_utc"]: digest(x) for x in sealed["bars"]}
    hot_records = current["recent_bars"]
    overlaps = [
        x for x in hot_records if x["start_utc"] in b1
    ]
    for row in overlaps:
        canonical_row = {k:row[k] for k in (
            "start_utc","open","high","low","close",
        )}
        if digest(canonical_row)!=b1[row["start_utc"]]:
            raise ValueError("P046_B3B_HOT_B1_IMMUTABLE_SOURCE_MISMATCH")
    if not overlaps:
        status = "UNANCHORED_NO_OVERLAPPING_SOURCE_M5"
    elif (datetime.fromisoformat(current["latest_closed_start_utc"]) <
          _hour(index["source_hour_utc"]) + timedelta(minutes=55)):
        status = "HOT_OLDER_THAN_SEALED_B1_SOURCE"
    else:
        status = "B1_IMMUTABLE_OVERLAP_VERIFIED_RESEARCH_ONLY"
    return HotAnchor(
        status=status,
        overlap_bars=len(overlaps),
        hour_utc=index["source_hour_utc"],
        canonical_source_matches=bool(overlaps),
    )
