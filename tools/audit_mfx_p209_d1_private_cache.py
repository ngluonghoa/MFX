"""P210: independent GET-only verification and private as-of D1 cache reader."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
import os
import json
import re
from typing import Any
from zoneinfo import ZoneInfo

from mfx_cache.native_d1_epoch_20261118 import (
    FreshEpochState, PrivateD1FreshEpochStore, audit_fresh_epoch,
    PUBLICATION_BUFFER,
)
from mfx_cache.native_fx_htf import NativeFXBar
from mfx_cache.native_htf_archive import _bar_valid
from mfx_cache.p209_d1_revision_snapshot_cache import (
    PREFIX, SCHEMA, PrivateP209D1Store,
)
from mfx_cache.td_m5_codec import digest
from tools.mfx_native_htf_drive_seal import (
    MAX_NATIVE_FILES, PrivateNativeDriveStore, audit_native_archive,
)
from tools.run_a04_p45_cloud_twelve_data_cache import (
    _drive_auth_info, _require_oauth_cache_folders, _session,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FIXED: dict[str, Any] = {
    "schema": SCHEMA,
    "state": "PRIVATE_QUARANTINE_NOT_CANONICAL",
    "owner_cache_collection_authorized": True,
    "vendor_retention_rights_verified": False,
    "publisher_first_known_verified": False,
    "owner_canonical_revision_approved": False,
    "source_admission": False,
    "may_overwrite_canonical": False,
    "may_publish_buy_sell": False,
    "may_trade": False,
    "broker_orders": 0,
}
_CORE_KEYS = set(_FIXED) | {
    "original_manifest_sha256", "original_bar_sha256", "revised_bar_sha256",
    "rows", "row_sha256",
}
_KEYS = _CORE_KEYS | {
    "identity_sha256", "first_runner_observed_utc", "record_sha256",
}


def _utc(value: Any) -> datetime:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P210_UTC_REQUIRED")
    return value


def _parent(state: FreshEpochState) -> tuple[str, str]:
    manifest = state.last_manifest
    if (type(state) is not FreshEpochState or state.manifests != 1
            or state.chunks != 1 or state.orphan_chunk is not None
            or type(manifest) is not dict
            or manifest.get("total_closed_bars") != 1
            or manifest.get("last_native_open_label") != "2026-11-18"):
        raise ValueError("P210_EXACT_ORIGINAL_P192_ROOT_REQUIRED")
    index = manifest.get("recent_native_bar_index")
    if (type(index) is not list or len(index) != 1
            or type(index[0]) is not dict
            or index[0].get("label") != "2026-11-18"
            or type(index[0].get("sha256")) is not str
            or not _SHA.fullmatch(index[0]["sha256"])):
        raise ValueError("P210_ORIGINAL_ROW_SHA_REQUIRED")
    return digest(manifest), index[0]["sha256"]


@dataclass(frozen=True, slots=True, repr=False)
class PrivateSnapshot:
    observed: datetime
    rows: tuple[NativeFXBar, ...] = field(repr=False)
    identity: str = field(repr=False)


def verify_snapshot(
    name: str, value: Any, *, parent: tuple[str, str], now_utc: datetime,
) -> PrivateSnapshot:
    now = _utc(now_utc)
    if type(value) is not dict or set(value) != _KEYS:
        raise ValueError("P210_EXACT_RECORD_SCHEMA")
    if any(type(value[k]) is not type(v) or value[k] != v
           for k, v in _FIXED.items()):
        raise ValueError("P210_AUTHORITY_DRIFT")
    if (value["original_manifest_sha256"], value["original_bar_sha256"]) != parent:
        raise ValueError("P210_PARENT_SHA_DRIFT")
    core = {k: value[k] for k in _CORE_KEYS}
    identity = digest(core)
    if (value["identity_sha256"] != identity
            or name != PREFIX + identity + ".json"
            or value["record_sha256"] != digest({
                k: v for k, v in value.items() if k != "record_sha256"
            })):
        raise ValueError("P210_RECORD_OR_FILENAME_SHA_DRIFT")
    observed = value["first_runner_observed_utc"]
    if type(observed) is not str:
        raise ValueError("P210_INVALID_OBSERVATION")
    stamp = _utc(datetime.fromisoformat(observed))
    if stamp.isoformat() != observed or stamp > now:
        raise ValueError("P210_INVALID_OBSERVATION")
    if type(value["rows"]) is not list or not 1 <= len(value["rows"]) <= 120:
        raise ValueError("P210_ROW_COUNT")
    rows = tuple(NativeFXBar(**raw) for raw in value["rows"])
    eligible = (stamp-PUBLICATION_BUFFER).astimezone(
        ZoneInfo("Australia/Sydney")).date()-timedelta(days=1)
    for row, raw in zip(rows, value["rows"]):
        _bar_valid(row, symbol="EUR/USD", interval="1day", zone="Australia/Sydney")
        if (asdict(row) != raw or date.fromisoformat(row.native_open_label) > eligible):
            raise ValueError("P210_ROW_SCHEMA_OR_UNCLOSED_AT_OBSERVATION")
    labels = [row.native_open_label for row in rows]
    hashes = [row.sha256() for row in rows]
    if (labels[0] != "2026-11-18" or labels != sorted(set(labels))
            or hashes != value["row_sha256"]
            or hashes[0] != value["revised_bar_sha256"]
            or hashes[0] == parent[1]):
        raise ValueError("P210_ROW_ORDER_OR_SHA_DRIFT")
    return PrivateSnapshot(stamp, rows, identity)


def read_private_snapshots(
    store: Any, *, original: FreshEpochState,
    now_utc: datetime, asof_utc: datetime,
) -> tuple[dict[str, Any], PrivateSnapshot | None]:
    """Audit every bounded object; choose only observed-at-or-before asof.

    Private research observation, never an original publisher as-of claim.
    No object returned to a canonical D1 strategy or public log.
    """
    now = _utc(now_utc)
    asof = _utc(asof_utc)
    if asof > now:
        raise ValueError("P210_ASOF_AFTER_AUDIT")
    parent = _parent(original)
    names = store.list_names("chunk")
    if (type(names) is not tuple or len(names) > MAX_NATIVE_FILES
            or any(type(n) is not str or not n.startswith(PREFIX) for n in names)
            or len(names) != len(set(names))):
        raise ValueError("P210_INVALID_NAMESPACE_LIST")
    snapshots = [
        verify_snapshot(name, store.read("chunk", name), parent=parent, now_utc=now)
        for name in names
    ]
    if store.list_names("chunk") != names:
        raise ValueError("P210_LIST_CHANGED_DURING_AUDIT")
    eligible = [snapshot for snapshot in snapshots if snapshot.observed <= asof]
    selected = max(eligible, key=lambda x: x.observed) if eligible else None
    if selected is not None and sum(
            x.observed == selected.observed for x in eligible) != 1:
        raise ValueError("P210_AMBIGUOUS_OBSERVATION_CLOCK")
    return ({
        "status": ("P210_PRIVATE_D1_INDEPENDENT_READONLY_SHA_PASS" if selected
                   else "P210_NO_SNAPSHOT_VISIBLE_AT_ASOF"),
        "snapshot_objects_verified": len(snapshots),
        "private_selected_closed_rows": len(selected.rows) if selected else 0,
        "original_p192_sha_preserved": True,
        "publisher_first_known_verified": False,
        "vendor_retention_rights_verified": False,
        "canonical_source_selected": False,
        "source_admission": False,
        "provider_price_requests": 0,
        "drive_writes": 0,
        "may_publish_buy_sell": False,
        "action": "NO_SIGNAL",
        "broker_orders": 0,
    }, selected)


def main() -> None:
    if (os.environ.get("MFX_REAL_CACHE_ENABLED") != "true"
            or os.environ.get("MFX_V2_BATCH_CACHE_ACCEPTED") != "true"
            or os.environ.get("MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED") != "true"
            or os.environ.get("MFX_D1_OWNER_CUTOFF_20261118") != "true"):
        print("MFX_P210_READONLY_GATE_DISABLED")
        return
    try:
        auth = _drive_auth_info()
        _require_oauth_cache_folders(auth)
        session = _session(auth)
        now = datetime.now(timezone.utc)
        legacy = audit_native_archive(
            PrivateNativeDriveStore(session, symbol="EUR/USD", interval="1day"),
            symbol="EUR/USD", interval="1day",
        )
        if legacy.last_manifest is None or legacy.uncommitted_chunk_names:
            raise ValueError("P210_LEGACY_ROOT_NOT_SEALED")
        original = audit_fresh_epoch(
            PrivateD1FreshEpochStore(session), origin_v1_sha=digest(legacy.last_manifest),
        )
        receipt, _ = read_private_snapshots(
            PrivateP209D1Store(session), original=original, now_utc=now, asof_utc=now,
        )
    except Exception:
        # Do not expose private raw rows, identities or OAuth exception bodies.
        raise RuntimeError("P210_PRIVATE_READONLY_AUDIT_FAILED") from None
    print("MFX_P210_PRIVATE_D1_READONLY_RESULT")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
