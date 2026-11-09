"""Actual frozen-Forex 18-label taxonomy router (NO numeric zone detection).

Used for research-only presentation of independently supplied label claims.
A claim is NOT evidence a B/S numeric rule fired: Forex 03 predicates and
parameters remain unimplemented. No feed, provider, cache, broker or orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from re import fullmatch

from forex_trading.catalog import ZONES, validate_catalog
from forex_trading.model import Direction, SignalStage, ZonePurpose
from forex_trading.quotes import ensure_utc


class DisplayBucket(str, Enum):
    BUY_CANDIDATE_UNVERIFIED = "BUY_CANDIDATE_UNVERIFIED"
    SELL_CANDIDATE_UNVERIFIED = "SELL_CANDIDATE_UNVERIFIED"
    WATCH_ONLY = "WATCH_ONLY"
    EXIT_LONG_WARNING_ONLY = "EXIT_LONG_WARNING_ONLY"


@dataclass(frozen=True, slots=True)
class UnverifiedZoneClaim:
    """A typed *claimed label*, not a detected technical event."""
    pair: str
    label: str
    origin_event_id: str
    first_known_utc: datetime

    def __post_init__(self) -> None:
        for name in ("pair", "label", "origin_event_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not fullmatch(
                r"[A-Za-z0-9_.:-]{1,128}", value
            ):
                raise ValueError("P017_INVALID_CLAIM_IDENTITY:" + name)
        ensure_utc(self.first_known_utc, "first_known_utc")


@dataclass(frozen=True, slots=True)
class ZoneClassification:
    pair: str
    label: str
    origin_event_id: str
    family: str
    purpose: ZonePurpose
    bucket: DisplayBucket
    direction: Direction | None
    stage: SignalStage = SignalStage.UNVERIFIED
    numerical_predicate_implemented: bool = False
    provider_rights_verified: bool = False
    signal_confirmed: bool = False
    can_trade: bool = False
    reason: str = "CLAIM_LABEL_ONLY_NO_NUMERIC_RULE_PROOF"


@dataclass(frozen=True, slots=True)
class EvidenceGroup:
    pair: str
    origin_event_id: str
    direction: Direction
    matched_rule_ids: tuple[str, ...]
    primary_rule_id: None = None
    stage: SignalStage = SignalStage.UNVERIFIED
    can_publish_trade_signal: bool = False
    reason: str = "MULTI_LABEL_EVIDENCE_NOT_MULTIPLE_OPPORTUNITIES"


@dataclass(frozen=True, slots=True)
class ZoneRoutingReceipt:
    classified: tuple[ZoneClassification, ...]
    candidate_groups: tuple[EvidenceGroup, ...]
    catalog_label_count: int = 18
    callable_numeric_detectors: int = 0
    actual_confirmed_signals: int = 0
    may_send_buy_sell_alert: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_market_cache_writes: int = 0


_BUCKETS: dict[ZonePurpose, tuple[DisplayBucket, Direction | None]] = {
    ZonePurpose.ENTRY_LONG_CANDIDATE: (
        DisplayBucket.BUY_CANDIDATE_UNVERIFIED, Direction.LONG,
    ),
    ZonePurpose.ENTRY_SHORT_CANDIDATE: (
        DisplayBucket.SELL_CANDIDATE_UNVERIFIED, Direction.SHORT,
    ),
    ZonePurpose.WATCH_ONLY: (DisplayBucket.WATCH_ONLY, None),
    ZonePurpose.EXIT_LONG_WARNING_ONLY: (
        DisplayBucket.EXIT_LONG_WARNING_ONLY, None,
    ),
}
EXPECTED_LABELS = frozenset((
    "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8",
    "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
    "FX-S9", "FX-S10",
))
MAX_CLAIMS = 256


def route_unverified_zone_claims(
    claims: tuple[UnverifiedZoneClaim, ...],
    decision_utc: datetime,
) -> ZoneRoutingReceipt:
    """Source-native label semantics; STRICTLY no numeric detection or alert.

    One origin event shared by B5/B6/B8 or S7/S9/S10 is one *unverified*
    directional opportunity; no primary/precedence is invented. All routing
    flags remain disabled because approved numeric predicates do not exist.
    """
    ensure_utc(decision_utc, "decision_utc")
    validate_catalog(ZONES)
    lookup = {item.label: item for item in ZONES}
    if (set(lookup) != EXPECTED_LABELS or len(ZONES) != 18
            or len(lookup) != 18):
        raise ValueError("P017_FROZEN_18_LABEL_CATALOG_DRIFT")
    if not isinstance(claims, tuple) or len(claims) > MAX_CLAIMS:
        raise ValueError("P017_UNBOUNDED_OR_MUTABLE_CLAIMS")

    routed: list[ZoneClassification] = []
    group_ids: dict[tuple[str, str, Direction], list[str]] = {}
    seen: set[tuple[str, str, str]] = set()
    for claim in claims:
        if not isinstance(claim, UnverifiedZoneClaim):
            raise TypeError("P017_EXPECTS_TYPED_ZONE_CLAIM")
        if claim.first_known_utc > decision_utc:
            raise ValueError("P017_FUTURE_LABEL_CLAIM_NOT_KNOWN")
        if claim.label not in lookup:
            raise ValueError("P017_UNKNOWN_OR_UNAPPROVED_ZONE_LABEL:" + claim.label)
        identity = (claim.pair, claim.origin_event_id, claim.label)
        if identity in seen:
            raise ValueError("P017_DUPLICATE_RULE_IN_ORIGIN_EVENT")
        seen.add(identity)
        meta = lookup[claim.label]
        bucket, direction = _BUCKETS[meta.purpose]
        routed.append(ZoneClassification(
            pair=claim.pair, label=claim.label,
            origin_event_id=claim.origin_event_id,
            family=meta.family, purpose=meta.purpose,
            bucket=bucket, direction=direction,
        ))
        if direction is not None:
            key = (claim.pair, claim.origin_event_id, direction)
            group_ids.setdefault(key, []).append(claim.label)

    # Never elevate a mixed LONG/SHORT event to a trade recommendation;
    # this is evidence taxonomy only. No arbitrary rule priority is assigned.
    groups = tuple(
        EvidenceGroup(pair=pair, origin_event_id=origin,
                      direction=direction, matched_rule_ids=tuple(labels))
        for (pair, origin, direction), labels in group_ids.items()
    )
    return ZoneRoutingReceipt(
        classified=tuple(routed), candidate_groups=groups,
    )
