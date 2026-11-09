"""Fail-closed bounded-corpus controls for P0.5b; no live data."""
from __future__ import annotations

import unittest

from tools.run_a03_coverage_feedback import (
    MAX_CASES, MAX_DEPTH, MUTATIONS, _base_payload, _canonical, _mutate,
)


class P05FeedbackGrammarGuards(unittest.TestCase):
    def test_bound_is_small_and_not_runtime_authority(self):
        self.assertEqual(MAX_CASES, 80)
        self.assertEqual(MAX_DEPTH, 2)
        self.assertEqual(len(set(MUTATIONS)), len(MUTATIONS))
        self.assertGreaterEqual(len(MUTATIONS), 15)

    def test_seed_is_synthetic_wire_fixture_without_credentials(self):
        seed = _base_payload()
        text = _canonical(seed)
        self.assertIn("EUR_USD", text)
        for bad in ("api_key", "access_token", "://", "account_id"):
            self.assertNotIn(bad, text)
        self.assertEqual(len(seed["candles"]), 1)

    def test_repeated_mutations_are_stable_and_not_in_place(self):
        seed = _base_payload()
        before = _canonical(seed)
        a = _mutate(seed, "volume_boolean")
        b = _mutate(seed, "volume_boolean")
        self.assertIsNotNone(a)
        self.assertEqual(a, b)
        self.assertEqual(_canonical(seed), before)
        self.assertEqual(a["candles"][0]["volume"], False)

    def test_unknown_mutation_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "P05_UNKNOWN_MUTATION"):
            _mutate(_base_payload(), "call_real_provider")
        empty = _mutate(_base_payload(), "empty_page")
        self.assertIsNotNone(empty)
        self.assertIsNone(_mutate(empty, "bid_price_zero"))

    def test_mutation_categories_are_independent_of_source_rights(self):
        seed = _base_payload()
        for token in ("wrong_instrument", "wrong_granularity",
                      "provisional_row", "bid_missing"):
            candidate = _mutate(seed, token)
            self.assertIsNotNone(candidate)
            self.assertNotEqual(_canonical(candidate), _canonical(seed))


if __name__ == "__main__":
    unittest.main()
