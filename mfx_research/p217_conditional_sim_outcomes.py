"""P217: conditional SIM level-fill scenarios on verified structural folds.

Not actual fill, realized PnL, portfolio return or an unconditional bound.
If the first full M5 slot is present, condition on no exit during the
unobserved entry-to-grid fragment and execution at the modeled level/cost.
Do not score gap opens, missing paths, late starts or untouched positions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from mfx_research.option_b_v2_exit_touch_audit import (
    AMBIGUOUS, NO_PATH, NO_TOUCH, OPEN_STOP, OPEN_TARGET, STOP, TARGET,
)
from mfx_research.p216_structural_sim_fold import (
    StructuralSimFoldReceipt, verify_structural_sim_fold,
)

VERSION = "MFX_P217_CONDITIONAL_SIM_OUTCOME_BOUNDS_V1"
M5 = timedelta(minutes=5)


def _ceil_m5(t: datetime) -> datetime:
    floor = t.replace(minute=t.minute-t.minute%5, second=0, microsecond=0)
    return floor if t == floor else floor + M5


@dataclass(frozen=True, slots=True, repr=False)
class ConditionalOutcome:
    index: int
    state: str
    conditional_lower_r: Decimal | None = field(repr=False, default=None)
    conditional_upper_r: Decimal | None = field(repr=False, default=None)
    entry_fragment_unobserved: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class ConditionalFoldSummary:
    outcomes: tuple[ConditionalOutcome, ...] = field(repr=False)
    planned_events: int
    scored_events: int
    unresolved_events: int
    ambiguous_events: int
    private_scored_subset_lower_sum_r: Decimal | None = field(repr=False)
    private_scored_subset_upper_sum_r: Decimal | None = field(repr=False)

    def safe_counts(self) -> dict[str, int]:
        return {
            "planned_events": self.planned_events,
            "conditional_scenarios_scored": self.scored_events,
            "unresolved_planned_events": self.unresolved_events,
            "same_bar_ambiguous_scored": self.ambiguous_events,
            "entry_fragment_unobserved": sum(
                x.entry_fragment_unobserved for x in self.outcomes),
        }


@dataclass(frozen=True, slots=True, repr=False)
class ConditionalOutcomeReport:
    source: StructuralSimFoldReceipt = field(repr=False)
    train: ConditionalFoldSummary = field(repr=False)
    test: ConditionalFoldSummary = field(repr=False)

    def public_summary(self) -> dict[str, object]:
        return {
            "version": VERSION,
            "train": self.train.safe_counts(),
            "test": self.test.safe_counts(),
            "conditional_level_fill_scenarios_only": True,
            "actual_fill_verified": False,
            "realized_profit_verified": False,
            "unconditional_outcome_bounds_verified": False,
            "portfolio_performance_computed": False,
            "historical_oos_qualified": False,
            "numeric_source_approved": False,
            "action": "NO_SIGNAL", "stage": "UNVERIFIED",
            "may_trade": False, "may_publish_buy_sell": False,
            "provider_requests": 0, "drive_writes": 0, "broker_orders": 0,
        }


def _one(source: StructuralSimFoldReceipt, index: int) -> ConditionalOutcome:
    event = source.audit.steps[index]
    risk = source.audit.prior.steps[index].economics
    if risk is None:
        return ConditionalOutcome(index, "NO_ACCEPTED_PLAN")
    path = source.audit.paths[index]
    decision = source.audit.prior.replay.steps[index].snapshot.decision_utc
    expected = _ceil_m5(decision)
    fragment = expected > decision
    if not path:
        return ConditionalOutcome(index, "UNRESOLVED_NO_PATH",
                                  entry_fragment_unobserved=fragment)
    if path[0].key.bar_start_utc != expected:
        return ConditionalOutcome(index, "UNRESOLVED_LATE_OR_OFF_GRID_START",
                                  entry_fragment_unobserved=fragment)
    if any(b.key.bar_end_utc-b.key.bar_start_utc != M5
           or b.key.bar_start_utc != _ceil_m5(b.key.bar_start_utc)
           or b.revision_number != 1
           or b.observation.first_known_utc > source.audit.evaluation_utc
           for b in path):
        raise ValueError("P217_EXACT_INITIAL_SIM_M5_GRID_REQUIRED")
    if event.status == NO_TOUCH:
        return ConditionalOutcome(index, "UNRESOLVED_NO_TOUCH",
                                  entry_fragment_unobserved=fragment)
    if event.status in (OPEN_STOP, OPEN_TARGET):
        return ConditionalOutcome(index, "UNRESOLVED_OPEN_BREACH",
                                  entry_fragment_unobserved=fragment)
    if event.status == NO_PATH or event.first_touch_m5_bar_index is None:
        raise ValueError("P217_INCONSISTENT_TOUCH_PATH")
    # Normalize planned net loss to -1 R. Reward already includes entry
    # and exit slippage/fees exactly once in P151. No additional spread.
    loss = Decimal(-1)
    reward = risk.experimental_net_risk_reward
    if (not reward.is_finite() or reward <= 0
            or risk.net_risk_quote_currency_per_base_unit <= 0):
        raise ValueError("P217_NONPOSITIVE_ACCEPTED_PLAN_ECONOMICS")
    if event.status == STOP:
        low, high = loss, loss
    elif event.status == TARGET:
        low, high = reward, reward
    elif event.status == AMBIGUOUS:
        low, high = loss, reward
    else:
        raise ValueError("P217_UNKNOWN_PRICED_TOUCH_STATE")
    return ConditionalOutcome(index, event.status, low, high, fragment)


def _summarize(source: StructuralSimFoldReceipt,
               indices: tuple[int, ...]) -> ConditionalFoldSummary:
    rows = tuple(_one(source, i) for i in indices)
    planned = sum(x.state != "NO_ACCEPTED_PLAN" for x in rows)
    scored = tuple(x for x in rows if x.conditional_lower_r is not None)
    lower = sum((x.conditional_lower_r for x in scored
                 if x.conditional_lower_r is not None), Decimal(0))
    upper = sum((x.conditional_upper_r for x in scored
                 if x.conditional_upper_r is not None), Decimal(0))
    return ConditionalFoldSummary(
        rows, planned, len(scored), planned-len(scored),
        sum(x.state == AMBIGUOUS for x in scored),
        lower if scored else None, upper if scored else None,
    )


def evaluate_conditional_sim_outcomes(
    source: StructuralSimFoldReceipt,
) -> ConditionalOutcomeReport:
    """Score only unique, eligible P213 fold members, never purged rows.

    Even a scored scenario assumes no exit in the partial entry slot,
    exact modeled level execution, and the P215 hypothetical costs.
    Unresolved plans stay in the denominator; subset sums are not returns.
    """
    if not verify_structural_sim_fold(source):
        raise ValueError("P217_UNVERIFIED_STRUCTURAL_FOLD")
    return ConditionalOutcomeReport(
        source, _summarize(source, source.fold.training_indices),
        _summarize(source, source.fold.test_indices),
    )
