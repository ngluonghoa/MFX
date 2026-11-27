"""P253 tests use invented synthetic quote values, not API data."""
from decimal import Decimal as D
from unittest import TestCase
import json

from mfx_research.p253_massive_bbo_schema_sim import VERSION, parse_sim_massive_bbo


def fixture(**kw):
    row = dict(bid_exchange=48, ask_exchange=48, bid_price=1.2,
               ask_price=1.3, participant_timestamp=1700000000000000001)
    row.update(kw)
    return json.dumps(dict(schema=VERSION, row=row))


class P253Tests(TestCase):
    def test_preserve_exact_decimal_and_nanoseconds(self):
        text = fixture().replace("1.2,", "1.200000000000000001,")
        r = parse_sim_massive_bbo(text)
        self.assertEqual(r.bid, D("1.200000000000000001"))
        self.assertEqual(r.participant_event_ns, 1700000000000000001)

    def test_crossed_price_rejected(self):
        with self.assertRaisesRegex(ValueError, "CROSSED"):
            parse_sim_massive_bbo(fixture(bid_price=1.4))

    def test_invalid_timestamp_venue_or_price(self):
        for kw in (dict(participant_timestamp=True), dict(participant_timestamp=0),
                   dict(bid_exchange=True), dict(ask_exchange=-1),
                   dict(ask_price="1.3"), dict(bid_price=-1),
                   dict(bid_price=float("nan"))):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                parse_sim_massive_bbo(fixture(**kw))

    def test_unknown_first_known_field_not_invented(self):
        with self.assertRaisesRegex(ValueError, "ENVELOPE"):
            parse_sim_massive_bbo(fixture(first_known_utc="invented"))

    def test_real_response_envelope_not_accepted(self):
        with self.assertRaises(ValueError):
            parse_sim_massive_bbo(json.dumps({"status":"OK", "results":[]}))

    def test_duplicate_field_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            parse_sim_massive_bbo(fixture().replace('"bid_exchange": 48,',
                '"bid_exchange": 48, "bid_exchange": 48,'))

    def test_no_authority_or_raw_values_in_public_summary(self):
        r = parse_sim_massive_bbo(fixture())
        d = r.public_summary()
        self.assertEqual(d["action"], "NO_SIGNAL")
        for k in ("publisher_first_known_verified", "account_rights_verified",
                  "may_construct_verified_quote", "may_replace_mid_cache",
                  "may_publish_buy_sell", "may_trade"):
            self.assertFalse(d[k])
        self.assertNotIn("1700000000000000001", repr(r))
        self.assertNotIn("bid_price", str(d))
