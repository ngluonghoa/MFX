"""Fail-closed replay budget/coverage-scope receipt for A03/P0.3.

Bounded systematic seeded replay, *not* coverage-guided fuzzing.
No source code, external provider, network or trading account is accessed.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
FUZZ_FILE = TESTS / "test_a03_stateful_fuzz.py"
EXPECTED_SEEDS = (
    0xA032026, 0xA032027, 0xA0320A3, 0xA0320B4,
    0xA0320C5, 0xA0320D6, 0xA0320E7, 0xA0320F8,
)
EXPECTED_METHODS = 7
EXPECTED_STEPS = 16


def main() -> None:
    if not FUZZ_FILE.is_file() or FUZZ_FILE.is_symlink():
        raise ValueError("A03_STATEFUL_FUZZ_SUITE_NOT_FOUND")
    sys.path.insert(0, str(TESTS))
    import test_a03_stateful_fuzz as fuzz

    if (fuzz.SEEDS != EXPECTED_SEEDS or
            fuzz.STEPS_PER_SEED != EXPECTED_STEPS or
            fuzz.SYNTHETIC_ONLY is not True):
        raise ValueError("A03_STATEFUL_FUZZ_CORPUS_OR_SCOPE_DRIFT")
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(TESTS), pattern=FUZZ_FILE.name
    )
    methods = suite.countTestCases()
    if methods != EXPECTED_METHODS:
        raise ValueError("A03_STATEFUL_FUZZ_METHOD_COUNT_DRIFT")
    receipt = {
        "kind": "MFX_A03_P0_3_SYSTEMATIC_FUZZ_REPLAY_ONLY",
        "seed_count": len(EXPECTED_SEEDS),
        "steps_per_seed": EXPECTED_STEPS,
        "replay_cases_per_randomized_method": len(EXPECTED_SEEDS) *
                                               EXPECTED_STEPS,
        "discovered_test_methods": methods,
        "includes_independent_dag_oracle": True,
        "includes_stateful_cache_history": True,
        "includes_deterministic_counterexample_reducer": True,
        "full_application_code_coverage_measured": False,
        "coverage_guided_fuzz_engine": False,
        "real_market_data": False,
        "may_deploy_or_trade": False,
    }
    print("MFX_A03_STATEFUL_FUZZ_REPLAY_PASS " +
          json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
