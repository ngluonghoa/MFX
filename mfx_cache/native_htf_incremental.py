"""A04/P0.59/P0.64 — PURE bounded source-native H4/D1 planning.

Do NOT infer Forex trading sessions. Provider prices are never fetched here.
The hourly or manual writer skips intervals without a newly eligible
closed native slot, requests a bounded overlap window only when due, and
fails closed for vendor revisions/history gaps.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, date
from typing import Any
from zoneinfo import ZoneInfo

from mfx_cache.native_fx_htf import NativeFXBatch, native_request_contract, H4_CLOSE_GRACE
from mfx_cache.native_htf_archive import (
    check_native_manifest, MAX_BATCH_BARS, plan_native_sealed,
    verify_native_sealed,
)

SYMBOL = "EUR/USD"
EXCHANGE_ZONE = "Australia/Sydney"
NATIVE_INTERVALS = ("4h", "1day")
MIN_OVERLAP_WINDOW = 24
EXTRA_SAFETY_ROWS = 4
# Twelve Data documents a typical REST candle publication delay of 0.3-2 min.
# Wait a conservative additional 15s after the upper end before even making
# a provider price request. This is an optimization, NOT a finality guarantee.
# Keep parser H4_CLOSE_GRACE independent: historical validation still filters
# source bars, and an occasionally stale provider answer still fails safe.
SOURCE_PUBLICATION_BUFFER = timedelta(minutes=2, seconds=15)


@dataclass(frozen=True, slots=True)
class IncrementalFetchPlan:
    symbol: str
    interval: str
    status: str
    request: dict[str, str] | None
    last_native_open_label: str | None
    latest_expected_closed_label: str
    calendar_slots_behind: int
    overlap_bar_count: int
    provider_requests_planned: int


def plan_native_fetch(
    *, interval: str, previous: dict[str, Any] | None,
    now_utc: datetime,
) -> IncrementalFetchPlan:
    """Conservative 0-or-1 call plan; not a statement of market sessions."""
    if interval not in NATIVE_INTERVALS:
        raise ValueError("P059_UNSUPPORTED_NATIVE_INTERVAL")
    if (type(now_utc) is not datetime or now_utc.tzinfo is None
            or now_utc.utcoffset() != timedelta(0)):
        raise ValueError("P059_REQUIRES_UTC")
    if previous is not None:
        check_native_manifest(
            previous,symbol=SYMBOL,interval=interval,zone=EXCHANGE_ZONE)
    if interval == "4h":
        # Avoid paying for H4 provider calls at the instant of candle
        # close. REST bars commonly appear up to ~2 minutes later; the
        # buffer also exceeds the parser's strict minimum close grace.
        safe = now_utc-max(H4_CLOSE_GRACE,SOURCE_PUBLICATION_BUFFER)
        current = safe.replace(hour=(safe.hour//4)*4,minute=0,
                               second=0,microsecond=0)
        expected = current-timedelta(hours=4)
        expected_label = expected.strftime("%Y-%m-%d %H:%M:%S")
        last = (datetime.strptime(
            previous["last_native_open_label"],"%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc) if previous is not None else None)
        if last is not None and (
            last.hour%4 or last.minute or last.second):
            raise ValueError("P059_LAST_H4_OFF_GRID")
        behind = (int((expected-last)//timedelta(hours=4))
                  if last is not None else 0)
    else:
        # Delay a new Sydney-local day until its preceding D1 candle
        # has had a conservative chance to publish. Subtract from UTC
        # BEFORE timezone conversion; this handles DST transitions.
        ready_local_day = (now_utc-SOURCE_PUBLICATION_BUFFER).astimezone(
            ZoneInfo(EXCHANGE_ZONE)).date()
        expected_day = ready_local_day-timedelta(days=1)
        expected_label = expected_day.isoformat()
        last_day = (date.fromisoformat(previous["last_native_open_label"])
                    if previous is not None else None)
        behind = (expected_day-last_day).days if last_day is not None else 0
    if behind < 0:
        raise ValueError("P059_FUTURE_OR_UNCLOSED_CACHE_TAIL")

    last_label = (previous["last_native_open_label"]
                  if previous is not None else None)
    prior_index = (previous["recent_native_bar_index"]
                   if previous is not None else [])
    if previous is not None and behind == 0:
        return IncrementalFetchPlan(
            symbol=SYMBOL,interval=interval,
            status="NO_NEW_CLOSED_SLOT_NO_VENDOR_CALL",
            request=None,last_native_open_label=last_label,
            latest_expected_closed_label=expected_label,
            calendar_slots_behind=0,overlap_bar_count=len(prior_index),
            provider_requests_planned=0,
        )

    if previous is None:
        size = MAX_BATCH_BARS
        state = "BOOTSTRAP_FULL_NATIVE_WINDOW"
    else:
        # Estimate source calendar slots plus the entire SHA-index overlap.
        # Never silently truncate prior SHA-bound candles when asleep for
        # longer than the safe max window; dedicated recovery is required.
        needed = behind+len(prior_index)+EXTRA_SAFETY_ROWS
        if needed > MAX_BATCH_BARS:
            raise ValueError("P059_INCREMENTAL_HISTORY_WINDOW_EXCEEDED")
        size = max(MIN_OVERLAP_WINDOW,needed)
        state = "INCREMENTAL_FETCH_REQUIRED"
    request = native_request_contract(symbol=SYMBOL,interval=interval)
    request["outputsize"] = str(size)
    return IncrementalFetchPlan(
        symbol=SYMBOL,interval=interval,status=state,
        request=request,last_native_open_label=last_label,
        latest_expected_closed_label=expected_label,
        calendar_slots_behind=behind,
        overlap_bar_count=len(prior_index),provider_requests_planned=1,
    )


def validate_incremental_source(
    batch: NativeFXBatch, *, previous: dict[str, Any] | None,
    plan: IncrementalFetchPlan,
) -> None:
    """Fail closed if provider omits/mutates any SHA-covered tail candle."""
    if (type(batch) is not NativeFXBatch
            or batch.symbol != SYMBOL or batch.interval != plan.interval
            or batch.exchange_timezone != EXCHANGE_ZONE
            or plan.request is None or plan.provider_requests_planned != 1):
        raise ValueError("P059_INVALID_SOURCE_OR_PLAN")
    if previous is not None:
        recent = {x["label"]: x["sha256"]
                  for x in previous["recent_native_bar_index"]}
        returned = {bar.native_open_label:bar.sha256()
                    for bar in batch.closed_bars}
        if any(label not in returned for label in recent):
            raise ValueError("P059_SOURCE_MISSING_SHA_OVERLAP")
        if any(returned[label] != sha for label,sha in recent.items()):
            raise ValueError("P059_SOURCE_NATIVE_REVISION_QUARANTINE")
    candidate = plan_native_sealed(batch,previous=previous)
    if candidate is not None:
        verify_native_sealed(candidate,previous=previous)
    elif previous is None:
        raise ValueError("P059_EMPTY_NATIVE_BOOTSTRAP")
