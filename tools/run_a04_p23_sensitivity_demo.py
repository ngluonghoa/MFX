"""A04/P0.23 hosted CI-only synthetic sensitivity receipt, not production."""
from __future__ import annotations

import json
import unittest


def main() -> None:
    suite = unittest.defaultTestLoader.discover(
        "tests", pattern="test_a04_p23_sensitivity_boundaries.py",
    )
    count = suite.countTestCases()
    if count != 21:
        raise ValueError("P023_PRE_REGISTERED_TEST_COUNT_DRIFT")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise ValueError("P023_INDEPENDENT_SYNTHETIC_ORACLE_FAILED")
    print("MFX_A04_P23_CAUSAL_SENSITIVITY_PASS")
    print("MFX_A04_P23_RECEIPT " + json.dumps({
        "pre_registered_test_methods": count,
        "rules": ["B2", "S2"],
        "oracle": "INDEPENDENT_STRICT_NEIGHBOR_PIVOT_AND_EXACT_DECIMAL",
        "hypothetical_threshold_authority": "SIM_UNAPPROVED",
        "source_numeric_obligations_unapproved": 36,
        "approved_forex_entry_numeric_rules": 0,
        "verified_real_market_buy_sell": 0,
        "real_provider_requests": 0,
        "drive_market_price_cache_writes": 0,
        "broker_orders": 0,
        "release_ready": False,
        "postmain_p022_push_ci_verified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
