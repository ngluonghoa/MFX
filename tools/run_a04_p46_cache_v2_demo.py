"""A04/P0.46 Cloud-only offline Cache V2 core receipts, never market data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_engine import (
    VERSION, compact_utc_days, derive_intraday, detect_missing,
    indicator_cache, make_chunk, modeled_write_pressure, plan_fetch,
    FetchCandidate,
)


def main() -> None:
    start = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    asof = datetime(2026, 11, 10, 16, tzinfo=timezone.utc)
    b = tuple(ClosedM5Bar(
        start_utc=(start + timedelta(minutes=i*5)).isoformat(),
        open="1.10", high="1.20", low="1.00", close="1.11",
    ) for i in range(24))
    counts = {tf: len(derive_intraday(b, tf, asof_utc=asof).candles)
              for tf in ("M15", "M30", "H1")}
    if counts != {"M15": 8, "M30": 4, "H1": 2}:
        raise RuntimeError("P046_WRONG_COMPLETE_MULTITIMEFRAME_3_6_12")
    chunks = tuple(make_chunk((row,), asof_utc=asof) for row in b[:12])
    comp = compact_utc_days(chunks, asof_utc=asof)
    if (len(comp) != 1 or len(comp[0].canonical_bars) != 12
            or comp[0].parent_deletion_authorized
            or comp[0].drive_verified_readback):
        raise RuntimeError("P046_UNSAFE_PURE_COMPACTION")
    ind = indicator_cache(b, period=5, asof_utc=asof)
    reused = indicator_cache(b, period=5, asof_utc=asof,
                             cached=ind.snapshot)
    if ind.reused or not reused.reused:
        raise RuntimeError("P046_INDICATOR_CACHE_REUSE_UNVERIFIED")
    holes = detect_missing(b, asof_utc=asof)
    if holes:
        raise RuntimeError("P046_M5_CONTINUITY_UNVERIFIED")
    plan = plan_fetch((FetchCandidate(
        symbol="EUR/USD", frame="M5",
        last_closed_start_utc="2026-11-10T13:55:00+00:00",
        last_polled_utc="2026-11-10T13:55:00+00:00",
        priority=0,
    ),), now_utc=asof, minute_credits_remaining=7,
        day_credits_remaining=720)
    if len(plan.selected) != 1 or plan.market_api_calls:
        raise RuntimeError("P046_SMART_FETCH_BUDGET_PROJECTION_FAILURE")
    modeled = modeled_write_pressure(
        polls_per_day=288, flushes_per_day=8, days=7,
    )
    print("MFX_A04_P46_CACHE_V2_PURE_CORE_SIM_NO_SIGNAL_PASS")
    print("MFX_A04_P46_RECEIPT " + json.dumps({
        "version": VERSION,
        "input_type": "SYNTHETIC_CLOSED_MID_M5_ONLY",
        "derived_counts": counts,
        "compaction_parent_chunks": len(chunks),
        "compaction_proposed_bars": len(comp[0].canonical_bars),
        "compaction_parent_deletion_allowed": False,
        "readback_verified": False,
        "gap_count": len(holes),
        "research_indicator_reuse": reused.reused,
        "fetch_budgeted_requests": len(plan.selected),
        "actual_network_calls": 0,
        "actual_drive_writes": 0,
        "theoretical_file_scenario": modeled,
        "source_numeric_rules_approved": 0,
        "real_user_buy_sell": 0,
        "broker_orders": 0,
        "p045_cloud_writer_activated": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
