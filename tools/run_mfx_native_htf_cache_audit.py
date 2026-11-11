"""MFX A04/P0.58 — source-native EUR/USD H4+D1 private Drive READ-ONLY audit.

Full bounded per-interval sealed SHA/parent chain audit; calendar-lag is
observation-only because neither an FX session calendar nor periodic H4/D1
writer has been accepted. No Twelve Data API, Drive mutation, signal, broker.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
from typing import Any
from zoneinfo import ZoneInfo

from mfx_cache.td_m5_codec import digest
from tools.mfx_native_htf_drive_seal import (
    PrivateNativeDriveStore, audit_native_archive,
)
from tools.run_a04_p45_cloud_twelve_data_cache import (
    _drive_auth_info, _require_oauth_cache_folders, _session,
)

SYMBOL = "EUR/USD"
INTERVALS = ("4h", "1day")
UTC = timezone.utc


def _now_utc(instant: datetime) -> None:
    if (type(instant) is not datetime or instant.tzinfo is None
            or instant.utcoffset() != timedelta(0)):
        raise ValueError("P058_AUDIT_REQUIRES_UTC")


def audit_native_cache(
    store: Any, *, interval: str, now_utc: datetime,
) -> dict[str, Any]:
    """Full content-addressed readback, with *observational* lag, no writes.

    The archive verifier checks all available historical manifests/chunks and
    rejects mutated content, broken SHA/parent links, mismatched native
    source/time semantics and duplicate items. Fail closed for one orphan,
    too: an hourly read-only audit has no recovery write authorization.
    """
    _now_utc(now_utc)
    if interval not in INTERVALS:
        raise ValueError("P058_NATIVE_INTERVAL_NOT_ALLOWED")
    state = audit_native_archive(store, symbol=SYMBOL, interval=interval)
    if state.last_manifest is None or state.manifest_count < 1:
        raise ValueError("P058_NATIVE_CACHE_NOT_BOOTSTRAPPED")
    if state.uncommitted_chunk_names:
        raise ValueError("P058_UNCOMMITTED_NATIVE_CHUNK_REQUIRES_REVIEW")
    if state.chunk_count != state.manifest_count:
        raise ValueError("P058_NATIVE_CHUNK_MANIFEST_COUNT_MISMATCH")

    manifest = state.last_manifest
    label = manifest["last_native_open_label"]
    zone = manifest["exchange_timezone"]
    if zone != "Australia/Sydney":
        raise ValueError("P058_UNEXPECTED_EURUSD_EXCHANGE_ZONE")
    if interval == "4h":
        last = datetime.strptime(label,"%Y-%m-%d %H:%M:%S").replace(
            tzinfo=UTC)
        if last.hour % 4 or last.minute or last.second:
            raise ValueError("P058_NATIVE_H4_NOT_ON_UTC_GRID")
        # Last fully closed 4h candle may be open as late as 00 UTC
        # for a 05:xx UTC audit. Never treat the open candle as closed.
        current_open = now_utc.replace(
            hour=(now_utc.hour//4)*4,
            minute=0,second=0,microsecond=0)
        expected_last_closed = current_open-timedelta(hours=4)
        if last > expected_last_closed:
            raise ValueError("P058_FUTURE_OR_UNCLOSED_NATIVE_H4")
        lag = int((expected_last_closed-last)//timedelta(hours=4))
        lag_unit = "4h_closed_slots"
    else:
        last_date = date.fromisoformat(label)
        today_local = now_utc.astimezone(ZoneInfo(zone)).date()
        expected_last_closed_day = today_local-timedelta(days=1)
        if last_date > expected_last_closed_day:
            raise ValueError("P058_FUTURE_OR_UNCLOSED_NATIVE_D1")
        # This measures calendar dates, NOT true Forex open sessions:
        # provider-reported weekend bars are not independently verified.
        lag = (expected_last_closed_day-last_date).days
        lag_unit = "calendar_days_not_market_sessions"
    if lag < 0:
        raise ValueError("P058_NEGATIVE_NATIVE_LAG")

    return {
        "status": ("LAST_EXPECTED_NATIVE_SLOT_PRESENT" if lag == 0
                   else "LAGGING_OR_MARKET_CLOSED_REVIEW_REQUIRED"),
        "symbol": SYMBOL, "interval": interval,
        "last_native_open_label": label,
        "exchange_timezone": zone,
        "time_reference": manifest["time_reference"],
        "lag": lag, "lag_unit": lag_unit,
        "manifest_count": state.manifest_count,
        "chunk_count": state.chunk_count,
        "historical_manifest_chunk_pairs_verified": state.manifest_count,
        "full_bounded_archive_verified": True,
        "uncommitted_chunks": 0,
        "total_closed_native_bars": manifest["total_closed_native_bars"],
        "last_manifest_sha256": digest(manifest),
        "source": "TWELVE_DATA_COMPOSITE_MID",
        "observed_only_not_market_session_sla": True,
        "read_only": True, "twelve_data_api_calls": 0,
        "drive_writes": 0, "broker_orders": 0,
        "numeric_buy_sell_signals": 0,
    }


def main() -> None:
    # Existing owner-enabled gates; this job never uses writer credentials
    # or the vendor key. No independent native cron write is activated.
    if (os.environ.get("MFX_REAL_CACHE_ENABLED") != "true"
            or os.environ.get("MFX_V2_BATCH_CACHE_ACCEPTED") != "true"
            or os.environ.get("MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED") != "true"):
        print("MFX_A04_P58_NATIVE_AUDIT_DISABLED_THREE_WAY_GATE")
        return
    auth = _drive_auth_info()
    _require_oauth_cache_folders(auth)
    session = _session(auth)
    now = datetime.now(UTC)
    receipts = [
        audit_native_cache(
            PrivateNativeDriveStore(session,symbol=SYMBOL,interval=tf),
            interval=tf,now_utc=now)
        for tf in INTERVALS
    ]
    print("MFX_A04_P58_NATIVE_H4_D1_READONLY_FULL_SHA_AUDIT_PASS")
    print(json.dumps({
        "status": ("BOTH_LATEST_SLOTS_PRESENT"
                   if all(r["lag"] == 0 for r in receipts)
                   else "ONE_OR_MORE_INTERVALS_LAGGING_REVIEW_ONLY"),
        "results": receipts,
        "provider_price_requests": 0,
        "drive_writes": 0,
        "read_only": True,
        "no_automated_native_writer": True,
        "broker_orders": 0,
        "approved_numeric_buy_sell_signals": False,
        "raw_ohlc_in_logs": False,
    },sort_keys=True))


if __name__ == "__main__":
    main()
