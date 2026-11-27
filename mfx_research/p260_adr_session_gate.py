"""P260: SIM UTC-session and ADR exhaustion gate, not live calendar policy."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction

from forex_trading.market_data import Timeframe
from mfx_research.p256_ema_watch import validate_series


@dataclass(frozen=True, slots=True, repr=False)
class ADRSessionGate:
    adr_pass: bool = field(repr=False)
    session_pass: bool = field(repr=False)

    def public_summary(self):
        return {"version": "MFX_P260_ADR_SESSION_V1", "research_only": True,
                "real_session_calendar_verified": False, "calibrated": False,
                "action": "NO_SIGNAL", "may_publish_buy_sell": False,
                "may_trade": False, "broker_orders": 0}


def adr_session_gate(daily, current, decision_utc: datetime, *,
                     lookback: int, max_adr: Decimal, allowed_utc_hours: tuple[int, int]):
    """Compare current observed M15 range to mean completed D1 ranges.

    Explicit half-open nonwrapping UTC window, no inferred DST/news calendar.
    Require contiguous M15 history from UTC midnight, no extrapolation.
    """
    identity = validate_series(current, Timeframe.M15, decision_utc)
    start = current[0].key.bar_start_utc
    end = current[-1].key.bar_end_utc
    if (start.hour or start.minute or start.second or start.microsecond
            or not start <= decision_utc < start + timedelta(days=1)
            or end > start + timedelta(days=1)
            or decision_utc - end >= timedelta(minutes=15)):
        raise ValueError("P260_INCOMPLETE_OR_STALE_CURRENT_SESSION")
    if (type(lookback) is not int or not 2 <= lookback <= 60
            or type(max_adr) is not Decimal or not max_adr.is_finite()
            or not Decimal(0) < max_adr <= Decimal(3)
            or type(allowed_utc_hours) is not tuple or len(allowed_utc_hours) != 2
            or any(type(x) is not int for x in allowed_utc_hours)
            or not 0 <= allowed_utc_hours[0] < allowed_utc_hours[1] <= 24):
        raise ValueError("P260_EXPLICIT_RESEARCH_POLICY_REQUIRED")
    validate_series(daily, Timeframe.D1, start, identity)
    if len(daily) != lookback or daily[-1].key.bar_end_utc != start:
        raise ValueError("P260_EXACT_PRIOR_SESSION_HISTORY_REQUIRED")
    adr = sum(Fraction(x.high) - Fraction(x.low) for x in daily) / lookback
    if adr <= 0:
        raise ValueError("P260_ZERO_ADR")
    used = Fraction(max(x.high for x in current)) - Fraction(min(x.low for x in current))
    left, right = allowed_utc_hours
    elapsed = decision_utc - start
    return ADRSessionGate(used < adr * Fraction(max_adr),
                          timedelta(hours=left) <= elapsed < timedelta(hours=right))
