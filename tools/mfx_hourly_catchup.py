"""A04/P0.51 — bounded recovery of CLOSED, complete UTC M5 hourly batches.

Pure selection + existing immutable chunk/manifest commit engine. Never
synthesize missing candles, override sealed history, or infer trade signals.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_engine import validate_m5
from mfx_cache.v2_batch_commit import BatchResult, PrivateObjectStore, commit_hour

MAX_RECOVERY_BATCHES = 4
MAX_VENDOR_M5_ROWS = 120


def latest_eligible_closed_hour(now_utc: datetime) -> datetime:
    """Last M5 UTC hourly batch whose END + 5 minutes is safely elapsed.

    A delayed GitHub cron can arrive at :00..:04 *next hour*. Do not skip
    older catchup hours merely because the current minute is less than five.
    The immediately previous hour itself still waits for its +5m grace.
    """
    if (type(now_utc) is not datetime or now_utc.tzinfo is None
            or now_utc.utcoffset() != timedelta(0)):
        raise ValueError("P067_EXACT_UTC_REQUIRED")
    boundary = now_utc.replace(minute=0, second=0, microsecond=0)
    return boundary - timedelta(hours=2 if now_utc.minute < 5 else 1)


def plan_bounded_catchup(
    observed: tuple[ClosedM5Bar, ...], *,
    previous_hour_utc: str | None, now_utc: datetime,
) -> tuple[tuple[datetime, tuple[ClosedM5Bar, ...]], ...]:
    """Choose <=4 whole hours chronologically from one 120-row vendor fetch.

    Initial bootstrap deliberately preserves the old one-hour-only behavior.
    Missing/partial hours are never invented; any skipped historical hours
    are marked as gaps by the immutable B1 commit engine.
    """
    if (type(now_utc) is not datetime or now_utc.tzinfo is None
            or now_utc.utcoffset() != timedelta(0)):
        raise ValueError("P051_EXACT_UTC_REQUIRED")
    if type(observed) is not tuple or len(observed) > MAX_VENDOR_M5_ROWS:
        raise ValueError("P051_VENDOR_M5_BOUNDED_REQUIRED")
    if not observed:
        return ()
    validate_m5(observed, asof_utc=now_utc)

    latest_hour = latest_eligible_closed_hour(now_utc)
    previous: datetime | None = None
    if previous_hour_utc is not None:
        if type(previous_hour_utc) is not str:
            raise ValueError("P051_PREVIOUS_HOUR_INVALID")
        try:
            previous = datetime.fromisoformat(previous_hour_utc)
        except ValueError as exc:
            raise ValueError("P051_PREVIOUS_HOUR_INVALID") from exc
        if (previous.tzinfo is None or previous.utcoffset() != timedelta(0)
                or previous.minute != 0 or previous.second != 0
                or previous.microsecond != 0
                or not previous_hour_utc.endswith("+00:00")):
            raise ValueError("P051_PREVIOUS_HOUR_INVALID")

    candidates: dict[datetime, list[ClosedM5Bar]] = {}
    for bar in observed:
        stamp = datetime.fromisoformat(bar.start_utc)
        hour = stamp.replace(minute=0, second=0, microsecond=0)
        if (hour > latest_hour
                or (previous is not None and hour <= previous)
                or (previous is None and hour != latest_hour)):
            continue
        candidates.setdefault(hour, []).append(bar)

    ready: list[tuple[datetime, tuple[ClosedM5Bar, ...]]] = []
    for hour, rows in sorted(candidates.items()):
        expected = tuple(
            (hour + timedelta(minutes=5*i)).isoformat() for i in range(12))
        if tuple(x.start_utc for x in rows) != expected:
            continue  # quarantine incomplete/partial hour, no interpolation
        ready.append((hour, tuple(rows)))
        if len(ready) == MAX_RECOVERY_BATCHES:
            break
    return tuple(ready)


def commit_bounded_catchup(
    store: PrivateObjectStore,
    batches: tuple[tuple[datetime, tuple[ClosedM5Bar, ...]], ...],
    *, real_now_utc: datetime,
) -> tuple[BatchResult, ...]:
    """Replay complete hours oldest first through the existing B1 verifier.

    Simulated as-of only selects a historical target hour; NEVER newer than
    actual wall-clock time or the close+5min eligibility for a given batch.
    Only the original B1 engine performs cloud writes and readbacks.
    """
    if (type(real_now_utc) is not datetime or real_now_utc.tzinfo is None
            or real_now_utc.utcoffset() != timedelta(0)
            or len(batches) > MAX_RECOVERY_BATCHES):
        raise ValueError("P051_RECOVERY_CLOCK_OR_BATCH_BOUND")
    results: list[BatchResult] = []
    previous_target: datetime | None = None
    for hour, rows in batches:
        if previous_target is not None and hour <= previous_target:
            raise ValueError("P051_RECOVERY_BATCHES_UNORDERED")
        previous_target = hour
        hour_asof = hour + timedelta(hours=1, minutes=5)
        if hour_asof > real_now_utc:
            raise ValueError("P051_RECOVERY_FUTURE_TARGET")
        result = commit_hour(store, now_utc=hour_asof, observed=rows)
        if (result.status != "BATCH_COMMITTED"
                or result.committed_hour_utc != hour.isoformat()
                or result.new_closed_m5 != 12):
            raise ValueError("P051_RECOVERY_UNEXPECTED_COMMIT_RESULT")
        results.append(result)
    return tuple(results)
