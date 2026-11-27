"""DEC-MFX-UNIFIED-001: typed mode policy; not a release or sign-off."""
from enum import Enum


class MfxMode(str, Enum):
    RESEARCH = "RESEARCH"
    VALIDATION = "VALIDATION"
    PRODUCTION = "PRODUCTION"


def require_candidate_mode(mode: MfxMode) -> None:
    """The currently unapproved candidate may run privately in R/V only.

    Validation of SIM fixtures is not independently verified market OOS.
    Production has no qualified profile or runtime release route yet.
    """
    if type(mode) is not MfxMode:
        raise TypeError("P271_EXACT_MFX_MODE_REQUIRED")
    if mode is MfxMode.PRODUCTION:
        raise ValueError("P271_PRODUCTION_PROFILE_NOT_QUALIFIED")
