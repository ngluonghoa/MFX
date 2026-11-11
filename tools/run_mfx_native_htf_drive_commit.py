"""MFX A04/P0.55: MANUAL, independently gated, native EUR/USD H4+D1 cache.

Fetch both validated source-native intervals BEFORE any Drive write. No new
cron, no changes to active M5 cache, no broker, no numeric signal approval.
The owner must deliberately enable MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os

from mfx_cache.native_htf_archive import plan_native_sealed, verify_native_sealed
from tools.mfx_native_htf_drive_seal import (
    PrivateNativeDriveStore, audit_native_archive, commit_native_batch,
)
from tools.run_a04_p45_cloud_twelve_data_cache import _settings, _session
from tools.run_mfx_native_htf_probe import (
    SYMBOL, _probe_one, _usage, plan_probe_quota,
)
from tools.run_a04_p46_cloud_batch_cache import quota_headroom


def main() -> None:
    if (os.environ.get("MFX_REAL_CACHE_ENABLED") != "true"
            or os.environ.get("MFX_V2_BATCH_CACHE_ACCEPTED") != "true"
            or os.environ.get("MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED") != "true"):
        print("MFX_A04_P55_NATIVE_DRIVE_DISABLED_EXPLICIT_THREE_WAY_GATE")
        return
    key, auth, cap = _settings()
    used, limit = _usage(key)
    if not plan_probe_quota(used,limit,cap):
        print("MFX_A04_P55_NATIVE_TWO_SERIES_QUOTA_NO_PRICE_REQUESTS")
        return

    now_utc = datetime.now(timezone.utc)
    h4 = _probe_one(key,"4h",now_utc=now_utc)
    current, maximum = _usage(key)
    permitted, threshold = quota_headroom(current,maximum,cap)
    if not permitted or current+1 > threshold:
        raise ValueError("P055_SECOND_NATIVE_PRICE_REQUEST_QUOTA_DENIED")
    d1 = _probe_one(key,"1day",now_utc=now_utc)
    if (h4.symbol != SYMBOL or d1.symbol != SYMBOL
            or h4.interval != "4h" or d1.interval != "1day"
            or h4.time_reference != "UTC_INTRADAY_OPEN"
            or d1.time_reference != "EXCHANGE_LOCAL_SESSION_DATE"
            or not h4.closed_bars or not d1.closed_bars):
        raise ValueError("P055_VENDOR_BOTH_NATIVE_SERIES_NOT_VALIDATED")

    # Authenticate ONLY after BOTH vendor envelopes have been validated;
    # source failures must never produce one-sided Drive writes.
    session = _session(auth)
    work = (
        (h4, PrivateNativeDriveStore(session,symbol=SYMBOL,interval="4h")),
        (d1, PrivateNativeDriveStore(session,symbol=SYMBOL,interval="1day")),
    )
    # Preflight ALL archives before writing the first one.
    for native, store in work:
        state = audit_native_archive(
            store,symbol=native.symbol,interval=native.interval)
        proposal = plan_native_sealed(native,previous=state.last_manifest)
        if proposal is None:
            if state.uncommitted_chunk_names:
                raise ValueError("P055_PREFLIGHT_UNCOMMITTED_CHUNK_WITH_NO_NEW_BAR")
            continue
        verify_native_sealed(proposal,previous=state.last_manifest)
        if (state.uncommitted_chunk_names
                and state.uncommitted_chunk_names != (proposal.chunk_name,)):
            raise ValueError("P055_PREFLIGHT_NATIVE_UNEXPECTED_ORPHAN")
    receipts=[]
    for native, store in work:
        receipt=commit_native_batch(store,native)
        receipts.append(asdict(receipt))
    total=sum(item["newly_closed_native_bars"] for item in receipts)
    status=("NATIVE_H4_D1_SEALED_BATCHES_COMMITTED" if total > 0
            else "NATIVE_H4_D1_ALREADY_CACHED_NO_NEW_BAR")
    print("MFX_A04_P55_NATIVE_H4_D1_DRIVE_PAIR_SHA_READBACK_PASS")
    print(json.dumps({
        "status":status,
        "results":receipts,
        "closed_native_bars_new":total,
        "provider_price_requests":2,
        "source":"TWELVE_DATA_COMPOSITE_MID",
        "timezone_origin_by_interval": {
            "4h": h4.closed_bars[0].exchange_timezone_origin,
            "1day": d1.closed_bars[0].exchange_timezone_origin,
        },
        "raw_quote_output_in_logs":False,
        "m5_cache_modified":False,
        "broker_orders":0,
        "source_numeric_signals_approved":False,
    },sort_keys=True))


if __name__ == "__main__":
    main()
