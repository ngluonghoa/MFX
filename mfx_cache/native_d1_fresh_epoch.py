"""MFX P0.171 — owner-authorized EUR/USD D1 2026-11-11 fresh epoch.

The historical V1 native D1 archive and P169 quarantine remain immutable.
An actual NEW provider response, not the old P169 stored observation, starts
this separate SHA-addressed epoch; all subsequent D1 revisions fail closed.
Only SOURCE MID cache custody is authorized, NOT first-known or live signals.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch, native_request_contract
from mfx_cache.native_htf_archive import (
    RECENT_INDEX_LIMIT, _bar_valid, plan_native_sealed,
)
from mfx_cache.td_m5_codec import digest
from tools.mfx_native_htf_drive_seal import PrivateNativeDriveStore, MAX_NATIVE_FILES
from tools.run_a04_p45_cloud_twelve_data_cache import CHUNK_FOLDER, MANIFEST_FOLDER

PREFIX = "MFX_P171_EURUSD_D1_20261111_FRESH_EPOCH_V1_"
SCHEMA = "MFX_P171_D1_FRESH_EPOCH_V1"
INCIDENT = "2026-11-11"
SOURCE = ("EUR/USD", "1day", "Australia/Sydney")
MIN_OVERLAP = 24
PUBLICATION_BUFFER = timedelta(minutes=2, seconds=15)


def _sha(s: Any) -> bool:
    return type(s) is str and len(s) == 64 and all(c in "0123456789abcdef" for c in s)


def _utc(t: datetime) -> datetime:
    if (type(t) is not datetime or t.tzinfo is None
            or t.utcoffset() != timedelta(0)):
        raise ValueError("P171_UTC_RUNNER_CLOCK_REQUIRED")
    return t


class PrivateD1FreshEpochStore(PrivateNativeDriveStore):
    """Disjoint namespaces within the SAME existing OAuth Drive folders."""

    def __init__(self, session: Any) -> None:
        super().__init__(session, symbol="EUR/USD", interval="1day")

    def _bucket(self, bucket: str) -> tuple[str, str]:
        if bucket == "chunk":
            return CHUNK_FOLDER, PREFIX+"chunk_"
        if bucket == "manifest":
            return MANIFEST_FOLDER, PREFIX+"manifest_"
        raise ValueError("P171_EPOCH_BUCKET_DENIED")


@dataclass(frozen=True)
class FreshEpochState:
    last_manifest: dict[str, Any] | None
    manifests: int
    chunks: int
    orphan_chunk: str | None


def _file_name(kind: str, label: str, sha: str) -> str:
    if (kind not in ("chunk", "manifest") or not _sha(sha)
            or len(label) != 10 or label[4] != "-" or label[7] != "-"):
        raise ValueError("P171_INVALID_FILE_IDENTITY")
    return f"{PREFIX}{kind}_{label.replace('-', '')}_{sha}.json"


def _source_batch(batch: NativeFXBatch) -> None:
    if (type(batch) is not NativeFXBatch
            or (batch.symbol, batch.interval, batch.exchange_timezone) != SOURCE
            or batch.time_reference != "EXCHANGE_LOCAL_SESSION_DATE"
            or batch.source != "TWELVE_DATA_COMPOSITE_MID"
            or batch.is_provider_native is not True
            or batch.vendor_calls_made_by_parser != 0
            or batch.google_drive_writes != 0
            or batch.confirmed_buy_sell_signals != 0
            or batch.broker_orders != 0):
        raise ValueError("P171_D1_NATIVE_SOURCE_REQUIRED")
    # Reuse hardened V1 source native OHLC/provenance validation, but never
    # inherit the old V1 index/manifest or any of its changed 11 Nov prices.
    plan_native_sealed(batch, previous=None)


def _validate_chunk(chunk: Any, name: str, origin: str) -> tuple[NativeFXBar, ...]:
    if (type(chunk) is not dict
            or set(chunk) != {"schema","source","symbol","interval",
                              "exchange_timezone","time_reference",
                              "origin_v1_manifest_sha256","bars"}
            or chunk["schema"] != SCHEMA
            or chunk["source"] != "TWELVE_DATA_COMPOSITE_MID"
            or (chunk["symbol"],chunk["interval"],chunk["exchange_timezone"])
                    != SOURCE
            or chunk["time_reference"] != "EXCHANGE_LOCAL_SESSION_DATE"
            or chunk["origin_v1_manifest_sha256"] != origin
            or type(chunk["bars"]) is not list
            or not 1 <= len(chunk["bars"]) <= 120):
        raise ValueError("P171_INVALID_EPOCH_CHUNK")
    try:
        bars = tuple(NativeFXBar(**item) for item in chunk["bars"])
        labels = [bar.native_open_label for bar in bars]
        if (labels != sorted(set(labels)) or
                any(label < INCIDENT for label in labels)):
            raise ValueError("P171_EPOCH_BAR_ORDER_OR_CUTOFF")
        for bar in bars:
            _bar_valid(bar, symbol="EUR/USD",interval="1day",
                       zone="Australia/Sydney")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("P171_INVALID_EPOCH_BAR") from exc
    if name != _file_name("chunk",bars[-1].native_open_label,digest(chunk)):
        raise ValueError("P171_EPOCH_CHUNK_SHA_OR_NAME_MISMATCH")
    return bars


def _validate_manifest(
    manifest: Any, name: str, chunk_name: str, chunk: dict[str,Any],
    previous: dict[str,Any] | None, origin: str,
) -> None:
    required = {
        "schema","symbol","interval","exchange_timezone","source",
        "source_side","origin_v1_manifest_sha256","owner_rebaseline_date",
        "parent_manifest_sha256","chunk_name","chunk_sha256",
        "batch_count","total_closed_bars","last_native_open_label",
        "recent_native_bar_index","first_observed_runner_utc",
        "owner_approved_cache_rebaseline","publisher_first_known_verified",
        "may_publish_buy_sell","broker_orders",
    }
    if (type(manifest) is not dict or set(manifest) != required
            or manifest["schema"] != SCHEMA
            or (manifest["symbol"],manifest["interval"],
                manifest["exchange_timezone"]) != SOURCE
            or manifest["source"] != "TWELVE_DATA_COMPOSITE_MID"
            or manifest["source_side"] != "MID"
            or manifest["origin_v1_manifest_sha256"] != origin
            or manifest["owner_rebaseline_date"] != INCIDENT
            or manifest["owner_approved_cache_rebaseline"] is not True
            or manifest["publisher_first_known_verified"] is not False
            or manifest["may_publish_buy_sell"] is not False
            or type(manifest["broker_orders"]) is not int
            or manifest["broker_orders"] != 0
            or type(manifest["batch_count"]) is not int
            or type(manifest["total_closed_bars"]) is not int):
        raise ValueError("P171_INVALID_EPOCH_MANIFEST")
    if (name != _file_name("manifest",
                          manifest["last_native_open_label"],digest(manifest))
            or manifest["chunk_name"] != chunk_name
            or manifest["chunk_sha256"] != digest(chunk)
            or (manifest["parent_manifest_sha256"]
                != (digest(previous) if previous is not None else None))
            or manifest["batch_count"]
                != (previous["batch_count"]+1 if previous else 1)
            or manifest["total_closed_bars"]
                != ((previous["total_closed_bars"] if previous else 0)
                    + len(chunk["bars"]))):
        raise ValueError("P171_EPOCH_CHAIN_OR_PARENT_SHA_MISMATCH")
    observed = manifest["first_observed_runner_utc"]
    if type(observed) is not str:
        raise ValueError("P171_INVALID_RUNNER_OBSERVED")
    try:
        stamp = _utc(datetime.fromisoformat(observed))
    except ValueError as exc:
        raise ValueError("P171_INVALID_RUNNER_OBSERVED") from exc
    if stamp.isoformat() != observed:
        raise ValueError("P171_INVALID_RUNNER_OBSERVED")
    recent = manifest["recent_native_bar_index"]
    if (type(recent) is not list or not 1 <= len(recent) <= RECENT_INDEX_LIMIT
            or any(type(item) is not dict
                or set(item) != {"label","sha256"}
                or not _sha(item["sha256"]) for item in recent)):
        raise ValueError("P171_INVALID_RECENT_INDEX")
    labels = [item["label"] for item in recent]
    if (labels != sorted(set(labels))
            or labels[-1] != manifest["last_native_open_label"]):
        raise ValueError("P171_RECENT_INDEX_BAD_LAST_LABEL")


def audit_fresh_epoch(store: Any, *, origin_v1_sha: str) -> FreshEpochState:
    """Independent complete SHA/parent readback, including orphan detection."""
    if not _sha(origin_v1_sha):
        raise ValueError("P171_ORIGINAL_V1_SHA_REQUIRED")
    manifests = store.list_names("manifest")
    chunks = store.list_names("chunk")
    if (type(manifests) is not tuple or type(chunks) is not tuple
            or len(manifests) > MAX_NATIVE_FILES
            or len(chunks) > MAX_NATIVE_FILES
            or len(set(manifests)) != len(manifests)
            or len(set(chunks)) != len(chunks)):
        raise ValueError("P171_EPOCH_LISTING_INVALID")
    prev: dict[str,Any] | None = None
    referenced: set[str] = set()
    old_index: dict[str,str] = {}
    for name in sorted(manifests):
        m = store.read("manifest",name)
        if type(m) is not dict:
            raise ValueError("P171_MALFORMED_MANIFEST")
        c_name = m.get("chunk_name")
        if type(c_name) is not str or c_name not in chunks or c_name in referenced:
            raise ValueError("P171_MISSING_OR_REUSED_CHUNK")
        c = store.read("chunk", c_name)
        bars = _validate_chunk(c,c_name,origin_v1_sha)
        if prev is None:
            if INCIDENT not in {bar.native_open_label for bar in bars}:
                raise ValueError("P171_INITIAL_REFETCH_MUST_CONTAIN_INCIDENT")
        elif bars[0].native_open_label <= prev["last_native_open_label"]:
            raise ValueError("P171_EPOCH_NONMONOTONIC_APPEND")
        expected_index = {
            **old_index,
            **{b.native_open_label:b.sha256() for b in bars},
        }
        expected_recent = [
            {"label":k,"sha256":v}
            for k,v in sorted(expected_index.items())[-RECENT_INDEX_LIMIT:]]
        _validate_manifest(m,name,c_name,c,prev,origin_v1_sha)
        if m["recent_native_bar_index"] != expected_recent:
            raise ValueError("P171_EPOCH_RECENT_SHA_INDEX_MISMATCH")
        old_index = {e["label"]:e["sha256"] for e in expected_recent}
        prev = m
        referenced.add(c_name)
    orphans = set(chunks)-referenced
    if len(orphans)>1:
        raise ValueError("P171_MULTIPLE_ORPHANS")
    return FreshEpochState(prev,len(manifests),len(chunks),
                           next(iter(orphans)) if orphans else None)


def plan_fresh_epoch_fetch(
    *, state: FreshEpochState, now_utc: datetime,
) -> dict[str,str] | None:
    """Use next closed Sydney D1 session only; NO extra hourly source call."""
    _utc(now_utc)
    last = state.last_manifest["last_native_open_label"] if state.last_manifest else None
    eligible = (now_utc-PUBLICATION_BUFFER).astimezone(
        ZoneInfo("Australia/Sydney")).date()-timedelta(days=1)
    if last is not None and last >= eligible.isoformat():
        return None
    if last is None:
        size = 120
    else:
        needed=(eligible-date.fromisoformat(last)).days
        needed+=len(state.last_manifest["recent_native_bar_index"])+4
        if needed > 120:
            raise ValueError("P171_D1_EPOCH_NEEDS_BOUNDED_MANUAL_RECOVERY")
        size=max(MIN_OVERLAP,needed)
    p = native_request_contract(symbol="EUR/USD",interval="1day")
    p["outputsize"]=str(size)
    return p


def plan_fresh_epoch_seal(
    batch: NativeFXBatch, *, state: FreshEpochState,
    origin_v1_sha: str, now_utc: datetime,
) -> tuple[str,dict[str,Any],str,dict[str,Any]] | None:
    """Owner-approved fresh D1 starts at 11 Nov; all later overlaps SHA-checked."""
    _utc(now_utc)
    if not _sha(origin_v1_sha):
        raise ValueError("P171_ORIGINAL_V1_SHA_REQUIRED")
    _source_batch(batch)
    previous = state.last_manifest
    previous_index = {
        x["label"]:x["sha256"]
        for x in previous["recent_native_bar_index"]} if previous else {}
    provided = {b.native_open_label:b.sha256() for b in batch.closed_bars}
    if any(label not in provided or provided[label]!=sha
           for label,sha in previous_index.items()):
        raise ValueError("P171_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
    cutoff = previous["last_native_open_label"] if previous else None
    new = tuple(b for b in batch.closed_bars if
                b.native_open_label>=INCIDENT and
                (cutoff is None or b.native_open_label>cutoff))
    if previous is None and INCIDENT not in {b.native_open_label for b in new}:
        raise ValueError("P171_FRESH_PROVIDER_MISSING_20261111")
    if not new:
        return None
    if len(new)>120:
        raise ValueError("P171_D1_NEW_BAR_LIMIT")
    c:dict[str,Any] = {
        "schema":SCHEMA,"source":"TWELVE_DATA_COMPOSITE_MID",
        "symbol":"EUR/USD","interval":"1day",
        "exchange_timezone":"Australia/Sydney",
        "time_reference":"EXCHANGE_LOCAL_SESSION_DATE",
        "origin_v1_manifest_sha256":origin_v1_sha,
        "bars":[asdict(b) for b in new],
    }
    c_name=_file_name("chunk",new[-1].native_open_label,digest(c))
    current_index={
        **previous_index,**{b.native_open_label:b.sha256() for b in new}}
    m:dict[str,Any] = {
        "schema":SCHEMA,"symbol":"EUR/USD","interval":"1day",
        "exchange_timezone":"Australia/Sydney",
        "source":"TWELVE_DATA_COMPOSITE_MID","source_side":"MID",
        "origin_v1_manifest_sha256":origin_v1_sha,
        "owner_rebaseline_date":INCIDENT,
        "parent_manifest_sha256":digest(previous) if previous else None,
        "chunk_name":c_name,"chunk_sha256":digest(c),
        "batch_count":previous["batch_count"]+1 if previous else 1,
        "total_closed_bars":(previous["total_closed_bars"] if previous else 0)+len(new),
        "last_native_open_label":new[-1].native_open_label,
        "recent_native_bar_index":[
            {"label":k,"sha256":v}
            for k,v in sorted(current_index.items())[-RECENT_INDEX_LIMIT:]],
        "first_observed_runner_utc":now_utc.isoformat(),
        "owner_approved_cache_rebaseline":True,
        "publisher_first_known_verified":False,
        "may_publish_buy_sell":False,"broker_orders":0,
    }
    m_name=_file_name("manifest",new[-1].native_open_label,digest(m))
    _validate_chunk(c,c_name,origin_v1_sha)
    _validate_manifest(m,m_name,c_name,c,previous,origin_v1_sha)
    return c_name,c,m_name,m


def commit_fresh_epoch(
    store: Any, *, batch:NativeFXBatch, origin_v1_sha:str,
    now_utc:datetime,
) -> dict[str,Any]:
    """Append only exact root/tail after a NEW verified provider fetch."""
    before=audit_fresh_epoch(store,origin_v1_sha=origin_v1_sha)
    candidate=plan_fresh_epoch_seal(
        batch,state=before,origin_v1_sha=origin_v1_sha,now_utc=now_utc)
    if candidate is None:
        if before.orphan_chunk is not None:
            raise ValueError("P171_UNRESOLVED_ORPHAN")
        return {
            "status":"NO_NEW_CLOSED_D1_FRESH_EPOCH_BAR",
            "new_bars":0,"total_bars":before.last_manifest["total_closed_bars"]
                if before.last_manifest else 0,
            "drive_objects_created_max":0,
            "broker_orders":0,"may_publish_buy_sell":False,
        }
    c_name,c,m_name,m=candidate
    if before.orphan_chunk is not None and before.orphan_chunk!=c_name:
        raise ValueError("P171_UNRELATED_EPOCH_ORPHAN_REQUIRES_REVIEW")
    if before.manifests>=MAX_NATIVE_FILES or before.chunks>=MAX_NATIVE_FILES+int(
            before.orphan_chunk is not None):
        raise ValueError("P171_EPOCH_ARCHIVE_CAPACITY")
    if audit_fresh_epoch(store,origin_v1_sha=origin_v1_sha)!=before:
        raise ValueError("P171_D1_EPOCH_PARENT_CHANGED_BEFORE_WRITE")
    store.put_if_absent("chunk",c_name,c)
    if store.read("chunk",c_name)!=c:
        raise ValueError("P171_CHUNK_READBACK_FAILED")
    after_chunk=audit_fresh_epoch(store,origin_v1_sha=origin_v1_sha)
    if (after_chunk.last_manifest!=before.last_manifest
            or after_chunk.orphan_chunk!=c_name):
        raise ValueError("P171_D1_EPOCH_PARENT_CHANGED_AFTER_CHUNK")
    store.put_if_absent("manifest",m_name,m)
    if store.read("manifest",m_name)!=m:
        raise ValueError("P171_MANIFEST_READBACK_FAILED")
    after=audit_fresh_epoch(store,origin_v1_sha=origin_v1_sha)
    if (after.last_manifest!=m or after.orphan_chunk is not None
            or after.manifests!=before.manifests+1):
        raise ValueError("P171_D1_EPOCH_COMMIT_CHAIN_INVALID")
    return {
        "status":"D1_FRESH_EPOCH_SHA_COMMITTED",
        "new_bars":len(c["bars"]),
        "total_bars":m["total_closed_bars"],
        "last_native_open_label":m["last_native_open_label"],
        "manifest_sha256":digest(m),
        "drive_objects_created_max":1 if before.orphan_chunk else 2,
        "broker_orders":0,"may_publish_buy_sell":False,
    }
