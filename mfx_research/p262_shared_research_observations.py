"""P262: one causal SIM snapshot for alternate B2/S2 research observations.

Do not combine independent observations into an entry, vote or fitted policy.
No real data relabeling, provider IO, or production authorization.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from forex_trading.market_data import MarketBar, Timeframe
from mfx_research.confirmed_swings import SyntheticPivotParameters
from mfx_research.p256_ema_watch import ema_watch, validate_series
from mfx_research.p257_previous_session_watch import previous_session_watch
from mfx_research.p258_session_reclaim_reject import session_reclaim_reject
from mfx_research.p259_early_bos import early_bos
from mfx_research.p260_adr_session_gate import adr_session_gate

VERSION = "MFX_P262_SHARED_RESEARCH_OBSERVATIONS_V1"


@dataclass(frozen=True, slots=True)
class ObservationPolicy:
    near_atr: Decimal
    pivot_left: int
    pivot_right: int
    adr_lookback: int
    max_adr: Decimal
    allowed_utc_hours: tuple[int, int]


@dataclass(frozen=True, slots=True, repr=False)
class ObservationSnapshot:
    daily: tuple[MarketBar, ...] = field(repr=False)
    h1: tuple[MarketBar, ...] = field(repr=False)
    current: tuple[MarketBar, ...] = field(repr=False)
    decision_utc: datetime = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class SideObservation:
    rule: str
    ema20: bool
    ema50: bool
    previous_session: bool
    reclaim_reject: bool
    bos: bool
    bos_available: bool


@dataclass(frozen=True, slots=True, repr=False)
class SharedObservations:
    snapshot: ObservationSnapshot = field(repr=False)
    policy: ObservationPolicy = field(repr=False)
    sides: tuple[SideObservation, ...] = field(repr=False)
    adr_pass: bool = field(repr=False)
    session_pass: bool = field(repr=False)

    def public_summary(self):
        return {"version": VERSION, "paired_observation_paths": 2,
                "simulated_only": True, "observations_combined_into_signal": False,
                "calibrated": False, "historical_oos_qualified": False,
                "action": "NO_SIGNAL", "stage": "UNVERIFIED",
                "may_publish_buy_sell": False, "may_trade": False,
                "broker_orders": 0}


def observe_shared_snapshot(snapshot: ObservationSnapshot, policy: ObservationPolicy):
    if type(snapshot) is not ObservationSnapshot or type(policy) is not ObservationPolicy:
        raise TypeError("P262_EXACT_TYPED_SNAPSHOT_AND_POLICY")
    current = snapshot.current
    identity = validate_series(current, Timeframe.M15, snapshot.decision_utc)
    if len(current) < 2:
        raise ValueError("P262_TWO_TRIGGER_BARS_REQUIRED")
    a, b = current[-2:]
    cutoff = a.key.bar_start_utc
    # One authoritative session prefix and D1 history; no separate caller
    # supplied previous-session level, trigger history, or ADR prefix.
    validate_series(snapshot.daily, Timeframe.D1, current[0].key.bar_start_utc, identity)
    validate_series(snapshot.h1, Timeframe.H1, cutoff, identity)
    first_known = max(a.first_known_utc, a.observation.retrieved_at_utc)
    if first_known > b.key.bar_start_utc:
        raise ValueError("P262_PRIOR_CLOSE_NOT_OBSERVABLE_BEFORE_SECOND")
    pivots = SyntheticPivotParameters("SIM:P262-BOS", policy.pivot_left, policy.pivot_right)
    gate = adr_session_gate(snapshot.daily, current, snapshot.decision_utc,
                           lookback=policy.adr_lookback, max_adr=policy.max_adr,
                           allowed_utc_hours=policy.allowed_utc_hours)
    previous = snapshot.daily[-1]
    history = current[:-2]
    # A same-session prefix intentionally has no overnight BOS seed.
    # Availability is distinct from a negative result.
    sides = []
    for rule in ("B2", "S2"):
        ema = ema_watch(rule, snapshot.h1, a, first_known, near_atr=policy.near_atr)
        prior = previous_session_watch(rule, previous, snapshot.h1, a, first_known,
                                       near_atr=policy.near_atr)
        early = session_reclaim_reject(rule, previous, (a, b), snapshot.decision_utc)
        available = observed = False
        if len(history) >= pivots.left_bars + pivots.right_bars + 1:
            bos = early_bos(rule, history, (a, b), snapshot.decision_utc,
                            left=pivots.left_bars, right=pivots.right_bars)
            available, observed = bos.available, bos.observed
        sides.append(SideObservation(rule, ema.near20, ema.near50, prior.near,
                                     early.observed, observed, available))
    return SharedObservations(snapshot, policy, tuple(sides),
                              gate.adr_pass, gate.session_pass)


def verify_shared_observations(value: SharedObservations):
    if type(value) is not SharedObservations:
        raise TypeError("P262_EXACT_RECEIPT_REQUIRED")
    if value != observe_shared_snapshot(value.snapshot, value.policy):
        raise ValueError("P262_RECEIPT_RECOMPUTE_DRIFT")
    return True
