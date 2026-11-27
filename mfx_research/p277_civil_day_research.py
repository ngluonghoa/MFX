"""M5-derived UTC civil-day sensitivity, never native Forex D1 or a signal."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from mfx_cache.td_m5_codec import ClosedM5Bar, _price
from mfx_research.shared_pivot_selection import strict_pivot_indices

HOUR = timedelta(hours=1)
M5 = timedelta(minutes=5)
DAY = timedelta(days=1)
START = date(2026, 11, 18)


@dataclass(frozen=True, slots=True)
class CivilDayStudy:
    complete_days: int
    complete_weekend_days: int
    incomplete_closed_days: int
    latest_contiguous_days: int
    one_one_structure_capacity: bool
    two_two_structure_capacity: bool

    def public_summary(self) -> dict[str, object]:
        return {
            "basis": "UTC_CIVIL_DAY_M5_ARCHIVE_PROXY_NOT_NATIVE_D1",
            "complete_days": self.complete_days,
            "complete_weekend_days": self.complete_weekend_days,
            "incomplete_closed_days": self.incomplete_closed_days,
            "latest_contiguous_days": self.latest_contiguous_days,
            "one_one_structure_capacity": self.one_one_structure_capacity,
            "two_two_structure_capacity": self.two_two_structure_capacity,
            "native_d1_calendar_qualified": False,
            "publisher_first_known_verified": False,
            "historical_oos_qualified": False,
            "action": "NO_SIGNAL",
        }


def _utc(value: datetime) -> None:
    if type(value) is not datetime or value.utcoffset() != timedelta(0):
        raise ValueError("P277_EXACT_UTC_REQUIRED")


def _capacity(prices: tuple[tuple[Decimal, Decimal], ...], width: int) -> bool:
    pivots = strict_pivot_indices(prices, width, width)
    return all(sum(kind == k for _, kind in pivots) >= 2 for k in ("HIGH", "LOW"))


def study_civil_days(
    raw: tuple[ClosedM5Bar, ...],
    commits: tuple[tuple[datetime, datetime], ...],
    *,
    cutoff: datetime,
) -> CivilDayStudy:
    """Only complete closed UTC days of the existing SHA-audited M5 prefix.

    The caller owns SHA provenance. Archive visibility is a proxy, not first-known.
    Weekend batches are counted, never asserted to be tradable Forex sessions.
    """
    _utc(cutoff)
    if type(raw) is not tuple or type(commits) is not tuple or (
        len(commits) > 256 or len(raw) != 12 * len(commits)
    ):
        raise ValueError("P277_BOUNDED_HOUR_JOIN_REQUIRED")
    groups: dict[date, list[tuple[datetime, Decimal, Decimal]]] = {}
    previous_end: datetime | None = None
    previous_known: datetime | None = None
    for i, (known, end) in enumerate(commits):
        _utc(known)
        _utc(end)
        if (end.minute or end.second or end.microsecond or end > known
                or (previous_end is not None and end <= previous_end)
                or (previous_known is not None and known < previous_known)):
            raise ValueError("P277_HOUR_CLOCK_DRIFT")
        previous_end, previous_known = end, known
        for j, bar in enumerate(raw[12*i:12*(i+1)]):
            if type(bar) is not ClosedM5Bar:
                raise ValueError("P277_TYPED_M5_REQUIRED")
            stamp = datetime.fromisoformat(bar.start_utc)
            _utc(stamp)
            if stamp != end-HOUR+j*M5:
                raise ValueError("P277_EXACT_M5_GRID_REQUIRED")
            o, hi, lo, c = (_price(v, "civil_day") for v in
                             (bar.open, bar.high, bar.low, bar.close))
            if lo > min(o, c) or hi < max(o, c) or lo > hi:
                raise ValueError("P277_INVALID_OHLC")
            if known <= cutoff and stamp.date() >= START:
                groups.setdefault(stamp.date(), []).append((stamp, hi, lo))
    complete: dict[date, tuple[Decimal, Decimal]] = {}
    incomplete = 0
    for day, rows in groups.items():
        start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        if start+DAY > cutoff:
            continue
        if len(rows) != 288 or any(row[0] != start+i*M5 for i, row in enumerate(rows)):
            incomplete += 1
            continue
        complete[day] = (max(r[1] for r in rows), min(r[2] for r in rows))
    if groups:
        first = min(groups)
        last = cutoff.date()-DAY
        if last >= first:
            incomplete += sum(first+timedelta(days=i) not in groups
                              for i in range((last-first).days+1))
    # Only the immediately preceding complete civil-day suffix is eligible.
    current = cutoff.date()-DAY
    suffix: list[tuple[Decimal, Decimal]] = []
    while current in complete:
        suffix.append(complete[current])
        current -= DAY
    prices = tuple(reversed(suffix))
    return CivilDayStudy(len(complete), sum(d.weekday() >= 5 for d in complete),
                         incomplete, len(prices), _capacity(prices, 1), _capacity(prices, 2))
