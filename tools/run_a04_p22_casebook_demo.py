"""Cloud CI-only P0.22 synthetic policy proposal and casebook receipt."""
from __future__ import annotations

import json
from mfx_research.p022_policy_casebook import run_truth_table


def main() -> None:
    receipt = run_truth_table()
    if (receipt["passed_cases"] != 14
            or receipt["source_rules_approved"] != 0
            or receipt["unapproved_numeric_obligations"] != 36
            or receipt["may_publish_verified_buy_sell"]
            or receipt["real_feed_calls"]
            or receipt["real_drive_market_cache_writes"]
            or receipt["release_ready"]):
        raise ValueError("P022_RESEARCH_DENIAL_GATE_FAILED")
    print("MFX_A04_P22_SIM_POLICY_CASEBOOK_PASS")
    print("MFX_A04_P22_RECEIPT " + json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
