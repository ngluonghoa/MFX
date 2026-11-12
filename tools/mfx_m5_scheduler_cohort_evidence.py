"""A04/P0.87 — hermetic, evidence-only M5 schedule/manifest latency cohort.

Caller supplies independently observed GitHub scheduled-run timestamps, writer
log receipts and Google Drive manifest name/creation time. THIS MODULE PERFORMS
NO CLOUD IO. It never knows which scheduler tick triggered a run; it cannot
attribute delay to GitHub dispatch, concurrency queue, provider or market hours.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
import re

from tools.mfx_hourly_catchup import latest_eligible_closed_hour

SCHEMA = "MFX_A04_P87_M5_SCHEDULE_MANIFEST_COHORT_V1"
EXPECTED_CRON_MINUTE = 10
MAX_RUNS = 100
MAX_BATCHES_PER_RUN = 4
_MANIFEST = re.compile(
    r"^MFX_TD_EURUSD_M5_V2_manifest_(\d{8}T\d{4}Z)_[0-9a-f]{64}\.json$"
)


def _utc(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


def _hour(value: object) -> bool:
    return (_utc(value) and value.minute == 0
            and value.second == 0 and value.microsecond == 0)


@dataclass(frozen=True, slots=True)
class ObservedM5Batch:
    hour_utc: datetime
    manifest_name: str
    manifest_created_utc: datetime


@dataclass(frozen=True, slots=True)
class ObservedScheduledRun:
    run_id: int
    event: str
    run_created_utc: datetime
    writer_status: str
    vendor_price_requests: int
    batches: tuple[ObservedM5Batch, ...]


@dataclass(frozen=True, slots=True)
class M5ScheduleCohortReceipt:
    schema: str
    status: str
    run_count: int
    observed_manifest_count: int
    multi_batch_recovery_runs: int
    total_writer_reported_vendor_requests: int
    missing_hours_between_observed_batches: int
    latest_observed_batch_hour_utc: str
    median_run_created_after_theoretical_tick_seconds: float
    median_manifest_after_hour_close_seconds: float
    median_run_created_to_manifest_seconds: float
    maximum_manifest_after_hour_close_seconds: float
    github_scheduled_tick_for_run_authenticated: bool = False
    github_schedule_delay_cause_proven: bool = False
    github_concurrency_queue_delay_proven: bool = False
    vendor_publication_delay_cause_proven: bool = False
    real_market_session_calendar_verified: bool = False
    entire_archive_sha_verified_by_this_module: bool = False
    cache_lag_permanently_fixed: bool = False
    native_h4_replacement_authorized: bool = False
    live_v2_authorized: bool = False
    numeric_signals_authorized: bool = False
    this_module_price_requests: int = 0
    this_module_drive_writes: int = 0
    this_module_broker_orders: int = 0


def evaluate_observed_m5_schedule_cohort(
    runs: tuple[ObservedScheduledRun, ...],
) -> M5ScheduleCohortReceipt:
    """Summarize coherent, caller-supplied observed timestamps, not cause.

    The cron-minute baseline is the first *theoretically eligible* tick
    after batch hour close. It is NOT the authenticated tick of any run.
    Delays can exceed an hour (backlog), and negative offsets are allowed
    for a prior delayed scheduled run that executes after close+5m.
    """
    if type(runs) is not tuple or not 1 <= len(runs) <= MAX_RUNS:
        raise ValueError("P087_RUN_COHORT_BOUND")
    run_ids: set[int] = set()
    hours: set[datetime] = set()
    tick_offsets: list[int] = []
    after_close: list[int] = []
    run_to_manifest: list[int] = []
    recoveries = 0
    reported_calls = 0

    for run in runs:
        if (type(run) is not ObservedScheduledRun
                or type(run.run_id) is not int or run.run_id <= 0
                or run.run_id in run_ids
                or run.event != "schedule"
                or not _utc(run.run_created_utc)
                or type(run.batches) is not tuple
                or not 1 <= len(run.batches) <= MAX_BATCHES_PER_RUN
                or type(run.vendor_price_requests) is not int
                or run.vendor_price_requests not in (0, 1)
                or run.writer_status != (
                    "BATCH_COMMITTED" if len(run.batches) == 1
                    else "BATCHES_COMMITTED")):
            raise ValueError("P087_RUN_RECEIPT_UNTRUSTED_OR_AMBIGUOUS")
        run_ids.add(run.run_id)
        recoveries += len(run.batches) > 1
        reported_calls += run.vendor_price_requests
        previous: datetime | None = None
        eligible = latest_eligible_closed_hour(run.run_created_utc)
        for batch in run.batches:
            if (type(batch) is not ObservedM5Batch
                    or not _hour(batch.hour_utc)
                    or not _utc(batch.manifest_created_utc)
                    or type(batch.manifest_name) is not str
                    or batch.manifest_created_utc < run.run_created_utc
                    or batch.hour_utc > eligible
                    or batch.hour_utc in hours
                    or (previous is not None
                        and batch.hour_utc <= previous))):
                raise ValueError("P087_BATCH_CLOCK_OR_ORDER_RECHECK_REQUIRED")
            match = _MANIFEST.fullmatch(batch.manifest_name)
            if (not match or match.group(1)
                    != batch.hour_utc.strftime("%Y%m%dT%H00Z")):
                raise ValueError("P087_MANIFEST_FILENAME_NOT_ATTESTED")
            if batch.manifest_created_utc < (
                    batch.hour_utc + timedelta(hours=1, minutes=5)):
                raise ValueError("P087_MANIFEST_BEFORE_CLOSED_HOUR_GRACE")
            hours.add(batch.hour_utc)
            previous = batch.hour_utc
            eligible_tick = (
                batch.hour_utc + timedelta(hours=1, minutes=EXPECTED_CRON_MINUTE))
            tick_offsets.append(round(
                (run.run_created_utc - eligible_tick).total_seconds(), 3))
            after_close.append(round(
                (batch.manifest_created_utc
                 - batch.hour_utc - timedelta(hours=1)).total_seconds(), 3))
            run_to_manifest.append(round(
                (batch.manifest_created_utc - run.run_created_utc).total_seconds(), 3))
    ordered = sorted(hours)
    missing = sum(
        int((b-a).total_seconds()//3600)-1
        for a, b in zip(ordered, ordered[1:])
    )
    return M5ScheduleCohortReceipt(
        schema=SCHEMA,
        status=("OBSERVED_BATCH_TIMELINE_CONSISTENT_CAUSE_UNVERIFIED"
                if not missing else "OBSERVED_M5_HOUR_GAPS_RECHECK_REQUIRED"),
        run_count=len(runs),
        observed_manifest_count=len(ordered),
        multi_batch_recovery_runs=recoveries,
        total_writer_reported_vendor_requests=reported_calls,
        missing_hours_between_observed_batches=missing,
        latest_observed_batch_hour_utc=ordered[-1].isoformat(),
        median_run_created_after_theoretical_tick_seconds=median(tick_offsets),
        median_manifest_after_hour_close_seconds=median(after_close),
        median_run_created_to_manifest_seconds=median(run_to_manifest),
        maximum_manifest_after_hour_close_seconds=max(after_close),
    )
