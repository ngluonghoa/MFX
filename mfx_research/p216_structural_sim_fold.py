"""P216: connect structural SIM targets to chronological replay and purged fold.

No arbitrary caller exits, no inferred fills, no real OOS or strategy approval.
The first obstacle is selected at the original decision, before any exit path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from forex_trading.market_data import MarketBar
from forex_trading.quotes import Quote
from mfx_research.bidask_cost_aware_sim_risk import SimPerUnitCosts
from mfx_research.mfx_b2s2_confirmed_policy_v2 import read_mfx_confirmed_b2s2_v2
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.option_b_v2_chronological_replay import (
    OptionBReplaySnapshot, replay_option_b_v2,
)
from mfx_research.option_b_v2_bidask_replay_bridge import (
    SimRiskBundle, price_option_b_v2_replay,
)
from mfx_research.option_b_v2_exit_touch_audit import (
    SimExitTouchAudit, audit_option_b_v2_sim_exit_touches,
)
from mfx_research.p213_purged_sim_fold import (
    SimFoldPlan, SimPurgedFold, split_verified_sim_exit_audit,
)
from mfx_research.p215_sim_structural_tp1 import (
    SimStructuralTargetPolicy, SimStructuralTargetReceipt, plan_sim_structural_tp1,
)

VERSION = "MFX_P216_STRUCTURAL_SIM_REPLAY_FOLD_V1"


@dataclass(frozen=True, slots=True, repr=False)
class SimQuoteCostInput:
    quote: Quote = field(repr=False)
    costs: SimPerUnitCosts = field(repr=False)
    max_quote_age: timedelta

    def __post_init__(self) -> None:
        if (type(self.quote) is not Quote or type(self.costs) is not SimPerUnitCosts
                or type(self.max_quote_age) is not timedelta
                or self.max_quote_age <= timedelta(0)):
            raise ValueError("P216_EXACT_SIM_QUOTE_COST_INPUT_REQUIRED")


@dataclass(frozen=True, slots=True, repr=False)
class StructuralSimFoldReceipt:
    structural_policy: SimStructuralTargetPolicy = field(repr=False)
    fold_plan: SimFoldPlan = field(repr=False)
    inputs: tuple[SimQuoteCostInput | None, ...] = field(repr=False)
    structural: tuple[SimStructuralTargetReceipt | None, ...] = field(repr=False)
    audit: SimExitTouchAudit = field(repr=False)
    fold: SimPurgedFold = field(repr=False)

    def public_summary(self) -> dict[str, str | bool | int]:
        accepted = tuple(i for i, s in enumerate(self.structural)
                         if s is not None and s.planned_exits is not None)
        train = sum(i in accepted for i in self.fold.training_indices)
        test = sum(i in accepted for i in self.fold.test_indices)
        return {
            "version": VERSION,
            "snapshots_checked": len(self.structural),
            "distinct_events": self.audit.prior.replay.distinct_event_windows,
            "duplicates_suppressed": len(self.fold.duplicate_indices),
            "structural_plans_accepted": len(accepted),
            "train_structural_plans": train,
            "test_structural_plans": test,
            "purged_windows": len(self.fold.purged_indices),
            "simulated_only": True,
            "historical_oos_qualified": False,
            "actual_fills_verified": False,
            "performance_computed": False,
            "numeric_source_approved": False,
            "action": "NO_SIGNAL", "stage": "UNVERIFIED",
            "may_publish_buy_sell": False, "may_trade": False,
            "provider_requests": 0, "drive_writes": 0, "broker_orders": 0,
        }


def run_structural_sim_fold(
    snapshots: tuple[OptionBReplaySnapshot, ...],
    inputs: tuple[SimQuoteCostInput | None, ...],
    paths: tuple[tuple[MarketBar, ...], ...],
    *, structural_policy: SimStructuralTargetPolicy, fold_plan: SimFoldPlan,
    evaluation_utc: datetime,
) -> StructuralSimFoldReceipt:
    if (type(structural_policy) is not SimStructuralTargetPolicy
            or type(fold_plan) is not SimFoldPlan
            or type(inputs) is not tuple or len(inputs) != len(snapshots)
            or any(x is not None and type(x) is not SimQuoteCostInput for x in inputs)
            or type(paths) is not tuple or len(paths) != len(snapshots)):
        raise ValueError("P216_TYPED_ALIGNED_RESEARCH_INPUTS_REQUIRED")
    pinned = read_mfx_confirmed_b2s2_v2()
    replay = replay_option_b_v2(snapshots, pinned)
    previous: dict[str, tuple[SimQuoteCostInput | None, SimRiskBundle | None]] = {}
    structural: list[SimStructuralTargetReceipt | None] = []
    bundles: list[SimRiskBundle | None] = []
    for step, supplied in zip(replay.steps, inputs):
        event = step.event_identity_sha256
        if step.duplicate_suppressed:
            old_input, old_bundle = previous[event]
            if supplied != old_input:
                raise ValueError("P216_DUPLICATE_QUOTE_OR_COST_DRIFT")
            structural.append(None)
            bundles.append(old_bundle)
            continue
        planned = None
        bundle = None
        if step.computed.experimental_action is CandidateAction.NO_SIGNAL:
            if supplied is not None:
                raise ValueError("P216_NO_QUOTE_FOR_NONCANDIDATE")
        elif supplied is not None:
            planned = plan_sim_structural_tp1(
                step.snapshot, structural_policy, quote=supplied.quote,
                costs=supplied.costs, max_quote_age=supplied.max_quote_age,
            )
            if planned.planned_exits is not None:
                bundle = SimRiskBundle(
                    supplied.quote, planned.planned_exits, supplied.costs,
                    supplied.max_quote_age,
                )
        previous[event] = (supplied, bundle)
        structural.append(planned)
        bundles.append(bundle)
    priced = price_option_b_v2_replay(snapshots, tuple(bundles), pinned)
    for plan, step, risk in zip(structural, priced.replay.steps, priced.steps):
        if step.duplicate_suppressed:
            continue
        expected = (plan.economics if plan is not None
                    and plan.planned_exits is not None else None)
        if risk.economics != expected:
            raise ValueError("P216_STRUCTURAL_REPLAY_ECONOMICS_DRIFT")
    audit = audit_option_b_v2_sim_exit_touches(
        priced, paths, evaluation_utc=evaluation_utc,
    )
    fold = split_verified_sim_exit_audit(audit, plan=fold_plan)
    return StructuralSimFoldReceipt(
        structural_policy, fold_plan, inputs, tuple(structural), audit, fold,
    )


def verify_structural_sim_fold(receipt: StructuralSimFoldReceipt) -> bool:
    if type(receipt) is not StructuralSimFoldReceipt:
        raise TypeError("P216_TYPED_RECEIPT_REQUIRED")
    snapshots = tuple(s.snapshot for s in receipt.audit.prior.replay.steps)
    rebuilt = run_structural_sim_fold(
        snapshots, receipt.inputs, receipt.audit.paths,
        structural_policy=receipt.structural_policy, fold_plan=receipt.fold_plan,
        evaluation_utc=receipt.audit.evaluation_utc,
    )
    if rebuilt != receipt:
        raise ValueError("P216_RECEIPT_DRIFT")
    return True
