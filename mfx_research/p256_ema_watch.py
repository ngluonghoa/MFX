"""P256: causal EMA20/50 dynamic S/R WATCH research, synthetic only."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction

from forex_trading.market_data import MarketBar, Timeframe
from forex_trading.quotes import ensure_utc
from mfx_research.causal_multitf_context import _validate_closed_synthetic

VERSION = "MFX_P256_EMA_WATCH_V1"


def validate_series(rows, tf, cutoff, identity=None):
    ensure_utc(cutoff, "cutoff")
    if (type(rows) is not tuple or not 1 <= len(rows) <= 512
            or any(type(b) is not MarketBar for b in rows)):
        raise ValueError("P256_BOUNDED_TYPED_SERIES_REQUIRED")
    # Fixed UTC synthetic calendar only; length alone does not establish grid.
    for bar in rows:
        start = bar.key.bar_start_utc
        if (start.second or start.microsecond
                or (tf is Timeframe.M15 and start.minute % 15)
                or (tf is Timeframe.H1 and start.minute)
                or (tf is Timeframe.D1 and (start.hour or start.minute))):
            raise ValueError("P261_OFF_GRID_SYNTHETIC_BAR")
    first = rows[0]
    actual = (first.key.instrument_version, first.observation.provider_id,
              first.key.calendar_version)
    if not all(x.startswith("SIM:") for x in actual):
        raise ValueError("P256_SIM_ONLY")
    if identity is not None and actual != identity:
        raise ValueError("P256_CROSS_FRAME_IDENTITY")
    _validate_closed_synthetic(rows, tf, cutoff, *actual)
    return actual


@dataclass(frozen=True, slots=True, repr=False)
class EMAWatch:
    near20: bool = field(repr=False)
    near50: bool = field(repr=False)

    def public_summary(self):
        return {"version": VERSION, "research_only": True,
                "original_numeric_approved": False, "calibrated": False,
                "action": "NO_SIGNAL", "may_publish_buy_sell": False,
                "may_trade": False, "broker_orders": 0}


def _ema(rows, period):
    # Exact rational arithmetic preserves B2/S2 reflection at equality.
    value = Fraction(rows[0].close)
    alpha = Fraction(2, period + 1)
    for bar in rows[1:]:
        value += alpha * (Fraction(bar.close) - value)
    return value


def ema_watch(rule, h1, probe, decision_utc: datetime, *, near_atr: Decimal):
    """H1 EMA seeded from first close; latest 14 simple TRs as scale.

    Freeze H1 history before the M15 probe opens; its CLOSED range must
    overlap the ATR band and its close be on the directional side of EMA.
    This is an alternate WATCH hypothesis, never an EARLY/CONFIRM signal.
    """
    if rule not in ("B2", "S2") or type(probe) is not MarketBar:
        raise ValueError("P256_RULE_OR_PROBE")
    if (type(near_atr) is not Decimal or not near_atr.is_finite()
            or not Decimal(0) <= near_atr <= Decimal(2)):
        raise ValueError("P256_EXPLICIT_BOUNDED_TOLERANCE")
    identity = validate_series((probe,), Timeframe.M15, decision_utc)
    cutoff = probe.key.bar_start_utc
    validate_series(h1, Timeframe.H1, cutoff, identity)
    if len(h1) < 50 or cutoff - h1[-1].key.bar_end_utc >= timedelta(hours=1):
        raise ValueError("P256_INSUFFICIENT_OR_STALE_H1")
    tr = [max(Fraction(b.high) - Fraction(b.low), abs(Fraction(b.high) - Fraction(a.close)),
              abs(Fraction(b.low) - Fraction(a.close))) for a, b in zip(h1[-15:-1], h1[-14:])]
    scale = sum(tr) / 14
    if scale <= 0:
        raise ValueError("P256_ZERO_TR")
    width = scale * Fraction(near_atr)

    def near(period):
        level = _ema(h1, period)
        close = Fraction(probe.close)
        return (Fraction(probe.low) <= level + width
                and Fraction(probe.high) >= level - width
                and (close >= level if rule == "B2" else close <= level))

    return EMAWatch(near(20), near(50))
