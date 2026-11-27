"""P259: early BOS of the latest pre-known confirmed M15 pivot, SIM only."""
from dataclasses import dataclass, field
from datetime import datetime

from forex_trading.market_data import Timeframe
from mfx_research.confirmed_swings import (
    PivotKind, SyntheticPivotParameters, detect_confirmed_swings,
)
from mfx_research.p256_ema_watch import validate_series
from mfx_research.shared_b2s2_geometry import strict_closed_cross


@dataclass(frozen=True, slots=True, repr=False)
class EarlyBOS:
    observed: bool = field(repr=False)
    available: bool = field(repr=False)

    def public_summary(self):
        return {"version": "MFX_P259_EARLY_BOS_V1", "research_only": True,
                "action": "NO_SIGNAL", "may_publish_buy_sell": False,
                "may_trade": False, "broker_orders": 0}


def early_bos(rule, history, probes, decision_utc: datetime, *, left: int, right: int):
    if rule not in ("B2", "S2"):
        raise ValueError("P259_RULE")
    identity = validate_series(probes, Timeframe.M15, decision_utc)
    if len(probes) != 2:
        raise ValueError("P259_TWO_PROBES")
    a, b = probes
    cutoff = a.key.bar_start_utc
    validate_series(history, Timeframe.M15, cutoff, identity)
    if (history[-1].key.bar_end_utc != cutoff
            or history[-1].observation.stream_id != a.observation.stream_id
            or history[-1].key.aggregation_version != a.key.aggregation_version
            or max(a.first_known_utc, a.observation.retrieved_at_utc) > b.key.bar_start_utc):
        raise ValueError("P259_HISTORY_OR_PRIOR_CLOSE_NOT_CAUSAL")
    policy = SyntheticPivotParameters("SIM:P259-BOS", left, right)
    scan = detect_confirmed_swings(history, Timeframe.M15, policy, cutoff)
    kind = PivotKind.HIGH if rule == "B2" else PivotKind.LOW
    pivots = [p for p in scan.pivots if p.kind is kind]
    if not pivots:
        return EarlyBOS(False, False)
    level = pivots[-1].price
    # Reject an already broken level in the available history after confirmation.
    later = history[pivots[-1].confirmation_index + 1:]
    if any(x.close > level if rule == "B2" else x.close < level for x in later):
        return EarlyBOS(False, False)
    observed = strict_closed_cross(rule, a.close, b.close, level)
    return EarlyBOS(observed, True)
