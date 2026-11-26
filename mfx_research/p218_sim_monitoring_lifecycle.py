"""P218: causal monitoring of structural SIM candidates, not a trade exit.

Expiry is a hypothetical candidate-monitoring cutoff, never a liquidation
price. Only retain P217 level-fill scenarios when their observed touch
interval strictly precedes a known invalidation and the expiry cutoff.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from forex_trading.market_data import MarketBar, Timeframe
from mfx_research.causal_multitf_context import _DURATIONS
from mfx_research.p214_sim_htf_invalidation import (
    SimInvalidationPolicy, check_sim_setup_invalidation,
)
from mfx_research.p216_structural_sim_fold import StructuralSimFoldReceipt
from mfx_research.p217_conditional_sim_outcomes import (
    ConditionalOutcome, evaluate_conditional_sim_outcomes,
)

VERSION = "MFX_P218_SIM_MONITORING_LIFECYCLE_V1"


@dataclass(frozen=True, slots=True)
class SimMonitoringPolicy:
    invalidation: SimInvalidationPolicy
    expiry_m15_slots: int

    def __post_init__(self) -> None:
        if (type(self.invalidation) is not SimInvalidationPolicy
                or type(self.expiry_m15_slots) is not int
                or not 1 <= self.expiry_m15_slots <= 32):
            raise ValueError("P218_EXPLICIT_BOUNDED_MONITORING_POLICY_REQUIRED")


@dataclass(frozen=True, slots=True, repr=False)
class SimHTFPath:
    h1: tuple[MarketBar, ...] = field(repr=False)
    h4: tuple[MarketBar, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if any(type(p) is not tuple or len(p) > 96
               or any(type(b) is not MarketBar for b in p)
               for p in (self.h1, self.h4)):
            raise ValueError("P218_EXACT_TYPED_HTF_PATH_REQUIRED")


@dataclass(frozen=True, slots=True, repr=False)
class SimMonitoringOutcome:
    index: int
    state: str
    lower_r: Decimal | None = field(default=None, repr=False)
    upper_r: Decimal | None = field(default=None, repr=False)
    expiry_utc: datetime | None = field(default=None, repr=False)
    invalidation_known_utc: datetime | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class SimMonitoringReport:
    source: StructuralSimFoldReceipt = field(repr=False)
    policy: SimMonitoringPolicy = field(repr=False)
    paths: tuple[SimHTFPath, ...] = field(repr=False)
    train: tuple[SimMonitoringOutcome, ...] = field(repr=False)
    test: tuple[SimMonitoringOutcome, ...] = field(repr=False)

    def public_summary(self) -> dict[str, object]:
        def counts(rows: tuple[SimMonitoringOutcome, ...]) -> dict[str, int]:
            planned = tuple(r for r in rows if r.state != "NO_ACCEPTED_PLAN")
            return {
                "planned_events": len(planned),
                "conditional_touch_scenarios_retained": sum(
                    r.lower_r is not None for r in planned),
                "unresolved_or_monitoring_cutoff_events": sum(
                    r.lower_r is None for r in planned),
            }
        return {
            "version": VERSION, "train": counts(self.train), "test": counts(self.test),
            "simulated_only": True,
            "expiry_is_candidate_monitoring_cutoff_only": True,
            "actual_fill_verified": False, "realized_profit_verified": False,
            "historical_oos_qualified": False, "numeric_source_approved": False,
            "action": "NO_SIGNAL", "stage": "UNVERIFIED",
            "may_publish_buy_sell": False, "may_trade": False,
            "provider_requests": 0, "drive_writes": 0, "broker_orders": 0,
        }


def _known(b: MarketBar) -> datetime:
    return max(b.key.bar_end_utc, b.first_known_utc,
               b.observation.first_known_utc, b.observation.retrieved_at_utc)


def _coverage_at(source: StructuralSimFoldReceipt, index: int,
                 path: SimHTFPath, policy: SimMonitoringPolicy,
                 cutoff: datetime) -> bool:
    snap = source.audit.prior.replay.steps[index].snapshot
    histories = {Timeframe.H1: snap.bars.hourly, Timeframe.H4: snap.bars.four_hour}
    paths = {Timeframe.H1: path.h1, Timeframe.H4: path.h4}
    for tf in policy.invalidation.frames:
        tip = histories[tf][-1].key.bar_end_utc
        for b in paths[tf]:
            if _known(b) > cutoff:
                break
            tip = b.key.bar_end_utc
        # A closed slot that has not yet been observed cannot be assumed intact.
        if tip + _DURATIONS[tf] <= cutoff:
            return False
    return True


def _one(source: StructuralSimFoldReceipt, row: ConditionalOutcome,
         path: SimHTFPath, policy: SimMonitoringPolicy,
         fold_end: datetime) -> SimMonitoringOutcome:
    i = row.index
    if row.state == "NO_ACCEPTED_PLAN":
        if path.h1 or path.h4:
            raise ValueError("P218_NO_HTF_PATH_WITHOUT_ACCEPTED_PLAN")
        return SimMonitoringOutcome(i, row.state)
    snap = source.audit.prior.replay.steps[i].snapshot
    horizon = snap.decision_utc + source.fold_plan.outcome_horizon
    expiry = snap.bars.trigger_m15[-1].key.bar_end_utc + timedelta(
        minutes=15*policy.expiry_m15_slots)
    if any(b.key.bar_end_utc > horizon or _known(b) > fold_end
           or _known(b) > source.audit.evaluation_utc for b in path.h1 + path.h4):
        raise ValueError("P218_HTF_PATH_CROSSES_FOLD_OR_HORIZON")
    for series in (path.h1, path.h4):
        if any(_known(a) > _known(b) for a, b in zip(series, series[1:])):
            raise ValueError("P218_NONMONOTONIC_HTF_KNOWLEDGE")
    checked = check_sim_setup_invalidation(
        snap, policy.invalidation, h1_path=path.h1, h4_path=path.h4,
        evaluation_utc=source.audit.evaluation_utc,
    )
    known = min((f.first_breach_known_utc for f in checked.frames
                 if f.first_breach_known_utc is not None), default=None)

    def result(state: str, retain: bool = False) -> SimMonitoringOutcome:
        return SimMonitoringOutcome(
            i, state, row.conditional_lower_r if retain else None,
            row.conditional_upper_r if retain else None, expiry, known,
        )

    if expiry <= snap.decision_utc:
        return result("EXPIRED_AT_DECISION_NO_SCENARIO")
    if row.conditional_lower_r is None:
        return result("UNRESOLVED_TOUCH_EVIDENCE")
    touch_i = source.audit.steps[i].first_touch_m5_bar_index
    if touch_i is None:
        raise ValueError("P218_SCORED_TOUCH_INDEX_REQUIRED")
    touch = source.audit.paths[i][touch_i]
    start, end = touch.key.bar_start_utc, touch.key.bar_end_utc
    cutoff = min(expiry, known) if known is not None else expiry
    if cutoff < start:
        if not _coverage_at(source, i, path, policy, cutoff):
            return result("UNRESOLVED_HTF_COVERAGE")
        return result("INVALIDATION_BEFORE_TOUCH" if known == cutoff
                      else "EXPIRY_BEFORE_TOUCH")
    if start <= cutoff <= end:
        return result("UNRESOLVED_CUTOFF_OVERLAPS_TOUCH_BAR")
    if not _coverage_at(source, i, path, policy, end):
        return result("UNRESOLVED_HTF_COVERAGE")
    return result("TOUCH_STRICTLY_BEFORE_MONITORING_CUTOFF", True)


def evaluate_sim_monitoring_lifecycle(
    source: StructuralSimFoldReceipt, paths: tuple[SimHTFPath, ...],
    *, policy: SimMonitoringPolicy,
) -> SimMonitoringReport:
    if (type(policy) is not SimMonitoringPolicy or type(paths) is not tuple
            or any(type(p) is not SimHTFPath for p in paths)):
        raise ValueError("P218_TYPED_POLICY_AND_PATHS_REQUIRED")
    base = evaluate_conditional_sim_outcomes(source)
    if len(paths) != len(source.structural):
        raise ValueError("P218_ONE_PATH_PER_SNAPSHOT_REQUIRED")
    members = set(source.fold.training_indices + source.fold.test_indices)
    if any((p.h1 or p.h4) and i not in members for i, p in enumerate(paths)):
        raise ValueError("P218_NO_MONITOR_PATH_FOR_EXCLUDED_WINDOW")
    train = tuple(_one(source, r, paths[r.index], policy, source.fold_plan.train_end)
                  for r in base.train.outcomes)
    test = tuple(_one(source, r, paths[r.index], policy, source.fold_plan.test_end)
                 for r in base.test.outcomes)
    return SimMonitoringReport(source, policy, paths, train, test)
