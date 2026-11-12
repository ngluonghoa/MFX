"""A04/P0.88: pure GitHub job-stage vs Drive creation time correlation.

Consumes ONLY externally supplied, sanitized API timestamps plus P0.87's
immutable scheduled-run/manifest cohort. No HTTP, Drive, vendor, broker or
workflow changes. Even identical clocks do not authenticate a scheduled tick.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median

from tools.mfx_m5_scheduler_cohort_evidence import (
    ObservedScheduledRun, evaluate_observed_m5_schedule_cohort,
)

SCHEMA = "MFX_A04_P88_M5_GITHUB_JOB_STAGE_CORRELATION_V1"


def _utc(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


@dataclass(frozen=True, slots=True)
class ObservedGitHubJob:
    run_id: int
    job_id: int
    run_created_utc: datetime
    job_created_utc: datetime
    job_started_utc: datetime
    job_completed_utc: datetime
    sync_step_started_utc: datetime
    sync_step_completed_utc: datetime
    job_conclusion: str = "success"


@dataclass(frozen=True, slots=True)
class M5JobStageReceipt:
    schema: str
    status: str
    run_count: int
    manifest_count: int
    median_run_to_job_create_seconds: float
    median_job_queue_seconds: float
    maximum_job_queue_seconds: float
    median_job_runtime_seconds: float
    maximum_job_runtime_seconds: float
    median_sync_step_seconds: float
    median_run_to_first_manifest_seconds: float
    all_manifests_within_sync_step: bool
    all_hours_contiguous_in_sample: bool
    original_event_dispatch_timestamp_authenticated: bool = False
    actual_scheduler_tick_matched_to_run: bool = False
    pre_run_github_delay_caused_by_scheduler_proven: bool = False
    concurrency_group_wait_proven: bool = False
    vendor_first_price_availability_proven: bool = False
    full_m5_history_sha_attested_by_this_check: bool = False
    production_cron_edit_authorized: bool = False
    native_h4_replacement_authorized: bool = False
    live_v2_or_trading_authorized: bool = False
    provider_requests_by_this_check: int = 0
    drive_writes_by_this_check: int = 0
    broker_orders_by_this_check: int = 0


def correlate_m5_job_stages(
    runs: tuple[ObservedScheduledRun, ...],
    jobs: tuple[ObservedGitHubJob, ...],
) -> M5JobStageReceipt:
    """Compare GitHub run/jobs and Drive stages, fail-closed on a false join.

    These same-run timestamps do not expose github.event.schedule dispatch
    time, resource-lock acquisition time, source price publication or the
    identity of the actual historical cron tick.
    """
    cohort = evaluate_observed_m5_schedule_cohort(runs)
    if (type(jobs) is not tuple or len(jobs) != len(runs)
            or not jobs or len(jobs) > 100):
        raise ValueError("P088_JOBS_COHORT_MISMATCH")
    ids = {r.run_id for r in runs}
    by_id: dict[int, ObservedGitHubJob] = {}
    job_ids: set[int] = set()
    r_to_job: list[float] = []
    queues: list[float] = []
    runtimes: list[float] = []
    syncs: list[float] = []
    run_to_first_manifest: list[float] = []
    for job in jobs:
        if (type(job) is not ObservedGitHubJob
                or type(job.run_id) is not int or type(job.job_id) is not int
                or job.run_id not in ids or job.run_id in by_id
                or job.job_id <= 0 or job.job_id in job_ids
                or job.job_conclusion != "success"):
            raise ValueError("P088_JOB_ID_OR_CONCLUSION_UNTRUSTED")
        clocks = (
            job.run_created_utc, job.job_created_utc, job.job_started_utc,
            job.sync_step_started_utc, job.sync_step_completed_utc,
            job.job_completed_utc,
        )
        if (not all(_utc(t) for t in clocks)
                or any(a > b for a, b in zip(clocks, clocks[1:]))):
            raise ValueError("P088_JOB_CLOCK_ORDER_INVALID")
        by_id[job.run_id] = job
        job_ids.add(job.job_id)
    if set(by_id) != ids:
        raise ValueError("P088_JOB_COVERAGE_MISMATCH")
    for run in runs:
        job = by_id[run.run_id]
        if job.run_created_utc != run.run_created_utc:
            raise ValueError("P088_RUN_JOIN_TIMESTAMP_MISMATCH")
        for batch in run.batches:
            if (batch.manifest_created_utc < job.sync_step_started_utc
                    or batch.manifest_created_utc > job.sync_step_completed_utc):
                raise ValueError("P088_MANIFEST_NOT_IN_MATCHED_WRITER_STEP")
        r_to_job.append(
            (job.job_created_utc - job.run_created_utc).total_seconds())
        queues.append(
            (job.job_started_utc - job.job_created_utc).total_seconds())
        runtimes.append(
            (job.job_completed_utc - job.job_started_utc).total_seconds())
        syncs.append(
            (job.sync_step_completed_utc - job.sync_step_started_utc).total_seconds())
        run_to_first_manifest.append(
            (run.batches[0].manifest_created_utc
             - job.run_created_utc).total_seconds())
    no_gaps = cohort.missing_hours_between_observed_batches == 0
    return M5JobStageReceipt(
        schema=SCHEMA,
        status=("OBSERVED_GITHUB_JOB_STAGES_CONSISTENT_CAUSE_UNVERIFIED"
                if no_gaps else "OBSERVED_M5_HOUR_GAPS_RECHECK_REQUIRED"),
        run_count=len(runs),
        manifest_count=cohort.observed_manifest_count,
        median_run_to_job_create_seconds=median(r_to_job),
        median_job_queue_seconds=median(queues),
        maximum_job_queue_seconds=max(queues),
        median_job_runtime_seconds=median(runtimes),
        maximum_job_runtime_seconds=max(runtimes),
        median_sync_step_seconds=median(syncs),
        median_run_to_first_manifest_seconds=median(run_to_first_manifest),
        all_manifests_within_sync_step=True,
        all_hours_contiguous_in_sample=no_gaps,
    )
