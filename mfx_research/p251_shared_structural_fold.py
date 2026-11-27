"""P251: bind P249 shared structural/risk parameters to P216 SIM replay.

The caller must provide explicit synthetic quote and cost inputs, and a
preregisterable chronological fold plan. Never manufacture quote-side data.
"""
from dataclasses import dataclass, field
from datetime import datetime

from forex_trading.market_data import MarketBar
from mfx_research.option_b_v2_chronological_replay import OptionBReplaySnapshot
from mfx_research.p213_purged_sim_fold import SimFoldPlan
from mfx_research.p216_structural_sim_fold import (
    SimQuoteCostInput, StructuralSimFoldReceipt, run_structural_sim_fold,
    verify_structural_sim_fold,
)
from mfx_research.p249_b2s2_sim_profile import read_shared_sim_profile

VERSION = "MFX_P251_SHARED_SIM_STRUCTURAL_FOLD_V1"


@dataclass(frozen=True, slots=True, repr=False)
class SharedStructuralFold:
    profile_sha256: str
    receipt: StructuralSimFoldReceipt = field(repr=False)

    def public_summary(self):
        return {
            **self.receipt.public_summary(),
            "version": VERSION,
            "shared_versioned_sim_profile": True,
            "real_quote_or_cost_inferred": False,
        }


def _inputs(inputs, max_age):
    if (type(inputs) is not tuple
            or any(x is not None and (
                type(x) is not SimQuoteCostInput or x.max_quote_age != max_age)
                for x in inputs)):
        raise ValueError("P251_EXACT_SHARED_QUOTE_AGE_REQUIRED")


def run_shared_structural_fold(
    snapshots: tuple[OptionBReplaySnapshot, ...],
    inputs: tuple[SimQuoteCostInput | None, ...],
    paths: tuple[tuple[MarketBar, ...], ...],
    *, fold_plan: SimFoldPlan, evaluation_utc: datetime,
) -> SharedStructuralFold:
    profile = read_shared_sim_profile()
    _inputs(inputs, profile.max_quote_age)
    receipt = run_structural_sim_fold(
        snapshots, inputs, paths, structural_policy=profile.structural,
        fold_plan=fold_plan, evaluation_utc=evaluation_utc,
    )
    return SharedStructuralFold(profile.fingerprint, receipt)


def verify_shared_structural_fold(value: SharedStructuralFold) -> bool:
    if type(value) is not SharedStructuralFold or type(value.receipt) is not StructuralSimFoldReceipt:
        raise TypeError("P251_TYPED_SHARED_FOLD_REQUIRED")
    profile = read_shared_sim_profile()
    if (value.profile_sha256 != profile.fingerprint
            or value.receipt.structural_policy != profile.structural):
        raise ValueError("P251_PROFILE_OR_STRUCTURAL_POLICY_DRIFT")
    _inputs(value.receipt.inputs, profile.max_quote_age)
    return verify_structural_sim_fold(value.receipt)
