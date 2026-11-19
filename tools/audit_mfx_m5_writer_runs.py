"""P0.197: GitHub-only historical M5 writer workflow run evidence.

Read-only REST query of the *existing* Twelve Data hourly writer workflow.
The returned GitHub event timestamps do NOT prove when an hourly cron event
was actually delivered, nor explain why a provider/Drive batch was late.
No vendor, price, Drive, broker or trading calls; no credential output.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import re
from typing import Any, Callable, Mapping

from tools.read_main_push_ci_diagnostic import _get_json

REPO = "ngluonghoa/MFX"
WORKFLOW = "twelve-data-cache.yml"
NATIVE_WRITER_WORKFLOW = "mfx-native-htf-incremental-commit.yml"
EXPECTED_CRON_MINUTE = 10
NATIVE_EXPECTED_CRON_MINUTE = 25
MAX_RUNS = 60
MAX_PUBLIC_ROWS = 24
WINDOW = timedelta(hours=36)
_FIXED_PATH = (
    f"/repos/{REPO}/actions/workflows/{WORKFLOW}/runs"
    f"?event=schedule&per_page={MAX_RUNS}"
)
_TOKEN_ENV = "MFX_P197_ACTIONS_READ_TOKEN"
_ZULU = re.compile(r"^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
_ALLOWED_EVENT = ("push", "schedule", "workflow_dispatch")
_ALLOWED_STATUS = (
    "queued", "in_progress", "completed", "pending", "waiting", "requested",
)
_ALLOWED_CONCLUSION = (
    None, "success", "failure", "cancelled", "skipped", "timed_out",
    "action_required", "neutral", "stale",
)


def checked_environment(env: Mapping[str, str]) -> str:
    if (env.get("GITHUB_REPOSITORY") != REPO
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("GITHUB_EVENT_NAME") not in _ALLOWED_EVENT
            or env.get("GITHUB_API_URL") != "https://api.github.com"):
        raise ValueError("P197_TRUSTED_MAIN_GITHUB_API_CONTEXT_REQUIRED")
    token = env.get(_TOKEN_ENV, "")
    if (not token or len(token) > 4096 or token.strip() != token
            or any(ord(ch) <= 32 for ch in token)):
        raise ValueError("P197_ACTIONS_READ_ONLY_TOKEN_REQUIRED")
    return token


def _time(value: object, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    if type(value) is not str or not _ZULU.fullmatch(value):
        raise ValueError("P197_GITHUB_RUN_UTC_TIMESTAMP_REQUIRED")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("P197_GITHUB_RUN_UTC_TIMESTAMP_INVALID") from exc
    return parsed.replace(tzinfo=timezone.utc)


def inspect_writer_runs(
    document: object, *, asof_utc: datetime,
    workflow: str = WORKFLOW,
    expected_cron_minute: int = EXPECTED_CRON_MINUTE,
) -> dict[str, Any]:
    """Summarize provider-independent GitHub run metadata, never stdout.

    No expectation that every nominal cron slot is always delivered. Runs
    delayed over a UTC-hour boundary cannot be reliably assigned to slots
    without external scheduler event identity.
    """
    # P0.199 only permits the two ALREADY approved hourly MFX writers.
    # The timestamp parser is shared, never a claim of source availability.
    if (workflow, expected_cron_minute) not in (
        (WORKFLOW, EXPECTED_CRON_MINUTE),
        (NATIVE_WRITER_WORKFLOW, NATIVE_EXPECTED_CRON_MINUTE),
    ):
        raise ValueError("P199_UNREVIEWED_GITHUB_WORKFLOW_SCOPE")
    if (type(asof_utc) is not datetime or asof_utc.tzinfo is None
            or asof_utc.utcoffset() != timedelta(0)):
        raise ValueError("P197_EXACT_UTC_ASOF_REQUIRED")
    if (not isinstance(document, dict)
            or not isinstance(document.get("workflow_runs"), list)
            or len(document["workflow_runs"]) > MAX_RUNS):
        raise ValueError("P197_BOUNDED_WORKFLOW_LIST_REQUIRED")
    rows = []
    seen_ids: set[int] = set()
    for record in document["workflow_runs"]:
        if not isinstance(record, dict):
            raise ValueError("P197_UNEXPECTED_GITHUB_RUN_ENTRY")
        if record.get("event") != "schedule" or record.get("head_branch") != "main":
            continue
        number = record.get("id")
        if type(number) is not int or number <= 0 or number in seen_ids:
            raise ValueError("P197_DUPLICATE_OR_INVALID_GITHUB_RUN_ID")
        seen_ids.add(number)
        created = _time(record.get("created_at"))
        started = _time(record.get("run_started_at"), nullable=True)
        assert created is not None
        if (created > asof_utc + timedelta(minutes=1)
                or started is not None and started > asof_utc + timedelta(minutes=1)):
            raise ValueError("P197_FUTURE_GITHUB_RUN_METADATA")
        status = record.get("status")
        conclusion = record.get("conclusion")
        if status not in _ALLOWED_STATUS or conclusion not in _ALLOWED_CONCLUSION:
            raise ValueError("P197_UNEXPECTED_GITHUB_RUN_STATE")
        # GitHub can independently update these timestamps; never convert
        # an inconsistent pair into an invented queue delay.
        delta = int((started - created).total_seconds()) if started else None
        clock_order_valid = delta is None or delta >= 0
        if delta is not None and delta < 0:
            delta = None
        rows.append({
            "run_id": number,
            "created_utc": created.isoformat(),
            "started_utc": started.isoformat() if started else None,
            "created_clock_minute": created.minute,
            "observed_created_to_started_seconds": delta,
            "created_started_clock_order_valid": clock_order_valid,
            "status": status,
            "conclusion": conclusion,
            "_created": created,
        })
    rows.sort(key=lambda row: (row["_created"], row["run_id"]), reverse=True)
    earliest = asof_utc - WINDOW
    window_rows = [row for row in rows if earliest <= row["_created"] <= asof_utc]
    emitted = []
    for row in window_rows[:MAX_PUBLIC_ROWS]:
        emitted.append({key: value for key, value in row.items()
                        if not key.startswith("_")})
    completed = [x for x in window_rows if x["status"] == "completed"]
    failures = sum(x["conclusion"] in ("failure", "timed_out", "cancelled")
                   for x in completed)
    latest = window_rows[0] if window_rows else None
    return {
        "schema": ("MFX_P197_GITHUB_SCHEDULED_M5_WRITER_READONLY_V1"
                   if workflow == WORKFLOW else
                   "MFX_P199_GITHUB_SCHEDULED_NATIVE_WRITER_READONLY_V1"),
        "result": ("OBSERVED_GITHUB_SCHEDULE_RUN_METADATA"
                   if window_rows else "NO_RECENT_RUNS_OBSERVED_REASON_UNKNOWN"),
        "repository": REPO,
        "workflow": workflow,
        "asof_utc": asof_utc.isoformat(),
        "nominal_cron_utc_minute": expected_cron_minute,
        "window_hours": int(WINDOW.total_seconds() // 3600),
        "first_api_page_limit": MAX_RUNS,
        "first_page_only": True,
        "recent_schedule_runs_observed": len(window_rows),
        "recent_completed_success": sum(
            x["status"] == "completed" and x["conclusion"] == "success"
            for x in window_rows
        ),
        "recent_completed_failed_cancelled_timedout": failures,
        "recent_completed_other": len(completed) - failures - sum(
            x["conclusion"] == "success" for x in completed
        ),
        "recent_in_progress_or_queued": len(window_rows) - len(completed),
        "latest_schedule_run_id": latest["run_id"] if latest else None,
        "latest_schedule_run_created_utc": (
            latest["created_utc"] if latest else None),
        "last_24_observed_run_summaries": emitted,
        "nominal_cron_dispatch_slots_independently_attested": False,
        "github_run_creation_time_is_not_a_verified_cron_slot": True,
        "missed_or_skipped_schedule_events_inferred": False,
        "provider_api_response_and_quota_proven": False,
        "drive_cache_write_timing_proven_by_this_report": False,
        "may_publish_buy_sell": False,
        "market_price_requests": 0,
        "drive_writes": 0,
        "broker_orders": 0,
        "signal_action": "NO_SIGNAL",
    }


def main() -> None:
    token = checked_environment(os.environ)
    payload = _get_json(token, _FIXED_PATH)
    result = inspect_writer_runs(
        payload, asof_utc=datetime.now(timezone.utc),
    )
    print("MFX_P197_GITHUB_SCHEDULED_M5_WRITER_READONLY_AUDIT_PASS")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
