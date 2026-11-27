"""P258: paired EARLY reclaim/reject of a pre-known session extreme."""
from dataclasses import dataclass, field
from datetime import datetime

from forex_trading.market_data import Timeframe
from mfx_research.p256_ema_watch import validate_series
from mfx_research.p257_previous_session_watch import previous_session_level


@dataclass(frozen=True, slots=True, repr=False)
class ReclaimReject:
    observed: bool = field(repr=False)

    def public_summary(self):
        return {"version": "MFX_P258_RECLAIM_REJECT_V1", "research_only": True,
                "action": "NO_SIGNAL", "may_publish_buy_sell": False,
                "may_trade": False, "broker_orders": 0}


def session_reclaim_reject(rule, previous_session, probes, decision_utc: datetime):
    """Strict closed cross back through a level fixed before the first probe.

    Prior close strictly beyond level, next close strictly back across;
    wick alone, equality and already reclaimed close are not events.
    No production event ID or authorization is inferred.
    """
    identity = validate_series(probes, Timeframe.M15, decision_utc)
    if len(probes) != 2:
        raise ValueError("P258_TWO_CONTIGUOUS_PROBES_REQUIRED")
    a, b = probes
    cutoff = a.key.bar_start_utc
    level = previous_session_level(rule, previous_session, cutoff, identity)
    if max(a.first_known_utc, a.observation.retrieved_at_utc) > b.key.bar_start_utc:
        raise ValueError("P258_PRIOR_CLOSE_NOT_KNOWN_BEFORE_SECOND_PROBE")
    observed = a.close < level < b.close if rule == "B2" else a.close > level > b.close
    return ReclaimReject(observed)
