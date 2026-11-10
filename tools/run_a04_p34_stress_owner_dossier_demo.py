"""Cloud-only P0.34 16-case deterministic SIM replay and 36-row owner dossier."""
from __future__ import annotations

import json

from mfx_research.p034_sim_adversarial_review import (
    SCENARIOS, VERSION, run_p034_adversarial_stress,
    verify_owner_decision_dossier,
)
from tools.run_a04_p33_replay_demo import fixture


def main() -> None:
    first = fixture("B2", 0)
    later = fixture("S2", 1)
    report = run_p034_adversarial_stress(first, later)
    owner = verify_owner_decision_dossier()
    accepted = [x.scenario for x in report.cases
                if x.outcome == "ACCEPTED_RESEARCH_ONLY"]
    denied = [x.scenario for x in report.cases
              if x.outcome == "EXPECTED_REJECTION"]
    if (
        report.version != VERSION
        or tuple(x.scenario for x in report.cases) != SCENARIOS
        or len(accepted) != 3
        or len(denied) != 13
        or len(owner.rows) != 36
        or owner.pending_owner_decisions != 36
        or owner.original_numeric_rules_approved != 0
        or owner.sim_examples_not_approved != 14
        or owner.may_publish_confirmed_buy_sell
        or owner.may_release
        or report.failed_scenarios != 0
        or report.original_forex_catalog_labels != 18
        or report.approved_mfx_design_labels != 22
        or report.source_approved_numeric_entry_rules != 0
        or report.confirmed_real_signals != 0
        or report.real_market_data_calls != 0
        or report.real_drive_quote_writes != 0
        or report.alerts_published != 0
        or report.broker_orders != 0
        or report.release_ready
        or any(item.action != "NO_SIGNAL"
               or item.may_publish or item.market_orders != 0
               for item in report.cases)
    ):
        raise RuntimeError("P034_STRESS_OR_EXTERNAL_OWNER_HARD_GATES_FAILED")
    print("MFX_A04_P34_16_ADVERSARIAL_SIM_STRESS_36_OWNER_GATE_PASS")
    print("MFX_A04_P34_RECEIPT " + json.dumps({
        "replay_source": "CLOSED_SIM_OHLC_ONLY",
        "scenario_count": len(report.cases),
        "accepted_research_only": accepted,
        "correctly_rejected": denied,
        "stable_first_prefix": all(
            item.prior_prefix_unchanged for item in report.cases
        ),
        "baseline_sim_chain_tip": report.baseline_tip_sha256,
        "owner_source_decisions_pending": owner.pending_owner_decisions,
        "source_approved_numeric_rules": owner.original_numeric_rules_approved,
        "sim_examples_not_approved": owner.sim_examples_not_approved,
        "mfx_design_labels": report.approved_mfx_design_labels,
        "real_trading_signals": report.confirmed_real_signals,
        "alerts_published": report.alerts_published,
        "real_market_quote_calls": report.real_market_data_calls,
        "real_drive_quote_writes": report.real_drive_quote_writes,
        "broker_orders": report.broker_orders,
        "release_ready": report.release_ready,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
