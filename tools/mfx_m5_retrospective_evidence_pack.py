"""A04/P0.90: offline, SHA-pinned *historical* cross-plane M5 evidence receipt.

This pure evaluator joins P0.87 hourly runs/Drive manifest metadata, P0.88
GH job stages, P0.89 immutable source identities, and the independently
reviewed P0.89 P0.66 read-only SHA audit. It authenticates NOTHING by
itself: all rows are caller-provided. The only real archive head it may
describe is the Git-reviewed 2026-11-12 09:00Z historical checkpoint.
It does not contact GitHub/Drive/Twelve Data, alter cron or permit trading.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from tools.mfx_m5_job_lifecycle_evidence import ObservedGitHubJob
from tools.mfx_m5_scheduler_cohort_evidence import ObservedScheduledRun
from tools.mfx_m5_schedule_source_provenance import (
    ObservedRunSource, classify_schedule_source_provenance,
)

SCHEMA = "MFX_A04_P90_PINNED_HISTORICAL_M5_EVIDENCE_V1"
AUDIT_RUN_ID = 43138482666
AUDIT_ATTEMPT = 4
AUDIT_JOB_ID = 131119847520
AUDIT_MARKER = "MFX_A04_P66_READONLY_SOURCE_SHA_PARITY_AUDIT_PASS"
AUDIT_FINISHED_UTC = datetime(2026, 11, 12, 10, 23, 9, 517000, timezone.utc)
AUDIT_HEAD_HOUR_UTC = datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc)
AUDIT_HEAD_SHA256 = (
    "9354cbe797c69b40a7466218db8cc8018b2c454396c95c33a66146d4939ec91d"
)
AUDIT_VERIFIED_PAIRS = 40
AUDIT_CLOSED_M5 = 480

# Explicitly reviewed 12 scheduled REST run -> source HEAD bindings (P0.89).
# This is a pinned historical cohort, not an auto-discovered current head.
REVIEWED_HEADS = {
    43158866760: "d61fe9ecb7c4214699f3d027e17fabada42a3b63",
    43151652891: "9e9c76a47eaf769e4104600796c87c8dcd247621",
    43144695651: "f19c78e0892c5bf4790762ccf1459f55f2cf5db8",
    43133264975: "4c60644d0a812eabee0e89519a29e1cce9731b61",
    43123068939: "4c60644d0a812eabee0e89519a29e1cce9731b61",
    43115786422: "4c60644d0a812eabee0e89519a29e1cce9731b61",
    43105022518: "4c60644d0a812eabee0e89519a29e1cce9731b61",
    43092969245: "4c60644d0a812eabee0e89519a29e1cce9731b61",
    43082949666: "4c60644d0a812eabee0e89519a29e1cce9731b61",
    43073227903: "627509cc4971b3222ccdfc97eba93d85b14fb44c",
    43063687329: "61cd36e04e0e2eb73de1e38fb2b42af71040310f",
    43053200735: "28dd1d617a7223196f85d612b221ea5cccea8563",
}


def _utc(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


@dataclass(frozen=True, slots=True)
class ObservedReviewedFullM5Audit:
    audit_run_id: int
    attempt: int
    job_id: int
    pass_marker: str
    finished_utc: datetime
    head_hour_utc: datetime
    head_manifest_sha256: str
    full_sha_manifest_chunk_pairs: int
    closed_m5_bars: int
    full_bounded_chain_verified: bool
    native_h4_archive_pairs: int
    native_h4_closed_bars: int
    exact_complete_h4_matches: int
    h4_mismatches: int
    provider_requests: int
    drive_writes: int
    broker_orders: int


@dataclass(frozen=True, slots=True)
class PinnedM5RetrospectiveReceipt:
    schema: str
    status: str
    reviewed_scheduled_run_count: int
    reviewed_manifest_batch_count: int
    reviewed_unique_source_heads: int
    source_cron_expression: str
    median_job_queue_seconds: float
    historical_audit_run_id: int
    historical_full_sha_pairs: int
    historical_closed_m5_bars: int
    historical_head_hour_utc: str
    historical_head_sha256: str
    historical_h4_exact_matches: int
    manifest_hours_missing_in_reviewed_sample: int
    time_since_historical_audit_seconds: float
    source_head_identities_match_reviewed_sample: bool
    # This pure function does not certify API responses, external time or
    # newly published bars after this one pinned historical snapshot.
    independently_authenticated_this_invocation: bool = False
    actual_github_cron_event_dispatch_utc_attested: bool = False
    vendor_first_available_utc_attested: bool = False
    latest_current_cache_head_verified: bool = False
    provider_license_and_calendar_verified: bool = False
    missing_market_session_gap_proven: bool = False
    gh_scheduler_root_cause_proven: bool = False
    production_cron_edit_authorized: bool = False
    live_v2_witness_or_writer_authorized: bool = False
    native_h4_source_replacement_authorized: bool = False
    numeric_buy_sell_or_broker_authorized: bool = False
    provider_calls_by_this_module: int = 0
    drive_writes_by_this_module: int = 0
    broker_orders_by_this_module: int = 0


def correlate_pinned_historical_m5_evidence(
    runs: tuple[ObservedScheduledRun, ...],
    jobs: tuple[ObservedGitHubJob, ...],
    sources: tuple[ObservedRunSource, ...],
    audit: ObservedReviewedFullM5Audit,
    *,
    report_as_of_utc: datetime,
) -> PinnedM5RetrospectiveReceipt:
    """Fail closed on substituted SHA/head, clock, sample, or safety gates.

    A PASS means supplied records agree with the *reviewed P0.89 historical*
    anchor, not that a fresh externally authenticated scan was run.
    """
    source = classify_schedule_source_provenance(runs, jobs, sources)
    # Report pinned run-to-HEAD substitution before a cohort-cardinality
    # summary error; both paths fail closed, but identify the actual defect.
    if (set(REVIEWED_HEADS) != {r.run_id for r in runs}
            or set(REVIEWED_HEADS) != {r.run_id for r in sources}
            or any(m.head_sha != REVIEWED_HEADS[m.run_id] for m in sources)):
        raise ValueError("P090_REVIEWED_RUN_HEAD_SUBSTITUTION")
    if (source.status != "P089_WORKFLOW_BLOB_SAME_CAUSAL_ORIGIN_UNVERIFIED"
            or source.run_count != 12
            or source.observed_manifest_count != 14
            or source.unique_head_commits_in_sample != 7
            or source.historical_unverified_hour_gaps_in_sample != 0
            or source.retry_attempts_need_separate_review != 0
            or not source.source_blob_identity_matches_pinned_review):
        raise ValueError("P090_REVIEWED_GITHUB_COHORT_NOT_EXACT")
    if (type(audit) is not ObservedReviewedFullM5Audit
            or type(audit.audit_run_id) is not int
            or audit.audit_run_id != AUDIT_RUN_ID
            or type(audit.attempt) is not int or audit.attempt != AUDIT_ATTEMPT
            or type(audit.job_id) is not int or audit.job_id != AUDIT_JOB_ID
            or audit.pass_marker != AUDIT_MARKER
            or not _utc(audit.finished_utc)
            or audit.finished_utc != AUDIT_FINISHED_UTC
            or not _utc(audit.head_hour_utc)
            or audit.head_hour_utc != AUDIT_HEAD_HOUR_UTC
            or audit.head_manifest_sha256 != AUDIT_HEAD_SHA256
            or type(audit.full_sha_manifest_chunk_pairs) is not int
            or audit.full_sha_manifest_chunk_pairs != AUDIT_VERIFIED_PAIRS
            or type(audit.closed_m5_bars) is not int
            or audit.closed_m5_bars != AUDIT_CLOSED_M5
            or audit.full_bounded_chain_verified is not True
            or type(audit.native_h4_archive_pairs) is not int
            or audit.native_h4_archive_pairs != 8
            or type(audit.native_h4_closed_bars) is not int
            or audit.native_h4_closed_bars != 126
            or type(audit.exact_complete_h4_matches) is not int
            or audit.exact_complete_h4_matches != 9
            or type(audit.h4_mismatches) is not int
            or audit.h4_mismatches != 0
            or type(audit.provider_requests) is not int
            or audit.provider_requests != 0
            or type(audit.drive_writes) is not int
            or audit.drive_writes != 0
            or type(audit.broker_orders) is not int
            or audit.broker_orders != 0):
        raise ValueError("P090_ARCHIVE_PIN_OR_SAFETY_RECEIPT_MISMATCH")
    if (not _utc(report_as_of_utc)
            or report_as_of_utc < audit.finished_utc
            or any(b.hour_utc > audit.head_hour_utc
                   or b.manifest_created_utc > audit.finished_utc
                   for r in runs for b in r.batches)):
        raise ValueError("P090_HISTORICAL_ASOF_OR_COVERAGE_INVALID")
    return PinnedM5RetrospectiveReceipt(
        schema=SCHEMA,
        status="P090_REVIEWED_HISTORICAL_ANCHORS_CORRELATED_CURRENT_HEAD_UNPROVEN",
        reviewed_scheduled_run_count=source.run_count,
        reviewed_manifest_batch_count=source.observed_manifest_count,
        reviewed_unique_source_heads=source.unique_head_commits_in_sample,
        source_cron_expression=source.source_controlled_cron_expression,
        median_job_queue_seconds=source.median_job_created_to_started_seconds,
        historical_audit_run_id=AUDIT_RUN_ID,
        historical_full_sha_pairs=AUDIT_VERIFIED_PAIRS,
        historical_closed_m5_bars=AUDIT_CLOSED_M5,
        historical_head_hour_utc=AUDIT_HEAD_HOUR_UTC.isoformat(),
        historical_head_sha256=AUDIT_HEAD_SHA256,
        historical_h4_exact_matches=audit.exact_complete_h4_matches,
        manifest_hours_missing_in_reviewed_sample=0,
        time_since_historical_audit_seconds=(
            report_as_of_utc - audit.finished_utc).total_seconds(),
        source_head_identities_match_reviewed_sample=True,
    )
