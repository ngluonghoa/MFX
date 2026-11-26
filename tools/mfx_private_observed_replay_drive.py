"""P221: bounded metadata join in the existing owner-gated GET-only probe.

No new dispatch, scheduling, credentials, writer, or provider calls.
Only current Drive metadata proxies, never historical source first-known.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any

from mfx_cache.native_htf_archive import _scope
from mfx_cache.p209_d1_revision_snapshot_cache import PREFIX as REVISED_PREFIX
from mfx_cache.v2_batch_commit import CHUNK_PREFIX, MANIFEST_PREFIX
from mfx_research.p219_m5_archive_time_prefixes import ObservedObjectTime
from mfx_research.p220_private_observed_six_tf import (
    PrivateObservedReplay, replay_private_observed_six_tf,
)
from mfx_research.six_tf_sealed_archive_consumer import (
    ReadOnlyObjectStore, SealedArchiveSixTFReceipt,
)
from tools.mfx_m5_rolling_manifest_audit import MAX_ROOTED_MANIFESTS
from tools.mfx_native_htf_drive_seal import MAX_NATIVE_FILES
from tools.run_a04_p45_cloud_twelve_data_cache import CHUNK_FOLDER, MANIFEST_FOLDER

_H4 = _scope("EUR/USD", "4h")
_SCOPES = {
    "m5_manifests": (MANIFEST_FOLDER, MANIFEST_PREFIX, MAX_ROOTED_MANIFESTS),
    "m5_chunks": (CHUNK_FOLDER, CHUNK_PREFIX, MAX_ROOTED_MANIFESTS),
    "h4_manifests": (MANIFEST_FOLDER, _H4 + "_manifest_", MAX_NATIVE_FILES),
    "h4_chunks": (CHUNK_FOLDER, _H4 + "_chunk_", MAX_NATIVE_FILES),
    "revised_d1_times": (CHUNK_FOLDER, REVISED_PREFIX, MAX_NATIVE_FILES),
}
_ID = re.compile(r"^[A-Za-z0-9_-]{8,160}$")
MAX_PAGES = 15
RECENT_COMMITS = 2


def _clock(value: Any) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise ValueError("P221_DRIVE_UTC_TIMESTAMP_REQUIRED")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _metadata(session: Any, scope: str) -> tuple[tuple[str, ObservedObjectTime], ...]:
    if scope not in _SCOPES:
        raise ValueError("P221_FIXED_METADATA_SCOPE_REQUIRED")
    folder, prefix, limit = _SCOPES[scope]
    records: dict[str, tuple[str, ObservedObjectTime]] = {}
    ids: set[str] = set()
    tokens: set[str] = set()
    token = None
    for _ in range(MAX_PAGES):
        params = {
            "q": f"'{folder}' in parents and name contains '{prefix}' and trashed = false",
            "pageSize": 1000,
            "fields": "nextPageToken,incompleteSearch,files(id,name,mimeType,parents,createdTime,modifiedTime)",
            "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
        }
        if token is not None:
            params["pageToken"] = token
        response = session.get("https://www.googleapis.com/drive/v3/files",
                               params=params, timeout=45)
        response.raise_for_status()
        data = response.json()
        if (type(data) is not dict or type(data.get("files")) is not list
                or data.get("incompleteSearch", False) is not False):
            raise ValueError("P221_INCOMPLETE_METADATA_LIST")
        for item in data["files"]:
            if (type(item) is not dict or type(item.get("id")) is not str
                    or _ID.fullmatch(item["id"]) is None
                    or type(item.get("name")) is not str
                    or not item["name"].startswith(prefix)
                    or item.get("mimeType") != "application/json"
                    or type(item.get("parents")) is not list
                    or folder not in item["parents"]):
                raise ValueError("P221_METADATA_SCOPE_DRIFT")
            name, ident = item["name"], item["id"]
            if name in records or ident in ids:
                raise ValueError("P221_DUPLICATE_METADATA_OBJECT")
            ids.add(ident)
            records[name] = (ident, ObservedObjectTime(
                name, _clock(item.get("createdTime")), _clock(item.get("modifiedTime"))))
            if len(records) > limit:
                raise ValueError("P221_BOUNDED_METADATA_LIST")
        token = data.get("nextPageToken")
        if token is None:
            return tuple(records[k] for k in sorted(records))
        if type(token) is not str or not token or token in tokens:
            raise ValueError("P221_PAGINATION_TOKEN_INVALID")
        tokens.add(token)
    raise ValueError("P221_METADATA_PAGE_LIMIT")


def _decisions(items: tuple[ObservedObjectTime, ...], now: datetime) -> tuple[datetime, ...]:
    if (type(now) is not datetime or now.tzinfo is None
            or now.utcoffset() != timedelta(0) or not items
            or any(x.created_utc > now for x in items)):
        raise ValueError("P221_REAL_METADATA_CLOCK_REQUIRED")
    recent = sorted({x.created_utc for x in items})[-RECENT_COMMITS:]
    return tuple(sorted({now, *recent, *(x-timedelta(microseconds=1) for x in recent)}))


def observed_replay_in_existing_probe(
    session: Any, evidence: SealedArchiveSixTFReceipt,
    m5: ReadOnlyObjectStore, h4: ReadOnlyObjectStore,
    original: ReadOnlyObjectStore, revised: ReadOnlyObjectStore,
    *, asof_utc: datetime,
) -> PrivateObservedReplay:
    if (evidence.active_d1_source_epoch != "P192_D1_FRESH_20261118"
            or not evidence.github_reviewed_m5_anchors_checked
            or evidence.technical.action != "NO_SIGNAL"
            or evidence.technical.stage != "UNVERIFIED"
            or evidence.may_publish_buy_sell or evidence.may_trade):
        raise ValueError("P221_OWNER_SELECTED_PRIVATE_EPOCH_REQUIRED")
    before = {k: _metadata(session, k) for k in _SCOPES}
    times = {k: tuple(x[1] for x in v) for k, v in before.items()}
    for key, count, tip in (
        ("m5_manifests", evidence.m5_total_archived_manifest_pairs,
         evidence.m5_manifest_tip_sha256),
        ("h4_manifests", evidence.h4_manifest_pairs_full_sha,
         evidence.h4_manifest_tip_sha256),
    ):
        items = times[key]
        if len(items) != count or not items or not items[-1].name.endswith("_" + tip + ".json"):
            raise ValueError("P221_CANONICAL_ARCHIVE_TIP_DRIFT")
    replay = replay_private_observed_six_tf(
        m5, h4, original, revised, **times,
        decisions_utc=_decisions(times["m5_manifests"], asof_utc),
        audited_at_utc=asof_utc)
    if (replay.fixture_anchors_used or replay.m5_pairs_metadata_checked !=
            evidence.m5_total_archived_manifest_pairs
            or replay.h4_pairs_verified != evidence.h4_manifest_pairs_full_sha
            or {k: _metadata(session, k) for k in _SCOPES} != before):
        raise ValueError("P221_REPLAY_SCOPE_OR_METADATA_DRIFT")
    return replay
