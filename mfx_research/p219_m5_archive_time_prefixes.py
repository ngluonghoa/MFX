"""P219: use current Drive metadata as a conservative archive-time proxy.

Never identify mutable Drive metadata with historical publisher first-known.
The current SHA-audited raw tail is the only price universe eligible here.
No network, writes, quote-side conversion, or trading authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_batch_commit import _validate_manifest
from mfx_cache.v2_engine import derive_intraday
from mfx_research.six_tf_sealed_archive_consumer import (
    ReadOnlyObjectStore, SyntheticFixturePins, _m5_pinned_rows, _snapshot,
)

VERSION = "MFX_P219_CURRENT_METADATA_ARCHIVE_TIME_PREFIX_V1"
HOUR = timedelta(hours=1)
MAX_DECISIONS = 32


def _utc(t: datetime) -> None:
    if (type(t) is not datetime or t.tzinfo is None
            or t.utcoffset() != timedelta(0)):
        raise ValueError("P219_EXACT_UTC_CLOCK_REQUIRED")


@dataclass(frozen=True, slots=True, repr=False)
class ObservedObjectTime:
    name: str = field(repr=False)
    created_utc: datetime = field(repr=False)
    modified_utc: datetime = field(repr=False)

    def __post_init__(self) -> None:
        _utc(self.created_utc)
        _utc(self.modified_utc)
        if (type(self.name) is not str or not self.name
                or self.created_utc != self.modified_utc):
            raise ValueError("P219_UNCHANGED_CURRENT_METADATA_REQUIRED")


@dataclass(frozen=True, slots=True, repr=False)
class ArchiveTimePrefix:
    decision_utc: datetime = field(repr=False)
    eligible_archived_hours: int
    eligible_but_raw_not_reread_hours: int
    verified_raw_hours: int
    private_m5: tuple[ClosedM5Bar, ...] = field(repr=False)
    private_derived: tuple[tuple[str, tuple[Any, ...]], ...] = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class ArchiveTimeReplay:
    audited_at_utc: datetime = field(repr=False)
    private_prefixes: tuple[ArchiveTimePrefix, ...] = field(repr=False)
    metadata_pairs: int
    current_raw_sha_hours: int
    private_tip_sha256: str = field(repr=False)
    fixture_anchors_used: bool = False

    def public_summary(self) -> dict[str, str | bool | int]:
        return {
            "version": VERSION,
            "metadata_pairs_checked": self.metadata_pairs,
            "current_raw_sha_hours": self.current_raw_sha_hours,
            "decision_cutoffs_checked": len(self.private_prefixes),
            "decision_cutoffs_with_available_verified_raw": sum(
                p.verified_raw_hours > 0 for p in self.private_prefixes),
            "decision_cutoffs_with_older_raw_not_reread": sum(
                p.eligible_but_raw_not_reread_hours > 0
                for p in self.private_prefixes),
            "fixture_anchors_used": self.fixture_anchors_used,
            "current_metadata_proxy_only": True,
            "metadata_historically_authenticated": False,
            "publisher_first_known_verified": False,
            "historical_oos_qualified": False,
            "action": "NO_SIGNAL", "stage": "UNVERIFIED",
            "may_publish_buy_sell": False, "may_trade": False,
            "provider_requests": 0, "drive_writes": 0, "broker_orders": 0,
        }


def _metadata_index(items: tuple[ObservedObjectTime, ...],
                    names: tuple[str, ...], now: datetime
                    ) -> dict[str, ObservedObjectTime]:
    if (type(items) is not tuple or len(items) != len(names)
            or any(type(i) is not ObservedObjectTime for i in items)):
        raise ValueError("P219_EXACT_METADATA_LIST_REQUIRED")
    result = {i.name: i for i in items}
    if (len(result) != len(items) or set(result) != set(names)
            or any(i.created_utc > now for i in items)):
        raise ValueError("P219_METADATA_NAME_OR_CLOCK_DRIFT")
    return result


def replay_m5_current_metadata_prefixes(
    store: ReadOnlyObjectStore, *,
    manifests: tuple[ObservedObjectTime, ...],
    chunks: tuple[ObservedObjectTime, ...],
    decisions_utc: tuple[datetime, ...],
    audited_at_utc: datetime,
    fixture_pins: SyntheticFixturePins | None = None,
) -> ArchiveTimeReplay:
    """Reverify existing root-pinned SHA tail; gate by observed metadata.

    Use max(chunk, manifest creation) as a conservative proxy for when
    the sealed batch could be read. File creation metadata is not an
    external historical attestation. Reject gaps in the metadata join;
    older manifest-only hours remain explicitly absent from raw features.
    """
    _utc(audited_at_utc)
    if type(decisions_utc) is not tuple or not 1 <= len(decisions_utc) <= MAX_DECISIONS:
        raise ValueError("P219_BOUNDED_DECISION_TUPLE_REQUIRED")
    for t in decisions_utc:
        _utc(t)
    if (any(a >= b for a, b in zip(decisions_utc, decisions_utc[1:]))
            or decisions_utc[-1] > audited_at_utc):
        raise ValueError("P219_CHRONOLOGICAL_OBSERVED_DECISIONS_REQUIRED")
    before = _snapshot(store)
    names, chunk_names = before
    mt = _metadata_index(manifests, names, audited_at_utc)
    ct = _metadata_index(chunks, chunk_names, audited_at_utc)
    rows, evidence = _m5_pinned_rows(
        store, asof_utc=audited_at_utc, fixture_pins=fixture_pins)
    raw_count = evidence["m5_manifest_chunk_pairs_full_sha_verified"]
    if type(raw_count) is not int or len(rows) != raw_count*12:
        raise ValueError("P219_CURRENT_RAW_TAIL_ACCOUNTING_DRIFT")
    raw_start = len(names)-raw_count
    available: list[tuple[str, datetime]] = []
    seen_chunks: set[str] = set()
    prior_time: datetime | None = None
    for i, name in enumerate(names):
        body = store.read("manifest", name)
        hour = _validate_manifest(name, body)
        ref = body["chunk_name"]
        if ref not in ct or ref in seen_chunks:
            raise ValueError("P219_METADATA_CHUNK_LINK_DRIFT")
        seen_chunks.add(ref)
        ctime, mtime = ct[ref].created_utc, mt[name].created_utc
        close = datetime.fromisoformat(hour) + HOUR
        if (ctime < close or mtime < ctime
                or (prior_time is not None and mtime < prior_time)):
            raise ValueError("P219_METADATA_COMMIT_CLOCK_DRIFT")
        prior_time = mtime
        available.append((hour, mtime))
        if i >= raw_start:
            offset = (i-raw_start)*12
            if rows[offset].start_utc != hour:
                raise ValueError("P219_VERIFIED_RAW_HOUR_MISMATCH")
    if seen_chunks != set(chunk_names) or _snapshot(store) != before:
        raise ValueError("P219_ARCHIVE_CHANGED_DURING_JOIN")
    prefixes = []
    for decision in decisions_utc:
        # Monotone sealed parent chain: all earlier metadata times must
        # also precede the decision, and no later batch may be included.
        eligible = sum(known <= decision for _, known in available)
        old = min(eligible, raw_start)
        count = eligible-old
        selected = tuple(rows[:count*12])
        derived = tuple(
            (frame, derive_intraday(selected, frame, asof_utc=decision).candles)
            for frame in ("M15", "M30", "H1")
        ) if selected else ()
        if selected and any(len(x) != count*n for (_, x), n in zip(
                derived, (4, 2, 1))):
            raise ValueError("P219_DERIVED_CLOSED_HOUR_ACCOUNTING_DRIFT")
        prefixes.append(ArchiveTimePrefix(decision, eligible, old, count,
                                         selected, derived))
    return ArchiveTimeReplay(
        audited_at_utc, tuple(prefixes), len(names), raw_count,
        evidence["m5_latest_manifest_sha256"], fixture_pins is not None,
    )
