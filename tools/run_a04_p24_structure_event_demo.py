"""Hosted A04/P0.24 SIM-only causal structural and replay gates (no IO)."""
from __future__ import annotations

import json
import unittest

from mfx_research.p024_structure_event_gate import (
    ResearchEventStatus, StructureStatus,
)
from tests.test_a04_p24_structure_event_gate import gate, structure


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
        scan = structure(rule)
        research_event = gate(rule)
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
