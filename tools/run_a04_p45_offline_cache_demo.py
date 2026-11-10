"""Cloud-only P045 offline sample: no provider or Google Drive credentials."""
from __future__ import annotations

from datetime import datetime, timezone
import json

from mfx_cache.td_m5_codec import (
    SYMBOL, compute_delta, content_chunk, digest,
    initial_manifest, next_manifest, parse_closed_utc_m5,
)


def main() -> None:
    now = datetime(2026, 11, 10, 10, 36, tzinfo=timezone.utc)
    fake = {
        "meta": {
            "symbol": SYMBOL, "interval": "5min",
            "exchange_timezone": "Australia/Sydney",
            "type": "Physical Currency",
        },
        "status": "ok", "values": [
            {"datetime": "2026-11-10 10:35:00", "open": "1.12",
             "high": "1.13", "low": "1.11", "close": "1.12"},
            {"datetime": "2026-11-10 10:30:00", "open": "1.12",
             "high": "1.13", "low": "1.11", "close": "1.12"},
            {"datetime": "2026-11-10 10:25:00", "open": "1.12",
             "high": "1.13", "low": "1.11", "close": "1.12"},
        ],
    }
    observed = parse_closed_utc_m5(fake, now_utc=now)
    old = initial_manifest(now)
    decision = compute_delta(old, observed)
    chunk = content_chunk(decision, now)
    manifest = next_manifest(
        old, decision, now_utc=now, new_chunk_sha256=digest(chunk),
    )
    again = compute_delta(manifest, observed)
    if (len(observed) != 2 or len(decision.new_bars) != 2
            or not again.no_change
            or manifest["total_chunks"] != 1
            or manifest["total_closed_bars_archived"] != 2
            or manifest["may_confirm_user_buy_sell"]
            or manifest["broker_orders"]):
        raise ValueError("P045_FAKE_CLOUD_CACHE_FAIL_CLOSED")
    print("MFX_A04_P45_FAKE_TWELVE_DATA_M5_CACHE_INCREMENTAL_PASS")
    print("MFX_P045_RESEARCH_RECEIPT " + json.dumps({
        "type": "SYNTHETIC_FIXTURE_NOT_REAL_TWELVEDATA_PRICE",
        "symbol": SYMBOL, "timeframe": "M5",
        "side": "MID", "requested_timezone": "UTC",
        "closed_only": True, "new_bars": len(decision.new_bars),
        "unchanged_reused": again.no_change,
        "immutable_chunk_sha256": digest(chunk),
        "manifest_sha256": digest(manifest),
        "confirmed_signals": 0, "broker_orders": 0,
        "real_cache_verified": False,
        "git_actions_secrets_required_for_real_cache": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
