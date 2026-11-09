"""A04/P0.24: causal SIM-only structural invalidation and ephemeral event ledger.

No frozen Forex source modifications, numeric source parameter approvals, real
market feed, Drive price-cache writes, persistent storage or broker orders.
A research BUFFERED event is never a verified or sendable BUY/SELL signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json

from forex_trading.market_data import MarketBar, Timeframe
from forex_trading.model import SignalStage
from forex_trading.quotes import ensure_utc

from mfx_research.causal_multitf_context import (
    SyntheticMultiTfBars, _validate_closed_synthetic,
)
from mfx_research.confirmed_swings import (
    ConfirmedSwing, PivotKind, SyntheticPivotParameters,
    detect_confirmed_swings,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.pullback_pilot import ResearchPullbackResult


def _sim(value: str, name: str) -> None:
    if (not isinstance(value, str) or
            not value.startswith("SIM:") or
            not 5 <= len(value) <= 128 or
            any(c.isspace() for c in value)):
        raise ValueError("P024_SIM_ONLY_" + name)


class StructureStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    INTACT = "INTACT"
    INVALIDATED = "INVALIDATED"


class ResearchEventStatus(str, Enum):
    BUFFERED = "RESEARCH_BUFFERED"
    DUPLICATE_DENIED = "DUPLICATE_DENIED"
    EXPIRED_DENIED = "EXPIRED_DENIED"
    STRUCTURE_DENIED = "STRUCTURE_DENIED"
    NO_SIGNAL = "NO_SIGNAL"
    LEDGER_FULL = "LEDGER_FULL"


@dataclass(frozen=True, slots=True)
class SimStructurePolicy:
    version: str

    def __post_init__(self) -> None:
        _sim(self.version, "STRUCTURE_POLICY")


@dataclass(frozen=True, slots=True)
class StructureReceipt:
    rule_id: str
    instrument_version: str
    policy_version: str
    status: StructureStatus
    anchor: Decimal | None
    pivot_first_known_utc: datetime | None
    decision_utc: datetime
    reason: str
    source_verified: bool = False
    may_send_confirmed_signal: bool = False
    can_trade: bool = False
    provider_requests: int = 0
    drive_market_cache_writes: int = 0

    def __post_init__(self) -> None:
        if self.rule_id not in ("B2", "S2"):
            raise ValueError("P024_B2_S2_ONLY")
        _sim(self.instrument_version, "STRUCTURE_PAIR")
        _sim(self.policy_version, "STRUCTURE_VERSION")
        ensure_utc(self.decision_utc, "decision_utc")
        if not isinstance(self.status, StructureStatus):
            raise TypeError("P024_TYPED_STRUCTURE_STATUS")
        if self.anchor is None:
            if (self.status is not StructureStatus.UNKNOWN
                    or self.pivot_first_known_utc is not None):
                raise ValueError("P024_UNKNOWN_STRUCTURE_ONLY")
        else:
            if (not isinstance(self.anchor, Decimal)
                    or not self.anchor.is_finite() or self.anchor <= 0
                    or self.status is StructureStatus.UNKNOWN
                    or self.pivot_first_known_utc is None):
                raise ValueError("P024_INVALID_STRUCTURE_ANCHOR")
            ensure_utc(self.pivot_first_known_utc, "pivot_first_known_utc")
            if self.pivot_first_known_utc > self.decision_utc:
                raise ValueError("P024_FUTURE_STRUCTURAL_PIVOT")
        if (type(self.source_verified) is not bool or self.source_verified
                or type(self.may_send_confirmed_signal) is not bool
                or self.may_send_confirmed_signal
                or type(self.can_trade) is not bool or self.can_trade
                or type(self.provider_requests) is not int
                or self.provider_requests != 0
                or type(self.drive_market_cache_writes) is not int
                or self.drive_market_cache_writes != 0):
            raise ValueError("P024_RESEARCH_MUST_NOT_GAIN_AUTHORITY")


def derive_sim_structure(
    rule_id: str,
    bars: SyntheticMultiTfBars,
    pivot_policy: SyntheticPivotParameters,
    policy: SimStructurePolicy,
    decision_utc: datetime,
) -> StructureReceipt:
    """Versioned synthetic-only structural boundary from *confirmed* pivots.

    This numerical anchor selection is an unapproved SIM experiment:
      B2: max(latest known D1 LOW, latest known H4 LOW) as support.
      S2: min(latest known D1 HIGH, latest known H4 HIGH) as resistance.
    A CLOSED M15 close below support/above resistance is strict invalidation.
    """
    ensure_utc(decision_utc, "decision_utc")
    if rule_id not in ("B2", "S2"):
        raise ValueError("P024_B2_S2_ONLY")
    if (not isinstance(bars, SyntheticMultiTfBars)
            or not isinstance(pivot_policy, SyntheticPivotParameters)
            or not isinstance(policy, SimStructurePolicy)):
        raise TypeError("P024_TYPED_RESEARCH_CONTEXT_REQUIRED")
    trigger = bars.trigger_m15
    if (not isinstance(trigger, tuple) or len(trigger) != 2
            or not all(isinstance(x, MarketBar) for x in trigger)):
        raise ValueError("P024_REQUIRES_TWO_M15_CLOSED_SYNTHETIC_BARS")
    first, last = trigger
    cutoff = first.key.bar_start_utc
    pair, provider, calendar = (
        first.key.instrument_version, first.observation.provider_id,
        first.key.calendar_version,
    )
    if (not pair.startswith("SIM:") or not provider.startswith("SIM:")
            or not calendar.startswith("SIM:")):
        raise ValueError("P024_NO_REAL_OR_UNPROVEN_MARKET_SOURCE")
    _validate_closed_synthetic(
        trigger, Timeframe.M15, decision_utc, pair, provider, calendar,
    )
    d1 = detect_confirmed_swings(
        bars.daily, Timeframe.D1, pivot_policy, cutoff,
    )
    h4 = detect_confirmed_swings(
        bars.four_hour, Timeframe.H4, pivot_policy, cutoff,
    )
    for series in (bars.daily, bars.four_hour):
        sample = series[0]
        if (sample.key.instrument_version != pair
                or sample.observation.provider_id != provider
                or sample.key.calendar_version != calendar):
            raise ValueError("P024_HTF_AND_TRIGGER_IDENTITY_CONFLICT")
    kind = PivotKind.LOW if rule_id == "B2" else PivotKind.HIGH
    latest: list[ConfirmedSwing] = []
    for scan in (d1, h4):
        known = [p for p in scan.pivots if p.kind is kind]
        if known:
            latest.append(known[-1])
    if len(latest) != 2:
        return StructureReceipt(
            rule_id=rule_id, instrument_version=pair,
            policy_version=policy.version, status=StructureStatus.UNKNOWN,
            anchor=None, pivot_first_known_utc=None,
            decision_utc=decision_utc,
            reason="P024_MISSING_CONFIRMED_HTF_PIVOT",
        )
    anchor = (max(p.price for p in latest) if rule_id == "B2"
              else min(p.price for p in latest))
    when = max(p.confirmed_first_known_utc for p in latest)
    if when > cutoff:
        raise ValueError("P024_HTF_PIVOT_KNOWN_AFTER_TRIGGER_WINDOW")
    breached = (
        last.close < anchor if rule_id == "B2"
        else last.close > anchor
    )
    return StructureReceipt(
        rule_id=rule_id, instrument_version=pair,
        policy_version=policy.version,
        status=(StructureStatus.INVALIDATED if breached
                else StructureStatus.INTACT),
        anchor=anchor, pivot_first_known_utc=when,
        decision_utc=decision_utc,
        reason=("P024_SIM_STRUCTURAL_BREACH" if breached
                else "P024_SIM_STRUCTURE_INTACT_UNAPPROVED"),
    )


@dataclass(frozen=True, slots=True)
class SimEventKey:
    instrument_version: str
    rule_id: str
    origin_event_id: str
    policy_version: str

    def __post_init__(self) -> None:
        _sim(self.instrument_version, "EVENT_PAIR")
        _sim(self.origin_event_id, "EVENT_ID")
        _sim(self.policy_version, "EVENT_POLICY")
        if self.rule_id not in ("B2", "S2"):
            raise ValueError("P024_EVENT_ONLY_B2_S2")


@dataclass(frozen=True, slots=True)
class SimEventRecord:
    key: SimEventKey
    first_known_utc: datetime
    buffered_at_utc: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.key, SimEventKey):
            raise TypeError("P024_TYPED_LEDGER_EVENT_KEY")
        ensure_utc(self.first_known_utc, "first_known_utc")
        ensure_utc(self.buffered_at_utc, "buffered_at_utc")
        if self.first_known_utc > self.buffered_at_utc:
            raise ValueError("P024_RECORDED_BEFORE_EVENT_KNOWN")


@dataclass(frozen=True, slots=True)
class SimEventLedger:
    version: str
    events: tuple[SimEventRecord, ...] = ()

    def __post_init__(self) -> None:
        _sim(self.version, "LEDGER_VERSION")
        if (not isinstance(self.events, tuple)
                or len(self.events) > 64
                or not all(isinstance(e, SimEventRecord) for e in self.events)):
            raise ValueError("P024_TYPED_BOUNDED_IMMUTABLE_LEDGER")
        if len({e.key for e in self.events}) != len(self.events):
            raise ValueError("P024_DUPLICATE_LEDGER_KEYS")

    def stable_digest(self) -> str:
        """Canonical digest of this *ephemeral* state; not persistent dedup."""
        rows = [
            (e.key.instrument_version, e.key.rule_id,
             e.key.origin_event_id, e.key.policy_version,
             e.first_known_utc.isoformat(), e.buffered_at_utc.isoformat())
            for e in self.events
        ]
        payload = json.dumps(sorted(rows), separators=(",", ":"))
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ResearchEventDecision:
    status: ResearchEventStatus
    ledger: SimEventLedger
    reason: str
    source_numeric_approved: bool = False
    may_send_confirmed_signal: bool = False
    can_trade: bool = False
    provider_requests: int = 0
    drive_market_cache_writes: int = 0


def buffer_sim_event(
    structure: StructureReceipt,
    signal: ResearchPullbackResult,
    key: SimEventKey,
    ledger: SimEventLedger,
    decision_utc: datetime,
    *,
    ttl_seconds: int,
) -> ResearchEventDecision:
    """Pure event transition; new ledger must be carried by caller to dedup.

    This DOES NOT provide durable/process-restart dedup or a notification.
    All accepted results are a RESEARCH_BUFFERED record, never live alert.
    """
    ensure_utc(decision_utc, "decision_utc")
    if (not isinstance(structure, StructureReceipt)
            or not isinstance(signal, ResearchPullbackResult)
            or not isinstance(key, SimEventKey)
            or not isinstance(ledger, SimEventLedger)):
        raise TypeError("P024_TYPED_RESEARCH_ONLY_EVENT_GATE_REQUIRED")
    if (type(ttl_seconds) is not int
            or not 1 <= ttl_seconds <= 86400):
        raise ValueError("P024_SIM_TTL_INVALID")
    if (structure.source_verified or structure.may_send_confirmed_signal
            or structure.can_trade or structure.provider_requests
            or structure.drive_market_cache_writes
            or signal.stage is not SignalStage.UNVERIFIED
            or signal.original_forex_numerical_parity
            or signal.source_verified_for_market
            or signal.may_send_confirmed_signal
            or signal.can_trade or signal.provider_requests
            or signal.drive_market_cache_writes):
        raise ValueError("P024_FORGED_SOURCE_OR_TRADE_PERMISSION")
    if (signal.rule_id != key.rule_id
            or signal.instrument_version != key.instrument_version
            or signal.origin_event_id != key.origin_event_id
            or signal.parameter_version != key.policy_version
            or structure.rule_id != key.rule_id
            or structure.instrument_version != key.instrument_version
            or structure.decision_utc > decision_utc):
        raise ValueError("P024_EVENT_CROSS_POLICY_OR_IDENTITY")
    ensure_utc(signal.first_known_utc, "first_known_utc")
    ensure_utc(signal.decision_utc, "signal_decision_utc")
    if (signal.first_known_utc > signal.decision_utc
            or signal.decision_utc > decision_utc
            or signal.first_known_utc > decision_utc):
        raise ValueError("P024_FUTURE_EVENT_CANNOT_BE_BUFFERED")
    age = decision_utc - signal.first_known_utc
    if age < timedelta(0):
        raise ValueError("P024_NEGATIVE_SIGNAL_AGE")
    def denied(status: ResearchEventStatus, reason: str) -> ResearchEventDecision:
        return ResearchEventDecision(status=status, ledger=ledger, reason=reason)
    if any(e.key == key for e in ledger.events):
        return denied(ResearchEventStatus.DUPLICATE_DENIED,
                      "P024_SAME_EVENT_ALREADY_IN_EPHEMERAL_LEDGER")
    if age > timedelta(seconds=ttl_seconds):
        return denied(ResearchEventStatus.EXPIRED_DENIED,
                      "P024_RESEARCH_EVENT_EXPIRED")
    if structure.status is not StructureStatus.INTACT:
        return denied(ResearchEventStatus.STRUCTURE_DENIED,
                      "P024_STRUCTURAL_STATUS_NOT_INTACT")
    expected = (
        CandidateAction.BUY if key.rule_id == "B2"
        else CandidateAction.SELL
    )
    if signal.action is CandidateAction.NO_SIGNAL:
        return denied(ResearchEventStatus.NO_SIGNAL,
                      "P024_NO_RESEARCH_TRIGGER")
    if signal.action is not expected:
        raise ValueError("P024_WRONG_SIDE_EVENT")
    if len(ledger.events) >= 64:
        return denied(ResearchEventStatus.LEDGER_FULL,
                      "P024_RESEARCH_LEDGER_AT_CAP")
    fresh = SimEventRecord(
        key=key, first_known_utc=signal.first_known_utc,
        buffered_at_utc=decision_utc,
    )
    next_ledger = SimEventLedger(
        version=ledger.version, events=ledger.events + (fresh,),
    )
    return ResearchEventDecision(
        status=ResearchEventStatus.BUFFERED, ledger=next_ledger,
        reason="P024_SIM_RESEARCH_BUFFERED_UNVERIFIED_NOT_PUBLISHED",
    )
