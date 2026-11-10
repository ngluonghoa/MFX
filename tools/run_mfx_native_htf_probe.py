"""A04/P0.53 — MANUAL-only native Forex H4/D1 Twelve Data metadata proof.

Exactly two potential vendor time_series calls (H4,D1) with bounded quota.
No raw prices printed, no Google Drive credentials or writes, no signals,
no local execution, no broker. Explicitly fail closed on vendor uncertainty.
"""
from __future__ import annotations

import json
import os
from typing import Any

from mfx_cache.native_fx_htf import (
    NativeFXBatch, native_request_contract, parse_native_forex,
)
from mfx_cache.td_m5_codec import digest
from tools.run_a04_p46_cloud_batch_cache import quota_headroom

SYMBOL = "EUR/USD"
INTERVALS = ("4h", "1day")
USAGE_URL = "https://api.twelvedata.com/api_usage"
TIME_SERIES_URL = "https://api.twelvedata.com/time_series"
MAX_REQUESTS = 2


def _read_payload(url: str, params: dict[str, str]) -> dict[str, Any]:
    """Do not leak signed API key URLs through HTTP/requests tracebacks."""
    import requests

    try:
        r = requests.get(url, params=params, timeout=45)
        if r.status_code != 200:
            raise ValueError("P053_VENDOR_HTTP_STATUS_NOT_200")
        payload = r.json()
    except (requests.RequestException, ValueError) as exc:
        # Intentionally discard exception chain: Requests exceptions can
        # embed the complete query URL, including the private apikey.
        if isinstance(exc, ValueError) and str(exc).startswith("P053_"):
            raise ValueError("P053_VENDOR_HTTP_STATUS_NOT_200") from None
        raise ValueError("P053_VENDOR_RESPONSE_UNAVAILABLE") from None
    if type(payload) is not dict or payload.get("status") == "error":
        raise ValueError("P053_VENDOR_ERROR_OR_INVALID_JSON")
    return payload


def _usage(apikey: str) -> tuple[int, int]:
    report = _read_payload(USAGE_URL, {"apikey": apikey})
    used, limit = report.get("current_usage"), report.get("plan_limit")
    if (type(used) is not int or type(limit) is not int
            or used < 0 or limit <= 0):
        raise ValueError("P053_VENDOR_USAGE_INVALID")
    return used, limit


def _probe_one(apikey: str, interval: str, *, now_utc: Any) -> NativeFXBatch:
    args = native_request_contract(symbol=SYMBOL, interval=interval)
    # Always send exactly the planned provider parameters and app key.
    response = _read_payload(TIME_SERIES_URL, {**args, "apikey": apikey})
    native = parse_native_forex(
        response, symbol=SYMBOL, interval=interval, now_utc=now_utc,
        requested_timezone="UTC" if interval == "4h" else None,
    )
    if not native.closed_bars:
        raise ValueError("P053_NO_CLOSED_NATIVE_ROWS")
    return native


def plan_probe_quota(used: int, limit: int, cap: int) -> bool:
    """Require headroom for both price calls, not just first API request."""
    permitted, threshold = quota_headroom(used, limit, cap)
    return permitted and used + MAX_REQUESTS <= threshold


def main() -> None:
    from datetime import datetime, timezone

    if (os.environ.get("MFX_REAL_CACHE_ENABLED") != "true"
            or os.environ.get("MFX_V2_BATCH_CACHE_ACCEPTED") != "true"):
        print("MFX_A04_P53_NATIVE_PROBE_DISABLED_EXISTING_CACHE_GATES")
        return
    apikey = os.environ.get("MFX_TWELVE_DATA_API_KEY", "")
    if not apikey:
        raise ValueError("P053_MISSING_VENDOR_KEY")
    cap = int(os.environ.get("MFX_TD_DAILY_CREDIT_CAP", "400"))
    if not 1 <= cap <= 720:
        raise ValueError("P053_INVALID_LOCAL_CAP")
    used, limit = _usage(apikey)
    if not plan_probe_quota(used, limit, cap):
        print("MFX_A04_P53_NATIVE_PROBE_QUOTA_NO_PRICE_REQUESTS")
        print(json.dumps({
            "status": "NOT_EXECUTED_INSUFFICIENT_PROVIDER_HEADROOM",
            "current_usage": used, "plan_limit": limit,
            "price_requests": 0, "drive_writes": 0, "broker_orders": 0,
        }, sort_keys=True))
        return
    # One fixed wall-clock timestamp for both TF close/settlement checks.
    now = datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []
    for interval in INTERVALS:
        if interval != INTERVALS[0]:
            # Re-check provider budget before the second price request.
            current, maximum = _usage(apikey)
            has_room, threshold = quota_headroom(current, maximum, cap)
            if not has_room or current + 1 > threshold:
                raise ValueError("P053_SECOND_NATIVE_REQUEST_QUOTA_BLOCK")
        result = _probe_one(apikey, interval, now_utc=now)
        bars = result.closed_bars
        results.append({
            "symbol": result.symbol,
            "interval": result.interval,
            "time_reference": result.time_reference,
            "exchange_timezone": result.exchange_timezone,
            "closed_native_bars": len(bars),
            "incomplete_excluded": result.incomplete_excluded,
            "first_native_open_label": bars[0].native_open_label,
            "last_native_open_label": bars[-1].native_open_label,
            "source": result.source,
            "native_closed_bars_sha256": digest(
                [x.sha256() for x in bars]),
            "provider_native": True,
            "drive_writes": 0,
            "broker_orders": 0,
            "user_signals": 0,
        })
    print("MFX_A04_P53_NATIVE_H4_D1_METADATA_ONLY_TWO_REQUESTS_PASS")
    print(json.dumps({
        "status": "NATIVE_H4_D1_SOURCE_METADATA_VALIDATED",
        "results": results,
        "requested_price_series": 2,
        "source_numeric_signals_approved": False,
        "private_drive_writes": 0,
        "broker_orders": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
