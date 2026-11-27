"""P270: pure shared B2/S2 two-candle price predicates.

No source conversion, causal selection, trend inference or action authority.
Caller retains all source/clock/policy gates. Missing micro-level remains
unavailable; overlap alone never creates a signal.
"""
from decimal import Decimal


def strict_closed_cross(
    rule: str, prior: Decimal, latest: Decimal, level: Decimal,
    *, prior_inclusive: bool = True,
) -> bool:
    """Price-only closed cross; adapters own source and as-of eligibility.

    BOS permits prior equality; strict session reclaim requires the prior
    close to be on the other side. Latest equality is never a cross.
    """
    if rule == "B2":
        return (prior <= level if prior_inclusive else prior < level) and latest > level
    if rule == "S2":
        return (prior >= level if prior_inclusive else prior > level) and latest < level
    raise ValueError("P270_B2_S2_ONLY")


def b2s2_geometry(
    rule: str, first_low: Decimal, first_high: Decimal,
    first_close: Decimal, last_close: Decimal,
    zone: tuple[Decimal, Decimal], level: Decimal | None,
    tolerance: Decimal, chase: Decimal,
) -> tuple[bool, bool, bool]:
    if rule not in ("B2", "S2"):
        raise ValueError("P270_B2_S2_ONLY")
    near = first_low <= zone[1]+tolerance and first_high >= zone[0]-tolerance
    if level is None:
        return near, False, False
    crossed = strict_closed_cross(rule, first_close, last_close, level)
    return near, crossed, crossed and (last_close-level if rule == "B2" else level-last_close) <= chase
