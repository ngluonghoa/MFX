"""P269 shared pure H1 feature arithmetic, not a source or mode gate.

Callers MUST validate closed series, identity, continuity and clocks first.
Works on already validated Decimal MarketBar and decimal-text DerivedCandle
without converting provenance, claiming entitlement or activating a detector.
Preserves simple mean TR (not Wilder ATR) and directional extrema anchors.
"""
from decimal import Decimal


def mean_true_range(rows, period: int) -> Decimal:
    if type(rows) is not tuple or type(period) is not int or not 1 <= period < len(rows):
        raise ValueError("P269_COMPLETE_H1_TR_WINDOW_REQUIRED")
    window = rows[-period-1:]
    values = [
        max(Decimal(x.high)-Decimal(x.low),
            abs(Decimal(x.high)-Decimal(prev.close)),
            abs(Decimal(x.low)-Decimal(prev.close)))
        for prev, x in zip(window, window[1:])
    ]
    return sum(values, Decimal(0)) / Decimal(period)


def h1_zone(rows, lookback: int, mean: Decimal, multiple: Decimal, rule: str):
    if (type(rows) is not tuple or type(lookback) is not int
            or not 1 <= lookback <= len(rows) or rule not in ("B2", "S2")):
        raise ValueError("P269_EXACT_H1_ZONE_WINDOW_AND_SIDE_REQUIRED")
    width = mean * multiple
    zone = rows[-lookback:]
    if rule == "B2":
        anchor = min(Decimal(x.low) for x in zone)
        return anchor, anchor + width
    anchor = max(Decimal(x.high) for x in zone)
    return anchor - width, anchor
