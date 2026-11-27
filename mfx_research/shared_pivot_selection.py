"""P273 shared strict pivot selection, not confirmation or source authority.

Callers own closed/contiguous series validation, source identity, right-bar
availability and as-of clocks. Candidate indices do not assert first-known.
"""
from decimal import Decimal
from typing import Literal


def strict_pivot_indices(
    prices: tuple[tuple[Decimal, Decimal], ...], left: int, right: int,
) -> tuple[tuple[int, Literal["HIGH", "LOW"]], ...]:
    if type(left) is not int or type(right) is not int or left < 1 or right < 1:
        raise ValueError("P273_POSITIVE_EXACT_PIVOT_WIDTHS_REQUIRED")
    pivots: list[tuple[int, Literal["HIGH", "LOW"]]] = []
    for i in range(left, len(prices) - right):
        hi, lo = prices[i]
        neighbors = prices[i-left:i] + prices[i+1:i+right+1]
        high = all(hi > h for h, _ in neighbors)
        low = all(lo < value for _, value in neighbors)
        if high == low:
            continue
        pivots.append((i, "HIGH" if high else "LOW"))
    return tuple(pivots)
