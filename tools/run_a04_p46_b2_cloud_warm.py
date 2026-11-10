"""P046-B2: manually dispatched, triple-gated private Drive WARM promotion.

No Twelve Data calls; reads only existing MFX B1 immutable source objects.
No delete/trash. No confirmed Forex entry conditions or broker interface.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os

from mfx_cache.v2_warm_promotion import promote_completed_utc_day
from tools.run_a04_p45_cloud_twelve_data_cache import _require_env, _session
from tools.run_a04_p46_cloud_batch_cache import PrivateDriveBatchStore


def main() -> None:
    if not all(os.environ.get(k) == "true" for k in (
        "MFX_REAL_CACHE_ENABLED",
        "MFX_V2_BATCH_CACHE_ACCEPTED",
        "MFX_V2_WARM_PROMOTION_ACCEPTED",
    )):
        print("MFX_A04_P46_B2_STAGED_WARM_PROMOTION_DISABLED_TRIPLE_GATE")
        return
    try:
        credentials = json.loads(_require_env("MFX_GDRIVE_SERVICE_ACCOUNT_JSON"))
    except (ValueError, TypeError) as exc:
        raise ValueError("P046_B2_INVALID_PRIVATE_GDRIVE_CREDENTIALS") from exc
    if (type(credentials) is not dict
            or credentials.get("type") != "service_account"
            or type(credentials.get("client_email")) is not str):
        raise ValueError("P046_B2_PRIVATE_GDRIVE_SERVICE_ACCOUNT_REQUIRED")
    store = PrivateDriveBatchStore(_session(credentials))
    result = promote_completed_utc_day(store, now_utc=datetime.now(timezone.utc))
    print(json.dumps({
        "status": result.status,
        "day_utc": result.day_utc,
        "source_hour_count": result.source_hour_count,
        "missing_utc_hours": result.missing_hour_count,
        "new_warm_and_promotion_objects_expected": result.expected_new_drive_objects,
        "source_parent_deletions": result.original_parent_objects_deleted,
        "actual_vendor_api_calls": result.actual_vendor_api_calls,
        "real_user_buy_sell_signals": result.approved_source_numeric_signals,
        "broker_orders": result.broker_orders,
        "real_market_asof_bidask_verified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
