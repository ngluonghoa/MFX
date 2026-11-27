"""P278 ordinal native-D1 vintage stability, not qualified trading structure."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal

from mfx_cache.native_fx_htf import NativeFXBar
from mfx_cache.td_m5_codec import _price
from mfx_research.p254_d1_research_vintage import select_private_d1_research_vintage
from mfx_research.shared_pivot_selection import strict_pivot_indices
from tools.audit_mfx_p209_d1_private_cache import PrivateSnapshot


@dataclass(frozen=True, slots=True)
class RevisionProfile:
    """Descriptive active-vintage transition accounting; not maturity policy."""

    prior_terminal_overlaps: int
    prior_older_overlaps: int
    prior_terminal_changes: int
    prior_older_changes: int
    revised_distinct_labels: int
    numeric_open_changes: int
    numeric_high_changes: int
    numeric_low_changes: int
    numeric_close_changes: int
    sha_changes_without_numeric_ohlc_change: int
    observed_age_bins: tuple[int, int, int, int, int, int]

    def public_summary(self) -> dict[str, object]:
        return {
            "basis": "PRIOR_ACTIVE_TERMINAL_VS_OLDER_LABEL",
            "prior_terminal_overlaps": self.prior_terminal_overlaps,
            "prior_older_overlaps": self.prior_older_overlaps,
            "prior_terminal_changes": self.prior_terminal_changes,
            "prior_older_changes": self.prior_older_changes,
            "revised_distinct_labels": self.revised_distinct_labels,
            "numeric_open_changes": self.numeric_open_changes,
            "numeric_high_changes": self.numeric_high_changes,
            "numeric_low_changes": self.numeric_low_changes,
            "numeric_close_changes": self.numeric_close_changes,
            "sha_changes_without_numeric_ohlc_change":
                self.sha_changes_without_numeric_ohlc_change,
            "runner_observed_hours_after_sydney_civil_day_end": dict(zip(
                ("before_end", "0_to_lt3", "3_to_lt6", "6_to_lt12",
                 "12_to_lt24", "24_or_more"), self.observed_age_bins)),
            "age_is_not_market_session_close": True,
            "maturity_policy_selected": False,
            "publisher_first_known_verified": False,
        }


def _age_bin(label: str, observed: datetime) -> int:
    # A civil-date boundary, never an inferred Forex market close. Timezone
    # conversion (including DST) precedes subtraction on the UTC axis.
    boundary = datetime.combine(date.fromisoformat(label) + timedelta(days=1),
                                time.min, tzinfo=ZoneInfo("Australia/Sydney"))
    age = observed - boundary
    for i, hours in enumerate((0, 3, 6, 12, 24)):
        if age < timedelta(hours=hours):
            return i
    return 5


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
    revision_profile: RevisionProfile

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
            "revision_profile": self.revision_profile.public_summary(),
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
    terminal_overlap = older_overlap = terminal_changed = older_changed = 0
    no_numeric_change = 0
    field_changes = [0, 0, 0, 0]
    bins = [0, 0, 0, 0, 0, 0]
    revised_labels: set[str] = set()
    for first, second in zip(active, active[1:]):
        before = {r.native_open_label: r for r in first.rows}
        after = {r.native_open_label: r for r in second.rows}
        common = before.keys() & after.keys()
        overlap += len(common)
        terminal = first.rows[-1].native_open_label
        for label in common:
            is_terminal = label == terminal
            terminal_overlap += int(is_terminal)
            older_overlap += int(not is_terminal)
            a, b = before[label], after[label]
            if a.sha256() == b.sha256():
                continue
            changed += 1
            revised_labels.add(label)
            terminal_changed += int(is_terminal)
            older_changed += int(not is_terminal)
            numeric = tuple(Decimal(x) != Decimal(y) for x, y in zip(
                (a.open, a.high, a.low, a.close),
                (b.open, b.high, b.low, b.close)))
            for i, different in enumerate(numeric):
                field_changes[i] += int(different)
            no_numeric_change += int(not any(numeric))
            bins[_age_bin(label, second.observed)] += 1
        added += len(after.keys()-before.keys())
        removed += len(before.keys()-after.keys())
    if (terminal_overlap + older_overlap != overlap
            or terminal_changed + older_changed != changed
            or sum(bins) != changed):
        raise ValueError("P279_REVISION_ACCOUNTING_DRIFT")
    profile = RevisionProfile(terminal_overlap, older_overlap,
                              terminal_changed, older_changed, len(revised_labels),
                              field_changes[0], field_changes[1], field_changes[2],
                              field_changes[3], no_numeric_change,
                              (bins[0], bins[1], bins[2], bins[3], bins[4], bins[5]))
    one = tuple(_capacity(_prices(snap), 1) for snap in active)
    two = tuple(_capacity(_prices(snap), 2) for snap in active)
    return VintageStudy(len(visible), len(active), overlap, changed, added, removed,
                        sum(one), sum(two), one[-1] if one else False,
                        two[-1] if two else False, profile)
