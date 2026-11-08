"""P2.2-B: synthetic-only price-content vs full claimed-source provenance.

Additive read-only contracts. They DO NOT change the existing CandleSnapshot
fingerprint, cache store, scan runner, source-rights gates or indicator runtime.
A lineage digest is not a signed receipt, licence, trusted availability witness
or distributed anti-rollback protection. Nothing here performs IO or trades.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from json import dumps

from .cache_core import CandleSnapshot
from .market_data import MarketBar
from .quotes import ensure_utc
from .source_stream_binding import (
    SourceStreamBinding, qualify_snapshot_binding,
)


class RightsEvent(str, Enum):
    """Caller-claimed rights state. There is deliberately no ALLOWED state."""

    UNVERIFIED = "UNVERIFIED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    DENIED = "DENIED"


class EvidenceChange(str, Enum):
    BLOCKED = "BLOCKED"
    UNCHANGED = "UNCHANGED"
    LINEAGE_ONLY = "LINEAGE_ONLY"
    CAUSAL_REPLAY_REVIEW = "CAUSAL_REPLAY_REVIEW"
    PRICE_DIRTY = "PRICE_DIRTY"


def _sha(payload: object) -> str:
    return sha256(dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _price(value: Decimal) -> str:
    # Same numeric value with differing provider decimal scale is the same
    # indicator input, e.g. 1.14000 and 1.14.
    return format(value.normalize(), "f")


def _price_row(bar: MarketBar) -> tuple[str, ...]:
    key = bar.key
    return (
        key.bar_start_utc.isoformat(), key.bar_end_utc.isoformat(),
        key.instrument_version, key.timeframe.value, key.side.value,
        key.calendar_version, key.aggregation_version,
        _price(bar.open), _price(bar.high), _price(bar.low), _price(bar.close),
        bar.lifecycle.value, bar.coverage.value, bar.quality.value,
    )


def price_content_digest(snapshot: CandleSnapshot) -> str:
    """Price/quality/period content; omits revision and retrieval metadata."""
    if not isinstance(snapshot, CandleSnapshot):
        raise TypeError("TYPED_CANDLE_SNAPSHOT_REQUIRED")
    return _sha((
        "FX_PRICE_CONTENT_V1", snapshot.partition.fingerprint,
        tuple(_price_row(bar) for bar in snapshot.closed_bars),
    ))


def _provenance_row(bar: MarketBar) -> tuple[object, ...]:
    o = bar.observation
    return (
        *(_price_row(bar)),
        bar.revision_number, bar.first_known_utc.isoformat(),
        o.provider_id, o.stream_id, o.endpoint, o.revision_id, o.raw_sha256,
        o.first_known_utc.isoformat(), o.retrieved_at_utc.isoformat(),
        o.source_timezone_policy, o.license_scope_claim,
    )


def provenance_digest(snapshot: CandleSnapshot) -> str:
    """Full *caller-declared* observation metadata and price content."""
    if not isinstance(snapshot, CandleSnapshot):
        raise TypeError("TYPED_CANDLE_SNAPSHOT_REQUIRED")
    return _sha((
        "FX_DECLARED_PROVENANCE_V1", snapshot.partition.fingerprint,
        snapshot.checked_at_utc.isoformat(), snapshot.source_head_claim,
        tuple(_provenance_row(bar) for bar in snapshot.closed_bars),
    ))


@dataclass(frozen=True, slots=True)
class SyntheticEvidenceReview:
    change: EvidenceChange
    reason: str
    old_price_digest: str
    new_price_digest: str
    old_provenance_digest: str
    new_provenance_digest: str
    first_price_dirty_utc: datetime | None
    first_causal_review_utc: datetime | None
    needs_indicator_recompute: bool
    needs_causal_replay_review: bool
    propose_new_price_chunk: bool
    propose_lineage_event: bool
    rights_event: RightsEvent
    reviewed_as_of_utc: datetime
    # These are NEVER permissions to use real licensed data.
    vendor_rights_verified: bool = False
    may_reuse_real_cached_data: bool = False
    may_persist_real_data: bool = False
    may_trade: bool = False


def compare_synthetic_evidence(
    previous: CandleSnapshot,
    incoming: CandleSnapshot,
    binding: SourceStreamBinding | None,
    decision_utc: datetime,
    *,
    rights_event: RightsEvent = RightsEvent.UNVERIFIED,
) -> SyntheticEvidenceReview:
    """Compare qualified synthetic snapshots WITHOUT mutating any cache.

    A new price is dirty only after an explicit later *claimed* revision;
    corrections to a prior event's first-known time need a separate causal
    replay review even when its OHLC does not change.
    Metadata-only changes propose a lineage event, not a price chunk rewrite.
    """
    if not isinstance(previous, CandleSnapshot) or not isinstance(incoming, CandleSnapshot):
        raise TypeError("TYPED_CANDLE_SNAPSHOTS_REQUIRED")
    if binding is not None and not isinstance(binding, SourceStreamBinding):
        raise TypeError("TYPED_SOURCE_STREAM_BINDING_REQUIRED")
    ensure_utc(decision_utc, "decision_utc")
    if not isinstance(rights_event, RightsEvent):
        raise TypeError("TYPED_RIGHTS_EVENT_REQUIRED")

    old_price = price_content_digest(previous)
    new_price = price_content_digest(incoming)
    old_lineage = provenance_digest(previous)
    new_lineage = provenance_digest(incoming)

    def report(
        change: EvidenceChange, reason: str,
        *, price_dirty_at: datetime | None = None,
        causal_review_at: datetime | None = None,
    ) -> SyntheticEvidenceReview:
        blocked = change is EvidenceChange.BLOCKED
        changed = old_lineage != new_lineage
        return SyntheticEvidenceReview(
            change, reason, old_price, new_price, old_lineage, new_lineage,
            price_dirty_at, causal_review_at,
            change is EvidenceChange.PRICE_DIRTY,
            change in (EvidenceChange.CAUSAL_REPLAY_REVIEW, EvidenceChange.PRICE_DIRTY),
            change is EvidenceChange.PRICE_DIRTY,
            (changed and not blocked) or rights_event is not RightsEvent.UNVERIFIED,
            rights_event, decision_utc,
        )

    # Revocation is a distinct fail-closed control-plane event, not a
    # convenient "metadata-only" cache refresh. A separate vetted workflow
    # must decide retention, purge, quarantine and access revocation.
    if rights_event in (RightsEvent.REVOKED, RightsEvent.EXPIRED, RightsEvent.DENIED):
        return report(EvidenceChange.BLOCKED, "SOURCE_RIGHTS_CONTROL_EVENT_BLOCKS_REUSE")

    if previous.partition != incoming.partition:
        return report(EvidenceChange.BLOCKED, "CROSS_PARTITION_EVIDENCE_CONFLICT")
    if incoming.checked_at_utc < previous.checked_at_utc:
        return report(EvidenceChange.BLOCKED, "SNAPSHOT_CLOCK_ROLLBACK")
    for item in (previous, incoming):
        review = qualify_snapshot_binding(item, binding, decision_utc)
        if not review.declared_metadata_consistent:
            return report(EvidenceChange.BLOCKED, "SOURCE_BINDING:" + review.reason)

    old = {b.key.bar_start_utc: b for b in previous.closed_bars}
    new = {b.key.bar_start_utc: b for b in incoming.closed_bars}
    if not old.keys() <= new.keys():
        return report(EvidenceChange.BLOCKED, "HISTORICAL_BAR_DISAPPEARED_NO_SILENT_DELETE")

    price_dirty_at = None
    causal_review_at = None
    for start, current in new.items():
        prior = old.get(start)
        if prior is None:
            price_dirty_at = start if price_dirty_at is None else min(start, price_dirty_at)
            continue
        if prior.key != current.key:
            return report(EvidenceChange.BLOCKED, "BAR_KEY_CHANGE_REQUIRES_REPARTITION")
        if (current.revision_number < prior.revision_number
                or current.first_known_utc < prior.first_known_utc
                or current.observation.first_known_utc < prior.observation.first_known_utc):
            return report(EvidenceChange.BLOCKED, "REVISION_OR_CAUSAL_CLOCK_ROLLBACK")
        price_changed = _price_row(prior) != _price_row(current)
        if price_changed:
            if (current.revision_number <= prior.revision_number
                    or current.first_known_utc <= prior.first_known_utc):
                return report(EvidenceChange.BLOCKED, "PRICE_CHANGE_WITHOUT_NEW_CAUSAL_REVISION")
            price_dirty_at = start if price_dirty_at is None else min(start, price_dirty_at)
        # Even unchanged OHLC may have a changed first-known or vendor revision.
        # That affects historical signal validity but NOT indicator OHLC inputs.
        if (current.revision_number != prior.revision_number
                or current.first_known_utc != prior.first_known_utc
                or current.observation.first_known_utc != prior.observation.first_known_utc
                or current.observation.revision_id != prior.observation.revision_id
                or current.observation.raw_sha256 != prior.observation.raw_sha256):
            causal_review_at = start if causal_review_at is None else min(start, causal_review_at)

    if price_dirty_at is not None:
        return report(
            EvidenceChange.PRICE_DIRTY, "PRICE_INPUT_CHANGED_RECOMPUTE_FROM_FIRST_DIRTY",
            price_dirty_at=price_dirty_at, causal_review_at=causal_review_at,
        )
    if old_price != new_price:
        return report(EvidenceChange.BLOCKED, "UNCLASSIFIED_PRICE_CONTENT_CHANGE")
    if causal_review_at is not None:
        return report(
            EvidenceChange.CAUSAL_REPLAY_REVIEW,
            "SAME_PRICE_CAUSAL_REVISION_REQUIRES_REPLAY_REVIEW",
            causal_review_at=causal_review_at,
        )
    if old_lineage != new_lineage:
        return report(EvidenceChange.LINEAGE_ONLY, "METADATA_ONLY_NO_PRICE_RECOMPUTE")
    return report(EvidenceChange.UNCHANGED, "NO_DECLARED_EVIDENCE_CHANGE")


@dataclass(frozen=True, slots=True)
class SyntheticLineageEvent:
    """In-memory hash-linked audit fixture; NOT a trusted anti-rollback witness."""

    generation: int
    observed_at_utc: datetime
    previous_event_sha256: str | None
    old_price_digest: str
    new_price_digest: str
    old_provenance_digest: str
    new_provenance_digest: str
    change: EvidenceChange
    rights_event: RightsEvent
    reason: str
    event_sha256: str


def _event_digest(event: SyntheticLineageEvent) -> str:
    return _sha((
        "FX_SYNTHETIC_LINEAGE_V1", event.generation,
        event.observed_at_utc.isoformat(), event.previous_event_sha256,
        event.old_price_digest, event.new_price_digest,
        event.old_provenance_digest, event.new_provenance_digest,
        event.change.value, event.rights_event.value, event.reason,
    ))


def make_synthetic_lineage_event(
    review: SyntheticEvidenceReview,
    observed_at_utc: datetime,
    previous: SyntheticLineageEvent | None = None,
) -> SyntheticLineageEvent:
    """Return a new immutable event, without storing or publishing it."""
    if not isinstance(review, SyntheticEvidenceReview):
        raise TypeError("TYPED_EVIDENCE_REVIEW_REQUIRED")
    ensure_utc(observed_at_utc, "observed_at_utc")
    if observed_at_utc < review.reviewed_as_of_utc:
        raise ValueError("LINEAGE_EVENT_PREDATES_ASOF_REVIEW")
    if previous is not None and not isinstance(previous, SyntheticLineageEvent):
        raise TypeError("TYPED_PREVIOUS_LINEAGE_EVENT_REQUIRED")
    if not review.propose_lineage_event:
        raise ValueError("NO_LINEAGE_EVENT_NEEDED")
    if previous is not None:
        if _event_digest(previous) != previous.event_sha256:
            raise ValueError("PREVIOUS_LINEAGE_EVENT_DIGEST_CORRUPT")
        if observed_at_utc < previous.observed_at_utc:
            raise ValueError("LINEAGE_EVENT_CLOCK_ROLLBACK")
        if review.old_provenance_digest != previous.new_provenance_digest:
            raise ValueError("LINEAGE_CHAIN_SNAPSHOT_DISCONTINUITY")
    item = SyntheticLineageEvent(
        1 if previous is None else previous.generation + 1,
        observed_at_utc,
        None if previous is None else previous.event_sha256,
        review.old_price_digest, review.new_price_digest,
        review.old_provenance_digest, review.new_provenance_digest,
        review.change, review.rights_event, review.reason, "",
    )
    return SyntheticLineageEvent(
        item.generation, item.observed_at_utc, item.previous_event_sha256,
        item.old_price_digest, item.new_price_digest,
        item.old_provenance_digest, item.new_provenance_digest,
        item.change, item.rights_event, item.reason, _event_digest(item),
    )


def validate_synthetic_lineage_chain(
    events: tuple[SyntheticLineageEvent, ...],
) -> bool:
    """Checks a supplied complete in-memory chain, NOT missing-tail rollback."""
    if not isinstance(events, tuple) or not events or len(events) > 10000:
        raise ValueError("INVALID_SYNTHETIC_LINEAGE_HISTORY")
    for i, item in enumerate(events):
        if not isinstance(item, SyntheticLineageEvent):
            raise TypeError("TYPED_LINEAGE_EVENT_REQUIRED")
        if item.generation != i + 1:
            raise ValueError("LINEAGE_SEQUENCE_GAP_OR_ROLLBACK")
        expected_previous = events[i - 1] if i else None
        if item.previous_event_sha256 != (
            expected_previous.event_sha256 if expected_previous else None
        ):
            raise ValueError("LINEAGE_PARENT_MISMATCH")
        if expected_previous is not None:
            if item.observed_at_utc < expected_previous.observed_at_utc:
                raise ValueError("LINEAGE_EVENT_CLOCK_ROLLBACK")
            if item.old_provenance_digest != expected_previous.new_provenance_digest:
                raise ValueError("LINEAGE_CHAIN_SNAPSHOT_DISCONTINUITY")
        if _event_digest(item) != item.event_sha256:
            raise ValueError("LINEAGE_EVENT_DIGEST_MISMATCH")
    return True
