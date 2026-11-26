"""P214: source-aligned H1/H4 closed invalidation for a frozen SIM setup.

Recompute P161, freeze the existing experimental H1 zone edge and
pre-trigger H4 pivot, then check later CLOSED bars. Explicit shared buffer
and selected frames are experimental caller inputs, never approved defaults.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from forex_trading.market_data import MarketBar, Timeframe
from forex_trading.quotes import ensure_utc
from mfx_research.causal_multitf_context import _DURATIONS, _validate_closed_synthetic
from mfx_research.confirmed_swings import PivotKind
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    compute_mfx_b2s2_v2_closed_candidate, read_mfx_confirmed_b2s2_v2,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.option_b_v2_chronological_replay import OptionBReplaySnapshot

VERSION = "MFX_P214_SIM_SETUP_HTF_CLOSED_INVALIDATION_V1"


@dataclass(frozen=True, slots=True)
class SimInvalidationPolicy:
    frames: tuple[Timeframe, ...]
    buffer: Decimal

    def __post_init__(self) -> None:
        if (type(self.frames) is not tuple or self.frames not in (
                (Timeframe.H1,), (Timeframe.H4,), (Timeframe.H1, Timeframe.H4))
                or any(type(x) is not Timeframe for x in self.frames)
                or type(self.buffer) is not Decimal or not self.buffer.is_finite()
                or self.buffer < 0):
            raise ValueError("P214_EXPLICIT_SHARED_FRAME_AND_BUFFER_REQUIRED")


@dataclass(frozen=True, slots=True, repr=False)
class SimFrameInvalidation:
    timeframe: Timeframe
    status: str
    frozen_anchor: Decimal = field(repr=False)
    inspected: int
    first_breach_known_utc: datetime | None = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class SimSetupInvalidation:
    rule_id: str
    status: str
    frames: tuple[SimFrameInvalidation, ...] = field(repr=False)

    def public_summary(self) -> dict[str, str | int | bool]:
        return {
            "version": VERSION,
            "frames_checked": len(self.frames),
            "simulated_only": True,
            "source_numeric_approved": False,
            "actual_market_invalidation_verified": False,
            "action": "NO_SIGNAL", "stage": "UNVERIFIED",
            "may_publish_buy_sell": False, "may_trade": False,
            "provider_requests": 0, "drive_writes": 0, "broker_orders": 0,
        }


def check_sim_setup_invalidation(
    snapshot: OptionBReplaySnapshot, policy: SimInvalidationPolicy,
    *, h1_path: tuple[MarketBar, ...], h4_path: tuple[MarketBar, ...],
    evaluation_utc: datetime,
) -> SimSetupInvalidation:
    if type(snapshot) is not OptionBReplaySnapshot or type(policy) is not SimInvalidationPolicy:
        raise TypeError("P214_EXACT_TYPED_SIM_SETUP_REQUIRED")
    ensure_utc(evaluation_utc, "evaluation_utc")
    if evaluation_utc <= snapshot.decision_utc:
        raise ValueError("P214_EVALUATION_MUST_FOLLOW_SETUP")
    if any(type(p) is not tuple or len(p) > 96
           for p in (h1_path, h4_path)):
        raise ValueError("P214_BOUNDED_IMMUTABLE_PATH_REQUIRED")
    computed = compute_mfx_b2s2_v2_closed_candidate(
        snapshot.rule_id, snapshot.bars, snapshot.confirmed_m15_history,
        read_mfx_confirmed_b2s2_v2(), snapshot.decision_utc,
    )
    paths = {Timeframe.H1: h1_path, Timeframe.H4: h4_path}
    if any(paths[tf] for tf in paths if tf not in policy.frames):
        raise ValueError("P214_UNSELECTED_FRAME_PATH")
    if computed.experimental_action is CandidateAction.NO_SIGNAL:
        if h1_path or h4_path:
            raise ValueError("P214_NO_PATH_WITHOUT_SETUP")
        return SimSetupInvalidation(snapshot.rule_id, "NO_SETUP", ())
    long = snapshot.rule_id == "B2"
    context = computed.source.derived_context
    h1_anchor = context.h1_zone_low if long else context.h1_zone_high
    kind = PivotKind.LOW if long else PivotKind.HIGH
    pivots = tuple(p for p in computed.source.four_hour.pivots if p.kind is kind)
    if not pivots:
        raise ValueError("P214_SETUP_H4_PIVOT_MISSING")
    anchors = {Timeframe.H1: h1_anchor, Timeframe.H4: pivots[-1].price}
    prior = {Timeframe.H1: snapshot.bars.hourly[-1],
             Timeframe.H4: snapshot.bars.four_hour[-1]}
    results: list[SimFrameInvalidation] = []
    for tf in policy.frames:
        anchor = anchors[tf]
        boundary = anchor - policy.buffer if long else anchor + policy.buffer
        if boundary <= 0:
            raise ValueError("P214_NONPOSITIVE_BUFFERED_BOUNDARY")
        last = prior[tf]
        path = paths[tf]
        if path:
            _validate_closed_synthetic(
                path, tf, evaluation_utc, last.key.instrument_version,
                last.observation.provider_id, last.key.calendar_version,
            )
            if (path[0].key.bar_start_utc != last.key.bar_end_utc
                    or any(b.observation.stream_id != last.observation.stream_id
                           or b.key.aggregation_version != last.key.aggregation_version
                           or b.key.bar_end_utc <= snapshot.decision_utc
                           for b in path)):
                raise ValueError("P214_GAP_OR_SETUP_SOURCE_DRIFT")
        breach = next((b for b in path
                       if (b.close < boundary if long else b.close > boundary)), None)
        known = None if breach is None else max(
            breach.first_known_utc, breach.observation.first_known_utc,
            breach.observation.retrieved_at_utc,
        )
        tip = path[-1].key.bar_end_utc if path else last.key.bar_end_utc
        complete = bool(path) and tip + _DURATIONS[tf] > evaluation_utc
        status = ("INVALIDATED" if breach is not None else
                  "INTACT_THROUGH_CLOSED_GRID" if complete else "UNKNOWN_INCOMPLETE")
        results.append(SimFrameInvalidation(tf, status, anchor, len(path), known))
    overall = ("INVALIDATED" if any(r.status == "INVALIDATED" for r in results)
               else "INTACT_THROUGH_CLOSED_GRID" if all(
                   r.status == "INTACT_THROUGH_CLOSED_GRID" for r in results)
               else "UNKNOWN_INCOMPLETE")
    return SimSetupInvalidation(snapshot.rule_id, overall, tuple(results))
