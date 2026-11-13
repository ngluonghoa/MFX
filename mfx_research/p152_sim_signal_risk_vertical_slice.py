"""MFX P0.152 — real SIM B2/S2 pattern -> explicit SIM BID/ASK economics.

This is the first offline composition of the already existing closed-OHLC
B2/S2 pilot, 22-role research classification and cost-aware net-R calculator.
STRICTLY SYNTHETIC: no market-data authority, real first-known, buy/sell
publication, broker orders, Drive price writes or licensed execution prices.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json

from forex_trading.market_data import MarketBar
from forex_trading.model import ActionIntent, SignalStage
from forex_trading.quotes import Quote, QuoteQuality, ensure_utc
from mfx_research.bidask_cost_aware_sim_risk import (
    CostAwareSimRiskReceipt, SimExitLevels, SimPerUnitCosts,
    evaluate_cost_aware_sim_risk,
)
from mfx_research.causal_multitf_context import (
    SyntheticDerivationParameters, SyntheticMultiTfBars,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p032_synthetic_ohlc_bridge import (
    ComputedSIMOHLCResearch, compute_and_route_sim_b2_s2,
)
from mfx_research.pullback_pilot import UnapprovedResearchParameters

VERSION = "MFX_V1_P152_OFFLINE_B2_S2_PATTERN_TO_NET_R_RESEARCH_V1"
_EXPECTED = {"B2": CandidateAction.BUY, "S2": CandidateAction.SELL}
_HINT = {"B2": "SIM_BUY_RESEARCH_CANDIDATE_ONLY",
         "S2": "SIM_SELL_RESEARCH_CANDIDATE_ONLY"}


@dataclass(frozen=True, slots=True)
class SyntheticPatternWithNetRisk:
    version: str
    pilot_rule_id: str
    pattern: ComputedSIMOHLCResearch
    economics: CostAwareSimRiskReceipt | None
    experimental_pattern: CandidateAction
    pattern_hint: str
    cost_evidence_status: str
    research_fingerprint_sha256: str
    decision_utc: str
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    original_forex_numeric_policy_approved: bool = False
    live_data_rights_verified: bool = False
    publisher_first_known_attested: bool = False
    real_bidask_execution_costs_verified: bool = False
    causal_oos_qualified: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_market_cache_writes: int = 0
    broker_orders: int = 0


def _join_quote(
    *, quote: Quote, last_mid: MarketBar, decision_utc: datetime,
) -> None:
    if type(quote) is not Quote:
        raise TypeError("P152_TYPED_CALLER_CLAIMED_SIM_QUOTE_REQUIRED")
    if (not quote.provider.startswith("SIM:")
            or not quote.source_revision.startswith("SIM:")
            or quote.quality is not QuoteQuality.VERIFIED):
        raise ValueError("P152_SIM_CLAIMED_QUOTE_ONLY")
    if quote.provider != last_mid.observation.provider_id:
        raise ValueError("P152_SIM_PATTERN_QUOTE_PROVIDER_MISMATCH")
    if not (last_mid.key.bar_end_utc <= quote.event_time_utc
            <= quote.first_known_utc <= decision_utc
            and last_mid.first_known_utc <= quote.first_known_utc):
        raise ValueError("P152_PATTERN_QUOTE_NONCAUSAL_JOIN")
    # A source MID close outside the simulated quote spread is a different
    # hypothetical price snapshot and may not be silently priced as same.
    if not quote.bid <= last_mid.close <= quote.ask:
        raise ValueError("P152_MID_OUTSIDE_SIM_BID_ASK_BRACKET")


def _digest(
    pattern: ComputedSIMOHLCResearch,
    economics: CostAwareSimRiskReceipt | None,
) -> str:
    # Non-secret local comparison digest, NOT an externally signed quote.
    obj: dict[str, object] = {
        "version": VERSION,
        "rule": pattern.pilot_rule_id,
        "origin": pattern.origin_event_id,
        "input_sha256": pattern.research_input_sha256,
        "candidate": pattern.experimental_numeric_action.value,
        "decision_utc": pattern.decision_utc.isoformat(),
        "economic": None,
    }
    if economics is not None:
        obj["economic"] = {
            "source_revision_claim": economics.source_revision_claim,
            "quote_first_known_claim": economics.quote_first_known_claim_utc,
            "bid": str(economics.reference_bid),
            "ask": str(economics.reference_ask),
            "entry": str(economics.effective_entry_price),
            "stop": str(economics.effective_stop_exit_price),
            "target": str(economics.effective_target_exit_price),
            "cost_version": economics.cost_version,
            "risk_plan_version": economics.risk_plan_version,
            "fee": str(economics.explicit_roundtrip_fee_per_base_unit),
            "risk": str(economics.net_risk_quote_currency_per_base_unit),
            "reward": str(economics.net_reward_quote_currency_per_base_unit),
        }
    return sha256(json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")).hexdigest()


def review_sim_b2_s2_with_net_risk(
    *,
    rule_id: str,
    bars: SyntheticMultiTfBars,
    derivation: SyntheticDerivationParameters,
    parameters: UnapprovedResearchParameters,
    decision_utc: datetime,
    quote: Quote | None = None,
    exits: SimExitLevels | None = None,
    costs: SimPerUnitCosts | None = None,
    max_quote_age: timedelta | None = None,
) -> SyntheticPatternWithNetRisk:
    """One offline computed SIM candidate plus *optional* same-event net R:R.

    The method intentionally does NOT convert a SIM BUY/SELL hint into the
    published action. Absence of a pattern never produces fabricated risk.
    """
    ensure_utc(decision_utc, "decision_utc")
    if type(rule_id) is not str or rule_id not in _EXPECTED:
        raise ValueError("P152_ONLY_B2_S2_SIM_PILOTS")
    bundle = (quote, exits, costs, max_quote_age)
    if any(v is not None for v in bundle) and not all(
            v is not None for v in bundle):
        raise ValueError("P152_EXACT_COMPLETE_SIM_RISK_BUNDLE_OR_NONE")
    pattern = compute_and_route_sim_b2_s2(
        rule_id, bars, derivation, parameters, decision_utc,
    )
    if (type(pattern) is not ComputedSIMOHLCResearch
            or pattern.research_phase is not SignalStage.UNVERIFIED
            or pattern.action != "NO_SIGNAL"
            or pattern.pattern_source_numeric_approved
            or pattern.actual_market_data_verified
            or pattern.may_send_buy_sell_or_exit_alert
            or pattern.real_provider_calls or pattern.broker_orders
            or pattern.real_drive_market_cache_writes):
        raise ValueError("P152_PATTERN_RESEARCH_ONLY_GATE")
    expected = _EXPECTED[rule_id]
    candidate = pattern.experimental_numeric_action
    if candidate not in (expected, CandidateAction.NO_SIGNAL):
        raise ValueError("P152_WRONG_DIRECTION_SIM_PATTERN")
    if candidate is expected:
        if (len(pattern.classified_output.events) != 1
                or len(pattern.classified_output.classified) != 1
                or pattern.classified_output.classified[0].label != rule_id):
            raise ValueError("P152_SIM_ROUTE_PATTERN_MISMATCH")
    elif (pattern.classified_output.events
          or pattern.classified_output.classified):
        raise ValueError("P152_NO_PATTERN_MUST_NOT_ROUTE")
    economics: CostAwareSimRiskReceipt | None = None
    cost_status = "NO_CLOSED_SIM_PATTERN"
    if candidate is expected:
        cost_status = "PATTERN_RESEARCH_ONLY_NO_SIM_RISK_BUNDLE"
        if all(v is not None for v in bundle):
            if (type(quote) is not Quote
                    or type(exits) is not SimExitLevels
                    or type(costs) is not SimPerUnitCosts
                    or type(max_quote_age) is not timedelta):
                raise TypeError("P152_TYPED_SIM_RISK_BUNDLE_REQUIRED")
            last = bars.trigger_m15[-1]
            _join_quote(quote=quote, last_mid=last, decision_utc=decision_utc)
            intent = (ActionIntent.ENTRY_LONG if rule_id == "B2"
                      else ActionIntent.ENTRY_SHORT)
            economics = evaluate_cost_aware_sim_risk(
                quote=quote, intent=intent, decision_utc=decision_utc,
                max_quote_age=max_quote_age, exits=exits,
                costs=costs, instrument="EUR/USD",
            )
            if (economics.action != "NO_SIGNAL"
                    or economics.stage != "UNVERIFIED"
                    or economics.original_forex_numeric_rules_approved
                    or economics.independently_verified_data_rights
                    or economics.real_execution_costs_approved
                    or economics.may_publish_buy_sell
                    or economics.may_trade
                    or economics.provider_requests
                    or economics.drive_market_cache_writes
                    or economics.broker_orders):
                raise ValueError("P152_SIM_ECONOMICS_CANNOT_AUTHORIZE_SIGNAL")
            cost_status = "SIM_NET_R_CALCULATED_NOT_EXECUTABLE"
    return SyntheticPatternWithNetRisk(
        version=VERSION, pilot_rule_id=rule_id,
        pattern=pattern, economics=economics,
        experimental_pattern=candidate,
        pattern_hint=(_HINT[rule_id] if candidate is expected
                      else "NO_SIM_PATTERN"),
        cost_evidence_status=cost_status,
        research_fingerprint_sha256=_digest(pattern, economics),
        decision_utc=decision_utc.isoformat(),
    )
