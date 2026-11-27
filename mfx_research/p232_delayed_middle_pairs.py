"""P232: retrospective M15 middle-pair research on sealed hourly archives.

The :15/:30 opens can have a complete settled pretrigger grid if the
previous hour was committed by :15. The pair is not available until the
current full-hour manifest commits. This is delayed research, not a live
entry, first-known attestation, or qualified historical OOS.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal

from mfx_cache.native_fx_htf import NativeFXBar
from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_engine import derive_intraday
from mfx_research.p263_private_ema_watch import (
    LATE_SEED_WINDOWS, PrivateEMAWatch, SEED_CLOCK_STATES, _observe_archive_ema, ema_clock_state,
    bind_private_ema_to_trigger, ema_seed_comparison_available, late_seed_window,
)
from mfx_research.p227_pretrigger_h1 import (
    PrivatePretriggerH1, _calculate_archive_h1_at_cutoff,
)
from mfx_research.p228_pretrigger_native import (
    PrivatePretriggerNative, calculate_pretrigger_native,
)
from mfx_research.p229_pretrigger_m15 import (
    PrivatePretriggerM15, _calculate_archive_geometry, early_observation_coverage,
)
from mfx_research.p230_private_boundary_path import (
    PrivateBoundaryReceipt, PrivateBoundaryPath, inspect_private_setup_boundaries,
)
from mfx_research.p231_private_trigger_identity import (
    PrivateTriggerIdentity, _identify_closed_trigger_pair, summarize_private_trigger_slots,
)
from mfx_research.mfx_b2s2_confirmed_policy_v2 import _p160_still_pinned
from mfx_research.mfx_b2s2_independent_policy_draft import read_independent_mfx_policy_draft
from mfx_research.six_tf_readonly_context import _expected_last_closed, _native_utc_start
from mfx_research.p237_private_setup_context_identity import (
    PrivateSetupContextIdentity, bind_private_setup_context,
)
from tools.audit_mfx_p209_d1_private_cache import PrivateSnapshot

MAX_SAMPLE = 32
MAX_HOURS = 256
M15 = timedelta(minutes=15)
HOUR = timedelta(hours=1)
GRACE = timedelta(seconds=15)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateDecisionSide:
    rule_id: str
    signed_distance_from_frozen_level: Decimal = field(repr=False)
    within_draft_chase_window: bool = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateDelayedDecision:
    trigger_end: datetime = field(repr=False)
    decision: datetime = field(repr=False)
    observed_closed_m15_bars: int
    closed_grid_complete: bool
    sides: tuple[PrivateDecisionSide, ...] = field(repr=False)
    expiry_policy_selected: bool = False
    numeric_policy_approved: bool = False
    action: str = "NO_SIGNAL"
    may_publish_buy_sell: bool = False
    may_trade: bool = False


def _inspect_delayed_decision(
    visible_raw: tuple[ClosedM5Bar, ...], h1: PrivatePretriggerH1,
    m15: PrivatePretriggerM15, *, trigger_end: datetime, decision: datetime,
) -> PrivateDelayedDecision:
    """P235: closed M15 path from frozen trigger to actual archive decision.

    Do not substitute a stale last close for the expected settled decision
    close. Only an unapproved MID draft geometry recheck, not a quote,
    entry, expiry selection, or post-entry monitoring.
    """
    for clock in (trigger_end, decision):
        if (type(clock) is not datetime or clock.tzinfo is None
                or clock.utcoffset() != timedelta(0)):
            raise ValueError("P235_EXACT_UTC_REQUIRED")
    if (type(h1) is not PrivatePretriggerH1 or type(m15) is not PrivatePretriggerM15
            or h1.cutoff_utc != trigger_end-2*M15 or m15.cutoff_utc != h1.cutoff_utc
            or decision-trigger_end < M15+GRACE
            or any(x.action != "NO_SIGNAL" or x.numeric_policy_approved
                   or x.publisher_first_known_verified or x.may_publish_buy_sell
                   or x.may_trade for x in (h1, m15)) or m15.d1_trend_qualified):
        raise ValueError("P235_DECISION_CONTEXT_DRIFT")
    expected = _expected_last_closed(decision, 15)
    post = tuple(b for b in visible_raw
                 if datetime.fromisoformat(b.start_utc) >= trigger_end)
    candles = derive_intraday(post, "M15", asof_utc=decision).candles if post else ()
    tip = trigger_end
    complete = True
    for candle in candles:
        start, end = map(datetime.fromisoformat, (candle.start_utc, candle.end_utc))
        if start < tip or end-start != M15 or end > expected:
            raise ValueError("P235_DECISION_GRID_DRIFT")
        complete = complete and start == tip
        tip = end
    complete = complete and bool(candles) and tip == expected
    sides = []
    if (complete and h1.status == "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED"
            and m15.status == "PRIVATE_M15_DRAFT_GEOMETRY_COMPUTED"):
        if (h1.mean_tr is None or not h1.mean_tr.is_finite() or h1.mean_tr <= 0
                or tuple(s.rule_id for s in m15.sides) != ("B2", "S2")):
            raise ValueError("P235_FROZEN_DRAFT_CONTEXT_DRIFT")
        _p160_still_pinned()
        chase = h1.mean_tr * read_independent_mfx_policy_draft().max_chase_multiple
        close = Decimal(candles[-1].close)
        for side in m15.sides:
            if side.level is None:
                continue
            if not side.level.is_finite() or side.level <= 0:
                raise ValueError("P235_FROZEN_LEVEL_DRIFT")
            distance = close-side.level if side.rule_id == "B2" else side.level-close
            sides.append(PrivateDecisionSide(side.rule_id, distance,
                                             0 < distance <= chase))
    return PrivateDelayedDecision(trigger_end, decision, len(candles), complete, tuple(sides))


@dataclass(frozen=True, slots=True, repr=False)
class PrivateDelayedMiddlePair:
    archive_decision_utc: datetime = field(repr=False)
    trigger_end_utc: datetime = field(repr=False)
    h1: PrivatePretriggerH1 = field(repr=False)
    native: PrivatePretriggerNative = field(repr=False)
    m15: PrivatePretriggerM15 = field(repr=False)
    boundary: PrivateBoundaryReceipt = field(repr=False)
    trigger_identity: PrivateTriggerIdentity = field(repr=False)
    delayed_decision: PrivateDelayedDecision = field(repr=False)
    setup_context_identity: PrivateSetupContextIdentity | None = field(repr=False)
    ema_watch: PrivateEMAWatch | None = field(default=None, repr=False)


PRECURSOR_STATES = ("complete", "prior_missing", "prior_late", "earlier_gap_or_late")
DECISION_STATES = ("complete", "interior_only", "trailing_only", "both_gaps")


@dataclass(frozen=True, slots=True, repr=False)
class MiddlePairClockCensus:
    verified_hours: int
    prior_hour_missing: int
    prior_hour_late: int
    earlier_history_gap_or_late: int
    private_eligible_indices: tuple[int, ...] = field(repr=False)
    private_precursor_states: tuple[str, ...] = field(repr=False)

    def public_summary(self) -> dict[str, int | bool]:
        eligible = len(self.private_eligible_indices)
        states = self.private_precursor_states
        if (type(states) is not tuple or len(states) != self.verified_hours
                or any(s not in PRECURSOR_STATES for s in states)
                or tuple(i for i, s in enumerate(states) if s == "complete")
                    != self.private_eligible_indices
                or tuple(states.count(s) for s in PRECURSOR_STATES[1:]) != (
                    self.prior_hour_missing, self.prior_hour_late,
                    self.earlier_history_gap_or_late)):
            raise ValueError("P243_PRECURSOR_STATE_ACCOUNTING_DRIFT")
        if (self.prior_hour_missing+self.prior_hour_late+self.earlier_history_gap_or_late
                +eligible != self.verified_hours):
            raise ValueError("P233_CLOCK_CENSUS_ACCOUNTING_DRIFT")
        return {"verified_hours": self.verified_hours,
                "prior_hour_missing_in_verified_tail": self.prior_hour_missing,
                "prior_hour_archived_after_setup": self.prior_hour_late,
                "earlier_required_history_gap_or_late": self.earlier_history_gap_or_late,
                "four_contiguous_h1_hours_available_before_setup": eligible,
                "clock_eligible_not_replayed_due_to_limit": max(0, eligible-MAX_SAMPLE),
                "selection_uses_prices_or_outcomes": False}


def middle_pair_clock_census(
    commits: tuple[tuple[datetime, datetime], ...],
) -> MiddlePairClockCensus:
    """Fixed four-hour precursor from pinned P160; clock-only selection."""
    if type(commits) is not tuple or len(commits)>MAX_HOURS:
        raise ValueError("P233_BOUNDED_COMMIT_HISTORY_REQUIRED")
    by_end: dict[datetime, datetime] = {}
    prev_known: datetime | None = None
    prev_end: datetime | None = None
    for known,end in commits:
        for clock in (known,end):
            if (type(clock) is not datetime or clock.tzinfo is None
                    or clock.utcoffset()!=timedelta(0)):
                raise ValueError("P233_EXACT_UTC_CLOCK_REQUIRED")
        if (end.minute or end.second or end.microsecond or known<end+GRACE
                or (prev_end is not None and end<=prev_end)
                or (prev_known is not None and known<prev_known)):
            raise ValueError("P233_ARCHIVE_CLOCK_DRIFT")
        by_end[end]=known
        prev_known,prev_end=known,end
    missing=late=gap=0
    eligible=[]
    states=[]
    for i,(_,end) in enumerate(commits):
        cutoff=end-3*M15
        prior=end-HOUR
        if prior not in by_end:
            missing+=1
            states.append("prior_missing")
        elif by_end[prior]>cutoff:
            late+=1
            states.append("prior_late")
        elif any(prior-j*HOUR not in by_end
                 or by_end[prior-j*HOUR]>cutoff for j in range(4)):
            gap+=1
            states.append("earlier_gap_or_late")
        else:
            eligible.append(i)
            states.append("complete")
    return MiddlePairClockCensus(len(commits),missing,late,gap,tuple(eligible),tuple(states))


@dataclass(frozen=True, slots=True, repr=False)
class DecisionClockCoverage:
    expected_slots: int
    observed_slots: int
    interior_missing_slots: int
    trailing_missing_slots: int

    @property
    def complete(self) -> bool:
        return self.interior_missing_slots == self.trailing_missing_slots == 0


def decision_clock_coverage(
    commits: tuple[tuple[datetime, datetime], ...],
) -> tuple[DecisionClockCoverage, ...]:
    """P238 independent clock-only denominator on verified full-hour archives.

    Same-clock catch-up is visible; a later commit is never backfilled.
    No session inference, market values, hypothetical clock or expiry rule.
    """
    middle_pair_clock_census(commits)
    result = []
    for i, (known, end) in enumerate(commits):
        expected = _expected_last_closed(known, 15)
        visible = tuple(e for k, e in commits[i:] if k <= known)
        tip = visible[-1]
        trigger_end = end-M15
        if tip > expected:
            raise ValueError("P238_DECISION_CLOCK_GRID_DRIFT")
        observed = 1+4*(len(visible)-1)
        expected_slots = (expected-trigger_end)//M15
        interior = (tip-trigger_end)//M15-observed
        trailing = (expected-tip)//M15
        if (min(interior, trailing) < 0
                or expected_slots != observed+interior+trailing):
            raise ValueError("P238_DECISION_CLOCK_ACCOUNTING_DRIFT")
        result.append(DecisionClockCoverage(expected_slots, observed, interior, trailing))
    return tuple(result)


def summarize_decision_clocks(
    rows: tuple[DecisionClockCoverage, ...], census: MiddlePairClockCensus,
) -> dict[str, int | bool]:
    if len(rows) != census.verified_hours:
        raise ValueError("P238_CLOCK_DENOMINATOR_DRIFT")
    complete = interior = trailing = both = 0
    for row in rows:
        if (type(row) is not DecisionClockCoverage or row.observed_slots < 1
                or min(row.interior_missing_slots,row.trailing_missing_slots) < 0
                or row.expected_slots != row.observed_slots+row.interior_missing_slots
                   +row.trailing_missing_slots):
            raise ValueError("P238_DECISION_CLOCK_ACCOUNTING_DRIFT")
        complete += int(row.complete)
        interior += int(row.interior_missing_slots > 0 and row.trailing_missing_slots == 0)
        trailing += int(row.trailing_missing_slots > 0 and row.interior_missing_slots == 0)
        both += int(row.interior_missing_slots > 0 and row.trailing_missing_slots > 0)
    joint = sum(rows[i].complete for i in census.private_eligible_indices)
    return {"verified_hours": len(rows), "decision_grid_complete": complete,
            "interior_gap_only": interior, "trailing_gap_only": trailing,
            "interior_and_trailing_gap": both,
            "pretrigger_and_decision_clock_complete": joint,
            "selection_uses_prices_or_outcomes": False,
            "expiry_policy_selected": False}


def summarize_joint_clock_blockers(
    census: MiddlePairClockCensus, rows: tuple[DecisionClockCoverage, ...],
    visibility: tuple[bool, ...],
) -> dict[str, object]:
    """P243 joint clock deficit, not a counterfactual recovery or expiry rule."""
    census.public_summary()
    summarize_decision_clocks(rows, census)
    if (type(visibility) is not tuple or len(visibility) != census.verified_hours
            or any(type(v) is not bool for v in visibility)):
        raise ValueError("P243_D1_VISIBILITY_DENOMINATOR_DRIFT")
    result: dict[str, object] = {}
    for present, key in ((False, "without_visible_d1_archive"),
                         (True, "with_visible_d1_archive")):
        matrix = {p: dict.fromkeys(DECISION_STATES, 0) for p in PRECURSOR_STATES}
        interior_slots = trailing_slots = total = 0
        for state, row, visible in zip(census.private_precursor_states, rows, visibility):
            if visible != present:
                continue
            decision_state = ("both_gaps" if row.interior_missing_slots and row.trailing_missing_slots
                              else "interior_only" if row.interior_missing_slots
                              else "trailing_only" if row.trailing_missing_slots
                              else "complete")
            matrix[state][decision_state] += 1
            interior_slots += row.interior_missing_slots
            trailing_slots += row.trailing_missing_slots
            total += 1
        result[key] = {
            "verified_hours": total,
            "precursor_by_decision_clock": matrix,
            "total_interior_missing_m15_slot_observations": interior_slots,
            "total_trailing_missing_m15_slot_observations": trailing_slots,
        }
    return {**result, "selection_uses_prices_or_outcomes": False,
            "schedule_change_selected": False, "expiry_policy_selected": False,
            "publisher_first_known_verified": False, "historical_oos_qualified": False,
            "action": "NO_SIGNAL"}


def _boundary_clock_gap(row: PrivateDelayedMiddlePair, frame: str) -> tuple[str, int]:
    """P244: count closed slots only, never export price, breach or direction."""
    if frame == "H1":
        minutes = 60
        anchor_present = row.h1.status == "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED"
        prior = _expected_last_closed(row.h1.cutoff_utc, minutes)
        paths = tuple(s.h1 for s in row.boundary.sides)
    elif frame == "H4":
        minutes = 240
        anchor_present = row.native.h4_status == "PRETRIGGER_H4_DRAFT_STRUCTURE_COMPUTED"
        prior = row.native.h4_prior_end
        paths = tuple(s.h4 for s in row.boundary.sides)
    else:
        raise ValueError("P244_UNKNOWN_BOUNDARY_FRAME")
    if not anchor_present:
        if any(p is not None for p in paths):
            raise ValueError("P244_BOUNDARY_ANCHOR_AVAILABILITY_DRIFT")
        return "anchor_unavailable", 0
    if prior is None or any(type(p) is not PrivateBoundaryPath for p in paths):
        raise ValueError("P244_BOUNDARY_PATH_MISSING")
    width = timedelta(minutes=minutes)
    span = _expected_last_closed(row.archive_decision_utc, minutes)-prior
    if span < timedelta(0) or span % width:
        raise ValueError("P244_BOUNDARY_EXPECTED_GRID_DRIFT")
    expected = span//width
    for p in paths:
        if (type(p.observed_closed_bars) is not int
                or not 0 <= p.observed_closed_bars <= expected
                or type(p.closed_grid_complete) is not bool
                or p.closed_grid_complete != (p.observed_closed_bars == expected)):
            raise ValueError("P244_BOUNDARY_SLOT_ACCOUNTING_DRIFT")
    if paths[0].observed_closed_bars != paths[1].observed_closed_bars:
        raise ValueError("P244_BOUNDARY_MIRROR_GRID_DRIFT")
    missing = expected-paths[0].observed_closed_bars
    if not expected:
        return "no_new_closed_slot_due", 0
    if not missing:
        return "complete_nonempty", 0
    return ("all_due_slots_missing" if missing == expected else "partial_grid"), missing


def _observed_h4_followup(
    row: PrivateDelayedMiddlePair, raw: tuple[ClosedM5Bar, ...],
    commits: tuple[tuple[datetime, datetime], ...],
    h4: tuple[tuple[datetime, tuple[NativeFXBar, ...]], ...],
) -> PrivateDelayedMiddlePair | None:
    """Revisit frozen inputs only at a real later H4 archive arrival.

    Restore originally missing slots, not the original decision. The new
    clock must independently satisfy the complete current M15/H1/H4 grids.
    No expiry, execution, or persistent event inference.
    """
    if (row.setup_context_identity is None or not row.delayed_decision.sides
            or _boundary_clock_gap(row, "H4")[1] == 0):
        return None
    prior = row.native.h4_prior_end
    assert prior is not None
    width = 4*HOUR
    expected = _expected_last_closed(row.archive_decision_utc, 240)
    def visible_at(clock: datetime) -> tuple[NativeFXBar, ...]:
        return tuple(b for known, bars in h4 if known <= clock for b in bars
                     if _native_utc_start(b.native_open_label)+width
                        <= _expected_last_closed(clock, 240))
    def original_ends(clock: datetime) -> set[datetime]:
        return {end for b in visible_at(clock)
                for end in (_native_utc_start(b.native_open_label)+width,)
                if prior < end <= expected}
    originally = original_ends(row.archive_decision_utc)
    due = {prior+i*width for i in range(1,(expected-prior)//width+1)}
    if len(originally) != row.boundary.sides[0].h4.observed_closed_bars:
        raise ValueError("P245_ORIGINAL_H4_CLOCK_DRIFT")
    for clock in sorted({known for known,_ in h4 if known > row.archive_decision_utc}):
        if original_ends(clock) != due:
            continue
        count = sum(known <= clock for known,_ in commits)
        visible_raw = raw[:12*count]
        boundary = inspect_private_setup_boundaries(
            visible_raw, visible_at(clock), row.h1, row.native, decision=clock)
        delayed = _inspect_delayed_decision(
            visible_raw, row.h1, row.m15, trigger_end=row.trigger_end_utc, decision=clock)
        return replace(row, archive_decision_utc=clock, boundary=boundary,
                       delayed_decision=delayed)
    return None


def _first_complete_observed_followup(
    first: PrivateDelayedMiddlePair, raw: tuple[ClosedM5Bar, ...],
    commits: tuple[tuple[datetime, datetime], ...],
    h4: tuple[tuple[datetime, tuple[NativeFXBar, ...]], ...],
) -> PrivateDelayedMiddlePair | None:
    """P246: first jointly complete observed clock, not price-based selection.

    Use existing immutable archive arrivals only. No expiry or live action
    inference; a complete grid is not an approved or successful trade.
    """
    if first.setup_context_identity is None:
        raise ValueError("P246_FROZEN_CONTEXT_REQUIRED")
    prior_h1 = _expected_last_closed(first.h1.cutoff_utc, 60)
    prior_h4 = first.native.h4_prior_end
    if prior_h4 is None:
        raise ValueError("P246_H4_ANCHOR_REQUIRED")
    width = 4*HOUR
    clocks = sorted({known for known,_ in commits+h4
                     if known >= first.archive_decision_utc})
    for clock in clocks:
        known_h1 = {end for known,end in commits if known <= clock}
        known_h4 = {_native_utc_start(b.native_open_label)+width
                    for known,bars in h4 if known <= clock for b in bars}
        def covered(start: datetime, step: timedelta, ends: set[datetime]) -> bool:
            last = _expected_last_closed(clock, int(step.total_seconds()//60))
            return last >= start and all(start+i*step in ends
                       for i in range(1,(last-start)//step+1))
        # M15 slots are derived only from complete sealed M5 hours.
        m15_ends = {end-j*M15 for end in known_h1 for j in range(4)}
        if not (covered(first.trigger_end_utc,M15,m15_ends)
                and covered(prior_h1,HOUR,known_h1)
                and covered(prior_h4,width,known_h4)):
            continue
        count = sum(known <= clock for known,_ in commits)
        visible_raw = raw[:12*count]
        visible_h4 = tuple(b for known,bars in h4 if known <= clock for b in bars
                           if _native_utc_start(b.native_open_label)+width
                              <= _expected_last_closed(clock,240))
        boundary = inspect_private_setup_boundaries(
            visible_raw,visible_h4,first.h1,first.native,decision=clock)
        delayed = _inspect_delayed_decision(
            visible_raw,first.h1,first.m15,trigger_end=first.trigger_end_utc,decision=clock)
        if (not delayed.closed_grid_complete
                or not all(s.h1 is not None and s.h4 is not None
                           and s.h1.closed_grid_complete and s.h4.closed_grid_complete
                           for s in boundary.sides)):
            raise ValueError("P246_METADATA_RAW_GRID_DRIFT")
        return replace(first,archive_decision_utc=clock,boundary=boundary,
                       delayed_decision=delayed)
    return None


@dataclass(frozen=True, slots=True, repr=False)
class PrivateDelayedMiddleReplay:
    verified_hours: int
    samples: tuple[PrivateDelayedMiddlePair, ...] = field(repr=False)
    clock_census: MiddlePairClockCensus | None = field(default=None, repr=False)
    clock_eligible_samples: tuple[PrivateDelayedMiddlePair, ...] = field(default=(), repr=False)
    decision_clocks: tuple[DecisionClockCoverage, ...] = field(default=(), repr=False)
    joint_clock_samples: tuple[PrivateDelayedMiddlePair, ...] = field(default=(), repr=False)
    d1_archive_visible_at_setup: tuple[bool, ...] = field(default=(), repr=False)
    h4_followups: tuple[tuple[PrivateDelayedMiddlePair, PrivateDelayedMiddlePair], ...] = field(default=(), repr=False)
    complete_followups: tuple[tuple[PrivateDelayedMiddlePair, PrivateDelayedMiddlePair], ...] = field(default=(), repr=False)

    @staticmethod
    def _summary(samples: tuple[PrivateDelayedMiddlePair, ...]) -> dict[str, int]:
        h1 = h4 = d1 = complete = geometry = joint = 0
        ema_coverage = ema_and_bound = ema_and_recheck = ema_and_boundary = 0
        ema_and_all = ema_zero_tr = 0
        ema_paired_seeds = ema_paired_bound = ema_paired_recheck = 0
        ema_states = dict.fromkeys(SEED_CLOCK_STATES, 0)
        long_states = dict.fromkeys(SEED_CLOCK_STATES[:-1], 0)
        late_windows = dict.fromkeys(LATE_SEED_WINDOWS, 0)
        h1_paths = h4_paths = both_grids = 0
        decision_grids = decision_rechecks = early_coverage = setup_identity_coverage = 0
        bound_and_decision = bound_and_boundary = combined_coverage = 0
        # P241: distinguish missing, stale and short D1 vintages, and H4 gaps.
        # Counts are structural availability only; no price or direction leaves memory.
        d1_states = dict.fromkeys(("NO_PRETRIGGER_D1_VINTAGE",
                                  "PRETRIGGER_D1_STALE",
                                  "PRETRIGGER_D1_HISTORY_INSUFFICIENT",
                                  "PRETRIGGER_D1_VINTAGE_PRESENT_CALENDAR_UNQUALIFIED"), 0)
        h4_states = dict.fromkeys(("NO_PRETRIGGER_H4_ARCHIVE",
                                  "PRETRIGGER_H4_STALE",
                                  "PRETRIGGER_H4_PIVOTS_INSUFFICIENT",
                                  "PRETRIGGER_H4_DRAFT_STRUCTURE_COMPUTED"), 0)
        decision_d1_gaps = 0
        boundary_states = ("anchor_unavailable", "no_new_closed_slot_due", "complete_nonempty",
                           "all_due_slots_missing", "partial_grid")
        h1_gap_counts = dict.fromkeys(boundary_states, 0)
        h4_gap_counts = dict.fromkeys(boundary_states, 0)
        h1_missing_slots = h4_missing_slots = 0
        bound_recheck_h1_only = bound_recheck_h4_only = bound_recheck_both_missing = 0
        for row in samples:
            if (row.archive_decision_utc-row.trigger_end_utc < M15+GRACE
                    or row.h1.cutoff_utc != row.trigger_end_utc-2*M15
                    or row.native.cutoff_utc != row.h1.cutoff_utc
                    or row.m15.cutoff_utc != row.h1.cutoff_utc
                    or row.h1.action != "NO_SIGNAL" or row.native.action != "NO_SIGNAL"
                    or row.m15.action != "NO_SIGNAL"
                    or any(x.numeric_policy_approved or x.publisher_first_known_verified
                           or x.may_publish_buy_sell or x.may_trade
                           for x in (row.h1, row.native, row.m15))
                    or row.native.d1_calendar_qualified or row.m15.d1_trend_qualified):
                raise ValueError("P232_RESEARCH_AUTHORITY_OR_CLOCK_DRIFT")
            boundary = row.boundary
            if (type(boundary) is not PrivateBoundaryReceipt
                    or boundary.cutoff_utc != row.h1.cutoff_utc
                    or boundary.action != "NO_SIGNAL" or boundary.buffer_selected
                    or boundary.invalidation_rule_approved or boundary.publisher_first_known_verified
                    or boundary.may_publish_buy_sell or boundary.may_trade
                    or tuple(s.rule_id for s in boundary.sides) != ("B2", "S2")):
                raise ValueError("P234_DELAYED_BOUNDARY_AUTHORITY_DRIFT")
            h1_paths += int(all(s.h1 is not None for s in boundary.sides))
            h4_paths += int(all(s.h4 is not None for s in boundary.sides))
            both_grids += int(all(s.h1 is not None and s.h4 is not None
                                  and s.h1.closed_grid_complete and s.h4.closed_grid_complete
                                  for s in boundary.sides))
            delayed = row.delayed_decision
            if (type(delayed) is not PrivateDelayedDecision
                    or delayed.trigger_end != row.trigger_end_utc
                    or delayed.decision != row.archive_decision_utc
                    or delayed.action != "NO_SIGNAL" or delayed.expiry_policy_selected
                    or delayed.numeric_policy_approved or delayed.may_publish_buy_sell
                    or delayed.may_trade or (delayed.sides and not delayed.closed_grid_complete)
                    or (delayed.closed_grid_complete and delayed.observed_closed_m15_bars < 1)):
                raise ValueError("P235_DELAYED_DECISION_AUTHORITY_DRIFT")
            decision_grids += int(delayed.closed_grid_complete)
            decision_rechecks += int(bool(delayed.sides))
            early_coverage += int(early_observation_coverage(row.m15, row.h1))
            ema_available = bind_private_ema_to_trigger(row.ema_watch, row.trigger_identity,
                                                        row.h1.cutoff_utc)
            ema_coverage += int(ema_available)
            paired_seeds = ema_seed_comparison_available(row.ema_watch, row.h1.cutoff_utc)
            ema_paired_seeds += int(paired_seeds)
            if ema_available:
                long_states[row.ema_watch.long_seed_clock_state] += 1
            ema_states[ema_clock_state(row.ema_watch, row.h1.cutoff_utc)] += 1
            late_window = late_seed_window(row.ema_watch, row.h1.cutoff_utc,
                                           row.archive_decision_utc)
            if late_window is not None:
                late_windows[late_window] += 1
            ema_zero_tr += int(row.ema_watch is not None and row.ema_watch.status == "ZERO_TR")
            expected_identity = bind_private_setup_context(row.h1, row.native, row.m15, row.trigger_identity)
            if row.setup_context_identity != expected_identity:
                raise ValueError("P237_SETUP_CONTEXT_BINDING_DRIFT")
            setup_identity_coverage += int(expected_identity is not None)
            bound = expected_identity is not None
            recheck = bool(delayed.sides)
            boundary_complete = all(s.h1 is not None and s.h4 is not None
                                    and s.h1.closed_grid_complete and s.h4.closed_grid_complete
                                    for s in boundary.sides)
            h1_state, h1_missing = _boundary_clock_gap(row, "H1")
            h4_state, h4_missing = _boundary_clock_gap(row, "H4")
            h1_gap_counts[h1_state] += 1
            h4_gap_counts[h4_state] += 1
            h1_missing_slots += h1_missing
            h4_missing_slots += h4_missing
            if bound and recheck:
                if "anchor_unavailable" in (h1_state, h4_state):
                    raise ValueError("P244_BOUND_CONTEXT_ANCHOR_DRIFT")
                bound_recheck_h1_only += int(h1_missing > 0 and h4_missing == 0)
                bound_recheck_h4_only += int(h4_missing > 0 and h1_missing == 0)
                bound_recheck_both_missing += int(h1_missing > 0 and h4_missing > 0)
            ema_paired_bound += int(paired_seeds and bound)
            ema_paired_recheck += int(paired_seeds and bound and recheck)
            ema_and_bound += int(ema_available and bound)
            ema_and_recheck += int(ema_available and bound and recheck)
            ema_and_boundary += int(ema_available and bound and boundary_complete)
            ema_and_all += int(ema_available and bound and recheck and boundary_complete)
            bound_and_decision += int(bound and recheck)
            bound_and_boundary += int(bound and boundary_complete)
            combined_coverage += int(bound and recheck and boundary_complete)
            h1_ok = row.h1.status == "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED"
            h4_ok = row.native.h4_status == "PRETRIGGER_H4_DRAFT_STRUCTURE_COMPUTED"
            d1_ok = row.native.d1_status == "PRETRIGGER_D1_VINTAGE_PRESENT_CALENDAR_UNQUALIFIED"
            if row.native.d1_status not in d1_states or row.native.h4_status not in h4_states:
                raise ValueError("P241_NATIVE_GAP_STATUS_DRIFT")
            d1_states[row.native.d1_status] += 1
            h4_states[row.native.h4_status] += 1
            decision_d1_gaps += int(recheck and not d1_ok)
            complete_ok = row.m15.history_to_setup_complete
            geometry_ok = row.m15.status == "PRIVATE_M15_DRAFT_GEOMETRY_COMPUTED"
            h1 += int(h1_ok)
            h4 += int(h4_ok)
            d1 += int(d1_ok)
            complete += int(complete_ok)
            geometry += int(geometry_ok)
            joint += int(h1_ok and h4_ok and d1_ok and complete_ok and geometry_ok)
        if (bound_recheck_h1_only + bound_recheck_h4_only + bound_recheck_both_missing
                + combined_coverage != bound_and_decision):
            raise ValueError("P244_BOUND_RECHECK_PARTITION_DRIFT")
        if (sum(ema_states.values()) != len(samples)
                or ema_coverage + ema_zero_tr != ema_states["COMPLETE"]):
            raise ValueError("P264_EMA_COVERAGE_PARTITION_DRIFT")
        if (sum(long_states.values()) != ema_coverage
                or long_states["COMPLETE"] != ema_paired_seeds):
            raise ValueError("P267_LONG_SEED_CONDITIONAL_PARTITION_DRIFT")
        if sum(late_windows.values()) != ema_states["LATE_HOUR"]:
            raise ValueError("P268_LATE_SEED_WINDOW_PARTITION_DRIFT")
        return {
            "middle_pairs_replayed": len(samples),
            **{f"ema_seed_clock_{k.lower()}": v for k, v in ema_states.items()},
            "ema_seed_zero_tr": ema_zero_tr,
            **{f"ema_late_seed_{k.lower()}": v for k, v in late_windows.items()},
            "ema_paired_50_100_seed_coverage": ema_paired_seeds,
            **{f"ema_long_seed_given_short_{k.lower()}": v for k, v in long_states.items()},
            "ema_paired_50_100_seed_bound_context": ema_paired_bound,
            "ema_paired_50_100_seed_bound_decision_recheck": ema_paired_recheck,
            "ema_with_bound_context": ema_and_bound,
            "ema_with_bound_context_and_decision_recheck": ema_and_recheck,
            "ema_with_bound_context_and_both_boundary_grids": ema_and_boundary,
            "ema_with_bound_context_decision_and_both_boundary_grids": ema_and_all,
            **{f"boundary_h1_{k}": v for k,v in h1_gap_counts.items()},
            **{f"boundary_h4_{k}": v for k,v in h4_gap_counts.items()},
            "boundary_h1_missing_slot_observations": h1_missing_slots,
            "boundary_h4_missing_slot_observations": h4_missing_slots,
            "bound_recheck_h1_only_gap": bound_recheck_h1_only,
            "bound_recheck_h4_only_gap": bound_recheck_h4_only,
            "bound_recheck_both_boundary_gaps": bound_recheck_both_missing,
            "pretrigger_h1_draft_contexts_computed": h1,
            "pretrigger_h4_draft_structures_computed": h4,
            "pretrigger_d1_fresh_vintages_with_five_rows": d1,
            "pretrigger_m15_settled_grid_complete": complete,
            "private_m15_draft_geometry_computed": geometry,
            "joint_inputs_present_d1_unqualified": joint,
            "boundary_h1_paths_inspected": h1_paths,
            "boundary_h4_paths_inspected": h4_paths,
            "boundary_both_closed_grids_complete": both_grids,
            "delayed_decision_m15_grids_complete": decision_grids,
            "delayed_decision_frozen_level_rechecks_computed": decision_rechecks,
            "pretrigger_m15_early_observation_coverage": early_coverage,
            "pretrigger_ema50_seeded_observation_coverage": ema_coverage,
            "bounded_setup_context_identity_coverage": setup_identity_coverage,
            "bound_context_with_decision_recheck_coverage": bound_and_decision,
            "bound_context_with_both_boundary_grids_coverage": bound_and_boundary,
            "bound_context_decision_and_both_boundary_grids_coverage": combined_coverage,
            "pretrigger_d1_no_visible_vintage": d1_states["NO_PRETRIGGER_D1_VINTAGE"],
            "pretrigger_d1_stale_vintage": d1_states["PRETRIGGER_D1_STALE"],
            "pretrigger_d1_short_history": d1_states["PRETRIGGER_D1_HISTORY_INSUFFICIENT"],
            "pretrigger_h4_no_visible_archive": h4_states["NO_PRETRIGGER_H4_ARCHIVE"],
            "pretrigger_h4_stale_archive": h4_states["PRETRIGGER_H4_STALE"],
            "pretrigger_h4_insufficient_pivots": h4_states["PRETRIGGER_H4_PIVOTS_INSUFFICIENT"],
            "decision_recheck_without_fresh_five_row_d1": decision_d1_gaps,
        }

    def public_summary(self) -> dict[str, object]:
        if len(self.samples) != min(MAX_SAMPLE,self.verified_hours):
            raise ValueError("P232_BOUNDED_SAMPLE_ACCOUNTING_DRIFT")
        summary: dict[str, object] = {
            "sample_basis": "LATEST_UP_TO_32_SHA_VERIFIED_HOURS_MIDDLE_M15_PAIR",
            "verified_hours": self.verified_hours,
            **self._summary(self.samples),
            "minimum_structural_delay_minutes": 15,
            "retrospective_delayed_research_only": True,
            "publisher_first_known_verified": False,
            "d1_calendar_qualified": False,
            "historical_oos_qualified": False,
            "market_signal_eligibility_assessed": False,
            "action": "NO_SIGNAL", "may_publish_buy_sell": False,
            "may_trade": False,
        }
        if self.clock_census is not None:
            if (self.clock_census.verified_hours!=self.verified_hours
                    or len(self.clock_eligible_samples)!=min(
                        MAX_SAMPLE,len(self.clock_census.private_eligible_indices))
                    or any(not row.m15.history_to_setup_complete
                           for row in self.clock_eligible_samples)):
                raise ValueError("P233_CLOCK_SELECTED_REPLAY_DRIFT")
            summary["clock_census"] = self.clock_census.public_summary()
            summary["decision_clock_census"] = summarize_decision_clocks(
                self.decision_clocks, self.clock_census)
            # P242: separate archive-era opportunities without selecting on
            # D1 price, trend, calendar, or history length.
            visibility = self.d1_archive_visible_at_setup
            if (type(visibility) is not tuple or len(visibility) != self.verified_hours
                    or any(type(v) is not bool for v in visibility)):
                raise ValueError("P242_D1_CLOCK_VISIBILITY_DRIFT")
            precursor = set(self.clock_census.private_eligible_indices)
            eras: dict[str, dict[str, int]] = {}
            for present, key in ((False, "without_visible_d1_archive"),
                                 (True, "with_visible_d1_archive")):
                indices = tuple(i for i, visible in enumerate(visibility) if visible == present)
                eras[key] = {
                    "verified_hours": len(indices),
                    "precursor_clock_complete": sum(i in precursor for i in indices),
                    "decision_clock_complete": sum(self.decision_clocks[i].complete for i in indices),
                    "joint_clock_complete": sum(i in precursor and self.decision_clocks[i].complete
                                                for i in indices),
                }
            summary["joint_clock_blocker_matrix"] = summarize_joint_clock_blockers(
                self.clock_census, self.decision_clocks, visibility)
            summary["d1_archive_clock_visibility_census"] = {
                **eras,
                "selection_uses_prices_or_outcomes": False,
                "d1_calendar_qualified": False,
                "publisher_first_known_verified": False,
                "historical_oos_qualified": False,
            }
            recent_indices = tuple(range(max(0,self.verified_hours-MAX_SAMPLE),
                                         self.verified_hours))
            eligible_indices = self.clock_census.private_eligible_indices[-MAX_SAMPLE:]
            joint_all = tuple(i for i in self.clock_census.private_eligible_indices
                              if self.decision_clocks[i].complete)
            joint_indices = joint_all[-MAX_SAMPLE:]
            if len(self.joint_clock_samples) != len(joint_indices):
                raise ValueError("P239_JOINT_CLOCK_SAMPLE_COUNT_DRIFT")
            seen: dict[int, PrivateDelayedMiddlePair] = {}
            for indices, cohort in (
                (recent_indices, self.samples),
                (eligible_indices, self.clock_eligible_samples),
                (joint_indices, self.joint_clock_samples),
            ):
                for i,row in zip(indices,cohort):
                    if visibility[i] != (row.native.d1_status != "NO_PRETRIGGER_D1_VINTAGE"):
                        raise ValueError("P242_D1_CLOCK_RAW_VISIBILITY_DRIFT")
                    clock = self.decision_clocks[i]
                    if (row.delayed_decision.closed_grid_complete != clock.complete
                            or row.delayed_decision.observed_closed_m15_bars != clock.observed_slots):
                        raise ValueError("P238_RAW_CLOCK_REPLAY_DRIFT")
                    if i in seen and seen[i] is not row:
                        raise ValueError("P239_OVERLAPPING_RECEIPT_NOT_REUSED")
                    seen[i] = row
            summary["clock_selected_replay"] = {
                "selection": "LATEST_UP_TO_32_CLOCK_ELIGIBLE_MIDDLE_PAIRS",
                **self._summary(self.clock_eligible_samples),
                "not_a_representative_market_sample": True,
                "historical_oos_qualified": False,
            }
            if any(not row.m15.history_to_setup_complete or not row.delayed_decision.closed_grid_complete
                   for row in self.joint_clock_samples):
                raise ValueError("P239_JOINT_CLOCK_RAW_COVERAGE_DRIFT")
            joint_summary = self._summary(self.joint_clock_samples)
            # P245: actual subsequent H4 arrivals are separate observations,
            # never substituted into the original decision or cohort margins.
            candidates = tuple(r for r in self.joint_clock_samples
                               if r.setup_context_identity is not None
                               and r.delayed_decision.sides
                               and _boundary_clock_gap(r,"H4")[1] > 0)
            seen_followups: set[int] = set()
            for original, later in self.h4_followups:
                if (not any(original is r for r in candidates) or id(original) in seen_followups
                        or later.archive_decision_utc <= original.archive_decision_utc
                        or replace(later, archive_decision_utc=original.archive_decision_utc,
                                   boundary=original.boundary,
                                   delayed_decision=original.delayed_decision) != original):
                    raise ValueError("P245_FROZEN_FOLLOWUP_DRIFT")
                seen_followups.add(id(original))
            later_summary = self._summary(tuple(later for _,later in self.h4_followups))
            summary["observed_later_h4_archive_recheck"] = {
                "original_joint_bound_recheck_with_h4_gap": len(candidates),
                "original_due_h4_slots_later_visible": len(self.h4_followups),
                "no_observed_recovery_in_audited_history": len(candidates)-len(self.h4_followups),
                "later_h4_grid_complete": (later_summary["boundary_h4_no_new_closed_slot_due"]
                                          +later_summary["boundary_h4_complete_nonempty"]),
                "later_m15_grid_complete": later_summary["delayed_decision_m15_grids_complete"],
                "later_frozen_level_recheck": later_summary["delayed_decision_frozen_level_rechecks_computed"],
                "later_bound_recheck_and_both_boundaries": later_summary[
                    "bound_context_decision_and_both_boundary_grids_coverage"],
                "original_decision_rewritten": False, "expiry_policy_selected": False,
                "publisher_first_known_verified": False, "historical_oos_qualified": False,
                "market_signal_eligibility_assessed": False, "action": "NO_SIGNAL",
            }
            first_by_id = {id(original): later for original,later in self.h4_followups}
            complete_ids: set[int] = set()
            for original, later in self.complete_followups:
                first = first_by_id.get(id(original))
                if (first is None or id(original) in complete_ids
                        or later.archive_decision_utc < first.archive_decision_utc
                        or replace(later,archive_decision_utc=original.archive_decision_utc,
                                   boundary=original.boundary,
                                   delayed_decision=original.delayed_decision) != original
                        or not later.delayed_decision.closed_grid_complete
                        or any(_boundary_clock_gap(later,f)[1] for f in ("H1","H4"))):
                    raise ValueError("P246_COMPLETE_FOLLOWUP_DRIFT")
                complete_ids.add(id(original))
            complete_summary = self._summary(tuple(later for _,later in self.complete_followups))
            summary["first_complete_observed_cross_frame_recheck"] = {
                "first_h4_recoveries": len(self.h4_followups),
                "joint_grid_recoveries": len(self.complete_followups),
                "no_joint_grid_recovery_in_audited_history": len(self.h4_followups)-len(self.complete_followups),
                "frozen_level_rechecks": complete_summary["delayed_decision_frozen_level_rechecks_computed"],
                "selection_uses_prices_or_outcomes": False,
                "original_decision_rewritten": False, "expiry_policy_selected": False,
                "publisher_first_known_verified": False, "historical_oos_qualified": False,
                "market_signal_eligibility_assessed": False, "action": "NO_SIGNAL",
            }
            prior_indices = set(recent_indices+eligible_indices)
            overlap = len(prior_indices.intersection(joint_indices))
            # Count distinct receipts once, not summed cohort margins.
            unique_summary = self._summary(tuple(seen[i] for i in sorted(seen)))
            summary["unique_receipt_technical_coverage"] = {
                **unique_summary,
                "cohort_observations": len(self.samples)+len(self.clock_eligible_samples)
                                       +len(self.joint_clock_samples),
                "repeated_cohort_observations": len(self.samples)+len(self.clock_eligible_samples)
                                                +len(self.joint_clock_samples)-len(seen),
                "market_signal_eligibility_assessed": False,
                "historical_oos_qualified": False,
                "action": "NO_SIGNAL",
            }
            summary["joint_clock_selected_replay"] = {
                "selection": "LATEST_UP_TO_32_PRETRIGGER_AND_DECISION_CLOCK_COMPLETE_PAIRS",
                "joint_clock_eligible_total": len(joint_all),
                "joint_clock_eligible_not_replayed_due_to_limit": len(joint_all)-len(joint_indices),
                **joint_summary,
                "reused_existing_cohort_receipts": overlap,
                "additional_unique_receipts": len(joint_indices)-overlap,
                "distinct_source_hour_receipts_all_cohorts": len(seen),
                "selection_uses_prices_or_outcomes": False,
                "not_a_representative_market_sample": True,
                "historical_oos_qualified": False,
                "joint_trigger_slot_accounting": summarize_private_trigger_slots(
                    tuple(row.trigger_identity for row in self.joint_clock_samples)),
            }
        elif (self.clock_eligible_samples or self.decision_clocks or self.joint_clock_samples
              or self.d1_archive_visible_at_setup or self.h4_followups or self.complete_followups):
            raise ValueError("P233_MISSING_CLOCK_CENSUS")
        summary["delayed_trigger_slot_accounting"] = summarize_private_trigger_slots(
            tuple(row.trigger_identity for row in self.samples+self.clock_eligible_samples))
        summary["boundary_invalidation_buffer_selected"] = False
        summary["post_entry_monitoring_verified"] = False
        summary["delayed_decision_expiry_policy_selected"] = False
        summary["delayed_decision_executable_quote_verified"] = False
        summary["early_event_rule_approved"] = False
        summary["full_setup_revision_identity_verified"] = False
        return summary


def replay_delayed_middle_pairs(
    raw: tuple[ClosedM5Bar, ...],
    commits: tuple[tuple[datetime, datetime], ...],
    h4: tuple[tuple[datetime, tuple[NativeFXBar, ...]], ...],
    d1: tuple[tuple[datetime, PrivateSnapshot], ...],
) -> PrivateDelayedMiddleReplay:
    """Call only with the final already SHA-audited P219 raw prefix.

    For each sampled hour, the observed decision is its actual manifest
    creation clock; even later M5 bars from that hour cannot affect the
    pretrigger context or middle trigger pair. No replay at invented clocks.
    """
    if (type(raw) is not tuple or type(commits) is not tuple
            or not 0 <= len(commits) <= MAX_HOURS or len(raw) != 12*len(commits)):
        raise ValueError("P232_EXACT_BOUNDED_PREFIX_REQUIRED")
    census = middle_pair_clock_census(commits)
    decision_clocks = decision_clock_coverage(commits)
    # Current immutable archive creation is only a local visibility proxy.
    # A revision observed earlier but archived later must not fill the gap.
    if type(d1) is not tuple:
        raise ValueError("P242_TYPED_D1_HISTORY_REQUIRED")
    archive_clocks = []
    for created, snap in d1:
        if (type(created) is not datetime or created.tzinfo is None
                or created.utcoffset() != timedelta(0) or type(snap) is not PrivateSnapshot
                or type(snap.observed) is not datetime or snap.observed.tzinfo is None
                or snap.observed.utcoffset() != timedelta(0) or snap.observed > created
                or not snap.rows):
            raise ValueError("P242_D1_ARCHIVE_CLOCK_DRIFT")
        archive_clocks.append(created)
    first_archive = min(archive_clocks) if archive_clocks else None
    d1_visibility = tuple(first_archive is not None and first_archive <= end-3*M15
                          for _, end in commits)
    recent = tuple(range(max(0,len(commits)-MAX_SAMPLE),len(commits)))
    eligible = census.private_eligible_indices[-MAX_SAMPLE:]
    joint = tuple(i for i in census.private_eligible_indices
                  if decision_clocks[i].complete)[-MAX_SAMPLE:]
    # Preserve both existing cohorts; reuse exact receipts for overlaps.
    # Each of three cohorts is capped at 32, no outcome-based selection.
    samples: dict[int, PrivateDelayedMiddlePair] = {}
    for i in sorted(set(recent+eligible+joint)):
        known, end = commits[i]
        cutoff = end-3*M15
        latest_open = end-2*M15
        trigger_end = end-M15
        prefix = raw[:12*(i+1)]
        # Full sealed hour: slots 3..8 are the two middle M15 bars.
        pair_raw = prefix[-9:-3]
        if known < end+GRACE:
            raise ValueError("P232_ARCHIVE_BEFORE_SETTLED_HOUR")
        h1 = _calculate_archive_h1_at_cutoff(
            prefix, commits[:i+1], cutoff=cutoff, decision_utc=known)
        pair = derive_intraday(pair_raw, "M15", asof_utc=known).candles
        if (len(pair) != 2 or datetime.fromisoformat(pair[0].start_utc) != cutoff
                or datetime.fromisoformat(pair[1].start_utc) != latest_open
                or datetime.fromisoformat(pair[-1].end_utc) != trigger_end
                or pair[0].end_utc != pair[1].start_utc):
            raise ValueError("P232_EXACT_MIDDLE_PAIR_REQUIRED")
        native = calculate_pretrigger_native(
            tuple((clock,bars) for clock,bars in h4 if clock<=known),
            tuple((clock,snap) for clock,snap in d1 if clock<=known),
            cutoff=cutoff, decision=known)
        m15 = _calculate_archive_geometry(
            prefix, commits[:i+1], h1, trigger_raw=pair_raw,
            latest_m15_open=latest_open, decision=known)
        # A catch-up batch may commit multiple source hours at the same
        # observed clock. Include every visible hour in boundary diagnostics,
        # but never in the frozen trigger pair or prior-context selection.
        visible_count = sum(clock <= known for clock, _ in commits)
        visible_raw = raw[:12*visible_count]
        visible_h4 = tuple(bar for clock,bars in h4 if clock<=known for bar in bars)
        boundary = inspect_private_setup_boundaries(
            visible_raw, visible_h4, h1, native, decision=known)
        identity = _identify_closed_trigger_pair(
            pair_raw, latest_m15_open=latest_open, decision=known)
        delayed = _inspect_delayed_decision(
            visible_raw, h1, m15, trigger_end=trigger_end, decision=known)
        setup_identity = bind_private_setup_context(h1, native, m15, identity)
        ema = _observe_archive_ema(prefix, commits[:i+1], pair[0],
                                   cutoff=cutoff, decision=known)
        samples[i] = PrivateDelayedMiddlePair(
            known,trigger_end,h1,native,m15,boundary,identity,delayed,setup_identity,ema)
    followups = tuple((samples[i], later) for i in joint
                      for later in (_observed_h4_followup(samples[i],raw,commits,h4),)
                      if later is not None)
    complete_followups = tuple((original,later) for original,first in followups
                               for later in (_first_complete_observed_followup(first,raw,commits,h4),)
                               if later is not None)
    receipt = PrivateDelayedMiddleReplay(
        len(commits),tuple(samples[i] for i in recent),census,
        tuple(samples[i] for i in eligible),decision_clocks,
        tuple(samples[i] for i in joint),d1_visibility,followups,complete_followups)
    receipt.public_summary()
    return receipt
