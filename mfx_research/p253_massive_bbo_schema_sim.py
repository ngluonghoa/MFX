"""P253: documented Massive BBO shape, synthetic fixture reader only.

Participant timestamp is exchange event time, NOT publisher first-known.
Never construct a forex_trading Quote or qualify account/data rights here.
"""
from dataclasses import dataclass, field
from decimal import Decimal
import json

VERSION = "MFX_P253_MASSIVE_BBO_SCHEMA_SIM_V1"
_FIELDS = {"ask_exchange", "ask_price", "bid_exchange", "bid_price", "participant_timestamp"}


def _pairs(rows):
    out = {}
    for k, v in rows:
        if k in out:
            raise ValueError("P253_DUPLICATE_JSON_KEY")
        out[k] = v
    return out


def _constant(_):
    raise ValueError("P253_NONFINITE_JSON")


def _price(value):
    if type(value) not in (int, Decimal):
        raise ValueError("P253_EXACT_JSON_NUMBER_REQUIRED")
    value = Decimal(value)
    if (not value.is_finite() or value <= 0
            or len(value.as_tuple().digits) > 24
            or abs(value.as_tuple().exponent) > 24):
        raise ValueError("P253_INVALID_BBO_PRICE")
    return value


@dataclass(frozen=True, slots=True, repr=False)
class SimMassiveBBOShape:
    participant_event_ns: int = field(repr=False)
    bid_exchange: int = field(repr=False)
    ask_exchange: int = field(repr=False)
    bid: Decimal = field(repr=False)
    ask: Decimal = field(repr=False)

    def public_summary(self):
        return {
            "version": VERSION, "documented_schema_shape_checked": True,
            "synthetic_only": True, "participant_event_clock_present": True,
            "publisher_first_known_verified": False,
            "account_rights_verified": False,
            "executable_broker_quote_verified": False,
            "may_construct_verified_quote": False,
            "may_replace_mid_cache": False,
            "action": "NO_SIGNAL", "may_publish_buy_sell": False,
            "may_trade": False, "broker_orders": 0,
        }


def parse_sim_massive_bbo(text: str) -> SimMassiveBBOShape:
    if type(text) is not str or not 0 < len(text) <= 4096:
        raise ValueError("P253_BOUNDED_SIM_JSON_REQUIRED")
    data = json.loads(text, parse_float=Decimal, parse_constant=_constant,
                      object_pairs_hook=_pairs)
    if (type(data) is not dict or set(data) != {"schema", "row"}
            or data["schema"] != VERSION or type(data["row"]) is not dict
            or set(data["row"]) != _FIELDS):
        raise ValueError("P253_EXACT_SIM_ENVELOPE_REQUIRED")
    row = data["row"]
    ns = row["participant_timestamp"]
    if type(ns) is not int or not 0 < ns <= 2**63-1:
        raise ValueError("P253_EXACT_PARTICIPANT_NANOSECONDS_REQUIRED")
    venues = (row["bid_exchange"], row["ask_exchange"])
    if any(type(v) is not int or not 0 <= v <= 2**31-1 for v in venues):
        raise ValueError("P253_EXACT_VENUE_IDS_REQUIRED")
    bid, ask = _price(row["bid_price"]), _price(row["ask_price"])
    if bid > ask:
        raise ValueError("P253_CROSSED_BBO")
    return SimMassiveBBOShape(ns, venues[0], venues[1], bid, ask)
