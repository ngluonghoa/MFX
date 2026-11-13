"""MFX v1 signal-first: two-sided cost-aware FX risk arithmetic, SIM ONLY.

Pure offline algebra over a CALLER-CLAIMED quote and SIM hypothetical exits.
Existing frozen Forex Quote/indicative_price guards enforce causal BID/ASK
selection but do NOT authenticate vendor account rights or live first-known.
No original B2/S2 source numeric approval, fills, signals, Drive, or broker IO.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from forex_trading.model import ActionIntent
from forex_trading.quotes import (
    PriceSide, Quote, indicative_price, ensure_utc,
)

VERSION = "MFX_V1_BIDASK_COST_AWARE_SIM_RISK_RESEARCH_V1"
INSTRUMENT = "EUR/USD"
ZERO = Decimal("0")


def _sim_version(value: str, label: str) -> None:
    if (type(value) is not str or not value.startswith("SIM:")
            or len(value) < 5 or len(value) > 128
            or any(c.isspace() or ord(c) < 33 or ord(c) > 126
                   for c in value)):
        raise ValueError("MFX_RISK_ONLY_SIM_VERSION_REQUIRED:" + label)


def _decimal(value: Decimal, label: str, *, positive: bool) -> None:
    if (type(value) is not Decimal or not value.is_finite()
            or (value <= ZERO if positive else value < ZERO)):
        raise ValueError("MFX_RISK_INVALID_DECIMAL:" + label)


@dataclass(frozen=True, slots=True)
class SimExitLevels:
    """Hypothetical exit-side absolute prices, NEVER executed fills.

    LONG stops/targets are BID exit levels; SHORT are ASK exit levels.
    They are intentionally not automatically calculated from MID OHLC.
    """

    version: str
    stop_price: Decimal
    target_price: Decimal
    exit_side: PriceSide

    def __post_init__(self) -> None:
        _sim_version(self.version, "exit_levels")
        _decimal(self.stop_price, "stop_price", positive=True)
        _decimal(self.target_price, "target_price", positive=True)
        if type(self.exit_side) is not PriceSide:
            raise TypeError("MFX_RISK_TYPED_EXIT_SIDE_REQUIRED")


@dataclass(frozen=True, slots=True)
class SimPerUnitCosts:
    """Explicit price-in-quote-currency per one base-unit assumptions.

    Entry/exit slippage and entry/exit commissions are all absolute
    nonnegative QUOTE-CURRENCY-PER-BASE-UNIT, NOT percent/pips/lots.
    Zero assumption is allowed for fixture maths but NEVER a zero-cost proof.
    """

    version: str
    entry_slippage: Decimal
    exit_slippage: Decimal
    entry_fee: Decimal
    exit_fee: Decimal

    def __post_init__(self) -> None:
        _sim_version(self.version, "costs")
        for name in ("entry_slippage", "exit_slippage",
                     "entry_fee", "exit_fee"):
            _decimal(getattr(self, name), name, positive=False)


@dataclass(frozen=True, slots=True)
class CostAwareSimRiskReceipt:
    version: str
    instrument: str
    intent: ActionIntent
    source_quote_provider_claim: str
    source_revision_claim: str
    quote_first_known_claim_utc: str
    decision_utc: str
    risk_plan_version: str
    cost_version: str
    entry_side: PriceSide
    exit_side: PriceSide
    reference_bid: Decimal
    reference_ask: Decimal
    reference_spread: Decimal
    entry_reference_price: Decimal
    effective_entry_price: Decimal
    stop_exit_reference_price: Decimal
    target_exit_reference_price: Decimal
    effective_stop_exit_price: Decimal
    effective_target_exit_price: Decimal
    explicit_roundtrip_fee_per_base_unit: Decimal
    net_risk_quote_currency_per_base_unit: Decimal
    net_reward_quote_currency_per_base_unit: Decimal
    experimental_net_risk_reward: Decimal
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    hypothetical_exit_only: bool = True
    original_forex_numeric_rules_approved: bool = False
    independently_verified_data_rights: bool = False
    publisher_first_known_attested: bool = False
    real_execution_costs_approved: bool = False
    historical_oos_qualified: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_market_cache_writes: int = 0
    broker_orders: int = 0


def evaluate_cost_aware_sim_risk(
    *,
    quote: Quote,
    intent: ActionIntent,
    decision_utc: datetime,
    max_quote_age: timedelta,
    exits: SimExitLevels,
    costs: SimPerUnitCosts,
    instrument: str,
) -> CostAwareSimRiskReceipt:
    """Calculate SIM net R:R for LONG/SHORT using source BID/ASK semantics.

    Exit stops/targets are hypothetical absolute EXIT-SIDE prices; they do not
    assert known future prices, actual slippage, fills, costs or signal rules.
    All raw numbers remain in-memory and MUST NOT be put in public CI logs.
    """
    if type(instrument) is not str or instrument != INSTRUMENT:
        raise ValueError("MFX_RISK_EXACT_EURUSD_ONLY")
    if type(quote) is not Quote:
        raise TypeError("MFX_RISK_TYPED_QUOTE_REQUIRED")
    if type(exits) is not SimExitLevels or type(costs) is not SimPerUnitCosts:
        raise TypeError("MFX_RISK_TYPED_SIM_ASSUMPTIONS_REQUIRED")
    if type(intent) is not ActionIntent or intent not in (
            ActionIntent.ENTRY_LONG, ActionIntent.ENTRY_SHORT):
        raise ValueError("MFX_RISK_ENTRY_LONG_OR_SHORT_ONLY")
    ensure_utc(decision_utc, "decision_utc")
    # Frozen original Forex quote guard requires VERIFIED (caller asserted),
    # causal first-known <= decision, max age and proper long/short side.
    entry = indicative_price(quote, intent, decision_utc, max_quote_age)
    expected_exit = (PriceSide.BID if intent is ActionIntent.ENTRY_LONG
                     else PriceSide.ASK)
    if exits.exit_side is not expected_exit:
        raise ValueError("MFX_RISK_EXIT_PRICE_SIDE_MISMATCH")
    if (intent is ActionIntent.ENTRY_LONG and not (
            exits.stop_price < quote.bid < exits.target_price)):
        raise ValueError("MFX_RISK_LONG_STOP_TARGET_ORDER_INVALID")
    if (intent is ActionIntent.ENTRY_SHORT and not (
            exits.target_price < quote.ask < exits.stop_price)):
        raise ValueError("MFX_RISK_SHORT_STOP_TARGET_ORDER_INVALID")
    fee = costs.entry_fee + costs.exit_fee
    if intent is ActionIntent.ENTRY_LONG:
        effective_entry = entry.value + costs.entry_slippage
        stop_effective = exits.stop_price - costs.exit_slippage
        target_effective = exits.target_price - costs.exit_slippage
        net_risk = effective_entry - stop_effective + fee
        net_reward = target_effective - effective_entry - fee
    else:
        effective_entry = entry.value - costs.entry_slippage
        stop_effective = exits.stop_price + costs.exit_slippage
        target_effective = exits.target_price + costs.exit_slippage
        net_risk = stop_effective - effective_entry + fee
        net_reward = effective_entry - target_effective - fee
    if (effective_entry <= ZERO or stop_effective <= ZERO
            or target_effective <= ZERO):
        raise ValueError("MFX_RISK_EFFECTIVE_PRICE_NOT_POSITIVE")
    if net_risk <= ZERO:
        raise ValueError("MFX_RISK_NET_RISK_NOT_POSITIVE")
    # Negative/zero reward is meaningful negative economics, NOT a signal.
    return CostAwareSimRiskReceipt(
        version=VERSION, instrument=INSTRUMENT, intent=intent,
        source_quote_provider_claim=quote.provider,
        source_revision_claim=quote.source_revision,
        quote_first_known_claim_utc=quote.first_known_utc.isoformat(),
        decision_utc=decision_utc.isoformat(),
        risk_plan_version=exits.version, cost_version=costs.version,
        entry_side=entry.side, exit_side=expected_exit,
        reference_bid=quote.bid, reference_ask=quote.ask,
        reference_spread=quote.ask - quote.bid,
        entry_reference_price=entry.value,
        effective_entry_price=effective_entry,
        stop_exit_reference_price=exits.stop_price,
        target_exit_reference_price=exits.target_price,
        effective_stop_exit_price=stop_effective,
        effective_target_exit_price=target_effective,
        explicit_roundtrip_fee_per_base_unit=fee,
        net_risk_quote_currency_per_base_unit=net_risk,
        net_reward_quote_currency_per_base_unit=net_reward,
        experimental_net_risk_reward=net_reward / net_risk,
    )
