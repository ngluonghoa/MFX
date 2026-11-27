"""P257: previous complete synthetic session extreme WATCH hypothesis."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction

from forex_trading.market_data import MarketBar, Timeframe
from mfx_research.p256_ema_watch import validate_series


@dataclass(frozen=True, slots=True, repr=False)
class SessionWatch:
    near: bool = field(repr=False)
    level: Decimal = field(repr=False)

    def public_summary(self):
        return {"version": "MFX_P257_PREVIOUS_SESSION_WATCH_V1",
                "research_only": True, "original_numeric_approved": False,
                "action": "NO_SIGNAL", "may_publish_buy_sell": False,
                "may_trade": False, "broker_orders": 0}


def previous_session_level(rule, previous, cutoff, identity):
    if rule not in ("B2", "S2") or type(previous) is not MarketBar:
        raise ValueError("P257_RULE_OR_SESSION")
    validate_series((previous,), Timeframe.D1, cutoff, identity)
    end = previous.key.bar_end_utc
    if (end.hour or end.minute or end.second or end.microsecond
            or cutoff - end >= timedelta(days=1)):
        raise ValueError("P257_NOT_IMMEDIATELY_PREVIOUS_SIM_UTC_SESSION")
    return previous.low if rule == "B2" else previous.high


def previous_session_watch(rule, previous, h1, probe, decision_utc: datetime,
                           *, near_atr: Decimal):
    if (type(near_atr) is not Decimal or not near_atr.is_finite()
            or not Decimal(0) <= near_atr <= Decimal(2)):
        raise ValueError("P257_EXPLICIT_BOUNDED_TOLERANCE")
    identity = validate_series((probe,), Timeframe.M15, decision_utc)
    cutoff = probe.key.bar_start_utc
    level = previous_session_level(rule, previous, cutoff, identity)
    validate_series(h1, Timeframe.H1, cutoff, identity)
    if len(h1) < 15 or cutoff - h1[-1].key.bar_end_utc >= timedelta(hours=1):
        raise ValueError("P257_STALE_OR_SHORT_H1")
    tr = [max(Fraction(b.high) - Fraction(b.low),
              abs(Fraction(b.high) - Fraction(a.close)),
              abs(Fraction(b.low) - Fraction(a.close)))
          for a, b in zip(h1[-15:-1], h1[-14:])]
    scale = sum(tr) / 14
    if scale <= 0:
        raise ValueError("P257_ZERO_TR")
    width = scale * Fraction(near_atr)
    price = Fraction(level)
    near = (Fraction(probe.low) <= price + width
            and Fraction(probe.high) >= price - width
            and (probe.close >= level if rule == "B2" else probe.close <= level))
    return SessionWatch(near, level)
