"""Cloud GitHub-only P044: real computed SIM B3/S4 patterns; no user alert."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import json

from forex_trading.market_data import Timeframe
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p044_sim_range_rejection import (
    SimRangeResearchBars, SimRangeResearchParameters,
    compute_sim_b3_s4_range_rejection,
)
from tools.run_a04_p19_causal_context_demo import _make_series
from tools.run_a04_p16_signal_demo import START


def _fixture(rule: str) -> tuple[SimRangeResearchBars, SimRangeResearchParameters]:
    # These are literally invented prices, never a vendor/broker feed.
    hourly = _make_series(Timeframe.H1, (
        ("1.105", "1.110", "1.100", "1.105"),
        ("1.105", "1.110", "1.100", "1.105"),
        ("1.105", "1.110", "1.100", "1.105"),
        ("1.105", "1.110", "1.100", "1.105"),
        ("1.105", "1.110", "1.100", "1.105"),
    ))
    values = (
        (("1.100", "1.101", "1.098", "1.099"),
         ("1.099", "1.105", "1.0988", "1.103"))
        if rule == "B3" else
        (("1.110", "1.112", "1.109", "1.111"),
         ("1.111", "1.112", "1.106", "1.107"))
    )
    initial = _make_series(Timeframe.M15, values)
    shift = timedelta(minutes=30)
    trigger = tuple(
        replace(bar,
                key=replace(
                    bar.key,
                    bar_start_utc=bar.key.bar_start_utc+shift,
                    bar_end_utc=bar.key.bar_end_utc+shift,
                ),
                observation=replace(
                    bar.observation,
                    first_known_utc=bar.observation.first_known_utc+shift,
                    retrieved_at_utc=bar.observation.retrieved_at_utc+shift,
                ),
                first_known_utc=bar.first_known_utc+shift,
                )
        for bar in initial
    )
    return (
        SimRangeResearchBars(hourly=hourly, trigger_m15=(trigger[0], trigger[1])),
        SimRangeResearchParameters(
            version="SIM:P044_EXPERIMENT_ONLY",
            h1_lookback=4, min_edge_touches=2,
            touch_tolerance_true_range_multiple=Decimal("0.1"),
            max_sweep_true_range_multiple=Decimal("0.5"),
            reclaim_margin_true_range_multiple=Decimal("0.1"),
        ),
    )


def main() -> None:
    evidence: list[dict[str, object]] = []
    for rule, expected in (
        ("B3", CandidateAction.BUY),
        ("S4", CandidateAction.SELL),
    ):
        bars, params = _fixture(rule)
        decision = bars.trigger_m15[-1].first_known_utc + timedelta(seconds=1)
        result = compute_sim_b3_s4_range_rejection(rule, bars, params, decision)
        if (result.experimental_pattern is not expected
                or result.action != "NO_SIGNAL"
                or result.stage.value != "UNVERIFIED"
                or len(result.classified_output.events) != 1
                or result.classified_output.events[0].matched_labels != (rule,)
                or result.source_numeric_approved
                or result.original_forex_numeric_parity
                or result.original_h4_range_validation_proven
                or result.actual_confirmed_signals
                or result.real_provider_calls or result.drive_real_quote_cache_writes
                or result.broker_orders or result.publish_alerts
                or result.release_ready):
            raise RuntimeError("P044_COMPUTED_SIM_PATTERN_OR_NO_SIGNAL_GATE_FAILED")
        evidence.append({
            "pilot": rule,
            "computed_experimental_pattern": result.experimental_pattern.value,
            "research_only_origin": result.origin_event_id,
            "research_reason": result.research_reason,
            "routed_label": result.classified_output.events[0].matched_labels[0],
            "outbound_action": result.action,
        })
    print("MFX_A04_P44_CAUSAL_COMPUTED_SIM_B3_S4_NO_SIGNAL_PASS")
    print("MFX_A04_P44_RECEIPT " + json.dumps({
        "stage": "UNVERIFIED",
        "computed_patterns": evidence,
        "source_numeric_approval": 0,
        "remaining_b2_s2_original_numeric_owner_decisions": 36,
        "frozen_original_forex_catalog": 18,
        "approved_design_labels": 22,
        "actual_h4_range_confirmation": False,
        "actual_licensed_market_data": False,
        "real_user_alerts": 0,
        "broker_orders": 0,
        "release_ready": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
