"""P0.166: compose P0.165 right-confirmed B2/S2 replay with P0.151 SIM net R.

Existing P0.161 computes candidates; P0.165 orders/deduplicates events;
P0.152 checks same-M15 synthetic BID/ASK quote linkage; P0.151 calculates
LONG ASK/BID and SHORT BID/ASK hypothetical per-unit net R:R.
No own price model, real quote, sourced SL/TP, signal or broker integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
import json

from forex_trading.model import ActionIntent
from forex_trading.quotes import Quote
from mfx_research.bidask_cost_aware_sim_risk import (
    CostAwareSimRiskReceipt, SimExitLevels, SimPerUnitCosts,
    evaluate_cost_aware_sim_risk,
)
from mfx_research.mfx_b2s2_confirmed_policy_v2 import MfxConfirmedB2S2V2Policy
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.option_b_v2_chronological_replay import (
    OptionBReplayReceipt, OptionBReplaySnapshot,
    replay_option_b_v2, verify_option_b_v2_replay,
)
from mfx_research.p152_sim_signal_risk_vertical_slice import _join_quote

VERSION = "MFX_OPTION_B_V2_BIDASK_CHRONOLOGICAL_SIM_RISK_V1"


@dataclass(frozen=True, slots=True, repr=False)
class SimRiskBundle:
    quote: Quote = field(repr=False)
    exits: SimExitLevels = field(repr=False)
    costs: SimPerUnitCosts = field(repr=False)
    max_quote_age: timedelta

    def __post_init__(self) -> None:
        if (type(self.quote) is not Quote
                or type(self.exits) is not SimExitLevels
                or type(self.costs) is not SimPerUnitCosts
                or type(self.max_quote_age) is not timedelta
                or self.max_quote_age <= timedelta(0)):
            raise TypeError("P166_EXACT_TYPED_POSITIVE_SIM_RISK_BUNDLE")


@dataclass(frozen=True, slots=True, repr=False)
class OptionBNetRStep:
    replay_step_event_sha256: str
    risk_input_sha256: str
    status: str
    economics: CostAwareSimRiskReceipt | None = field(repr=False, default=None)


@dataclass(frozen=True, slots=True, repr=False)
class OptionBNetRReplayReceipt:
    version: str
    replay: OptionBReplayReceipt = field(repr=False)
    bundles: tuple[SimRiskBundle | None, ...] = field(repr=False)
    steps: tuple[OptionBNetRStep, ...] = field(repr=False)
    risk_chain_sha256: str = field(repr=False)
    simulated_economic_evaluations: int = 0
    duplicate_economic_evaluations_suppressed: int = 0
    no_economic_bundle_snapshots: int = 0
    no_pattern_snapshots: int = 0
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    simulated_only: bool = True
    owner_numeric_policy_approved: bool = False
    original_forex_numeric_parity_verified: bool = False
    licensed_source_verified: bool = False
    source_d1_revision_qualified: bool = False
    publisher_first_known_verified: bool = False
    actual_bidask_costs_verified: bool = False
    real_out_of_sample_qualified: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_market_writes: int = 0
    broker_orders: int = 0

    def as_safe_record(self) -> dict[str, str | int | bool]:
        return {
            "version": self.version,
            "snapshots_checked": self.replay.snapshots_checked,
            "distinct_event_windows": self.replay.distinct_event_windows,
            "repeated_windows_suppressed": self.replay.repeated_windows_suppressed,
            "simulated_economic_evaluations":
                self.simulated_economic_evaluations,
            "duplicate_economic_evaluations_suppressed":
                self.duplicate_economic_evaluations_suppressed,
            "no_economic_bundle_snapshots": self.no_economic_bundle_snapshots,
            "no_pattern_snapshots": self.no_pattern_snapshots,
            "action": self.action,
            "stage": self.stage,
            "simulated_only": self.simulated_only,
            "owner_numeric_policy_approved": self.owner_numeric_policy_approved,
            "original_forex_numeric_parity_verified":
                self.original_forex_numeric_parity_verified,
            "licensed_source_verified": self.licensed_source_verified,
            "source_d1_revision_qualified": self.source_d1_revision_qualified,
            "publisher_first_known_verified": self.publisher_first_known_verified,
            "actual_bidask_costs_verified": self.actual_bidask_costs_verified,
            "real_out_of_sample_qualified": self.real_out_of_sample_qualified,
            "may_publish_buy_sell": self.may_publish_buy_sell,
            "may_trade": self.may_trade,
            "provider_requests": self.provider_requests,
            "drive_market_writes": self.drive_market_writes,
            "broker_orders": self.broker_orders,
        }


def _digest(record: object) -> str:
    return sha256(json.dumps(
        record, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _risk_fingerprint(bundle: SimRiskBundle | None) -> str:
    """Private deterministic input identity (not publisher-authorized evidence)."""
    if bundle is None:
        return _digest(["SIM:ABSENT"])
    q, e, c = bundle.quote, bundle.exits, bundle.costs
    return _digest([
        "SIM:PRIVATE_BIDASK_RISK_BUNDLE",
        q.provider, q.source_revision, q.event_time_utc.isoformat(),
        q.first_known_utc.isoformat(), str(q.bid), str(q.ask), q.quality.value,
        e.version, e.exit_side.value, str(e.stop_price), str(e.target_price),
        c.version, str(c.entry_slippage), str(c.exit_slippage),
        str(c.entry_fee), str(c.exit_fee),
        bundle.max_quote_age.days, bundle.max_quote_age.seconds,
        bundle.max_quote_age.microseconds,
    ])


def price_option_b_v2_replay(
    snapshots: tuple[OptionBReplaySnapshot, ...],
    bundles: tuple[SimRiskBundle | None, ...],
    policy: MfxConfirmedB2S2V2Policy,
) -> OptionBNetRReplayReceipt:
    """Only price unique computed SIM candidates, with exact quote causality.

    Any same-event quote/cost change is rejected: no retroactive reprice.
    Duplicate same evidence reuses an earlier private result but does not
    generate a second economic calculation or another signal.
    """
    if type(bundles) is not tuple or len(bundles) != len(snapshots):
        raise ValueError("P166_EXACT_ONE_RISK_BUNDLE_PER_REPLAY_SNAPSHOT")
    if any(type(x) is not SimRiskBundle and x is not None for x in bundles):
        raise TypeError("P166_SIM_RISK_BUNDLE_OR_NONE_REQUIRED")
    replay = replay_option_b_v2(snapshots, policy)
    if not verify_option_b_v2_replay(replay):
        raise ValueError("P166_UNVERIFIED_OPTION_B_CHRONOLOGICAL_REPLAY")
    previous: dict[str, tuple[str, CostAwareSimRiskReceipt | None]] = {}
    rows: list[OptionBNetRStep] = []
    cost_count = 0
    skipped = 0
    no_bundle = 0
    no_pattern = 0
    chain = _digest([VERSION, replay.chain_sha256])

    for step, bundle in zip(replay.steps, bundles):
        candidate = step.computed.experimental_action
        expected = (CandidateAction.BUY if step.snapshot.rule_id == "B2"
                    else CandidateAction.SELL)
        if candidate not in (expected, CandidateAction.NO_SIGNAL):
            raise ValueError("P166_OPPOSITE_UNAPPROVED_OPTION_B_CANDIDATE")
        fp = _risk_fingerprint(bundle)
        event = step.event_identity_sha256
        if event in previous:
            prev_fp, prev_risk = previous[event]
            if not step.duplicate_suppressed or fp != prev_fp:
                raise ValueError("P166_DUPLICATE_EVENT_REPRICE_OR_COST_REVISION")
            status = "DUPLICATE_SIM_EVENT_NOT_REPRICED"
            economic = prev_risk
            skipped += 1
        else:
            if step.duplicate_suppressed:
                raise ValueError("P166_DUPLICATE_WITHOUT_PRIOR_EVIDENCE")
            economic = None
            if candidate is CandidateAction.NO_SIGNAL:
                if bundle is not None:
                    raise ValueError("P166_NO_COMPUTED_PATTERN_MUST_NOT_PRICE")
                status = "NO_SIM_PATTERN_NO_ECONOMIC_RESULT"
                no_pattern += 1
            elif bundle is None:
                status = "SIM_PATTERN_NO_BIDASK_EXIT_COST_BUNDLE"
                no_bundle += 1
            else:
                q = bundle.quote
                last = step.snapshot.bars.trigger_m15[-1]
                _join_quote(
                    quote=q, last_mid=last,
                    decision_utc=step.snapshot.decision_utc,
                )
                intent = (ActionIntent.ENTRY_LONG
                          if candidate is CandidateAction.BUY
                          else ActionIntent.ENTRY_SHORT)
                economic = evaluate_cost_aware_sim_risk(
                    quote=q, intent=intent,
                    decision_utc=step.snapshot.decision_utc,
                    max_quote_age=bundle.max_quote_age,
                    exits=bundle.exits, costs=bundle.costs,
                    instrument="EUR/USD",
                )
                if (economic.action != "NO_SIGNAL"
                        or economic.stage != "UNVERIFIED"
                        or economic.may_publish_buy_sell
                        or economic.may_trade
                        or economic.original_forex_numeric_rules_approved
                        or economic.independently_verified_data_rights
                        or economic.publisher_first_known_attested
                        or economic.real_execution_costs_approved
                        or economic.historical_oos_qualified
                        or economic.provider_requests
                        or economic.drive_market_cache_writes
                        or economic.broker_orders):
                    raise ValueError("P166_SIM_RISK_PUBLIC_AUTHORITY_DRIFT")
                status = "SIM_NET_R_CALCULATED_NOT_MARKET_EXECUTABLE"
                cost_count += 1
            previous[event] = (fp, economic)
        chain = _digest([
            VERSION, chain, step.chain_sha256, event, fp, status,
            None if economic is None else [
                str(economic.net_risk_quote_currency_per_base_unit),
                str(economic.net_reward_quote_currency_per_base_unit),
                str(economic.experimental_net_risk_reward),
                economic.cost_version, economic.risk_plan_version,
            ],
        ])
        rows.append(OptionBNetRStep(
            replay_step_event_sha256=event, risk_input_sha256=fp,
            status=status, economics=economic,
        ))
    return OptionBNetRReplayReceipt(
        version=VERSION, replay=replay,
        bundles=bundles, steps=tuple(rows), risk_chain_sha256=chain,
        simulated_economic_evaluations=cost_count,
        duplicate_economic_evaluations_suppressed=skipped,
        no_economic_bundle_snapshots=no_bundle,
        no_pattern_snapshots=no_pattern,
    )


def verify_option_b_v2_risk_replay(report: OptionBNetRReplayReceipt) -> bool:
    """Recompute exact original source/quotes and compare immutable records."""
    if type(report) is not OptionBNetRReplayReceipt:
        raise TypeError("P166_TYPED_OPTION_B_RISK_REPLAY_RECEIPT_REQUIRED")
    snapshots = tuple(step.snapshot for step in report.replay.steps)
    recreated = price_option_b_v2_replay(
        snapshots, report.bundles,
        __import__(
            "mfx_research.mfx_b2s2_confirmed_policy_v2",
            fromlist=["read_mfx_confirmed_b2s2_v2"],
        ).read_mfx_confirmed_b2s2_v2(),
    )
    if report != recreated:
        raise ValueError("P166_SIM_BIDASK_REPLAY_CHAIN_OR_RIGHTS_DRIFT")
    return True
