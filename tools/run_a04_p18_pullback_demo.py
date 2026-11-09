"""P0.18 CI-only actual parametric B2/S2 research decisions, synthetic inputs."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import json

from forex_trading.market_data import MarketBar
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.pullback_pilot import (
    ClaimedStructuralContext, StructuralTrend, UnapprovedResearchParameters,
    evaluate_unapproved_b2_s2,
)
from tools.run_a04_p16_signal_demo import START, synthetic_m15_bars


def case(rule: str) -> tuple[
    tuple[MarketBar, MarketBar],
    ClaimedStructuralContext,
    UnapprovedResearchParameters,
]:
    """Fully synthetic B2/S2 numbers; NO claimed Forex-approved parameters."""
    if rule == "B2":
        bars = synthetic_m15_bars(("1.1010", "1.1018"))
        first = replace(
            bars[0], open=Decimal("1.1013"), high=Decimal("1.1015"),
            low=Decimal("1.1006"), close=Decimal("1.1010"),
        )
        last = replace(
            bars[1], open=Decimal("1.1010"), high=Decimal("1.1021"),
            low=Decimal("1.1009"), close=Decimal("1.1018"),
        )
        ctx = ClaimedStructuralContext(
            rule_id="B2", instrument_version="SIM:PAIR-1",
            origin_event_id="SIM:B2-PULLBACK-1",
            d1_trend=StructuralTrend.UP, h4_trend=StructuralTrend.UP,
            h1_zone_low=Decimal("1.1005"), h1_zone_high=Decimal("1.1011"),
            known_micro_level=Decimal("1.1015"), known_atr=Decimal("0.0020"),
            context_first_known_utc=START - timedelta(minutes=5),
        )
    elif rule == "S2":
        bars = synthetic_m15_bars(("1.1999", "1.1993"))
        first = replace(
            bars[0], open=Decimal("1.2001"), high=Decimal("1.2005"),
            low=Decimal("1.1997"), close=Decimal("1.1999"),
        )
        last = replace(
            bars[1], open=Decimal("1.1999"), high=Decimal("1.2000"),
            low=Decimal("1.1991"), close=Decimal("1.1993"),
        )
        ctx = ClaimedStructuralContext(
            rule_id="S2", instrument_version="SIM:PAIR-1",
            origin_event_id="SIM:S2-PULLBACK-1",
            d1_trend=StructuralTrend.DOWN, h4_trend=StructuralTrend.DOWN,
            h1_zone_low=Decimal("1.2000"), h1_zone_high=Decimal("1.2007"),
            known_micro_level=Decimal("1.1996"), known_atr=Decimal("0.0020"),
            context_first_known_utc=START - timedelta(minutes=5),
        )
    else:
        raise ValueError("P018_TEST_FIXTURE_ONLY_B2_OR_S2")
    params = UnapprovedResearchParameters(
        version="SIM:P018-UNAPPROVED-001",
        near_zone_atr_multiple=Decimal("0.5"),
        max_chase_atr_multiple=Decimal("0.5"),
    )
    return (first, last), ctx, params


def main() -> None:
    examples: list[dict[str, str | bool | int]] = []
    for rule, action in (("B2", CandidateAction.BUY),
                         ("S2", CandidateAction.SELL)):
        bars, ctx, params = case(rule)
        result = evaluate_unapproved_b2_s2(
            bars, ctx, params, bars[-1].first_known_utc + timedelta(seconds=1),
        )
        row = result.as_record()
        if (result.action is not action or row["stage"] != "UNVERIFIED"
                or row["may_send_confirmed_signal"] is not False
                or row["original_forex_numerical_parity"] is not False
                or row["can_trade"] is not False
                or row["provider_requests"] != 0
                or row["drive_market_cache_writes"] != 0):
            raise ValueError("P018_FALSE_PARITY_OR_UNEXPECTED_RESEARCH_OUTPUT")
        examples.append(row)
    print("MFX_A04_P18_PARAMETRIC_B2_S2_RESEARCH_PASS")
    print("MFX_A04_P18_RECEIPT " + json.dumps({
        "cases": len(examples),
        "research_actions": [r["action"] for r in examples],
        "rules": [r["rule_id"] for r in examples],
        "parameter_status": "SIMULATED_NOT_APPROVED",
        "source_verified": False,
        "original_forex_numerical_parity": False,
        "confirmed_signals": 0,
        "authorized_buy_sell_alerts": 0,
        "provider_requests": 0,
        "drive_market_cache_writes": 0,
        "can_trade": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
