"""MFX signal-first: pure UTC closed-slot age evidence for hourly M5 cache.

Source tip is SHA-audited by the caller; this module never fetches bars,
modifies a cache, invents candles, changes a schedule or authorizes trades.
A historic cache close cannot be made current by retrospective replay.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from mfx_research.six_tf_readonly_context import (
    GRACE, _expected_last_closed,
)

FRAME_WIDTHS = (("M5", 5), ("M15", 15), ("M30", 30), ("H1", 60))
HOUR = timedelta(hours=1)


def diagnose_hourly_m5_freshness(
    *, m5_latest_hour_utc: str, asof_utc: datetime,
) -> dict[str, Any]:
    """Timestamp-only gap to the *latest eligible CLOSED* M5-derived frames.

    This never certifies vendor first-known, source data licence, BUY/SELL
    correctness or decision-time timeliness. The source hour must first
    be independently SHA-audited and its M5 chunk confirmed closed.
    """
    if (type(asof_utc) is not datetime or asof_utc.tzinfo is None
            or asof_utc.utcoffset() != timedelta(0)):
        raise ValueError("MFX_V1_FRESHNESS_EXACT_UTC_ASOF_REQUIRED")
    if type(m5_latest_hour_utc) is not str:
        raise ValueError("MFX_V1_FRESHNESS_SOURCE_HOUR_REQUIRED")
    try:
        source_hour = datetime.fromisoformat(m5_latest_hour_utc)
    except ValueError as exc:
        raise ValueError("MFX_V1_FRESHNESS_SOURCE_HOUR_REQUIRED") from exc
    if (source_hour.tzinfo is None
            or source_hour.utcoffset() != timedelta(0)
            or source_hour.minute or source_hour.second
            or source_hour.microsecond
            or source_hour.isoformat() != m5_latest_hour_utc):
        raise ValueError("MFX_V1_FRESHNESS_UTC_HOUR_GRID_REQUIRED")

    last_end = source_hour + HOUR
    if last_end > asof_utc - GRACE:
        raise ValueError("MFX_V1_FRESHNESS_SOURCE_HOUR_NOT_YET_CLOSED")
    expected = {
        name: _expected_last_closed(asof_utc, width)
        for name, width in FRAME_WIDTHS
    }
    gaps: dict[str, int] = {}
    for frame, width in FRAME_WIDTHS:
        difference = expected[frame] - last_end
        if difference < timedelta(0):
            raise ValueError("MFX_V1_FRESHNESS_FUTURE_SOURCE_TIP")
        if difference % timedelta(minutes=width):
            raise ValueError("MFX_V1_FRESHNESS_SOURCE_NOT_ON_FRAME_GRID")
        gaps[frame] = difference // timedelta(minutes=width)

    # P0.196: distinguish a CLOSED hourly batch actually overdue from
    # ordinary unsealed intrahour M5 slots. A 12-bar, one-hour archive
    # cannot by itself keep five-minute frames current at arbitrary as-of.
    # Follow the existing +5-minute eligibility fence, not close+15s
    # presentation grace: a just-closed full hour is not writer-eligible.
    eligible_hour = asof_utc.replace(
        minute=0, second=0, microsecond=0,
    ) - HOUR * (2 if asof_utc.minute < 5 else 1)
    if source_hour > eligible_hour:
        raise ValueError("P196_M5_SOURCE_HOUR_BEFORE_ELIGIBLE_5MIN_GRACE")
    missing_eligible_hours = (eligible_hour - source_hour) // HOUR
    on_time_hourly_end = eligible_hour + HOUR
    intrahour_unsealed = (
        expected["M5"] - on_time_hourly_end
    ) // timedelta(minutes=5)
    if (not 0 <= intrahour_unsealed <= 11
            or gaps["M5"] != 12 * missing_eligible_hours
                + intrahour_unsealed):
        raise ValueError("P196_M5_HOURLY_CADENCE_SLOT_ACCOUNTING_DRIFT")
    cadence = {
        "mode": "IMMUTABLE_FULL_UTC_HOUR_M5_BATCHES_ONLY",
        "latest_eligible_full_hour_utc": eligible_hour.isoformat(),
        "eligible_complete_hour_batches_missing_from_archive":
            missing_eligible_hours,
        "m5_slots_unsealed_even_with_on_time_hourly_archive":
            intrahour_unsealed,
        "observed_closed_m5_slots_missing": gaps["M5"],
        "m5_slot_accounting_verified": True,
        "full_hour_archival_status": (
            "ELIGIBLE_FULL_HOUR_BACKLOG" if missing_eligible_hours
            else "ALL_ELIGIBLE_FULL_HOURS_ARCHIVED"
        ),
        "intrahour_missing_is_expected_from_hourly_design":
            intrahour_unsealed > 0,
        "github_writer_run_result_independently_observed": False,
        "provider_publisher_first_known_verified": False,
        "permission_to_publish_live_buy_sell": False,
    }
    age = (asof_utc - last_end).total_seconds()
    return {
        "status": ("M5_M15_CLOSED_TIP_MATCHES_ASOF"
                   if gaps["M5"] == 0 and gaps["M15"] == 0
                   else "HOURLY_M5_ARCHIVE_CURRENT_ASOF_GAP_NO_SIGNAL"),
        "m5_latest_source_hour_utc": m5_latest_hour_utc,
        "m5_last_archived_closed_end_utc": last_end.isoformat(),
        "asof_utc": asof_utc.isoformat(),
        "m5_latest_archived_close_age_seconds": int(age),
        "required_last_closed_end_utc": {
            name: dt.isoformat() for name, dt in expected.items()
        },
        "closed_source_slot_gaps": gaps,
        "sealed_hourly_m5_cadence_evidence": cadence,
        "intraday_m5_m15_source_tip_meets_freshness": (
            gaps["M5"] == 0 and gaps["M15"] == 0
        ),
        "freshness_evidence_is_not_provider_first_known": True,
        "source_numeric_signals_approved": False,
        "provider_price_requests": 0,
        "cache_writes": 0,
        "broker_orders": 0,
    }
