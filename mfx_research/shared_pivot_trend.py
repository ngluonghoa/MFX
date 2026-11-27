"""P272 shared pure trend predicate on already-confirmed chronological pivots.

Callers must independently validate source, closed bars, right-bar causality,
and clock. No pivot is created or D1 calendar qualified by this calculation.
"""
from collections.abc import Sequence
from decimal import Decimal
from typing import Literal


def trend_from_pivot_prices(
    highs: Sequence[Decimal], lows: Sequence[Decimal],
) -> Literal["UP", "DOWN", "UNKNOWN"]:
    """Use the last two confirmed highs and lows; equality is not a trend."""
    if len(highs) < 2 or len(lows) < 2:
        return "UNKNOWN"
    if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
        return "UP"
    if highs[-1] < highs[-2] and lows[-1] < lows[-2]:
        return "DOWN"
    return "UNKNOWN"
