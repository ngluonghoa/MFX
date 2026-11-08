"""Enforce A03/P0.1 deterministic synthetic property-suite presence in CI.

Test methods are discovered and actually executed by unittest in the main
Python 3.11 and 3.12 CI jobs. This additional inventory check fails closed
on accidental exclusion/removal of required regression properties.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1] / "tests" / "test_a03_seeded_properties.py"
EXPECTED_TEST_METHODS = 24
EXPECTED_SEED = "0xA032026"


def main() -> None:
    if not SUITE.is_file() or SUITE.is_symlink():
        raise ValueError("A03_PROPERTY_SUITE_MISSING")
    source = SUITE.read_text(encoding="utf-8")
    if EXPECTED_SEED not in source or "RANGE = 96" not in source:
        raise ValueError("A03_SEED_OR_EXPLORATION_RANGE_CHANGED")
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(SUITE.parent), pattern=SUITE.name,
    )
    count = suite.countTestCases()
    if count != EXPECTED_TEST_METHODS:
        raise ValueError(f"A03_PROPERTY_TEST_COUNT_DRIFT:{count}")
    print("MFX_A03_SEEDED_PROPERTY_SUITE_PRESENT " + json.dumps({
        "scope": "DETERMINISTIC_SYNTHETIC_READ_ONLY",
        "test_methods_discovered": count,
        "seed": EXPECTED_SEED,
        "draws_per_randomized_method": 96,
        "no_real_provider_data": True,
        "tp_sl_numeric_fill_model_tested": False,
        "mutation_score_measured": False,
        "may_deploy_or_trade": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
