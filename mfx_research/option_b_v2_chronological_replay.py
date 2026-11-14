"""P0.165: chronological bounded Option B v2 CLOSED-bar replay, SIM only.

Reuse P0.161 actual D1/H4 confirmed pivots + prior M15 confirmed level.
No new trading strategy arithmetic, vendor/Drive I/O, real-market backtest,
data-rights grant, source-restatement bypass, release or broker order.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
from typing import Any

from forex_trading.market_data import MarketBar
from mfx_research.causal_multitf_context import SyntheticMultiTfBars
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    MfxB2S2V2ClosedResearch, MfxConfirmedB2S2V2Policy,
    compute_mfx_b2s2_v2_closed_candidate,
    read_mfx_confirmed_b2s2_v2,
)

VERSION = "MFX_OPTION_B_V2_CHRONOLOGICAL_REPLAY_SIM_ONLY_V1"
MAX_SNAPSHOTS = 32
GENESIS = sha256(b"MFX:P0.165:UNAPPROVED-CLOSED-SIM-REPLAY").hexdigest()


@dataclass(frozen=True, slots=True, repr=False)
class OptionBReplaySnapshot:
    rule_id: str
    bars: SyntheticMultiTfBars
    confirmed_m15_history: tuple[MarketBar, ...]
    decision_utc: datetime


@dataclass(frozen=True, slots=True, repr=False)
class OptionBReplayStep:
    snapshot: OptionBReplaySnapshot = field(repr=False)
    computed: MfxB2S2V2ClosedResearch = field(repr=False)
    source_identity_sha256: str
    event_identity_sha256: str
    source_content_sha256: str
    chain_sha256: str
    duplicate_suppressed: bool


@dataclass(frozen=True, slots=True, repr=False)
class OptionBReplayReceipt:
    version: str
    steps: tuple[OptionBReplayStep, ...] = field(repr=False)
    chain_sha256: str = field(repr=False)
    owner_policy_fingerprint_sha256: str = field(repr=False)
    snapshots_checked: int = 0
    distinct_event_windows: int = 0
    repeated_windows_suppressed: int = 0
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    simulated_only: bool = True
    source_license_verified: bool = False
    native_d1_revision_qualified: bool = False
    publisher_first_known_verified: bool = False
    live_bidask_rr_available: bool = False
    real_oos_qualified: bool = False
    numeric_policy_owner_approved: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    broker_orders: int = 0
    provider_calls: int = 0
    drive_market_writes: int = 0

    def as_safe_record(self) -> dict[str, str | int | bool]:
        """Public scope metadata only: never OHLC, private direction or hashes."""
        return {
            "version": self.version,
            "snapshots_checked": self.snapshots_checked,
            "distinct_event_windows": self.distinct_event_windows,
            "repeated_windows_suppressed": self.repeated_windows_suppressed,
            "action": self.action,
            "stage": self.stage,
            "simulated_only": self.simulated_only,
            "source_license_verified": self.source_license_verified,
            "native_d1_revision_qualified": self.native_d1_revision_qualified,
            "publisher_first_known_verified": self.publisher_first_known_verified,
            "live_bidask_rr_available": self.live_bidask_rr_available,
            "real_oos_qualified": self.real_oos_qualified,
            "numeric_policy_owner_approved": self.numeric_policy_owner_approved,
            "may_publish_buy_sell": self.may_publish_buy_sell,
            "may_trade": self.may_trade,
            "broker_orders": self.broker_orders,
            "provider_calls": self.provider_calls,
            "drive_market_writes": self.drive_market_writes,
        }


def _canonical(value: Any) -> Any:
    """Explicit stable typed canonicalisation; raw snapshot digest stays private."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("P165_EXACT_UTC_REQUIRED")
        return value.isoformat()
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("P165_FINITE_DECIMAL_REQUIRED")
        return str(value)
    if type(value) in (str, bool, int) or value is None:
        return value
    if type(value) is tuple:
        return [_canonical(v) for v in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _canonical(getattr(value, f.name)) for f in fields(value)}
    raise ValueError("P165_UNSUPPORTED_SOURCE_TYPE")


def _digest(value: Any) -> str:
    return sha256(json.dumps(
        _canonical(value), sort_keys=True, ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _utc(value: Any) -> datetime:
    if (type(value) is not datetime
            or value.tzinfo is None or value.utcoffset() != timedelta(0)):
        raise ValueError("P165_EXACT_UTC_DECISION_REQUIRED")
    return value


def replay_option_b_v2(
    snapshots: tuple[OptionBReplaySnapshot, ...],
    policy: MfxConfirmedB2S2V2Policy,
) -> OptionBReplayReceipt:
    """Recompute each CLOSED and known source snapshot in event-time order.

    Duplicates require byte-equivalent input and same rule/event identity.
    Any restated earlier event or opposite rule for the same M15 trigger
    fails rather than rewriting a prior simulated result. This is *not*
    historical point-in-time proof from a real vendor.
    """
    if (type(snapshots) is not tuple or not 1 <= len(snapshots) <= MAX_SNAPSHOTS
            or any(type(s) is not OptionBReplaySnapshot for s in snapshots)):
        raise ValueError("P165_TYPED_BOUNDED_REPLAY_SNAPSHOTS_REQUIRED")
    if (type(policy) is not MfxConfirmedB2S2V2Policy
            or policy != read_mfx_confirmed_b2s2_v2()):
        raise ValueError("P165_EXACT_UNAPPROVED_OPTION_B_V2_POLICY_REQUIRED")

    prior_decision: datetime | None = None
    prior_trigger_end: datetime | None = None
    original_source: str | None = None
    seen: dict[str, tuple[str, str]] = {}
    chain = GENESIS
    steps: list[OptionBReplayStep] = []
    duplicated = 0

    for index, snap in enumerate(snapshots):
        decision = _utc(snap.decision_utc)
        if prior_decision is not None and decision <= prior_decision:
            raise ValueError("P165_DECISION_REPLAY_NOT_STRICT_CHRONOLOGICAL")
        # Source-level correctness and strict CLOSED right-pivot causality
        # are *recalculated* by P0.161, not accepted from caller flags.
        result = compute_mfx_b2s2_v2_closed_candidate(
            rule_id=snap.rule_id, bars=snap.bars,
            confirmed_m15_history=snap.confirmed_m15_history,
            policy=policy, decision_utc=decision,
        )
        if (result.public_action != "NO_SIGNAL"
                or result.stage != "UNVERIFIED"
                or result.live_buy_sell_allowed or result.may_trade
                or result.independent_numeric_rule_approved
                or result.source_market_rights_verified
                or result.native_d1_revision_hold_cleared
                or result.true_historical_oos_qualified
                or result.broker_orders or result.new_provider_requests
                or result.new_drive_market_writes):
            raise ValueError("P165_PRIVATE_EXPERIMENTAL_SOURCE_AUTHORITY_DRIFT")

        first, last = snap.bars.trigger_m15
        if (prior_trigger_end is not None
                and last.key.bar_end_utc < prior_trigger_end):
            raise ValueError("P165_TRIGGER_WINDOW_REPLAY_ROLLBACK")
        source_identity = _digest((
            last.key.instrument_version,
            last.key.calendar_version, last.key.aggregation_version,
            last.key.side.value,
            last.observation.provider_id, last.observation.stream_id,
        ))
        if original_source is not None and source_identity != original_source:
            raise ValueError("P165_REPLAY_CROSS_SOURCE_STREAM_DRIFT")
        # Event identity intentionally excludes B2/S2: opposite signals from
        # one closed M15 event must be CONFLICT, not two independent trades.
        event = _digest((
            source_identity,
            first.key.bar_start_utc, last.key.bar_end_utc,
        ))
        # FULL private typed source including prior HTF and M15 history;
        # excludes evaluation time so a repeated read can be deduplicated.
        source_content = _digest((
            snap.rule_id, policy.fingerprint_sha256,
            snap.bars, snap.confirmed_m15_history,
        ))
        repeat = event in seen
        if repeat and seen[event] != (source_content, snap.rule_id):
            raise ValueError("P165_DUPLICATE_EVENT_RESTATED_OR_DIRECTION_CONFLICT")
        if not repeat:
            seen[event] = (source_content, snap.rule_id)
        else:
            duplicated += 1

        chain = _digest((
            VERSION, index, chain, decision,
            event, source_content, result.experimental_action.value,
            repeat, result.public_action,
        ))
        steps.append(OptionBReplayStep(
            snapshot=snap, computed=result,
            source_identity_sha256=source_identity,
            event_identity_sha256=event,
            source_content_sha256=source_content,
            chain_sha256=chain,
            duplicate_suppressed=repeat,
        ))
        prior_decision = decision
        prior_trigger_end = last.key.bar_end_utc
        original_source = source_identity

    return OptionBReplayReceipt(
        version=VERSION, steps=tuple(steps),
        chain_sha256=chain,
        owner_policy_fingerprint_sha256=policy.fingerprint_sha256,
        snapshots_checked=len(steps),
        distinct_event_windows=len(seen),
        repeated_windows_suppressed=duplicated,
    )


def verify_option_b_v2_replay(
    report: OptionBReplayReceipt,
) -> bool:
    """Replay every historical decision again; detect modified receipts."""
    if type(report) is not OptionBReplayReceipt or not report.steps:
        raise TypeError("P165_TYPED_NONEMPTY_REPLAY_RECEIPT_REQUIRED")
    snapshots = tuple(step.snapshot for step in report.steps
                      if type(step) is OptionBReplayStep)
    if len(snapshots) != len(report.steps):
        raise ValueError("P165_UNTYPED_REPLAY_STEP")
    recreated = replay_option_b_v2(
        snapshots, read_mfx_confirmed_b2s2_v2(),
    )
    if report != recreated:
        raise ValueError("P165_REPLAY_CHAIN_OR_AUTHORITY_DRIFT")
    return True
