"""P270: pure shared B2/S2 two-candle price predicates.

No source conversion, causal selection, trend inference or action authority.
Caller retains all source/clock/policy gates. Missing micro-level remains
unavailable; overlap alone never creates a signal.
"""
from decimal import Decimal


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
    if rule == "B2":
        crossed = first_close <= level < last_close
        return near, crossed, crossed and last_close-level <= chase
    crossed = first_close >= level > last_close
    return near, crossed, crossed and level-last_close <= chase
