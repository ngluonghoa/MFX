"""P278 ordinal native-D1 vintage stability, not qualified trading structure."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from mfx_cache.native_fx_htf import NativeFXBar
from mfx_cache.td_m5_codec import _price
from mfx_research.p254_d1_research_vintage import select_private_d1_research_vintage
from mfx_research.shared_pivot_selection import strict_pivot_indices
from tools.audit_mfx_p209_d1_private_cache import PrivateSnapshot


@dataclass(frozen=True, slots=True)
class VintageStudy:
    visible_snapshots: int
    distinct_active_vintages: int
    overlap_comparisons: int
    changed_overlap_rows: int
    added_rows: int
    removed_rows: int
    one_one_capacity_vintages: int
    two_two_capacity_vintages: int
    latest_one_one_capacity: bool
    latest_two_two_capacity: bool

    def public_summary(self) -> dict[str, object]:
        return {
            "basis": "P254_WHOLE_VISIBLE_NATIVE_D1_VINTAGES_ORDINAL_ONLY",
            "visible_snapshots": self.visible_snapshots,
            "distinct_active_vintages": self.distinct_active_vintages,
            "overlap_comparisons": self.overlap_comparisons,
            "changed_overlap_rows": self.changed_overlap_rows,
            "added_rows": self.added_rows,
            "removed_rows": self.removed_rows,
            "one_one_capacity_vintages": self.one_one_capacity_vintages,
            "two_two_capacity_vintages": self.two_two_capacity_vintages,
            "latest_one_one_capacity": self.latest_one_one_capacity,
            "latest_two_two_capacity": self.latest_two_two_capacity,
            "native_d1_calendar_qualified": False,
            "publisher_first_known_verified": False,
            "historical_oos_qualified": False,
            "action": "NO_SIGNAL",
        }


def _prices(snapshot: PrivateSnapshot) -> tuple[tuple[Decimal, Decimal], ...]:
    labels: list[date] = []
    result: list[tuple[Decimal, Decimal]] = []
    for row in snapshot.rows:
        if (type(row) is not NativeFXBar or row.symbol != "EUR/USD"
                or row.interval != "1day" or row.price_side != "MID"
                or row.time_reference != "EXCHANGE_LOCAL_SESSION_DATE"
                or row.exchange_timezone != "Australia/Sydney"):
            raise ValueError("P278_NATIVE_D1_SCOPE_REQUIRED")
        label = date.fromisoformat(row.native_open_label)
        if label.isoformat() != row.native_open_label or (labels and label <= labels[-1]):
            raise ValueError("P278_ORDERED_D1_LABELS_REQUIRED")
        o, h, low, c = (_price(v, "native_d1") for v in
                        (row.open, row.high, row.low, row.close))
        if low > min(o, c) or h < max(o, c) or low > h:
            raise ValueError("P278_INVALID_D1_OHLC")
        labels.append(label)
        result.append((h, low))
    return tuple(result)


def _capacity(prices: tuple[tuple[Decimal, Decimal], ...], width: int) -> bool:
    pivots = strict_pivot_indices(prices, width, width)
    return all(sum(kind == k for _, kind in pivots) >= 2 for k in ("HIGH", "LOW"))


def study_native_vintages(
    history: tuple[tuple[datetime, PrivateSnapshot], ...],
    *,
    cutoff: datetime,
) -> VintageStudy:
    """Consume only P220 SHA-verified snapshots; never stitch or backdate.

    Active whole vintage is selected at each distinct archive-creation clock,
    not merely the most recently uploaded file. Ordinal capacity does not
    mean session continuity, confirmed trading pivots or a qualified trend.
    """
    # P254 validates bounded input, unique observation clocks and UTC.
    latest = select_private_d1_research_vintage(history, cutoff=cutoff)
    visible = tuple((created, snap) for created, snap in history if created <= cutoff)
    for _, snap in visible:
        _prices(snap)
    active: list[PrivateSnapshot] = []
    for clock in sorted({created for created, _ in visible}):
        selected = select_private_d1_research_vintage(visible, cutoff=clock)
        if selected is None:
            raise ValueError("P278_VISIBLE_VINTAGE_REQUIRED")
        if not active or selected.observed != active[-1].observed:
            active.append(selected)
    if (active[-1] if active else None) != latest:
        raise ValueError("P278_FINAL_SELECTION_DRIFT")
    overlap = changed = added = removed = 0
    for first, second in zip(active, active[1:]):
        before = {r.native_open_label: r.sha256() for r in first.rows}
        after = {r.native_open_label: r.sha256() for r in second.rows}
        common = before.keys() & after.keys()
        overlap += len(common)
        changed += sum(before[k] != after[k] for k in common)
        added += len(after.keys()-before.keys())
        removed += len(before.keys()-after.keys())
    one = tuple(_capacity(_prices(snap), 1) for snap in active)
    two = tuple(_capacity(_prices(snap), 2) for snap in active)
    return VintageStudy(len(visible), len(active), overlap, changed, added, removed,
                        sum(one), sum(two), one[-1] if one else False,
                        two[-1] if two else False)
