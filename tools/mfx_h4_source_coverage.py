"""A04/P0.70: source-native H4 vs M5-derived UTC-grid gap diagnostics.

A weekend is a CANDIDATE for a closed market session, not proof. Never
infer a vendor outage is a non-trading day, waive M5 holes, or approve
replacement of provider-native H4 from these diagnostics. Pure research.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

UTC = timezone.utc
H4 = timedelta(hours=4)
MAX_SHADOW_SPAN_H4_SLOTS = 72
VERSION = "MFX_A04_P70_DUAL_SOURCE_H4_GRID_GAP_DIAGNOSTICS_V1"


def _shadow_label(value: str) -> datetime:
    if type(value) is not str:
        raise ValueError("P070_SHADOW_UTC_LABEL_REQUIRED")
    try:
        ts = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("P070_SHADOW_UTC_LABEL_INVALID") from exc
    if (ts.utcoffset() != timedelta(0) or ts.tzinfo is None
            or ts.hour % 4 or ts.minute or ts.second or ts.microsecond
            or ts.isoformat() != value):
        raise ValueError("P070_SHADOW_UTC_4H_GRID_REQUIRED")
    return ts


def _native_label(value: str) -> datetime:
    if type(value) is not str:
        raise ValueError("P070_NATIVE_UTC_LABEL_REQUIRED")
    try:
        ts = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError("P070_NATIVE_UTC_LABEL_INVALID") from exc
    if (ts.strftime("%Y-%m-%d %H:%M:%S") != value
            or ts.hour % 4 or ts.minute or ts.second):
        raise ValueError("P070_NATIVE_UTC_4H_GRID_REQUIRED")
    return ts.replace(tzinfo=UTC)


def h4_dual_source_grid_diagnostics(
    shadow_starts_utc: tuple[str, ...],
    native_starts_utc: tuple[str, ...],
) -> dict[str, Any]:
    """Classify ONLY the span between first and last COMPLETE M5->H4.

    The native archive is independently SHA-verified by the caller, and
    M5 shadow source is independently SHA-verified. This function only
    classifies calendar labels; it does NOT validate or provide OHLC.

    In particular, BOTH_ABSENT during Saturday/Sunday is UNSUPPORTED
    weekend SESSION CANDIDATE, never automatically granted as parity.
    """
    if type(shadow_starts_utc) is not tuple or type(native_starts_utc) is not tuple:
        raise ValueError("P070_TYPED_TUPLE_LABELS_REQUIRED")
    shadow = tuple(_shadow_label(x) for x in shadow_starts_utc)
    native = tuple(_native_label(x) for x in native_starts_utc)
    if (any(a >= b for a, b in zip(shadow, shadow[1:]))
            or any(a >= b for a, b in zip(native, native[1:]))):
        raise ValueError("P070_DUPLICATE_OR_UNSORTED_LABELS")
    if not shadow:
        return {
            "h4_coverage_report_version": VERSION,
            "h4_utc_grid_slots_scanned": 0,
            "h4_both_sources_present_grid_slots": 0,
            "h4_native_present_m5_missing_slots": 0,
            "h4_m5_present_native_missing_slots": 0,
            "h4_both_sources_absent_grid_slots": 0,
            "h4_weekend_dual_absence_candidates": 0,
            "h4_weekday_dual_absence_unexplained": 0,
            "h4_native_present_m5_missing_samples_utc": [],
            "h4_m5_present_native_missing_samples_utc": [],
            "h4_dual_absence_samples_utc": [],
            "h4_weekend_session_policy_proven": False,
            "h4_weekend_gaps_auto_waived": False,
            "h4_coverage_diagnostics_research_only": True,
        }

    num_slots = int((shadow[-1] - shadow[0]) / H4) + 1
    if (num_slots < 1 or num_slots > MAX_SHADOW_SPAN_H4_SLOTS
            or shadow[-1] - shadow[0] != (num_slots - 1) * H4):
        raise ValueError("P070_SHADOW_SPAN_BOUNDED_4H_REQUIRED")
    shadow_set, native_set = set(shadow), set(native)
    both, native_only, m5_only, neither = 0, [], [], []
    for i in range(num_slots):
        stamp = shadow[0] + i * H4
        a, b = stamp in shadow_set, stamp in native_set
        if a and b:
            both += 1
        elif a:
            m5_only.append(stamp)
        elif b:
            native_only.append(stamp)
        else:
            neither.append(stamp)
    return {
        "h4_coverage_report_version": VERSION,
        "h4_utc_grid_slots_scanned": num_slots,
        "h4_both_sources_present_grid_slots": both,
        "h4_native_present_m5_missing_slots": len(native_only),
        "h4_m5_present_native_missing_slots": len(m5_only),
        "h4_both_sources_absent_grid_slots": len(neither),
        "h4_weekend_dual_absence_candidates":
            sum(x.weekday() in (5, 6) for x in neither),
        "h4_weekday_dual_absence_unexplained":
            sum(x.weekday() not in (5, 6) for x in neither),
        "h4_native_present_m5_missing_samples_utc":
            [x.isoformat() for x in native_only[:8]],
        "h4_m5_present_native_missing_samples_utc":
            [x.isoformat() for x in m5_only[:8]],
        "h4_dual_absence_samples_utc":
            [x.isoformat() for x in neither[:8]],
        "h4_weekend_session_policy_proven": False,
        "h4_weekend_gaps_auto_waived": False,
        "h4_coverage_diagnostics_research_only": True,
    }
