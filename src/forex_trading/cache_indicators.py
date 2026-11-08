"""EMA reference arithmetic for synthetic incremental-cache parity testing.

No signal thresholds, broker connectivity, source acquisition or backtest.
A source revision invalidates EMA from the earliest dirty bar forward.
"""
from decimal import Decimal


def _validated_closes(closes: tuple[Decimal, ...]) -> None:
    if not isinstance(closes, tuple):
        raise TypeError("Closes must be immutable Decimal tuple")
    for value in closes:
        if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
            raise ValueError("Positive finite Decimal close required")


def ema_full(closes: tuple[Decimal, ...], period: int) -> tuple[Decimal, ...]:
    """Experimental EMA seeded from first close. No trading calibration."""
    return ema_recompute(closes, period, (), 0)


def ema_recompute(
    closes: tuple[Decimal, ...],
    period: int,
    previous_ema: tuple[Decimal, ...],
    dirty_index: int,
) -> tuple[Decimal, ...]:
    """Reuse only the known-good prefix BEFORE the first dirty candle.

    A trusted caller must tie previous_ema and prefix bars to the same source
    fingerprints; this function does not attest them. If this is not proven,
    call ema_full. Revisions to historical bars recalc the recursive tail.
    """
    _validated_closes(closes)
    if type(period) is not int or period < 1 or period > 10_000:
        raise ValueError("EMA period must be positive and bounded")
    if not isinstance(previous_ema, tuple) or type(dirty_index) is not int:
        raise TypeError("Immutable EMA checkpoint and integer dirty index required")
    if dirty_index < 0 or dirty_index > len(closes) or dirty_index > len(previous_ema):
        raise ValueError("Dirty index outside available validated prefix")
    if any(not isinstance(v, Decimal) or not v.is_finite() or v <= 0
           for v in previous_ema[:dirty_index]):
        raise ValueError("Invalid prior EMA checkpoint")
    if dirty_index == 0 and previous_ema:
        # Explicit full recompute ignores stale previous cache.
        previous_ema = ()
    if not closes:
        if dirty_index:
            raise ValueError("Empty close series cannot have a reused prefix")
        return ()
    if dirty_index == len(closes):
        return previous_ema[:dirty_index]
    alpha = Decimal(2) / Decimal(period + 1)
    out = list(previous_ema[:dirty_index])
    for idx in range(dirty_index, len(closes)):
        price = closes[idx]
        # Seed same way in FULL and incremental paths, deterministic Decimal math.
        value = price if idx == 0 else alpha * price + (Decimal(1) - alpha) * out[-1]
        out.append(value)
    return tuple(out)
