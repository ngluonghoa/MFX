"""P213: strict chronological, purged split of verified SIM exit audit.

No parameter fitting, performance calculation, or real OOS qualification.
Caller-supplied plan is a design input, not proof of external preregistration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256
import json

from mfx_research.option_b_v2_exit_touch_audit import (
    SimExitTouchAudit, verify_option_b_v2_sim_exit_touch_audit,
)
from mfx_research.option_b_v2_chronological_replay import OptionBReplaySnapshot

VERSION = "MFX_P213_PURGED_CHRONOLOGICAL_SIM_SPLIT_V1"


def _utc(value: datetime) -> None:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P213_EXACT_UTC_REQUIRED")


@dataclass(frozen=True, slots=True)
class SimFoldPlan:
    train_end: datetime
    test_start: datetime
    test_end: datetime
    embargo: timedelta
    outcome_horizon: timedelta

    def __post_init__(self) -> None:
        for value in (self.train_end, self.test_start, self.test_end):
            _utc(value)
        if (type(self.embargo) is not timedelta or self.embargo < timedelta(0)
                or type(self.outcome_horizon) is not timedelta
                or self.outcome_horizon <= timedelta(0)
                or not self.train_end + self.embargo <= self.test_start < self.test_end):
            raise ValueError("P213_INVALID_EXPLICIT_FOLD_BOUNDARIES")

    def fingerprint(self) -> str:
        record = [VERSION, self.train_end.isoformat(),
                  self.test_start.isoformat(), self.test_end.isoformat(),
                  str(self.embargo), str(self.outcome_horizon)]
        return sha256(json.dumps(record, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True, repr=False)
class SimPurgedFold:
    plan_fingerprint: str = field(repr=False)
    audited_chain: str = field(repr=False)
    training_indices: tuple[int, ...] = field(repr=False)
    test_indices: tuple[int, ...] = field(repr=False)
    purged_indices: tuple[int, ...] = field(repr=False)
    duplicate_indices: tuple[int, ...] = field(repr=False)
    outside_indices: tuple[int, ...] = field(repr=False)

    def public_summary(self) -> dict[str, str | bool | int]:
        return {
            "version": VERSION,
            "training_windows": len(self.training_indices),
            "test_windows": len(self.test_indices),
            "purged_windows": len(self.purged_indices),
            "duplicate_windows": len(self.duplicate_indices),
            "outside_windows": len(self.outside_indices),
            "nonempty_train_and_test": bool(self.training_indices and self.test_indices),
            "simulated_only": True,
            "external_preregistration_verified": False,
            "historical_oos_qualified": False,
            "performance_computed": False,
            "action": "NO_SIGNAL",
            "stage": "UNVERIFIED",
            "may_trade": False,
            "broker_orders": 0,
            "provider_requests": 0,
            "drive_writes": 0,
        }


def _feature_start(s: OptionBReplaySnapshot) -> datetime:
    bars = (s.bars.daily + s.bars.four_hour + s.bars.hourly
            + s.bars.micro_seed_m15 + s.bars.trigger_m15
            + s.confirmed_m15_history)
    return min(b.key.bar_start_utc for b in bars)


def split_verified_sim_exit_audit(
    audit: SimExitTouchAudit, *, plan: SimFoldPlan,
) -> SimPurgedFold:
    """Assign by predeclared clocks, not price, direction or touch outcome.

    A conservative full feature window must be disjoint from training,
    and the fixed outcome horizon plus all actual path publication clocks
    must mature inside the chosen split. Missing paths remain missing;
    membership alone is not a complete sample or a valid realized trade.
    """
    if type(plan) is not SimFoldPlan:
        raise TypeError("P213_EXACT_FOLD_PLAN_REQUIRED")
    if not verify_option_b_v2_sim_exit_touch_audit(audit):
        raise ValueError("P213_UNVERIFIED_AUDIT")
    train: list[int] = []
    test: list[int] = []
    purged: list[int] = []
    duplicates: list[int] = []
    outside: list[int] = []
    for index, (step, path) in enumerate(zip(audit.prior.replay.steps, audit.paths)):
        if step.duplicate_suppressed:
            duplicates.append(index)
            continue
        snap = step.snapshot
        decision = snap.decision_utc
        start = _feature_start(snap)
        horizon = decision + plan.outcome_horizon
        if any(b.key.bar_end_utc > horizon for b in path):
            raise ValueError("P213_EXIT_PATH_EXCEEDS_FIXED_HORIZON")
        maturity = max([horizon] + [
            max(b.first_known_utc, b.observation.first_known_utc,
                b.observation.retrieved_at_utc, b.key.bar_end_utc)
            for b in path
        ])
        if decision < plan.train_end:
            if maturity <= plan.train_end and maturity <= audit.evaluation_utc:
                train.append(index)
            else:
                purged.append(index)
        elif plan.test_start <= decision < plan.test_end:
            if (start >= plan.test_start
                    and maturity <= plan.test_end
                    and maturity <= audit.evaluation_utc):
                test.append(index)
            else:
                purged.append(index)
        elif plan.train_end <= decision < plan.test_start:
            purged.append(index)
        else:
            outside.append(index)
    if sorted(train + test + purged + duplicates + outside) != list(range(len(audit.steps))):
        raise ValueError("P213_PARTITION_ACCOUNTING_DRIFT")
    return SimPurgedFold(
        plan.fingerprint(), audit.chain_sha256, tuple(train), tuple(test),
        tuple(purged), tuple(duplicates), tuple(outside),
    )
