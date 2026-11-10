"""P0.47: pure read-only research preflight for offline HOT/B1 fixtures.

This does not fetch vendor quotes, write Drive, claim global index latestness,
release market signals, or authorize broker activity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from mfx_cache.v2_batch_commit import PrivateObjectStore
from mfx_cache.v3_hot_overlay import freshness
from mfx_cache.v3_sealed_index import (
    _check_utc, _hour, check_hot_against_sealed_index, validate_index,
)


@dataclass(frozen=True, slots=True)
class OfflinePreflight:
    status: str
    sealed_b1_hour_utc: str | None
    last_closed_m5_utc: str | None
    hot_age_seconds: int | None
    verified_overlap_m5: int
    offline_research_usable: bool
    globally_latest_source_proven: bool = False
    source_numeric_buy_sell_authorized: bool = False
    broker_orders_authorized: bool = False
    vendor_requests: int = 0
    drive_writes: int = 0


def inspect_offline_hot_b1(
    source: PrivateObjectStore,
    sealed_index: dict[str, Any] | None,
    hot_state: dict[str, Any] | None,
    *, now_utc: datetime,
) -> OfflinePreflight:
    """Fail closed using injected read-only storage; NEVER signals/trades.

    Even successful overlap proves only consistency with the referenced
    immutable B1 hour. It cannot prove the pointer globally latest.
    """
    _check_utc(now_utc)
    if sealed_index is None or hot_state is None:
        return OfflinePreflight(
            status=("NO_SEALED_B1_INDEX" if sealed_index is None
                    else "NO_HOT_OVERLAY"),
            sealed_b1_hour_utc=None, last_closed_m5_utc=None,
            hot_age_seconds=None, verified_overlap_m5=0,
            offline_research_usable=False,
        )

    idx = validate_index(sealed_index, now_utc=now_utc)
    health = freshness(hot_state, now_utc=now_utc)
    hour = _hour(idx["source_hour_utc"])
    last_closed_start = datetime.fromisoformat(
        hot_state["latest_closed_start_utc"]
    )
    common = {
        "sealed_b1_hour_utc": idx["source_hour_utc"],
        "last_closed_m5_utc": hot_state["latest_closed_start_utc"],
        "hot_age_seconds": health.age_seconds,
    }
    # Avoid unnecessary immutable reads on obviously unusable state.
    if last_closed_start < hour + timedelta(minutes=55):
        return OfflinePreflight(
            status="HOT_BEHIND_INDEXED_B1",
            verified_overlap_m5=0, offline_research_usable=False,
            **common,
        )
    if not health.research_data_usable:
        return OfflinePreflight(
            status="HOT_STALE_GAPPED_OR_INSUFFICIENT",
            verified_overlap_m5=0, offline_research_usable=False,
            **common,
        )
    if idx["source_continuity_status"] != "CONTIGUOUS_WITH_PRIOR_BATCH":
        return OfflinePreflight(
            status="B1_SOURCE_CONTINUITY_UNVERIFIED",
            verified_overlap_m5=0, offline_research_usable=False,
            **common,
        )

    # Exactly two source-addressed immutable reads by existing B3-B guard,
    # never a full historical listing or a Drive mutation.
    anchor = check_hot_against_sealed_index(
        source, idx, hot_state, now_utc=now_utc,
    )
    valid = (
        anchor.canonical_source_matches
        and anchor.status == "B1_IMMUTABLE_OVERLAP_VERIFIED_RESEARCH_ONLY"
    )
    return OfflinePreflight(
        status=("OFFLINE_ANCHORED_RESEARCH_ONLY_NO_LATESTNESS_PROOF"
                if valid else "HOT_UNANCHORED_SEALED_B1"),
        verified_overlap_m5=anchor.overlap_bars,
        offline_research_usable=valid,
        **common,
    )
