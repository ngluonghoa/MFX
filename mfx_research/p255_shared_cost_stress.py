"""P255: fixed structural target, adverse fee sensitivity, SIM only.

No parameter tuning, realized return, historical OOS, or data acquisition.
"""
from dataclasses import dataclass, field, replace
from decimal import Decimal
from forex_trading.model import ActionIntent
from mfx_research.bidask_cost_aware_sim_risk import evaluate_cost_aware_sim_risk
from mfx_research.p249_b2s2_sim_profile import read_shared_sim_profile
from mfx_research.p252_shared_sim_lifecycle import (
    SharedSimLifecycle, verify_shared_sim_lifecycle,
)

VERSION = "MFX_P255_FIXED_TARGET_SIM_COST_STRESS_V1"


@dataclass(frozen=True, slots=True, repr=False)
class FixedTargetStress:
    lifecycle: SharedSimLifecycle = field(repr=False)
    fee_increments: tuple[Decimal, ...] = field(repr=False)
    eligible_count: int
    pass_counts: tuple[int, ...]

    def public_summary(self):
        return {
            "version": VERSION, "simulated_only": True,
            "structural_plans_checked": self.eligible_count,
            "scenario_count": len(self.fee_increments),
            "net_r_pass_counts": self.pass_counts,
            "fixed_target_no_reselection": True,
            "calibrated": False, "historical_oos_qualified": False,
            "performance_computed": False, "action": "NO_SIGNAL",
            "may_publish_buy_sell": False, "may_trade": False,
            "broker_orders": 0, "provider_requests": 0, "drive_writes": 0,
        }


def stress_fixed_targets(lifecycle: SharedSimLifecycle,
                         fee_increments: tuple[Decimal, ...]) -> FixedTargetStress:
    verify_shared_sim_lifecycle(lifecycle)
    if (type(fee_increments) is not tuple or not 2 <= len(fee_increments) <= 32
            or any(type(x) is not Decimal or not x.is_finite() or x < 0
                   for x in fee_increments)
            or fee_increments[0] != 0
            or any(a >= b for a, b in zip(fee_increments, fee_increments[1:]))):
        raise ValueError("P255_STRICT_ADVERSE_FEE_GRID_REQUIRED")
    profile = read_shared_sim_profile()
    receipt = lifecycle.structural.receipt
    counts = [0] * len(fee_increments)
    eligible = 0
    for step, supplied, plan in zip(receipt.audit.prior.replay.steps,
                                    receipt.inputs, receipt.structural):
        if plan is None or plan.planned_exits is None:
            continue
        if supplied is None or plan.economics is None:
            raise ValueError("P255_ACCEPTED_PLAN_WITHOUT_INPUT")
        eligible += 1
        intent = (ActionIntent.ENTRY_LONG if step.snapshot.rule_id == "B2"
                  else ActionIntent.ENTRY_SHORT)
        prior = plan.economics.experimental_net_risk_reward
        for i, increase in enumerate(fee_increments):
            costs = replace(supplied.costs,
                            entry_fee=supplied.costs.entry_fee + increase)
            result = evaluate_cost_aware_sim_risk(
                quote=supplied.quote, intent=intent,
                decision_utc=step.snapshot.decision_utc,
                max_quote_age=profile.max_quote_age,
                exits=plan.planned_exits, costs=costs, instrument="EUR/USD",
            )
            if ((i == 0 and result != plan.economics)
                    or result.experimental_net_risk_reward > prior):
                raise ValueError("P255_FIXED_TARGET_ECONOMICS_DRIFT")
            prior = result.experimental_net_risk_reward
            counts[i] += int(prior >= profile.structural.min_net_r)
    return FixedTargetStress(lifecycle, fee_increments, eligible, tuple(counts))


def verify_fixed_target_stress(receipt: FixedTargetStress) -> bool:
    if type(receipt) is not FixedTargetStress:
        raise TypeError("P255_TYPED_STRESS_REQUIRED")
    if stress_fixed_targets(receipt.lifecycle, receipt.fee_increments) != receipt:
        raise ValueError("P255_STRESS_RECEIPT_DRIFT")
    return True
