import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from forex_trading import ActionIntent
from forex_trading.quotes import PriceSide, Quote, QuoteQuality, indicative_price


T = datetime(2026, 11, 7, tzinfo=timezone.utc)
AGE = timedelta(seconds=10)


def quote(**changes):
    values = dict(provider="synthetic", source_revision="synthetic-rev-1",
                  event_time_utc=T, first_known_utc=T + timedelta(seconds=1),
                  bid=Decimal("1.20000"), ask=Decimal("1.20025"),
                  quality=QuoteQuality.VERIFIED)
    values.update(changes)
    return Quote(**values)


class QuoteTests(unittest.TestCase):
    def test_all_four_quote_sides(self):
        cases = {
            ActionIntent.ENTRY_LONG: (PriceSide.ASK, Decimal("1.20025")),
            ActionIntent.EXIT_LONG: (PriceSide.BID, Decimal("1.20000")),
            ActionIntent.ENTRY_SHORT: (PriceSide.BID, Decimal("1.20000")),
            ActionIntent.EXIT_SHORT: (PriceSide.ASK, Decimal("1.20025")),
        }
        for action, expected in cases.items():
            with self.subTest(action=action):
                got = indicative_price(quote(), action, T + timedelta(seconds=2), AGE)
                self.assertEqual((got.side, got.value), expected)

    def test_no_lookahead(self):
        with self.assertRaisesRegex(ValueError, "not yet known"):
            indicative_price(quote(), ActionIntent.ENTRY_LONG, T, AGE)

    def test_stale_data_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            indicative_price(quote(), ActionIntent.ENTRY_LONG, T + timedelta(minutes=5), AGE)

    def test_unverified_data_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unverified"):
            indicative_price(quote(quality=QuoteQuality.UNVERIFIED),
                             ActionIntent.ENTRY_LONG, T + timedelta(seconds=2), AGE)

    def test_blocked_data_fails_closed(self):
        with self.assertRaises(ValueError):
            indicative_price(quote(quality=QuoteQuality.BLOCKED),
                             ActionIntent.ENTRY_SHORT, T + timedelta(seconds=2), AGE)

    def test_bad_age_policy(self):
        with self.assertRaises(ValueError):
            indicative_price(quote(), ActionIntent.ENTRY_LONG, T + timedelta(seconds=2),
                             timedelta(0))

    def test_crossed_quote_rejected(self):
        with self.assertRaises(ValueError):
            quote(bid=Decimal("1.3"), ask=Decimal("1.2"))

    def test_nan_quote_rejected(self):
        with self.assertRaises(ValueError):
            quote(bid=Decimal("NaN"))

    def test_zero_quote_rejected(self):
        with self.assertRaises(ValueError):
            quote(bid=Decimal("0"))

    def test_float_quote_rejected(self):
        with self.assertRaises(TypeError):
            quote(bid=1.20000)

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            quote(event_time_utc=datetime(2026, 11, 7))

    def test_first_known_before_event_rejected(self):
        with self.assertRaises(ValueError):
            quote(first_known_utc=T - timedelta(seconds=1))

    def test_empty_revision_rejected(self):
        with self.assertRaises(ValueError):
            quote(source_revision="")

    def test_unknown_intent_rejected(self):
        with self.assertRaises(TypeError):
            indicative_price(quote(), "BUY", T + timedelta(seconds=2), AGE)
