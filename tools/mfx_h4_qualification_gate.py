"""A04/P0.92 — offline, source-typed H4 qualification review (NEVER GO).

Compose *existing* P0.70 UTC dual-source gap grid and P0.66 audited counters
into a bounded cross-field review. The observations are caller-supplied and
are NOT cryptographically authenticated by this module. A weekend is only a
session-closure candidate, never an automatic data-hole waiver.

No Google Drive, network price API, GitHub, filesystem, scheduler or broker IO.
This is research, not a production H4 selector or strategy authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from tools.mfx_h4_source_coverage import (
    MAX_SHADOW_SPAN_H4_SLOTS, h4_dual_source_grid_diagnostics,
)

SCHEMA = "MFX_A04_P92_H4_SESSION_QUALIFICATION_REVIEW_V1"
H4 = timedelta(hours=4)
MIN_WINDOWS = 30
MIN_SPAN = timedelta(days=7)


def _utc(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


def _sha256(value: object) -> bool:
    return (type(value) is str and len(value) == 64
            and all(x in "0123456789abcdef" for x in value))


@dataclass(frozen=True, slots=True)
class ReviewedH4Evidence:
    # Source proof is an earlier external read-only auditor result, not
    # permission for this module to trust an arbitrary supplied TRUE flag.
    audit_run_id: int
    audit_attempt: int
    audit_completed_utc: datetime
    m5_latest_hour_utc: datetime
    m5_head_sha256: str
    m5_manifest_chunk_pairs_verified: int
    m5_closed_bars: int
    m5_full_bounded_sha_verified: bool
    native_manifest_chunk_pairs_verified: int
    native_closed_bars: int
    native_full_bounded_sha_verified: bool
    complete_48xm5_h4_starts_utc: tuple[str, ...]
    native_h4_starts_utc_in_or_around_span: tuple[str, ...]
    exact_ohlc_matches: int
    ohlc_mismatches: int
    native_missing_for_complete_m5: int
    interior_incomplete_h4_windows: int
    boundary_partial_h4_windows: int
    provider_calls_in_prior_audit: int = 0
    drive_writes_in_prior_audit: int = 0
    broker_orders_in_prior_audit: int = 0


@dataclass(frozen=True, slots=True)
class H4QualificationReview:
    schema: str
    status: str
    audit_run_id: int
    h4_complete_m5_windows: int
    h4_exact_matches: int
    h4_span_seconds: float
    h4_at_least_30_exact: bool
    h4_at_least_7_real_days: bool
    h4_all_4h_slots_present_in_both_sources: bool
    h4_native_only_slots: int
    h4_m5_only_slots: int
    h4_dual_absent_weekend_candidates: int
    h4_dual_absent_weekday_unexplained: int
    h4_boundary_partial_ignored_for_threshold: int
    h4_interior_missing_m5_windows: int
    h4_observation_threshold_met_for_research_only: bool
    audit_head_sha256: str
    # Deliberately cannot be raised by self-supplied input, even on a
    # synthetic 30-window 7-day sample.
    independently_authenticated_by_this_module: bool = False
    independent_market_session_calendar_verified: bool = False
    actual_vendor_session_and_data_rights_verified: bool = False
    external_monotonic_witness_verified: bool = False
    h4_production_cutover_authorized: bool = False
    may_reduce_native_h4_requests: bool = False
    may_replace_native_h4: bool = False
    may_change_sydney_native_d1: bool = False
    numeric_fx_buy_sell_authorized: bool = False
    broker_orders_authorized: bool = False
    provider_calls_by_this_module: int = 0
    drive_writes_by_this_module: int = 0
    broker_orders_by_this_module: int = 0


def review_h4_qualification(e: ReviewedH4Evidence) -> H4QualificationReview:
    """Fail closed on contradictory counters, SHA and clock/label evidence.

    A future sample may meet the *research* threshold, but this evaluator
    still returns OWNER_AND_SESSION_EVIDENCE_REQUIRED, never cutover GO.
    """
    if type(e) is not ReviewedH4Evidence:
        raise ValueError("P092_TYPED_REVIEWED_EVIDENCE_REQUIRED")
    integers = (
        e.audit_run_id, e.audit_attempt, e.m5_manifest_chunk_pairs_verified,
        e.m5_closed_bars, e.native_manifest_chunk_pairs_verified,
        e.native_closed_bars, e.exact_ohlc_matches, e.ohlc_mismatches,
        e.native_missing_for_complete_m5, e.interior_incomplete_h4_windows,
        e.boundary_partial_h4_windows, e.provider_calls_in_prior_audit,
        e.drive_writes_in_prior_audit, e.broker_orders_in_prior_audit,
    )
    if (any(type(x) is not int or x < 0 for x in integers)
            or e.audit_run_id == 0 or e.audit_attempt == 0
            or e.m5_manifest_chunk_pairs_verified == 0
            or e.native_manifest_chunk_pairs_verified == 0
            or e.m5_closed_bars != 12 * e.m5_manifest_chunk_pairs_verified
            or e.native_closed_bars == 0
            or not _utc(e.audit_completed_utc)
            or not _utc(e.m5_latest_hour_utc)
            or e.m5_latest_hour_utc.minute or e.m5_latest_hour_utc.second
            or e.m5_latest_hour_utc.microsecond
            or e.audit_completed_utc < (
                e.m5_latest_hour_utc + timedelta(hours=1, minutes=5))
            or not _sha256(e.m5_head_sha256)
            or e.m5_full_bounded_sha_verified is not True
            or e.native_full_bounded_sha_verified is not True
            or any(x != 0 for x in integers[-3:])):
        raise ValueError("P092_AUDIT_SHA_CLOCK_OR_SAFE_SCOPE_INVALID")
    labels = e.complete_48xm5_h4_starts_utc
    native = e.native_h4_starts_utc_in_or_around_span
    if (type(labels) is not tuple or type(native) is not tuple
            or not labels or len(labels) > MAX_SHADOW_SPAN_H4_SLOTS
            or len(native) > 256
            or any(type(s) is not str for s in labels+native)):
        raise ValueError("P092_BOUNDED_TYPED_H4_LABELS_REQUIRED")
    # Reuse P0.70's UTC 4h alignment, ordering and weekend-only candidate
    # semantics; do not duplicate or weaken its gap diagnostics.
    grid: dict[str, Any] = h4_dual_source_grid_diagnostics(labels, native)
    stamps = tuple(datetime.fromisoformat(s) for s in labels)
    if (stamps[-1] + H4 > e.m5_latest_hour_utc + timedelta(hours=1)
            or stamps[-1] + H4 > e.audit_completed_utc
            or e.m5_closed_bars < 48 * len(stamps)
            or e.native_closed_bars < (
                grid["h4_both_sources_present_grid_slots"]
                + grid["h4_native_present_m5_missing_slots"])
            or e.exact_ohlc_matches + e.ohlc_mismatches
            != grid["h4_both_sources_present_grid_slots"]
            or e.native_missing_for_complete_m5
            != grid["h4_m5_present_native_missing_slots"]
            or e.exact_ohlc_matches + e.ohlc_mismatches
            + e.native_missing_for_complete_m5 != len(stamps)):
        raise ValueError("P092_SOURCE_PARITY_COUNTER_OR_48M5_JOIN_INVALID")
    span = stamps[-1] - stamps[0]
    enough = e.exact_ohlc_matches >= MIN_WINDOWS
    week = span >= MIN_SPAN
    no_source_gaps = (
        e.ohlc_mismatches == 0
        and e.native_missing_for_complete_m5 == 0
        and e.interior_incomplete_h4_windows == 0
        and grid["h4_native_present_m5_missing_slots"] == 0
        and grid["h4_m5_present_native_missing_slots"] == 0
    )
    no_dual_absence = grid["h4_both_sources_absent_grid_slots"] == 0
    all_slots = no_source_gaps and no_dual_absence
    theoretical = bool(enough and week and all_slots)
    if not no_source_gaps:
        status = "P092_NO_GO_SOURCE_MISMATCH_OR_INTERIOR_GAP"
    elif grid["h4_weekday_dual_absence_unexplained"]:
        status = "P092_NO_GO_UNEXPLAINED_WEEKDAY_DUAL_ABSENCE"
    elif grid["h4_weekend_dual_absence_candidates"]:
        status = "P092_NO_GO_UNVERIFIED_WEEKEND_SESSION_CANDIDATE"
    elif not enough or not week:
        status = "P092_NO_GO_INSUFFICIENT_30_WINDOWS_OR_7_DAYS"
    else:
        status = "P092_REVIEW_THRESHOLD_ONLY_SESSION_AND_OWNER_GO_REQUIRED"
    return H4QualificationReview(
        schema=SCHEMA, status=status, audit_run_id=e.audit_run_id,
        h4_complete_m5_windows=len(stamps),
        h4_exact_matches=e.exact_ohlc_matches,
        h4_span_seconds=span.total_seconds(),
        h4_at_least_30_exact=enough, h4_at_least_7_real_days=week,
        h4_all_4h_slots_present_in_both_sources=all_slots,
        h4_native_only_slots=grid["h4_native_present_m5_missing_slots"],
        h4_m5_only_slots=grid["h4_m5_present_native_missing_slots"],
        h4_dual_absent_weekend_candidates=grid[
            "h4_weekend_dual_absence_candidates"],
        h4_dual_absent_weekday_unexplained=grid[
            "h4_weekday_dual_absence_unexplained"],
        h4_boundary_partial_ignored_for_threshold=(
            e.boundary_partial_h4_windows),
        h4_interior_missing_m5_windows=e.interior_incomplete_h4_windows,
        h4_observation_threshold_met_for_research_only=theoretical,
        audit_head_sha256=e.m5_head_sha256,
    )
