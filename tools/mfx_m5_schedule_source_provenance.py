"""A04/P0.89: offline run-source identity / scheduler provenance boundary.

This code only joins caller-supplied GitHub REST run metadata, previously
observed job stages and immutable Drive filename timestamps. It cannot fetch
GitHub, authenticate arbitrary caller fields, access Drive or vendor APIs,
or infer the actual event dispatch tick from github.event.schedule.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median

from tools.mfx_m5_job_lifecycle_evidence import (
    ObservedGitHubJob, correlate_m5_job_stages,
)
from tools.mfx_m5_scheduler_cohort_evidence import (
    ObservedScheduledRun, evaluate_observed_m5_schedule_cohort,
)

SCHEMA = "MFX_A04_P89_SCHEDULE_SOURCE_PROVENANCE_V1"
REPOSITORY = "ngluonghoa/MFX"
WORKFLOW_ID = 413180668
WORKFLOW_PATH = ".github/workflows/twelve-data-cache.yml"
WORKFLOW_BLOB_SHA = "c506c0c7212e17d20ea22090e1887fd8aa7bf38b"
CRON_EXPRESSION_IN_SOURCE = "10 * * * *"


def _utc(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


def _sha(value: object) -> bool:
    return (type(value) is str and len(value) == 40
            and all(c in "0123456789abcdef" for c in value))


@dataclass(frozen=True, slots=True)
class ObservedRunSource:
    run_id: int
    run_attempt: int
    event_name: str
    workflow_id: int
    workflow_path: str
    repository: str
    head_sha: str
    checked_workflow_blob_sha: str
    created_at_utc: datetime
    run_started_at_utc: datetime
    conclusion: str


@dataclass(frozen=True, slots=True)
class M5RunSourceReceipt:
    schema: str
    status: str
    run_count: int
    observed_manifest_count: int
    unique_head_commits_in_sample: int
    distinct_workflow_blobs_in_sample: int
    source_controlled_cron_expression: str
    median_run_created_to_run_started_seconds: float
    median_job_created_to_started_seconds: float
    median_job_started_to_finished_seconds: float
    historical_unverified_hour_gaps_in_sample: int
    retry_attempts_need_separate_review: int
    source_blob_identity_matches_pinned_review: bool
    # This is a caller-supplied provenance receipt, not external trust.
    externally_authenticated_source_and_event_receipt: bool = False
    actual_scheduled_tick_utc_authenticated: bool = False
    internal_github_event_dispatch_utc_observed: bool = False
    concurrency_wait_before_run_created_proven: bool = False
    vendor_first_available_candle_utc_observed: bool = False
    gh_scheduler_root_cause_proven: bool = False
    cron_or_workflow_change_authorized: bool = False
    provider_probe_authorized: bool = False
    live_cache_writer_change_authorized: bool = False
    native_h4_replacement_authorized: bool = False
    external_witness_cas_authorized: bool = False
    numeric_trading_or_broker_authorized: bool = False
    provider_calls_by_this_module: int = 0
    drive_writes_by_this_module: int = 0
    broker_orders_by_this_module: int = 0


def classify_schedule_source_provenance(
    runs: tuple[ObservedScheduledRun, ...],
    jobs: tuple[ObservedGitHubJob, ...],
    metadata: tuple[ObservedRunSource, ...],
) -> M5RunSourceReceipt:
    """Fail closed on mixed source versions, fake event types and bad joins.

    The pinned workflow blob was read externally for 7 distinct historical
    source commits. Neither run_started_at nor the cron expression is an
    authenticated timestamp for original GitHub's internal schedule event.
    """
    stage = correlate_m5_job_stages(runs, jobs)
    cohort = evaluate_observed_m5_schedule_cohort(runs)
    if (type(metadata) is not tuple or len(metadata) != len(runs)
            or not metadata or len(metadata) > 100):
        raise ValueError("P089_RUN_SOURCE_COHORT_BOUND")
    sources: dict[int, ObservedRunSource] = {}
    heads: set[str] = set()
    blobs: set[str] = set()
    offsets: list[float] = []
    retries = 0
    jobs_by_id = {j.run_id: j for j in jobs}
    for record in metadata:
        if (type(record) is not ObservedRunSource
                or type(record.run_id) is not int
                or record.run_id <= 0
                or record.run_id in sources
                or type(record.run_attempt) is not int
                or record.run_attempt < 1
                or record.event_name != "schedule"
                or type(record.workflow_id) is not int
                or record.workflow_id != WORKFLOW_ID
                or record.workflow_path != WORKFLOW_PATH
                or record.repository != REPOSITORY
                or record.conclusion != "success"
                or not _sha(record.head_sha)
                or not _sha(record.checked_workflow_blob_sha)
                or record.checked_workflow_blob_sha != WORKFLOW_BLOB_SHA
                or not _utc(record.created_at_utc)
                or not _utc(record.run_started_at_utc)):
            raise ValueError("P089_SOURCE_EVENT_OR_CONFIG_RECHECK_REQUIRED")
        sources[record.run_id] = record
        heads.add(record.head_sha)
        blobs.add(record.checked_workflow_blob_sha)
        retries += record.run_attempt != 1
    if set(sources) != {r.run_id for r in runs}:
        raise ValueError("P089_RUN_SOURCE_COVERAGE_MISMATCH")
    for run in runs:
        source = sources[run.run_id]
        job = jobs_by_id[run.run_id]
        if (source.created_at_utc != run.run_created_utc
                or source.created_at_utc != job.run_created_utc
                or source.run_started_at_utc < source.created_at_utc
                or source.run_started_at_utc > job.job_started_utc):
            raise ValueError("P089_RUN_SOURCE_CLOCK_JOIN_MISMATCH")
        offsets.append(
            (source.run_started_at_utc-source.created_at_utc).total_seconds()
        )
    if not heads or len(blobs) != 1:
        raise ValueError("P089_SOURCE_BLOB_RECHECK_REQUIRED")
    gaps = cohort.missing_hours_between_observed_batches
    if gaps:
        status = "P089_OBSERVED_HOURLY_GAPS_RECHECK_REQUIRED"
    elif retries:
        status = "P089_RETRY_ATTEMPT_RECHECK_REQUIRED"
    else:
        status = "P089_WORKFLOW_BLOB_SAME_CAUSAL_ORIGIN_UNVERIFIED"
    return M5RunSourceReceipt(
        schema=SCHEMA,
        status=status,
        run_count=len(runs),
        observed_manifest_count=cohort.observed_manifest_count,
        unique_head_commits_in_sample=len(heads),
        distinct_workflow_blobs_in_sample=len(blobs),
        source_controlled_cron_expression=CRON_EXPRESSION_IN_SOURCE,
        median_run_created_to_run_started_seconds=median(offsets),
        median_job_created_to_started_seconds=stage.median_job_queue_seconds,
        median_job_started_to_finished_seconds=stage.median_job_runtime_seconds,
        historical_unverified_hour_gaps_in_sample=gaps,
        retry_attempts_need_separate_review=retries,
        source_blob_identity_matches_pinned_review=True,
    )
