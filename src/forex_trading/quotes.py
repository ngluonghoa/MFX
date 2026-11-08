"""Strict causal, quote-side indicative prices. Absolutely no fills or orders."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from .model import ActionIntent


class PriceSide(str, Enum):
    BID = "BID"
    ASK = "ASK"


class QuoteQuality(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"


def ensure_utc(value: datetime, field: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be an aware UTC datetime")


@dataclass(frozen=True, slots=True)
class Quote:
    provider: str
    source_revision: str
    event_time_utc: datetime
    first_known_utc: datetime
    bid: Decimal
    ask: Decimal
    quality: QuoteQuality

    def __post_init__(self) -> None:
        ensure_utc(self.event_time_utc, "event_time_utc")
        ensure_utc(self.first_known_utc, "first_known_utc")
        if self.first_known_utc < self.event_time_utc:
            raise ValueError("first-known precedes event")
        if not self.provider or not self.source_revision:
            raise ValueError("provider and immutable revision are mandatory")
        if not isinstance(self.quality, QuoteQuality):
            raise TypeError("Explicit quote quality required")
        if not isinstance(self.bid, Decimal) or not isinstance(self.ask, Decimal):
            raise TypeError("Quote-side numeric values must be Decimal")
        if not self.bid.is_finite() or not self.ask.is_finite():
            raise ValueError("nonfinite bid/ask")
        if self.bid <= 0 or self.ask < self.bid:
            raise ValueError("require positive non-crossed BID <= ASK")


@dataclass(frozen=True, slots=True)
class IndicativePrice:
    side: PriceSide
    value: Decimal
    source_revision: str
    first_known_utc: datetime


_PRICE_SIDE: dict[ActionIntent, PriceSide] = {
    ActionIntent.ENTRY_LONG: PriceSide.ASK,
    ActionIntent.EXIT_LONG: PriceSide.BID,
    ActionIntent.ENTRY_SHORT: PriceSide.BID,
    ActionIntent.EXIT_SHORT: PriceSide.ASK,
}


def indicative_price(
    quote: Quote, intent: ActionIntent, decision_utc: datetime, max_age: timedelta
) -> IndicativePrice:
    """Fail-closed reference price. Does NOT confirm eligibility, fill, or a real signal."""
    ensure_utc(decision_utc, "decision_utc")
    if not isinstance(intent, ActionIntent):
        raise TypeError("Unknown action intent")
    if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
        raise ValueError("Explicit positive quote age policy required")
    if quote.quality is not QuoteQuality.VERIFIED:
        raise ValueError("unverified quote source")
    if quote.first_known_utc > decision_utc:
        raise ValueError("source was not yet known at decision time")
    if decision_utc - quote.first_known_utc > max_age:
        raise ValueError("source is stale under explicit quote age policy")
    side = _PRICE_SIDE[intent]
    return IndicativePrice(
        side, quote.bid if side is PriceSide.BID else quote.ask,
        quote.source_revision, quote.first_known_utc,
    )
