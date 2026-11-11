"""MFX A04/P0.60 — independent private Drive native H4/D1 planner PREVIEW.

Reads sealed archive data and prints a bounded per-interval decision. There is
NO Twelve Data key, NO vendor calls, NO Drive writes, NO trader, NO new gate.
Do not mistake this preview for provider proof or an authorized source write.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any

from mfx_cache.td_m5_codec import digest
from mfx_cache.native_htf_incremental import (
    NATIVE_INTERVALS, SYMBOL, plan_native_fetch,
)
from tools.mfx_native_htf_drive_seal import (
    PrivateNativeDriveStore, audit_native_archive,
    native_append_slots_remaining,
)
from tools.run_a04_p45_cloud_twelve_data_cache import (
    _drive_auth_info, _require_oauth_cache_folders, _session,
)


def preview_incremental_native_cache(
    stores: dict[str,Any], *, now_utc: datetime,
) -> dict[str,Any]:
    """Read-only full archive SHA checks BEFORE previewing ANY TF.

    Do not mark lag as a Forex session violation. A calendar slot is a
    potential source request, not a guarantee that the provider published a
    new candle. Every plan is advisory only.
    """
    if set(stores) != set(NATIVE_INTERVALS):
        raise ValueError("P060_PREVIEW_REQUIRES_H4_D1")
    snapshots: list[tuple[str,Any]] = []
    for interval in NATIVE_INTERVALS:
        state = audit_native_archive(
            stores[interval],symbol=SYMBOL,interval=interval)
        if state.last_manifest is None:
            raise ValueError("P060_PREVIEW_NATIVE_CACHE_NOT_BOOTSTRAPPED")
        if state.uncommitted_chunk_names:
            raise ValueError("P060_PREVIEW_UNCOMMITTED_NATIVE_CHUNK")
        snapshots.append((interval,state))
    reports: list[dict[str,Any]] = []
    for interval,state in snapshots:
        plan = plan_native_fetch(
            interval=interval,previous=state.last_manifest,
            now_utc=now_utc)
        room = native_append_slots_remaining(state)
        capacity_blocked = bool(plan.provider_requests_planned and room < 1)
        reports.append({
            "symbol":SYMBOL,
            "interval":interval,
            "decision":("NATIVE_ARCHIVE_CAPACITY_BLOCKED_NO_VENDOR_CALL"
                        if capacity_blocked else plan.status),
            "archive_append_slots_remaining":room,
            "source_fetch_blocked_by_capacity":capacity_blocked,
            "last_native_open_label":plan.last_native_open_label,
            "latest_expected_closed_label":plan.latest_expected_closed_label,
            "calendar_slots_behind":plan.calendar_slots_behind,
            "overlap_sha_bars":plan.overlap_bar_count,
            "requested_outputsize_if_approved":(
                int(plan.request["outputsize"])
                if plan.request is not None and not capacity_blocked else None),
            "provider_price_requests_if_approved":(
                0 if capacity_blocked else plan.provider_requests_planned),
            "current_manifest_sha256":digest(state.last_manifest),
        })
    return {
        "status":"READONLY_NATIVE_INCREMENTAL_PREVIEW",
        "symbol":SYMBOL,
        "intervals":reports,
        "total_price_requests_if_approved":sum(
            x["provider_price_requests_if_approved"] for x in reports),
        "read_only":True,
        "real_provider_price_requests":0,
        "real_provider_usage_requests":0,
        "drive_writes":0,
        "new_authorization_gate_required_for_writer":
            "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED",
        "automatic_native_writer_enabled":False,
        "broker_orders":0,
        "raw_ohlc_in_logs":False,
    }


def main() -> None:
    if (os.environ.get("MFX_REAL_CACHE_ENABLED") != "true"
            or os.environ.get("MFX_V2_BATCH_CACHE_ACCEPTED") != "true"
            or os.environ.get("MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED") != "true"):
        print("MFX_A04_P60_PREVIEW_DISABLED_EXISTING_THREE_GATES")
        return
    auth = _drive_auth_info()
    _require_oauth_cache_folders(auth)
    sess = _session(auth)
    stores = {
        interval:PrivateNativeDriveStore(
            sess,symbol=SYMBOL,interval=interval)
        for interval in NATIVE_INTERVALS
    }
    receipt = preview_incremental_native_cache(
        stores,now_utc=datetime.now(timezone.utc))
    print("MFX_A04_P60_NATIVE_INCREMENTAL_READONLY_PREVIEW_PASS")
    print(json.dumps(receipt,sort_keys=True))


if __name__=="__main__":
    main()
