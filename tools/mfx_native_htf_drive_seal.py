"""MFX A04/P0.55 — strict per-pair/native-TF private Drive sealed archive.

Adapter uses the existing OAuth app-created CHUNKS/MANIFESTS folders, with
NON-overlapping native H4/D1 per-symbol prefixes. No Drive calls on import.
No new schedule, provider price call, numeric signal or broker.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import (
    NativeSealedPlan, _name, _scope, check_native_manifest,
    plan_native_sealed, verify_native_sealed,
)
from mfx_cache.td_m5_codec import digest
from tools.run_a04_p45_cloud_twelve_data_cache import (
    CHUNK_FOLDER, MANIFEST_FOLDER, _drive_get, _drive_create,
)

MAX_NATIVE_FILES = 256


class PrivateNativeDriveStore:
    """MFX-owned Drive API access scoped to a symbol+native TF name prefix.

    The source M5 V2 enumeration filters on a separate prefix and is not
    touched. This is cooperative concurrency only, NOT an atomic Drive CAS.
    """
    def __init__(self, session: Any, *, symbol: str, interval: str) -> None:
        self._scope = _scope(symbol, interval)
        self._session = session
        self._ids: dict[tuple[str, str], str] = {}

    def _bucket(self, bucket: str) -> tuple[str, str]:
        if bucket == "chunk":
            return CHUNK_FOLDER, self._scope + "_chunk_"
        if bucket == "manifest":
            return MANIFEST_FOLDER, self._scope + "_manifest_"
        raise ValueError("P055_NATIVE_DRIVE_BUCKET_DENIED")

    def list_names(self, bucket: str) -> tuple[str, ...]:
        folder, prefix = self._bucket(bucket)
        found: dict[str, str] = {}
        token: str | None = None
        page_count = 0
        while True:
            page_count += 1
            if page_count > 10:
                raise ValueError("P055_NATIVE_DRIVE_PAGE_LIMIT")
            params = {
                "q": (f"'{folder}' in parents and name contains "
                      f"'{prefix}' and trashed = false"),
                "pageSize": 1000,
                "fields": "nextPageToken,files(id,name,mimeType,parents)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if token:
                params["pageToken"] = token
            response = self._session.get(
                "https://www.googleapis.com/drive/v3/files",
                params=params, timeout=45,
            )
            response.raise_for_status()
            doc = response.json()
            if type(doc) is not dict or type(doc.get("files")) is not list:
                raise ValueError("P055_NATIVE_DRIVE_BAD_LIST")
            for item in doc["files"]:
                if (type(item) is not dict
                        or type(item.get("id")) is not str
                        or type(item.get("name")) is not str
                        or item.get("mimeType") != "application/json"
                        or folder not in item.get("parents", [])
                        or not item["name"].startswith(prefix)):
                    raise ValueError("P055_NATIVE_DRIVE_WRONG_OBJECT_SCOPE")
                if item["name"] in found:
                    raise ValueError("P055_NATIVE_DRIVE_DUPLICATE_NAME")
                found[item["name"]] = item["id"]
                if len(found) > MAX_NATIVE_FILES:
                    raise ValueError("P055_NATIVE_DRIVE_ARCHIVE_BOUND")
            next_token = doc.get("nextPageToken")
            if next_token is None:
                break
            if type(next_token) is not str or not next_token or next_token == token:
                raise ValueError("P055_NATIVE_DRIVE_INVALID_PAGE_TOKEN")
            token = next_token
        self._ids.update({(bucket,name):id for name,id in found.items()})
        return tuple(sorted(found))

    def read(self, bucket: str, name: str) -> dict[str, Any]:
        _, prefix = self._bucket(bucket)
        if not name.startswith(prefix):
            raise ValueError("P055_NATIVE_DRIVE_READ_SCOPE_DENIED")
        # Refresh the remote listing on every read to avoid stale cached IDs.
        if name not in self.list_names(bucket):
            raise ValueError("P055_NATIVE_DRIVE_OBJECT_MISSING")
        value = _drive_get(self._session, self._ids[(bucket,name)])
        if type(value) is not dict:
            raise ValueError("P055_NATIVE_DRIVE_OBJECT_NOT_JSON")
        return value

    def put_if_absent(
        self, bucket: str, name: str, body: dict[str, Any],
    ) -> None:
        folder, prefix = self._bucket(bucket)
        if not name.startswith(prefix) or type(body) is not dict:
            raise ValueError("P055_NATIVE_DRIVE_WRITE_SCOPE_DENIED")
        existing = self.list_names(bucket)
        if name in existing:
            if self.read(bucket,name) != body:
                raise ValueError("P055_NATIVE_EXISTING_OBJECT_MUTATED")
            return
        file_id = _drive_create(self._session, folder, name, body)
        self._ids[(bucket,name)] = file_id
        if self.read(bucket,name) != body:
            raise ValueError("P055_NATIVE_NEW_OBJECT_READBACK_MISMATCH")


@dataclass(frozen=True, slots=True)
class NativeArchiveState:
    last_manifest: dict[str, Any] | None
    latest_manifest_name: str | None
    manifest_count: int
    chunk_count: int
    uncommitted_chunk_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NativeCommitReceipt:
    status: str
    symbol: str
    interval: str
    last_native_open_label: str | None
    newly_closed_native_bars: int
    total_closed_native_bars: int
    manifest_sha256: str | None
    drive_objects_created_max: int
    broker_orders: int = 0


def _batch_from_chunk(chunk: Any) -> NativeFXBatch:
    if (type(chunk) is not dict
            or type(chunk.get("bars")) is not list
            or not chunk["bars"]):
        raise ValueError("P055_ARCHIVE_CHUNK_SCHEMA_INVALID")
    try:
        bars = tuple(NativeFXBar(**r) for r in chunk["bars"])
        return NativeFXBatch(
            symbol=chunk["symbol"], interval=chunk["interval"],
            exchange_timezone=chunk["exchange_timezone"],
            time_reference=chunk["time_reference"],
            closed_bars=bars, incomplete_excluded=0,
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("P055_ARCHIVE_CHUNK_DECODE_FAILED") from exc


def audit_native_archive(
    store: Any, *, symbol: str, interval: str,
) -> NativeArchiveState:
    """Verify ALL staged native pairs, canonical SHA and complete parent chain.

    Bounded by MAX_NATIVE_FILES. Does not assume a real market-session
    calendar; checks structural immutability and source provenance only.
    """
    _scope(symbol,interval)
    names = store.list_names("manifest")
    chunk_names = set(store.list_names("chunk"))
    if len(names) > MAX_NATIVE_FILES or len(chunk_names) > MAX_NATIVE_FILES:
        raise ValueError("P055_ARCHIVE_TOO_LARGE_TO_VERIFY")
    previous: dict[str, Any] | None = None
    referenced: set[str] = set()
    last_name: str | None = None
    labels: set[str] = set()
    for name in names:
        m = store.read("manifest",name)
        if type(m) is not dict:
            raise ValueError("P055_MANIFEST_TYPE_INVALID")
        try:
            check_native_manifest(
                m,symbol=symbol,interval=interval,
                zone=m["exchange_timezone"])
            if name != _name(
                    "manifest",symbol,interval,
                    m["last_native_open_label"],digest(m)):
                raise ValueError("P055_MANIFEST_NAME_SHA_MISMATCH")
            chunk_name = m["chunk_name"]
            if chunk_name not in chunk_names:
                raise ValueError("P055_MISSING_REFERENCED_CHUNK")
            if m["last_native_open_label"] in labels:
                raise ValueError("P055_DUPLICATE_NATIVE_MANIFEST_LABEL")
            labels.add(m["last_native_open_label"])
            raw_chunk = store.read("chunk",chunk_name)
            b = _batch_from_chunk(raw_chunk)
            candidate = plan_native_sealed(b,previous=previous)
            if (candidate is None or candidate.chunk != raw_chunk
                    or candidate.manifest != m
                    or candidate.chunk_name != chunk_name
                    or candidate.manifest_name != name
                    or candidate.chunk_sha256 != m["chunk_sha256"]):
                raise ValueError("P055_HISTORY_CHAIN_OR_CONTENT_MISMATCH")
        except (KeyError, TypeError) as exc:
            raise ValueError("P055_MALFORMED_SEALED_ARCHIVE") from exc
        if chunk_name in referenced:
            raise ValueError("P055_REUSED_CHUNK_REFERENCE")
        referenced.add(chunk_name)
        previous = m
        last_name = name
    orphan_names = tuple(sorted(chunk_names - referenced))
    if len(orphan_names) > 1:
        raise ValueError("P055_MULTIPLE_UNCOMMITTED_NATIVE_CHUNKS")
    return NativeArchiveState(
        last_manifest=previous, latest_manifest_name=last_name,
        manifest_count=len(names),chunk_count=len(chunk_names),
        uncommitted_chunk_names=orphan_names,
    )


def commit_native_batch(
    store: Any, batch: NativeFXBatch,
) -> NativeCommitReceipt:
    """Strict 2-object immutable write with remote readbacks at each stage.

    A single orphan chunk may be recovered only when its exact bytes and
    name match the newly computed sealed candidate. Never deletes/edits.
    """
    if type(batch) is not NativeFXBatch:
        raise ValueError("P055_NATIVE_BATCH_REQUIRED")
    state = audit_native_archive(
        store,symbol=batch.symbol,interval=batch.interval)
    plan = plan_native_sealed(batch,previous=state.last_manifest)
    if plan is None:
        if state.uncommitted_chunk_names:
            raise ValueError("P055_NATIVE_ORPHAN_UNRESOLVED")
        return NativeCommitReceipt(
            status="NO_NEW_CLOSED_NATIVE_BAR",symbol=batch.symbol,
            interval=batch.interval,
            last_native_open_label=(
                state.last_manifest["last_native_open_label"]
                if state.last_manifest else None),
            newly_closed_native_bars=0,
            total_closed_native_bars=(
                state.last_manifest["total_closed_native_bars"]
                if state.last_manifest else 0),
            manifest_sha256=(
                digest(state.last_manifest) if state.last_manifest else None),
            drive_objects_created_max=0,
        )
    verify_native_sealed(plan,previous=state.last_manifest)
    if (state.uncommitted_chunk_names
            and state.uncommitted_chunk_names != (plan.chunk_name,)):
        raise ValueError("P055_UNKNOWN_NATIVE_ORPHAN_QUARANTINE")
    # Only cooperative GitHub concurrency; verify parent immediately before
    # and again after the first Drive object, never claim atomic CAS.
    current = audit_native_archive(
        store,symbol=batch.symbol,interval=batch.interval)
    if current != state:
        raise ValueError("P055_PARENT_CHANGED_BEFORE_NATIVE_WRITE")
    store.put_if_absent("chunk",plan.chunk_name,plan.chunk)
    if store.read("chunk",plan.chunk_name) != plan.chunk:
        raise ValueError("P055_CHUNK_READBACK_MISMATCH")
    after_chunk = audit_native_archive(
        store,symbol=batch.symbol,interval=batch.interval)
    if (after_chunk.last_manifest != state.last_manifest
            or after_chunk.latest_manifest_name != state.latest_manifest_name
            or after_chunk.uncommitted_chunk_names != (plan.chunk_name,)):
        raise ValueError("P055_PARENT_CHANGED_AFTER_CHUNK_WRITE")
    store.put_if_absent("manifest",plan.manifest_name,plan.manifest)
    if store.read("manifest",plan.manifest_name) != plan.manifest:
        raise ValueError("P055_MANIFEST_READBACK_MISMATCH")
    end = audit_native_archive(
        store,symbol=batch.symbol,interval=batch.interval)
    if (end.latest_manifest_name != plan.manifest_name
            or end.last_manifest != plan.manifest
            or end.uncommitted_chunk_names
            or end.manifest_count != state.manifest_count+1):
        raise ValueError("P055_NATIVE_COMMIT_NOT_UNIQUE_LATEST")
    return NativeCommitReceipt(
        status="RECOVERED_ORPHAN_AND_COMMITTED"
               if state.uncommitted_chunk_names else "NATIVE_BATCH_COMMITTED",
        symbol=batch.symbol,interval=batch.interval,
        last_native_open_label=plan.manifest["last_native_open_label"],
        newly_closed_native_bars=plan.newly_closed_bars,
        total_closed_native_bars=plan.manifest["total_closed_native_bars"],
        manifest_sha256=plan.manifest_sha256,
        drive_objects_created_max=(
            1 if state.uncommitted_chunk_names else 2),
    )
