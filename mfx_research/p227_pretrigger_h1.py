"""P227: H1 context as actually archive-visible before the two M15 trigger bars.

Current immutable archive metadata is a proxy, never publisher first-known.
Private MID arithmetic under the pinned, explicitly unapproved MFX draft.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_cache.v2_engine import derive_intraday, validate_m5
from mfx_research.mfx_b2s2_confirmed_policy_v2 import _p160_still_pinned
from mfx_research.mfx_b2s2_independent_policy_draft import (
    read_independent_mfx_policy_draft,
)
from mfx_research.six_tf_readonly_context import _expected_last_closed

HOUR = timedelta(hours=1)
M5 = timedelta(minutes=5)
M15 = timedelta(minutes=15)
MAX_HOURS = 256


@dataclass(frozen=True, slots=True, repr=False)
class PrivatePretriggerH1:
    status: str
    visible_contiguous_h1_rows: int
    cutoff_utc: datetime = field(repr=False)
    mean_tr: Decimal | None = field(default=None, repr=False)
    support_zone: tuple[Decimal, Decimal] | None = field(default=None, repr=False)
    resistance_zone: tuple[Decimal, Decimal] | None = field(default=None, repr=False)
    action: str = "NO_SIGNAL"
    publisher_first_known_verified: bool = False
    numeric_policy_approved: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    source_context_sha256: str | None = field(default=None, repr=False)


def _utc(value: datetime) -> None:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P227_EXACT_UTC_CLOCK_REQUIRED")


def calculate_pretrigger_h1(
    raw: tuple[ClosedM5Bar, ...],
    commits: tuple[tuple[datetime, datetime], ...],
    *, latest_m15_open: datetime, decision_utc: datetime,
) -> PrivatePretriggerH1:
    """Use only full source hours committed by the FIRST trigger candle open.

    Each commit is (observed manifest availability, source hour end).
    Caller supplies the already SHA-audited P219 raw prefix; no new I/O.
    Never include an hour merely because it is visible by decision close.
    """
    _utc(latest_m15_open)
    _utc(decision_utc)
    if (latest_m15_open.minute % 15 or latest_m15_open.second
            or latest_m15_open.microsecond
            or latest_m15_open + M15 != _expected_last_closed(decision_utc, 15)):
        raise ValueError("P227_LATEST_CLOSED_TRIGGER_GRID_REQUIRED")
    _validate_hour_prefix_shape(raw, commits)
    if datetime.fromisoformat(raw[-1].start_utc) + M5 != latest_m15_open + M15:
        raise ValueError("P227_TRIGGER_SOURCE_TIP_MISMATCH")
    return _calculate_archive_h1_at_cutoff(
        raw, commits, cutoff=latest_m15_open-M15, decision_utc=decision_utc)


def _validate_hour_prefix_shape(
    raw: tuple[ClosedM5Bar, ...], commits: tuple[tuple[datetime, datetime], ...],
) -> None:
    if (type(commits) is not tuple or not 1 <= len(commits) <= MAX_HOURS
            or type(raw) is not tuple or len(raw) != 12 * len(commits)):
        raise ValueError("P227_EXACT_BOUNDED_SHA_HOUR_PREFIX_REQUIRED")


def _calculate_archive_h1_at_cutoff(
    raw: tuple[ClosedM5Bar, ...], commits: tuple[tuple[datetime, datetime], ...],
    *, cutoff: datetime, decision_utc: datetime,
) -> PrivatePretriggerH1:
    """Internal archive prefix calculation; a caller must bind its trigger."""
    _utc(cutoff)
    _utc(decision_utc)
    if (cutoff >= decision_utc or cutoff.minute % 15 or cutoff.second
            or cutoff.microsecond):
        raise ValueError("P232_SETUP_CUTOFF_GRID_REQUIRED")
    _validate_hour_prefix_shape(raw, commits)
    validate_m5(raw, asof_utc=decision_utc)
    visible = 0
    previous_known: datetime | None = None
    previous_end: datetime | None = None
    for i, (known, end) in enumerate(commits):
        _utc(known)
        _utc(end)
        if (end.minute or end.second or end.microsecond or end > known
                or known > decision_utc
                or (previous_known is not None and known < previous_known)
                or (previous_end is not None and end <= previous_end)):
            raise ValueError("P227_NONCAUSAL_ARCHIVE_CLOCK")
        hour = raw[i*12:(i+1)*12]
        if any(datetime.fromisoformat(b.start_utc) != end - HOUR + j*M5
               for j, b in enumerate(hour)):
            raise ValueError("P227_ARCHIVE_HOUR_ALIGNMENT_DRIFT")
        visible += int(known <= cutoff and end <= cutoff)
        previous_known, previous_end = known, end
    if visible == 0:
        return PrivatePretriggerH1("NO_PRETRIGGER_ARCHIVE_HOUR", 0, cutoff)
    # The grace fence is only for closed-slot arithmetic, not first-known.
    eligible = tuple(b for b in raw[:12*visible]
                     if datetime.fromisoformat(b.start_utc) + M5
                     <= cutoff - timedelta(seconds=15))
    if not eligible:
        return PrivatePretriggerH1("NO_PRETRIGGER_ARCHIVE_HOUR", 0, cutoff)
    bars = derive_intraday(eligible, "H1", asof_utc=cutoff).candles
    if not bars or datetime.fromisoformat(bars[-1].end_utc) != _expected_last_closed(cutoff, 60):
        return PrivatePretriggerH1("PRETRIGGER_H1_STALE", 0, cutoff)
    _p160_still_pinned()
    policy = read_independent_mfx_policy_draft()
    needed = max(policy.h1_tr_mean_period + 1, policy.h1_zone_lookback)
    suffix = bars[-needed:]
    start = len(suffix) - 1
    while start > 0 and suffix[start-1].end_utc == suffix[start].start_utc:
        start -= 1
    suffix = suffix[start:]
    if len(suffix) < needed:
        return PrivatePretriggerH1("PRETRIGGER_H1_HISTORY_INSUFFICIENT", len(suffix), cutoff)
    tr = [max(Decimal(x.high)-Decimal(x.low),
              abs(Decimal(x.high)-Decimal(prev.close)),
              abs(Decimal(x.low)-Decimal(prev.close)))
          for prev, x in zip(suffix, suffix[1:])]
    period = policy.h1_tr_mean_period
    mean = sum(tr[-period:], Decimal(0)) / Decimal(period)
    if mean <= 0:
        return PrivatePretriggerH1("PRETRIGGER_H1_ZERO_RANGE", len(suffix), cutoff)
    zone = suffix[-policy.h1_zone_lookback:]
    low, high = min(Decimal(x.low) for x in zone), max(Decimal(x.high) for x in zone)
    width = mean * policy.h1_width_multiple
    if high - width <= 0:
        return PrivatePretriggerH1("PRETRIGGER_H1_NONPOSITIVE_ZONE", len(suffix), cutoff)
    source_context = digest({"schema": "P237_H1_DRAFT_INPUT_V1",
                             "cutoff": cutoff.isoformat(),
                             "policy": policy.canonical_sha256,
                             "source": [b.source_sha256 for b in suffix]})
    return PrivatePretriggerH1(
        "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED", len(suffix), cutoff, mean,
        (low, low+width), (high-width, high),
        source_context_sha256=source_context,
    )
