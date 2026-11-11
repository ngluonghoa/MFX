"""A04/P0.59/P0.64 — gated hourly + manual native EUR/USD H4/D1 writer.

P0.64 schedules the previously manual-tested P0.59 source-native incremental
commit every UTC hour at :25, without changing its data integrity or quota
contracts. Both modes preflight both archives BEFORE provider calls; skip
intervals without newly eligible closed slots. No broker or BUY/SELL.
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
    native_append_slots_remaining,
)
from tools.run_a04_p45_cloud_twelve_data_cache import _settings, _session
from tools.run_a04_p46_cloud_batch_cache import quota_headroom
from tools.run_mfx_native_htf_probe import _usage, _read_payload, TIME_SERIES_URL


def summarize_incremental_receipts(
    receipts: list[dict[str,Any]],
) -> dict[str,Any]:
    """Separate actual immutable writes from vendor-side stale responses.

    A source request and a successful SHA audit do NOT establish that a
    new candle was persisted. Reject impossible storage receipts rather
    than reporting a misleading 'COMMITTED' status.
    """
    if type(receipts) is not list or not receipts:
        raise ValueError("P060_NATIVE_RECEIPTS_REQUIRED")
    accepted = {
        "NO_NEW_CLOSED_NATIVE_BAR",
        "NATIVE_BATCH_COMMITTED",
        "RECOVERED_ORPHAN_AND_COMMITTED",
    }
    seen: set[str] = set()
    committed: list[str] = []
    vendor_stale: list[str] = []
    new_total = 0
    for r in receipts:
        if (type(r) is not dict
                or r.get("status") not in accepted
                or r.get("symbol") != SYMBOL
                or r.get("interval") not in NATIVE_INTERVALS
                or r["interval"] in seen
                or type(r.get("newly_closed_native_bars")) is not int
                or r["newly_closed_native_bars"] < 0
                or type(r.get("drive_objects_created_max")) is not int
                or not 0 <= r["drive_objects_created_max"] <= 2
                or r.get("broker_orders") != 0):
            raise ValueError("P060_NATIVE_INVALID_COMMIT_RECEIPT")
        seen.add(r["interval"])
        n = r["newly_closed_native_bars"]
        if r["status"] == "NO_NEW_CLOSED_NATIVE_BAR":
            if n != 0 or r["drive_objects_created_max"] != 0:
                raise ValueError("P060_NATIVE_STALE_RECEIPT_HAS_WRITES")
            vendor_stale.append(r["interval"])
        else:
            if n < 1 or r["drive_objects_created_max"] not in (1,2):
                raise ValueError("P060_NATIVE_COMMIT_RECEIPT_NO_NEW_BARS")
            committed.append(r["interval"])
        new_total += n
    return {
        "status": ("NATIVE_INCREMENTAL_NEW_BARS_COMMITTED" if new_total
                   else "NATIVE_INCREMENTAL_PROVIDER_STALE_NO_NEW_BAR"),
        "total_newly_closed_native_bars": new_total,
        "intervals_with_new_native_bars": committed,
        "intervals_provider_stale_no_new_bar": vendor_stale,
    }


def main() -> None:
    if (os.environ.get("MFX_REAL_CACHE_ENABLED") != "true"
            or os.environ.get("MFX_V2_BATCH_CACHE_ACCEPTED") != "true"
            or os.environ.get("MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED") != "true"
            or os.environ.get("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED") != "true"):
        print("MFX_A04_P59_INCREMENTAL_DISABLED_EXPLICIT_FOUR_GATE")
        return

    # GitHub injects a protected event name; never report a manual
    # acceptance marker for an unattended hourly scheduled run.
    scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
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
    # Audit BOTH scopes before vendor usage/price calls. Capacity is a
    # hard bounded SHA-auditor constraint, not available Drive quota.
    # Fail all due intervals before spending credits if either cannot
    # safely accept one more immutable Chunk+Manifest pair.
    for _,_,archive,plan in archives:
        if (plan.provider_requests_planned
                and native_append_slots_remaining(archive) < 1):
            raise ValueError("P063_NATIVE_CAPACITY_EXHAUSTED_NO_VENDOR_CALL")
    due = [a for a in archives if a[3].provider_requests_planned]
    if not due:
        print("MFX_A04_P59_NATIVE_NO_NEW_CLOSED_SLOTS_ZERO_VENDOR_CALLS")
        print(json.dumps({
            "status":"NO_NATIVE_CLOSED_SLOTS_DUE",
            "provider_price_requests":0,"provider_usage_requests":0,
            "drive_writes":0,"broker_orders":0,
            "automatic_native_schedule_activated":scheduled,
            "execution_mode":"hourly_schedule" if scheduled else "manual",
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
            "automatic_native_schedule_activated":scheduled,
            "execution_mode":"hourly_schedule" if scheduled else "manual",
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
    summary = summarize_incremental_receipts(receipts)
    print("MFX_A04_P64_HOURLY_NATIVE_INCREMENTAL_SHA_READBACK_PASS"
          if scheduled
          else "MFX_A04_P59_NATIVE_INCREMENTAL_MANUAL_SHA_READBACK_PASS")
    print(json.dumps({
        **summary,
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
        "automatic_native_schedule_activated":scheduled,
        "execution_mode":"hourly_schedule" if scheduled else "manual",
    },sort_keys=True))


if __name__ == "__main__":
    main()
