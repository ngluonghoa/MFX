"""P276: single pure B2/S2 candidate-decision core; never release authority.

Inputs must come from validated source adapters. Unknown structure or missing
geometry must not be turned into an affirmative candidate. The lazy geometry
provider preserves P018's trend/invalidation-first evaluation and reasons.
"""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

Geometry = tuple[bool, bool, bool]


@dataclass(frozen=True, slots=True, repr=False)
class B2S2Decision:
    rule_id: str
    action: Literal["BUY", "SELL", "NO_SIGNAL"]
    reason: str


def decide_b2s2(
    rule: str, d1_trend: str, h4_trend: str,
    structure_invalidated: bool | None,
    geometry: Callable[[], Geometry | None],
) -> B2S2Decision:
    if rule not in ("B2", "S2"):
        raise ValueError("P276_B2_S2_ONLY")
    if any(t not in ("UP", "DOWN", "UNKNOWN") for t in (d1_trend, h4_trend)):
        raise ValueError("P276_EXACT_TREND_REQUIRED")
    if structure_invalidated is not None and type(structure_invalidated) is not bool:
        raise TypeError("P276_EXACT_INVALIDATION_OR_UNKNOWN")
    expected = "UP" if rule == "B2" else "DOWN"
    if d1_trend != expected or h4_trend != expected:
        return B2S2Decision(rule, "NO_SIGNAL", "P018_TREND_NOT_SUPPORTED")
    if structure_invalidated is None:
        return B2S2Decision(rule, "NO_SIGNAL", "P276_STRUCTURE_UNVERIFIED")
    if structure_invalidated:
        return B2S2Decision(rule, "NO_SIGNAL", "P018_STRUCTURE_INVALIDATED")
    values = geometry()
    if values is None:
        return B2S2Decision(rule, "NO_SIGNAL", "P276_GEOMETRY_UNAVAILABLE")
    if type(values) is not tuple or len(values) != 3 or any(type(v) is not bool for v in values):
        raise TypeError("P276_EXACT_GEOMETRY_REQUIRED")
    near, crossed, anti_chase = values
    if not near:
        return B2S2Decision(rule, "NO_SIGNAL", "P018_PRIOR_M15_NOT_NEAR_H1_ZONE")
    if not crossed:
        return B2S2Decision(rule, "NO_SIGNAL", "P018_NO_LATEST_MICRO_BREAK")
    if not anti_chase:
        return B2S2Decision(rule, "NO_SIGNAL", "P018_SYNTHETIC_ANTI_CHASE_LIMIT")
    return B2S2Decision(rule, "BUY" if rule == "B2" else "SELL",
                        "P018_SYNTHETIC_PARAMETRIC_PATTERN_UNVERIFIED")
