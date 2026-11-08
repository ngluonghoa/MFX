"""A03/P0.2 independent synthetic oracles for mutation adequacy, not trading.

These checks intentionally do NOT compute their expected EMA values through
ema_full / ema_recompute, so an equally wrong pair of implementations fails.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from forex_trading.cache_indicators import ema_full
from forex_trading.cache_core import reconcile_closed_delta
from test_a03_seeded_properties import _snapshot
from forex_trading.model import ActionIntent
from forex_trading.quotes import PriceSide, Quote, QuoteQuality, indicative_price


class A03IndependentMutationOracles(unittest.TestCase):
    def test_quote_exact_first_known_boundary_is_eligible(self):
        at = datetime(2026, 11, 8, 5, 0, tzinfo=timezone.utc)
        quote = Quote("TEST_ONLY", "SYNTH_A03", at - timedelta(minutes=1), at,
                      Decimal("1.12000"), Decimal("1.12020"),
                      QuoteQuality.VERIFIED)
        result = indicative_price(
            quote, ActionIntent.ENTRY_LONG, at, timedelta(seconds=1)
        )
        self.assertEqual(result.value, Decimal("1.12020"))
        self.assertEqual(result.side, PriceSide.ASK)
        self.assertEqual(result.first_known_utc, at)

    def test_ema_closed_form_weighted_three_point_oracle(self):
        # period=3 -> alpha=2/(3+1)=0.5; 1 -> 2 -> 3.5 exactly.
        # Expected constants are independent of EMA implementation.
        values = (Decimal("1"), Decimal("3"), Decimal("5"))
        self.assertEqual(
            ema_full(values, 3),
            (Decimal("1"), Decimal("2"), Decimal("3.5")),
        )

    def test_same_revision_rejected_even_if_known_later(self):
        snapshot = _snapshot(2)
        old = snapshot.closed_bars[-1]
        incoming = replace(old, first_known_utc=snapshot.checked_at_utc +
                           timedelta(seconds=1), close=Decimal("1.1300"))
        with self.assertRaisesRegex(ValueError, "OLDER_OR_SAME_REVISION_CONFLICT"):
            reconcile_closed_delta(
                snapshot, (incoming,),
                snapshot.checked_at_utc + timedelta(seconds=2),
                new_source_head_claim="HEAD-SYNTH-V2",
            )

    def test_higher_revision_rejected_if_not_known_later(self):
        snapshot = _snapshot(2)
        old = snapshot.closed_bars[-1]
        incoming = replace(
            old, revision_number=2, close=Decimal("1.1300"),
            observation=replace(old.observation, revision_id="REV-2"),
        )
        with self.assertRaisesRegex(ValueError, "OLDER_OR_SAME_REVISION_CONFLICT"):
            reconcile_closed_delta(
                snapshot, (incoming,),
                snapshot.checked_at_utc + timedelta(seconds=1),
                new_source_head_claim="HEAD-SYNTH-V2",
            )

    def test_ema_calculation_not_trivial_raw_prices(self):
        values = (Decimal("1"), Decimal("3"), Decimal("5"))
        computed = ema_full(values, 3)
        self.assertNotEqual(computed, values)
        self.assertGreater(computed[1], values[0])
        self.assertLess(computed[1], values[1])


if __name__ == "__main__":
    unittest.main()
