"""A04/P0.46-B1 — staged private GitHub hourly Twelve Data→Drive writer.

OFF unless BOTH separate repository variables are explicitly true. This uses
a service-account credential on GitHub Actions, NOT ChatGPT MCP OAuth.
No local files, live signals, brokers, or Forex source numeric promotion.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any

from mfx_cache.v2_batch_commit import (
    CHUNK_PREFIX, MANIFEST_PREFIX, MAX_LIST, PrivateObjectStore,
    _last_manifest, commit_hour,
)
from mfx_cache.v2_warm_promotion import WARM_PREFIX, PROMOTION_PREFIX
from mfx_cache.td_m5_codec import parse_closed_utc_m5
from tools.mfx_hourly_catchup import (
    plan_bounded_catchup, commit_bounded_catchup,
    latest_eligible_closed_hour,
)
from tools.run_a04_p45_cloud_twelve_data_cache import (
    CHUNK_FOLDER, MANIFEST_FOLDER, _drive_create, _drive_get, _session,
    _settings, _vendor_m5, _vendor_usage,
)


class PrivateDriveBatchStore(PrivateObjectStore):
    """Bounded paginated folder reads; exact name & bytes verified.

    Drive multi-file atomic CAS does NOT exist. One GitHub concurrency group
    plus every-run rechecks prevent cooperative, not adversarial races.
    """
    def __init__(self, session: Any) -> None:
        self._session = session
        self._ids: dict[tuple[str, str], str] = {}

    @staticmethod
    def _folder(bucket: str) -> tuple[str, str]:
        if bucket == "chunk":
            return CHUNK_FOLDER, CHUNK_PREFIX
        if bucket == "manifest":
            return MANIFEST_FOLDER, MANIFEST_PREFIX
        if bucket == "warm":
            return CHUNK_FOLDER, WARM_PREFIX
        if bucket == "promotion":
            return MANIFEST_FOLDER, PROMOTION_PREFIX
        raise ValueError("P046_B1_UNAUTHORIZED_DRIVE_BUCKET")

    def list_names(self, bucket: str) -> tuple[str, ...]:
        folder, prefix = self._folder(bucket)
        records: dict[str, str] = {}
        page_token: str | None = None
        pages = 0
        while True:
            pages += 1
            if pages > 15:
                raise ValueError("P046_B1_DRIVE_LIST_TOO_LARGE_FAIL_CLOSED")
            parameters = {
                "q": (f"'{folder}' in parents and name contains "
                      f"'{prefix}' and trashed = false"),
                "pageSize": 1000,
                "fields": "nextPageToken,files(id,name,mimeType,parents)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if page_token is not None:
                parameters["pageToken"] = page_token
            response = self._session.get(
                "https://www.googleapis.com/drive/v3/files",
                params=parameters, timeout=45,
            )
            response.raise_for_status()
            data = response.json()
            if (not isinstance(data, dict)
                    or not isinstance(data.get("files"), list)):
                raise ValueError("P046_B1_INVALID_PRIVATE_DRIVE_LIST")
            for item in data["files"]:
                if (not isinstance(item, dict)
                        or type(item.get("id")) is not str
                        or type(item.get("name")) is not str
                        or item.get("mimeType") != "application/json"
                        or not item["name"].startswith(prefix)
                        or folder not in item.get("parents", [])):
                    raise ValueError("P046_B1_UNEXPECTED_DRIVE_OBJECT")
                if item["name"] in records:
                    raise ValueError("P046_B1_DUPLICATE_NAME_DRIVE_FORK")
                records[item["name"]] = item["id"]
                if len(records) > MAX_LIST:
                    raise ValueError("P046_B1_DRIVE_LIST_BOUNDED")
            token = data.get("nextPageToken")
            if token is None:
                break
            if type(token) is not str or not token:
                raise ValueError("P046_B1_DRIVE_PAGE_TOKEN_INVALID")
            page_token = token
        for name, file_id in records.items():
            self._ids[(bucket, name)] = file_id
        return tuple(sorted(records))

    def read(self, bucket: str, name: str) -> dict[str, Any]:
        if (bucket, name) not in self._ids:
            self.list_names(bucket)
        ident = self._ids.get((bucket, name))
        if ident is None:
            raise ValueError("P046_B1_REQUIRED_PRIVATE_OBJECT_MISSING")
        value = _drive_get(self._session, ident)
        if not isinstance(value, dict):
            raise ValueError("P046_B1_INVALID_DRIVE_JSON_READBACK")
        return value

    def put_if_absent(
        self, bucket: str, name: str, body: dict[str, Any],
    ) -> None:
        folder, prefix = self._folder(bucket)
        if not name.startswith(prefix):
            raise ValueError("P046_B1_UNAUTHORIZED_DRIVE_NAME")
        self.list_names(bucket)
        if (bucket, name) in self._ids:
            if self.read(bucket, name) != body:
                raise ValueError("P046_B1_EXISTING_DRIVE_OBJECT_MUTATED")
            return
        file_id = _drive_create(self._session, folder, name, body)
        self._ids[(bucket, name)] = file_id
        if self.read(bucket, name) != body:
            raise ValueError("P046_B1_NEW_DRIVE_READBACK_MISMATCH")


def needs_hourly_fetch(store: PrivateObjectStore, now: datetime) -> bool:
    """Keep 5m publication grace, but allow older CLOSED-hour catchup at :00..:04.

    GitHub's scheduled runner may arrive late in the next hour at minute 00-04.
    Blanket minute<5 skip silently strands old immutable M5 hours forever.
    Preserve original first-boot no-fetch-before-:05 behavior.
    """
    if (type(now) is not datetime or now.tzinfo is None
            or now.utcoffset() != timedelta(0)):
        raise ValueError("P067_M5_WRITER_EXACT_UTC_REQUIRED")
    _, previous = _last_manifest(store)
    if previous is None and now.minute < 5:
        return False
    latest_eligible = latest_eligible_closed_hour(now)
    if previous is None:
        return True
    return datetime.fromisoformat(previous["hour_utc"]) < latest_eligible


def quota_headroom(used: int, limit: int, local_cap: int) -> tuple[bool, int]:
    """Reserve at most ten provider credits without blocking 8-credit plans.

    /api_usage reports provider-side usage; the local cap is an additional
    safety ceiling, not a substitute for provider daily-plan accounting.
    Fail closed on malformed usage instead of assuming spare credits.
    """
    if (type(used) is not int or type(limit) is not int
            or type(local_cap) is not int or used < 0
            or limit <= 0 or local_cap <= 0):
        raise ValueError("P046_B1_PROVIDER_USAGE_INVALID")
    reserve = min(10, max(1, limit // 8))
    threshold = min(local_cap, limit - reserve)
    return used < threshold, threshold


def main() -> None:
    # Separate activation gate intentionally protects against prior P045
    # MFX_REAL_CACHE_ENABLED already being configured.
    if (os.environ.get("MFX_REAL_CACHE_ENABLED") != "true"
            or os.environ.get("MFX_V2_BATCH_CACHE_ACCEPTED") != "true"):
        print("MFX_A04_P46_B1_CLOUD_BATCH_DISABLED_DUAL_GATE")
        return
    now = datetime.now(timezone.utc)
    api_key, sa, cap = _settings()
    store = PrivateDriveBatchStore(_session(sa))

    # Recover a previously uploaded immutable chunk even if vendor is down.
    replay = commit_hour(store, now_utc=now)
    if replay.recovered_orphan:
        print(json.dumps({
            "status": replay.status,
            "hour_utc": replay.committed_hour_utc,
            "new_vendor_requests": 0,
            "new_confirmed_market_signals": 0,
            "broker_orders": 0,
        }, sort_keys=True))
        return
    if not needs_hourly_fetch(store, now):
        print("MFX_A04_P46_B1_UTC_HOUR_ALREADY_COMMITTED_NO_API_CALL")
        return
    used, limit = _vendor_usage(api_key)
    has_headroom, threshold = quota_headroom(used, limit, cap)
    if not has_headroom:
        print("MFX_A04_P46_B1_PROVIDER_QUOTA_HEADROOM_NO_PRICE_REQUEST")
        print(json.dumps({
            "current_usage": used, "plan_limit": limit,
            "configured_cap": cap, "safe_fetch_threshold": threshold,
            "price_requests": 0, "broker_orders": 0,
        }, sort_keys=True))
        return
    print("MFX_A04_P46_B1_PROVIDER_QUOTA_PREFLIGHT_PASS")
    print(json.dumps({
        "current_usage": used, "plan_limit": limit,
        "configured_cap": cap, "safe_fetch_threshold": threshold,
    }, sort_keys=True))
    # Use 120 rows to tolerate runner delay. The pure planner keeps ONLY
    # the exactly 12 CLOSED bars from the prior full UTC hour.
    vendor_payload = _vendor_m5(api_key, bootstrap=True)
    rows = parse_closed_utc_m5(vendor_payload, now_utc=now)
    _, previous = _last_manifest(store)
    batches = plan_bounded_catchup(
        rows,
        previous_hour_utc=previous["hour_utc"] if previous else None,
        now_utc=now,
    )
    accepted = commit_bounded_catchup(store, batches, real_now_utc=now)
    print(json.dumps({
        "status": ("BATCHES_COMMITTED" if len(accepted) > 1 else
                   "BATCH_COMMITTED" if accepted else
                   "NOT_DUE_OR_INCOMPLETE_HOUR"),
        "hour_utc": accepted[-1].committed_hour_utc if accepted else None,
        "committed_hours_utc": [r.committed_hour_utc for r in accepted],
        "committed_batches": len(accepted),
        "m5_bars_in_batch": 12 if len(accepted) == 1 else 0,
        "m5_bars_total": sum(r.new_closed_m5 for r in accepted),
        "max_recovery_batches_per_run": 4,
        "vendor_price_requests": 1,
        "source": "TWELVE_DATA_COMPOSITE_MID",
        "utc_only": True,
        "user_signals": 0,
        "broker_orders": 0,
        "license_scope_verified": False,
        "fully_automatic_forex_signal_ready": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
