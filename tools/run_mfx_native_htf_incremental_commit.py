"""A04/P0.59 — gated MANUAL-only incremental native EUR/USD H4/D1 writer.

Preflight and SHA check both archives BEFORE vendor calls. Skip intervals
without new fully closed slots; always check full provider overlap SHA before
ANY Drive write. Immutable write is still delegated to existing P0.55
idempotent Chunk+Manifest commit. No H4/D1 cron or broker.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from typing import Any

from mfx_cache.native_fx_htf import parse_native_forex
from mfx_cache.native_htf_archive import plan_native_sealed, verify_native_sealed
from mfx_cache.native_htf_incremental import (
    NATIVE_INTERVALS, SYMBOL, plan_native_fetch,
    validate_incremental_source,
)
from tools.mfx_native_htf_drive_seal import (
    PrivateNativeDriveStore, audit_native_archive, commit_native_batch,
)
from tools.run_a04_p45_cloud_twelve_data_cache import _settings, _session
from tools.run_a04_p46_cloud_batch_cache import quota_headroom
from tools.run_mfx_native_htf_probe import _usage, _read_payload, TIME_SERIES_URL


def main() -> None:
    if (os.environ.get("MFX_REAL_CACHE_ENABLED") != "true"
            or os.environ.get("MFX_V2_BATCH_CACHE_ACCEPTED") != "true"
            or os.environ.get("MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED") != "true"
            or os.environ.get("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED") != "true"):
        print("MFX_A04_P59_INCREMENTAL_DISABLED_EXPLICIT_FOUR_GATE")
        return

    key, auth, cap = _settings()
    now = datetime.now(timezone.utc)
    session = _session(auth)
    archives: list[tuple[str, Any, Any, Any]] = []
    for interval in NATIVE_INTERVALS:
        store = PrivateNativeDriveStore(session,symbol=SYMBOL,interval=interval)
        archive = audit_native_archive(store,symbol=SYMBOL,interval=interval)
        if archive.uncommitted_chunk_names:
            # One orphan might be recoverable in the legacy writer, but
            # this *incremental* approval does not allow ambiguous resume.
            raise ValueError("P059_ORPHAN_REQUIRES_SEPARATE_RECOVERY")
        plan = plan_native_fetch(
            interval=interval, previous=archive.last_manifest, now_utc=now)
        archives.append((interval,store,archive,plan))
    due = [a for a in archives if a[3].provider_requests_planned]
    if not due:
        print("MFX_A04_P59_NATIVE_NO_NEW_CLOSED_SLOTS_ZERO_VENDOR_CALLS")
        print(json.dumps({
            "status":"NO_NATIVE_CLOSED_SLOTS_DUE",
            "provider_price_requests":0,"provider_usage_requests":0,
            "drive_writes":0,"broker_orders":0,
        },sort_keys=True))
        return

    # The usage API itself consumes credits. Conservatively reserve budget
    # for all price calls AND up to one usage call per selected interval.
    used,limit = _usage(key)
    ok,threshold = quota_headroom(used,limit,cap)
    if not ok or used+(2*len(due))+1 > threshold:
        print("MFX_A04_P59_NATIVE_QUOTA_NO_PRICE_REQUESTS")
        print(json.dumps({
            "status":"NOT_EXECUTED_INSUFFICIENT_QUOTA_HEADROOM",
            "price_requests":0,"drive_writes":0,"broker_orders":0,
        },sort_keys=True))
        return

    prepared: list[tuple[str,Any,Any,Any]] = []
    for idx, (interval,store,archive,plan) in enumerate(due):
        if idx:
            current,maximum = _usage(key)
            accepted,limit_now = quota_headroom(current,maximum,cap)
            if not accepted or current+2 > limit_now:
                raise ValueError("P059_QUOTA_RECHECK_FAILS_BEFORE_ANY_DRIVE_WRITE")
        assert plan.request is not None
        envelope = _read_payload(
            TIME_SERIES_URL,{**plan.request,"apikey":key})
        batch = parse_native_forex(
            envelope,symbol=SYMBOL,interval=interval,now_utc=now,
            requested_timezone="UTC" if interval=="4h" else None)
        validate_incremental_source(
            batch,previous=archive.last_manifest,plan=plan)
        proposal = plan_native_sealed(batch,previous=archive.last_manifest)
        if proposal is not None:
            verify_native_sealed(proposal,previous=archive.last_manifest)
        prepared.append((interval,batch,store,archive))

    # Second all-scope preflight protects against provider request delays.
    for interval,_,store,archive in prepared:
        state = audit_native_archive(
            store,symbol=SYMBOL,interval=interval)
        if state != archive:
            raise ValueError("P059_NATIVE_ARCHIVE_CHANGED_DURING_FETCH")

    receipts = [asdict(commit_native_batch(store,batch))
                for _,batch,store,_ in prepared]
    print("MFX_A04_P59_NATIVE_INCREMENTAL_MANUAL_SHA_READBACK_PASS")
    print(json.dumps({
        "status":"NATIVE_INCREMENTAL_VALIDATED_AND_COMMITTED",
        "results":receipts,"source":"TWELVE_DATA_COMPOSITE_MID",
        "provider_price_requests":len(due),
        "provider_usage_requests":len(due),
        "requested_outputsize_by_interval":{
            interval:int(plan.request["outputsize"])
            for interval,_,_,plan in due if plan.request is not None},
        "intervals_skipped_no_new_closed_slot":[
            interval for interval,_,_,plan in archives
            if plan.provider_requests_planned == 0],
        "m5_cache_modified":False,"broker_orders":0,
        "source_numeric_signals_approved":False,
        "automatic_native_schedule_activated":False,
    },sort_keys=True))


if __name__ == "__main__":
    main()
