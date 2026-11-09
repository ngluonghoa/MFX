"""Hosted A04/P0.24 SIM-only causal structural and replay gates (no IO)."""
from __future__ import annotations

from datetime import timedelta
import json
import unittest

from mfx_research.confirmed_swings import derive_swing_b2_s2_research
from mfx_research.p024_structure_event_gate import (
    ResearchEventStatus, SimEventKey, SimEventLedger, SimStructurePolicy,
    StructureStatus, buffer_sim_event, derive_sim_structure,
)
from tools.run_a04_p19_causal_context_demo import case_from_closed_bars
from tools.run_a04_p20_confirmed_swing_demo import case_confirmed


def main() -> None:
    tests = unittest.defaultTestLoader.discover(
        "tests", pattern="test_a04_p24_structure_event_gate.py",
    )
    count = tests.countTestCases()
    if count != 20:
        raise ValueError("P024_PRE_REGISTERED_GROUPED_METHOD_COUNT_DRIFT")
    result = unittest.TextTestRunner(verbosity=1).run(tests)
    if not result.wasSuccessful():
        raise ValueError("P024_CAUSAL_STRUCTURE_EVENT_ORACLE_FAILED")
    actions: list[str] = []
    for rule in ("B2", "S2"):
        bars, swing_policy = case_confirmed(rule)
        _, zone_policy, trigger_policy = case_from_closed_bars(rule)
        decision = bars.trigger_m15[-1].first_known_utc + timedelta(seconds=1)
        scan = derive_sim_structure(
            rule, bars, swing_policy,
            SimStructurePolicy("SIM:P024-DEMO"), decision,
        )
        triggered = derive_swing_b2_s2_research(
            rule, bars, swing_policy, zone_policy, trigger_policy,
            decision, origin_event_id="SIM:P024-DEMO-" + rule,
        )
        signal = triggered.signal
        key = SimEventKey(
            instrument_version=signal.instrument_version,
            rule_id=rule, origin_event_id=signal.origin_event_id,
            policy_version=signal.parameter_version,
        )
        research_event = buffer_sim_event(
            scan, signal, key, SimEventLedger("SIM:P024-DEMO"),
            decision, ttl_seconds=600,
        )
        if (scan.status is not StructureStatus.INTACT
                or research_event.status is not ResearchEventStatus.BUFFERED
                or scan.may_send_confirmed_signal
                or research_event.may_send_confirmed_signal
                or research_event.source_numeric_approved
                or research_event.can_trade
                or scan.provider_requests or scan.drive_market_cache_writes
                or research_event.provider_requests
                or research_event.drive_market_cache_writes):
            raise ValueError("P024_FORGED_PRODUCTION_STATUS")
        actions.append(research_event.status.value)
    print("MFX_A04_P24_SIM_STRUCTURE_EVENT_SAFETY_PASS")
    print("MFX_A04_P24_RECEIPT " + json.dumps({
        "pre_registered_grouped_methods": count,
        "rules": ["B2", "S2"],
        "research_event_results": actions,
        "structural_policy": "SIM:CONFIRMED_PIVOT_ANCHOR_NOT_FOREX_APPROVED",
        "event_ledger": "EPHEMERAL_IMMUTABLE_PURE_NOT_PERSISTED",
        "source_numeric_approvals": 0,
        "b2_s2_numeric_obligations_unapproved": 36,
        "forex_entry_numeric_approvals": 0,
        "verified_real_market_signals": 0,
        "broker_orders": 0,
        "real_market_data_calls": 0,
        "drive_real_quote_cache_writes": 0,
        "release_ready": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
