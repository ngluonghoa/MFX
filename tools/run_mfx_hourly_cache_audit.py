"""A04/P0.50 — hourly read-only verification of private sealed Forex cache.

No provider requests, no cache writes, no numeric BUY/SELL signals, no broker.
A short tail is independently validated; full-history verification is NOT claimed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any

from mfx_cache.td_m5_codec import digest
from mfx_cache.v2_batch_commit import (
    CHUNK_PREFIX, MANIFEST_PREFIX, PrivateObjectStore,
    _validate_chunk, _validate_manifest,
)
from tools.run_a04_p45_cloud_twelve_data_cache import (
    _drive_auth_info, _require_oauth_cache_folders, _session,
)
from tools.run_a04_p46_cloud_batch_cache import PrivateDriveBatchStore

AUDIT_WINDOW = 3


def audit_recent_cache(
    store: PrivateObjectStore, *, now_utc: datetime,
) -> dict[str, Any]:
    """Verify last <=3 manifest/chunk SHA links without reading vendor data."""
    if (type(now_utc) is not datetime or now_utc.tzinfo is None
            or now_utc.utcoffset() != timedelta(0)):
        raise ValueError("P050_AUDIT_REQUIRES_UTC")

    manifests = tuple(sorted(store.list_names("manifest")))
    chunks = set(store.list_names("chunk"))
    if not manifests:
        raise ValueError("P050_NO_SEALED_MANIFEST_YET")
    if len(set(manifests)) != len(manifests):
        raise ValueError("P050_DUPLICATE_MANIFEST_NAMES")
    hours = [name[len(MANIFEST_PREFIX):len(MANIFEST_PREFIX)+13]
             for name in manifests]
    if (any(not name.startswith(MANIFEST_PREFIX) for name in manifests)
            or len(set(hours)) != len(hours)):
        raise ValueError("P050_DUPLICATE_OR_UNKNOWN_MANIFEST_HOUR")

    recent_names = manifests[-AUDIT_WINDOW:]
    previous: dict[str, Any] | None = None
    latest: dict[str, Any] | None = None
    for name in recent_names:
        manifest = store.read("manifest", name)
        _validate_manifest(name, manifest)
        chunk_name = manifest["chunk_name"]
        if chunk_name not in chunks or not chunk_name.startswith(CHUNK_PREFIX):
            raise ValueError("P050_MANIFEST_CHUNK_NOT_LISTED")
        chunk = store.read("chunk", chunk_name)
        _validate_chunk(chunk_name, chunk)
        if (digest(chunk) != manifest["chunk_sha256"]
                or chunk["hour_utc"] != manifest["hour_utc"]
                or chunk["parent_manifest_sha256"] !=
                manifest["parent_manifest_sha256"]):
            raise ValueError("P050_CHUNK_MANIFEST_SHA_OR_PARENT_MISMATCH")
        if previous is not None:
            before = datetime.fromisoformat(previous["hour_utc"])
            after = datetime.fromisoformat(manifest["hour_utc"])
            elapsed = (after-before).total_seconds()
            if elapsed <= 0 or elapsed % 3600:
                raise ValueError("P050_UNORDERED_MANIFEST_HOURS")
            gap = int(elapsed//3600)-1
            if (manifest["parent_manifest_sha256"] != digest(previous)
                    or manifest["total_batches"] != previous["total_batches"]+1
                    or manifest["gap_prior_hours_unverified"] != gap
                    or manifest["continuity_status"] != (
                        "MISSING_PRIOR_HOURS_UNVERIFIED"
                        if gap else "CONTIGUOUS_WITH_PRIOR_BATCH")):
                raise ValueError("P050_BROKEN_MANIFEST_PARENT_OR_CONTINUITY")
        elif len(manifests) == 1:
            if (manifest["parent_manifest_sha256"] is not None
                    or manifest["total_batches"] != 1
                    or manifest["continuity_status"] !=
                    "BOOTSTRAP_HISTORY_UNVERIFIED"):
                raise ValueError("P050_INVALID_ROOT_MANIFEST")
        previous = manifest
        latest = manifest
    assert latest is not None

    latest_time = datetime.fromisoformat(latest["hour_utc"])
    target_time = (now_utc.replace(minute=0, second=0, microsecond=0)
                   - timedelta(hours=1))
    difference_seconds = (target_time-latest_time).total_seconds()
    if difference_seconds < 0 or difference_seconds % 3600:
        raise ValueError("P050_FUTURE_OR_UNALIGNED_MANIFEST_HOUR")
    lag_hours = int(difference_seconds//3600)

    return {
        "status": "FRESH_LAST_CLOSED_HOUR" if lag_hours == 0
                  else "LAGGING_OR_MARKET_CLOSED_NEEDS_REVIEW",
        "last_manifest_hour_utc": latest["hour_utc"],
        "last_hour_lag": lag_hours,
        "latest_continuity_status": latest["continuity_status"],
        "manifest_count": len(manifests),
        "chunk_count": len(chunks),
        "audited_manifest_chunk_pairs": len(recent_names),
        "full_history_audited": len(manifests) <= AUDIT_WINDOW,
        "total_closed_m5": latest["total_closed_m5"],
        "last_manifest_sha256": digest(latest),
        "source": "TWELVE_DATA_COMPOSITE_MID",
        "read_only": True,
        "twelve_data_api_calls": 0,
        "broker_orders": 0,
        "live_signals": 0,
    }


def main() -> None:
    if (os.environ.get("MFX_REAL_CACHE_ENABLED") != "true"
            or os.environ.get("MFX_V2_BATCH_CACHE_ACCEPTED") != "true"):
        print("MFX_A04_P50_AUDIT_DISABLED_DUAL_GATE")
        return
    auth = _drive_auth_info()
    _require_oauth_cache_folders(auth)
    store = PrivateDriveBatchStore(_session(auth))
    receipt = audit_recent_cache(store, now_utc=datetime.now(timezone.utc))
    print("MFX_A04_P50_READONLY_DRIVE_CACHE_AUDIT_PASS")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
