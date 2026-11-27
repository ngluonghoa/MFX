"""P252: freeze the P249 profile through P251/P218 SIM lifecycle."""
from dataclasses import dataclass, field

from mfx_research.p218_sim_monitoring_lifecycle import (
    SimHTFPath, SimMonitoringReport, evaluate_sim_monitoring_lifecycle,
)
from mfx_research.p249_b2s2_sim_profile import read_shared_sim_profile
from mfx_research.p251_shared_structural_fold import (
    SharedStructuralFold, verify_shared_structural_fold,
)

VERSION = "MFX_P252_SHARED_SIM_LIFECYCLE_V1"


@dataclass(frozen=True, slots=True, repr=False)
class SharedSimLifecycle:
    profile_sha256: str
    structural: SharedStructuralFold = field(repr=False)
    monitoring: SimMonitoringReport = field(repr=False)

    def public_summary(self):
        return {
            **self.monitoring.public_summary(),
            "version": VERSION,
            "shared_profile_pinned": True,
            "expiry_m15_slots": 4,
            "persistent_idempotence_verified": False,
        }


def run_shared_sim_lifecycle(
    structural: SharedStructuralFold, paths: tuple[SimHTFPath, ...],
) -> SharedSimLifecycle:
    verify_shared_structural_fold(structural)
    profile = read_shared_sim_profile()
    result = evaluate_sim_monitoring_lifecycle(
        structural.receipt, paths, policy=profile.monitoring,
    )
    return SharedSimLifecycle(profile.fingerprint, structural, result)


def verify_shared_sim_lifecycle(value: SharedSimLifecycle) -> bool:
    if type(value) is not SharedSimLifecycle or type(value.monitoring) is not SimMonitoringReport:
        raise TypeError("P252_EXACT_SHARED_LIFECYCLE_REQUIRED")
    rebuilt = run_shared_sim_lifecycle(value.structural, value.monitoring.paths)
    if value != rebuilt:
        raise ValueError("P252_LIFECYCLE_OR_PROFILE_DRIFT")
    return True
