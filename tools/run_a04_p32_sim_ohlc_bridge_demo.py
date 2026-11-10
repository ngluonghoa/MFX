"""Cloud-only P0.32: computed SIM OHLC B2/S2 pilot -> NO_SIGNAL 22-zone router."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json

from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p032_synthetic_ohlc_bridge import (
    compute_and_route_sim_b2_s2,
)
from tools.run_a04_p19_causal_context_demo import case_from_closed_bars


def main() -> None:
    evidence: list[dict[str, object]] = []
    for rule, expected in (
        ("B2", CandidateAction.BUY),
        ("S2", CandidateAction.SELL),
    ):
        bars, derivation, parameters = case_from_closed_bars(rule)
        decision = bars.trigger_m15[-1].first_known_utc + timedelta(seconds=1)
        result = compute_and_route_sim_b2_s2(
            rule, bars, derivation, parameters, decision,
        )
        events = result.classified_output.events
        if (result.experimental_numeric_action is not expected
                or len(result.classified_output.classified) != 1
                or len(events) != 1
                or events[0].matched_labels != (rule,)
                or not events[0].research_opportunity_id
                or result.research_phase.value != "UNVERIFIED"
                or result.action != "NO_SIGNAL"
                or result.may_send_buy_sell_or_exit_alert
                or result.pattern_source_numeric_approved
                or result.actual_buy_sell_signals != 0
                or result.real_provider_calls != 0
                or result.real_drive_market_cache_writes != 0
                or result.broker_orders != 0
                or result.release_ready):
            raise RuntimeError("P032_SIM_CALC_OR_SAFE_ROUTING_NOT_PROVEN")
        evidence.append({
            "pilot": rule,
            "experimental_pattern": result.experimental_numeric_action.value,
            "routed_labels": [x.label for x in result.classified_output.classified],
            "router_external_action": events[0].action,
            "source_parity_approved": result.pattern_source_numeric_approved,
            "research_fingerprint": result.research_input_sha256,
        })
    bars, derivation, params = case_from_closed_bars("B2")
    previous, last = bars.trigger_m15
    no_pattern = compute_and_route_sim_b2_s2(
        "B2", replace(bars, trigger_m15=(previous,
              replace(last, close=previous.close))),
        derivation, params, last.first_known_utc + timedelta(seconds=1),
    )
    if (no_pattern.experimental_numeric_action is not CandidateAction.NO_SIGNAL
            or len(no_pattern.classified_output.events) != 0
            or no_pattern.action != "NO_SIGNAL"):
        raise RuntimeError("P032_NO_PATTERN_MUST_NOT_CREATE_FAKE_LABEL")
    print("MFX_A04_P32_SIM_CLOSED_OHLC_TO_22_ZONE_ROUTER_PASS")
    print("MFX_A04_P32_RECEIPT " + json.dumps({
        "evidence": evidence,
        "fixture_context": ["D1", "H4", "H1", "M15"],
        "p032_computed_pilots": ["B2", "S2"],
        "source_numeric_approvals": 0,
        "original_b2_s2_obligations_pending": 36,
        "all_22_price_detectors_implemented": False,
        "real_market_confirmed_alerts": 0,
        "vendor_calls": 0,
        "real_drive_quote_cache_writes": 0,
        "broker_orders": 0,
        "release_ready": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
