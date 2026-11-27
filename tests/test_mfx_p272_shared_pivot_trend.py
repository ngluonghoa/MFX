"""P272 shared pivot trend: preserve SIM and native H4 price semantics."""
from decimal import Decimal
from unittest import TestCase

from mfx_research.shared_pivot_trend import trend_from_pivot_prices


def prices(*values: str) -> tuple[Decimal, ...]:
    return tuple(Decimal(x) for x in values)


class P272Tests(TestCase):
    def test_strict_higher_high_and_low(self):
        self.assertEqual(trend_from_pivot_prices(prices("12", "13"), prices("9", "10")), "UP")

    def test_strict_lower_high_and_low(self):
        self.assertEqual(trend_from_pivot_prices(prices("13", "12"), prices("10", "9")), "DOWN")

    def test_equal_boundary_unknown(self):
        self.assertEqual(trend_from_pivot_prices(prices("12", "12"), prices("9", "10")), "UNKNOWN")
        self.assertEqual(trend_from_pivot_prices(prices("12", "13"), prices("9", "9")), "UNKNOWN")

    def test_mixed_and_missing_unknown(self):
        self.assertEqual(trend_from_pivot_prices(prices("12", "13"), prices("10", "9")), "UNKNOWN")
        self.assertEqual(trend_from_pivot_prices(prices("12"), prices("9", "10")), "UNKNOWN")
        self.assertEqual(trend_from_pivot_prices(prices("12", "13"), ()), "UNKNOWN")

    def test_only_latest_two_confirmed_pivots(self):
        self.assertEqual(trend_from_pivot_prices(prices("30", "12", "13"),
                                                prices("20", "9", "10")), "UP")

    def test_price_reflection_swaps_direction(self):
        highs, lows = prices("12", "13"), prices("9", "10")
        anchor = Decimal("40")
        self.assertEqual(trend_from_pivot_prices(
            tuple(anchor-x for x in lows), tuple(anchor-x for x in highs)), "DOWN")
