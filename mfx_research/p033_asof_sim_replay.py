"""P0.33 — deterministic chronological replay of CLOSED synthetic B2/S2 OHLC.

Replay feeds the already computed, UNAPPROVED P0.32 research patterns into
the P0.31 22-label NO_SIGNAL router. A SHA256 hash-chain is an in-memory
reproducibility/tamper check, NOT a data vendor signature, persistent ledger,
real out-of-sample validation, broker backtest, or permission to trade.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json

from forex_trading.model import SignalStage
from mfx_research.causal_multitf_context import (
    SyntheticDerivationParameters, SyntheticMultiTfBars,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.pullback_pilot import UnapprovedResearchParameters
from mfx_research.p032_synthetic_ohlc_bridge import (
    ComputedSIMOHLCResearch, compute_and_route_sim_b2_s2,
)

VERSION = "MFX_A04_P33_CHRONOLOGICAL_SIM_REPLAY_CHAIN_V1"
MAX_WINDOWS = 96
GENESIS_SHA256 = sha256(
    ("MFX|P0.33|SIM_ONLY|NO_SIGNAL|" + VERSION).encode("ascii")
).hexdigest()


@dataclass(frozen=True, slots=True)
class SyntheticReplayWindow:
    """An as-of CLOSED SIM snapshot; NOT a real investment data sample."""

    rule_id: str
    bars: SyntheticMultiTfBars
    derivation: SyntheticDerivationParameters
    parameters: UnapprovedResearchParameters
    decision_utc: datetime


@dataclass(frozen=True, slots=True)
class ResearchReplayEntry:
    index: int
    decision_utc: datetime
    computed_receipt: ComputedSIMOHLCResearch
    payload_sha256: str
    previous_link_sha256: str
    chain_sha256: str

    @property
    def origin_event_id(self) -> str:
        return self.computed_receipt.origin_event_id

    @property
    def research_input_sha256(self) -> str:
        return self.computed_receipt.research_input_sha256

    @property
    def experimental_pattern(self) -> CandidateAction:
        return self.computed_receipt.experimental_numeric_action

    @property
    def linked_research_labels(self) -> tuple[str, ...]:
        return tuple(r.label for r in self.computed_receipt.classified_output.classified)

    @property
    def action(self) -> str:
        return "NO_SIGNAL"


@dataclass(frozen=True, slots=True)
class ResearchReplayReport:
    version: str
    entries: tuple[ResearchReplayEntry, ...]
    genesis_sha256: str
    chain_tip_sha256: str
    replay_asof_utc: datetime
    executed_sim_snapshots: int
    experimental_pattern_observations: int
    no_pattern_snapshots: int
    original_forex_catalog_labels: int = 18
    approved_mfx_design_labels: int = 22
    owner_signed_entry_numeric_rules: int = 0
    original_b2_s2_owner_numeric_obligations_pending: int = 36
    actual_confirmed_buy_sell_signals: int = 0
    real_market_backtest_trades: int = 0
    actual_out_of_sample_performance_metrics: int = 0
    provider_calls: int = 0
    real_drive_market_cache_writes: int = 0
    broker_orders: int = 0
    publish_alerts: bool = False
    may_trade: bool = False
    release_ready: bool = False


def _exact_utc(value: datetime, name: str) -> None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P033_EXACT_UTC_REQUIRED:" + name)


def _digest(data: dict[str, object]) -> str:
    raw = json.dumps(
        data, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
    ).encode("utf-8")
    return sha256(raw).hexdigest()


def _payload(index: int, receipt: ComputedSIMOHLCResearch) -> dict[str, object]:
    """Canonical in-memory audit record for deterministic linked receipts."""
    out = receipt.classified_output
    return {
        "version": VERSION,
        "index": index,
        "pilot": receipt.pilot_rule_id,
        "decision_utc": receipt.decision_utc.isoformat(),
        "first_known_utc": receipt.first_known_utc.isoformat(),
        "origin": receipt.origin_event_id,
        "synthetic_ohlc_fingerprint": receipt.research_input_sha256,
        "experimental_pattern": receipt.experimental_numeric_action.value,
        "pattern_reason": receipt.research_reason,
        "stage": receipt.research_phase.value,
        "h1_true_range_atr": str(receipt.actual_ohlc_computation.h1_true_range_atr),
        "context_time": receipt.actual_ohlc_computation.known_at_start_utc.isoformat(),
        "computed_timeframes": list(receipt.context_derived_from),
        "labels": [r.label for r in out.classified],
        "opportunity_ids": [
            r.research_opportunity_id for r in out.events
        ],
        "router_actions": [r.action for r in out.events],
        "external_action": receipt.action,
        "numeric_approval": receipt.pattern_source_numeric_approved,
        "actual_signals": receipt.actual_buy_sell_signals,
        "provider_calls": receipt.real_provider_calls,
        "drive_cache_writes": receipt.real_drive_market_cache_writes,
        "broker_orders": receipt.broker_orders,
        "release_ready": receipt.release_ready,
    }


def _link(prev_sha: str, payload_sha: str) -> str:
    if len(prev_sha) != 64 or len(payload_sha) != 64:
        raise ValueError("P033_CHAIN_INPUT_DIGEST_REQUIRED")
    return sha256(bytes.fromhex(prev_sha) + bytes.fromhex(payload_sha)).hexdigest()


def _verify_entry_invariants(entry: ResearchReplayEntry) -> None:
    receipt = entry.computed_receipt
    report = receipt.classified_output
    if (receipt.version != "MFX_A04_P32_CAUSAL_SIM_OHLC_TO_22_ZONE_RESEARCH_V1"
            or receipt.pilot_rule_id not in ("B2", "S2")
            or receipt.research_phase is not SignalStage.UNVERIFIED
            or receipt.action != "NO_SIGNAL"
            or receipt.pattern_source_numeric_approved
            or receipt.may_send_buy_sell_or_exit_alert
            or receipt.actual_buy_sell_signals != 0
            or receipt.real_provider_calls != 0
            or receipt.real_drive_market_cache_writes != 0
            or receipt.broker_orders != 0
            or receipt.release_ready
            or report.mfx_design_labels != 22
            or report.numeric_entry_predicates_approved != 0
            or report.original_b2_s2_source_numeric_obligations_pending != 36
            or report.confirmed_buy_sell_signals != 0
            or report.confirmed_exit_warnings != 0
            or report.may_send_live_alerts
            or report.may_trade
            or report.broker_orders != 0
            or entry.decision_utc != receipt.decision_utc):
        raise ValueError("P033_RESEARCH_ONLY_SOURCE_APPROVAL_GATE")
    expected = (
        (receipt.pilot_rule_id,)
        if receipt.experimental_numeric_action is not CandidateAction.NO_SIGNAL
        else ()
    )
    if (entry.linked_research_labels != expected
            or len(report.events) != len(expected)
            or any(event.action != "NO_SIGNAL" or event.conflict
                   for event in report.events)):
        raise ValueError("P033_COMPUTED_PATTERN_ROUTING_INCONSISTENCY")


def verify_sim_replay_chain(report: ResearchReplayReport) -> bool:
    """Validate a provided IN-MEMORY chain receipt; does not persist/sign it."""
    if not isinstance(report, ResearchReplayReport):
        raise TypeError("P033_TYPED_REPLAY_RECEIPT_REQUIRED")
    _exact_utc(report.replay_asof_utc, "replay_asof_utc")
    if (report.version != VERSION or report.genesis_sha256 != GENESIS_SHA256
            or len(report.entries) > MAX_WINDOWS
            or report.executed_sim_snapshots != len(report.entries)
            or report.owner_signed_entry_numeric_rules != 0
            or report.original_b2_s2_owner_numeric_obligations_pending != 36
            or report.original_forex_catalog_labels != 18
            or report.approved_mfx_design_labels != 22
            or report.actual_confirmed_buy_sell_signals != 0
            or report.real_market_backtest_trades != 0
            or report.actual_out_of_sample_performance_metrics != 0
            or report.provider_calls != 0
            or report.real_drive_market_cache_writes != 0
            or report.broker_orders != 0
            or report.publish_alerts
            or report.may_trade
            or report.release_ready):
        raise ValueError("P033_INVALID_REPLAY_CLAIM_OR_COUNT")
    prior = GENESIS_SHA256
    last_time: datetime | None = None
    origins: set[str] = set()
    observations = 0
    for index, entry in enumerate(report.entries):
        if not isinstance(entry, ResearchReplayEntry):
            raise TypeError("P033_TYPED_REPLAY_ENTRY_REQUIRED")
        _exact_utc(entry.decision_utc, "entry.decision_utc")
        if (entry.index != index
                or (last_time is not None and entry.decision_utc <= last_time)
                or entry.decision_utc > report.replay_asof_utc):
            raise ValueError("P033_REPLAY_NOT_STRICT_ASOF_ORDER")
        if entry.origin_event_id in origins:
            raise ValueError("P033_DUPLICATE_OR_REVISED_RESEARCH_EVENT")
        origins.add(entry.origin_event_id)
        _verify_entry_invariants(entry)
        p_hash = _digest(_payload(index, entry.computed_receipt))
        link = _link(prior, p_hash)
        if (entry.payload_sha256 != p_hash
                or entry.previous_link_sha256 != prior
                or entry.chain_sha256 != link):
            raise ValueError("P033_REPLAY_HASH_CHAIN_TAMPER_OR_DRIFT")
        if entry.experimental_pattern is not CandidateAction.NO_SIGNAL:
            observations += 1
        last_time = entry.decision_utc
        prior = link
    if (report.chain_tip_sha256 != prior
            or report.experimental_pattern_observations != observations
            or report.no_pattern_snapshots != len(report.entries) - observations):
        raise ValueError("P033_REPLAY_TIP_OR_PATTERN_COUNTS_INCONSISTENT")
    return True


def run_asof_sim_ohlc_replay(
    windows: tuple[SyntheticReplayWindow, ...],
    replay_asof_utc: datetime,
) -> ResearchReplayReport:
    """Replay only already available synthetic snapshots in causal clock order.

    No hidden signal decisions: each B2/S2 pattern is recomputed from
    independently validated CLOSED OHLC via P032; all user actions NO_SIGNAL.
    """
    _exact_utc(replay_asof_utc, "replay_asof_utc")
    if not isinstance(windows, tuple) or len(windows) > MAX_WINDOWS:
        raise ValueError("P033_BOUNDED_IMMUTABLE_REPLAY_REQUIRED")
    prior = GENESIS_SHA256
    previous_time: datetime | None = None
    origins: set[str] = set()
    entries: list[ResearchReplayEntry] = []
    observed = 0
    for index, window in enumerate(windows):
        if not isinstance(window, SyntheticReplayWindow):
            raise TypeError("P033_TYPED_SYNTHETIC_REPLAY_WINDOW_REQUIRED")
        _exact_utc(window.decision_utc, "window.decision_utc")
        if window.decision_utc > replay_asof_utc:
            raise ValueError("P033_FUTURE_REPLAY_WINDOW_AFTER_ASOF")
        if previous_time is not None and window.decision_utc <= previous_time:
            raise ValueError("P033_NONINCREASING_REPLAY_DECISION_CLOCK")
        result = compute_and_route_sim_b2_s2(
            window.rule_id, window.bars, window.derivation,
            window.parameters, window.decision_utc,
        )
        if result.origin_event_id in origins:
            raise ValueError("P033_DUPLICATE_OR_REVISED_RESEARCH_EVENT")
        origins.add(result.origin_event_id)
        payload = _digest(_payload(index, result))
        link = _link(prior, payload)
        entry = ResearchReplayEntry(
            index=index, decision_utc=window.decision_utc,
            computed_receipt=result, payload_sha256=payload,
            previous_link_sha256=prior, chain_sha256=link,
        )
        _verify_entry_invariants(entry)
        entries.append(entry)
        if result.experimental_numeric_action is not CandidateAction.NO_SIGNAL:
            observed += 1
        prior = link
        previous_time = window.decision_utc

    report = ResearchReplayReport(
        version=VERSION,
        entries=tuple(entries),
        genesis_sha256=GENESIS_SHA256,
        chain_tip_sha256=prior,
        replay_asof_utc=replay_asof_utc,
        executed_sim_snapshots=len(entries),
        experimental_pattern_observations=observed,
        no_pattern_snapshots=len(entries) - observed,
    )
    if not verify_sim_replay_chain(report):
        raise ValueError("P033_CHAIN_VALIDATION_FAILED")
    return report
