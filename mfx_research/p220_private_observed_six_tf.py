"""P220: join M5 archive-time prefixes, native H4 and private D1 vintages.

Current metadata proxy only, not historical publisher first-known.
No market-side conversion, synthetic relabeling of actual bars, or release.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from mfx_cache.native_d1_epoch_20261118 import audit_fresh_epoch
from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from mfx_cache.td_m5_codec import digest
from mfx_research import p193_owner_nov18_active_d1_reader as p193
from mfx_research.p219_m5_archive_time_prefixes import (
    ObservedObjectTime, _metadata_index, replay_m5_current_metadata_prefixes,
)
from mfx_research.p177_real_source_b2s2_readiness import (
    PrivateB2S2Readiness, compute_private_option_b2s2_requirements,
)
from mfx_research.sealed_multibar_private_features import (
    calculate_private_multibar_from_sealed_rows,
)
from mfx_research.sealed_private_pivot_sensitivity import (
    scan_private_sealed_pivot_sensitivity,
)
from mfx_research.sealed_private_m15_microbreak import (
    compute_private_sealed_m15_microbreak,
)
from mfx_research.six_tf_readonly_context import (
    SixTimeframeResearchReceipt, _native_utc_start,
    build_six_timeframe_readonly_context,
)
from mfx_research.six_tf_sealed_archive_consumer import (
    ReadOnlyObjectStore, SyntheticFixturePins, _snapshot,
)
from tools.audit_mfx_p209_d1_private_cache import (
    PrivateSnapshot, _parent, verify_snapshot,
)
from tools.mfx_native_htf_drive_seal import MAX_NATIVE_FILES, _batch_from_chunk

VERSION = "MFX_P220_PRIVATE_OBSERVED_SIX_TF_REPLAY_V1"


@dataclass(frozen=True, slots=True, repr=False)
class PrivateObservedContext:
    decision_utc: datetime = field(repr=False)
    m5_verified_hours: int
    h4_visible_rows: int
    d1_visible_rows: int
    context: SixTimeframeResearchReceipt | None = field(repr=False)
    readiness: PrivateB2S2Readiness | None = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateObservedReplay:
    private_contexts: tuple[PrivateObservedContext, ...] = field(repr=False)
    h4_pairs_verified: int
    d1_snapshots_verified: int
    m5_pairs_metadata_checked: int
    fixture_anchors_used: bool

    def public_summary(self) -> dict[str, object]:
        return {
            "version": VERSION,
            "decision_cutoffs_checked": len(self.private_contexts),
            "cutoffs_with_all_six_fresh_frames": sum(
                r.context is not None and r.context.research_technical_context_complete
                for r in self.private_contexts),
            "cutoffs_with_private_b2s2_requirements": sum(
                r.readiness is not None for r in self.private_contexts),
            "cutoffs_without_visible_m5": sum(
                r.m5_verified_hours == 0 for r in self.private_contexts),
            "cutoffs_without_visible_revised_d1": sum(
                r.d1_visible_rows == 0 for r in self.private_contexts),
            "h4_pairs_verified": self.h4_pairs_verified,
            "d1_snapshots_verified": self.d1_snapshots_verified,
            "m5_pairs_metadata_checked": self.m5_pairs_metadata_checked,
            "fixture_anchors_used": self.fixture_anchors_used,
            "current_metadata_proxy_only": True,
            "publisher_first_known_verified": False,
            "canonical_source_selected": False,
            "historical_oos_qualified": False,
            "action": "NO_SIGNAL", "stage": "UNVERIFIED",
            "may_publish_buy_sell": False, "may_trade": False,
            "provider_requests": 0, "drive_writes": 0, "broker_orders": 0,
        }


def _native_h4_history(
    store: ReadOnlyObjectStore, manifests: tuple[ObservedObjectTime, ...],
    chunks: tuple[ObservedObjectTime, ...], now: datetime,
) -> tuple[tuple[datetime, tuple[NativeFXBar, ...]], ...]:
    names, chunk_names = before = _snapshot(store)
    if not 1 <= len(names) <= MAX_NATIVE_FILES or len(names) != len(chunk_names):
        raise ValueError("P220_H4_BOUNDED_COMPLETE_PAIR_LIST_REQUIRED")
    mt = _metadata_index(manifests, names, now)
    ct = _metadata_index(chunks, chunk_names, now)
    previous: dict[str, Any] | None = None
    seen: set[str] = set()
    history: list[tuple[datetime, tuple[NativeFXBar, ...]]] = []
    for name in names:
        body = store.read("manifest", name)
        ref = body["chunk_name"]
        if ref not in ct or ref in seen:
            raise ValueError("P220_H4_CHUNK_LINK_DRIFT")
        seen.add(ref)
        raw = store.read("chunk", ref)
        batch = _batch_from_chunk(raw)
        if (batch.interval != "4h" or batch.symbol != "EUR/USD"
                or batch.exchange_timezone != "Australia/Sydney"):
            raise ValueError("P220_H4_NATIVE_SCOPE_REQUIRED")
        candidate = plan_native_sealed(batch, previous=previous)
        if (candidate is None or candidate.manifest != body
                or candidate.manifest_name != name or candidate.chunk != raw
                or candidate.chunk_name != ref):
            raise ValueError("P220_H4_SHA_PARENT_OR_RAW_DRIFT")
        created, committed = ct[ref].created_utc, mt[name].created_utc
        close = _native_utc_start(body["last_native_open_label"])+timedelta(hours=4)
        if (created < close or committed < created
                or (history and committed < history[-1][0])):
            raise ValueError("P220_H4_COMMIT_CLOCK_DRIFT")
        history.append((committed, batch.closed_bars))
        previous = body
    if seen != set(chunk_names) or _snapshot(store) != before:
        raise ValueError("P220_H4_LIST_CHANGED")
    return tuple(history)


def _private_d1_history(
    original_store: ReadOnlyObjectStore, revised_store: ReadOnlyObjectStore,
    times: tuple[ObservedObjectTime, ...], now: datetime,
) -> tuple[tuple[datetime, PrivateSnapshot], ...]:
    origin = p193.PINNED_ORIGINAL_D1_V1_HEAD_SHA256
    root = p193.read_p192_owner_d1_epoch(
        original_store, old_v1_manifest_sha256=origin, asof_utc=now)
    original = audit_fresh_epoch(original_store, origin_v1_sha=origin)
    if (original.last_manifest is None
            or digest(original.last_manifest) != root.epoch_manifest_sha256):
        raise ValueError("P220_ORIGINAL_D1_ROOT_DRIFT")
    parent = _parent(original)
    names = revised_store.list_names("chunk")
    if (type(names) is not tuple or len(names) > MAX_NATIVE_FILES
            or names != tuple(sorted(set(names)))):
        raise ValueError("P220_BOUNDED_D1_SNAPSHOT_LIST_REQUIRED")
    metadata = _metadata_index(times, names, now)
    result = []
    for name in names:
        snap = verify_snapshot(name, revised_store.read("chunk", name),
                               parent=parent, now_utc=now)
        created = metadata[name].created_utc
        if created < snap.observed:
            raise ValueError("P220_D1_ARCHIVE_BEFORE_OBSERVATION")
        result.append((created, snap))
    if len({s.observed for _, s in result}) != len(result):
        raise ValueError("P220_AMBIGUOUS_D1_OBSERVATION")
    if (revised_store.list_names("chunk") != names
            or audit_fresh_epoch(original_store, origin_v1_sha=origin) != original):
        raise ValueError("P220_D1_READONLY_SNAPSHOT_DRIFT")
    return tuple(result)


def _batch(interval: str, rows: tuple[NativeFXBar, ...]) -> NativeFXBatch:
    return NativeFXBatch(
        symbol="EUR/USD", interval=interval, exchange_timezone="Australia/Sydney",
        time_reference=("UTC_INTRADAY_OPEN" if interval == "4h"
                        else "EXCHANGE_LOCAL_SESSION_DATE"),
        closed_bars=rows[-120:], incomplete_excluded=0,
    )


def replay_private_observed_six_tf(
    m5_store: ReadOnlyObjectStore, h4_store: ReadOnlyObjectStore,
    original_d1_store: ReadOnlyObjectStore, revised_d1_store: ReadOnlyObjectStore,
    *, m5_manifests: tuple[ObservedObjectTime, ...],
    m5_chunks: tuple[ObservedObjectTime, ...],
    h4_manifests: tuple[ObservedObjectTime, ...],
    h4_chunks: tuple[ObservedObjectTime, ...],
    revised_d1_times: tuple[ObservedObjectTime, ...],
    decisions_utc: tuple[datetime, ...], audited_at_utc: datetime,
    fixture_pins: SyntheticFixturePins | None = None,
) -> PrivateObservedReplay:
    m5 = replay_m5_current_metadata_prefixes(
        m5_store, manifests=m5_manifests, chunks=m5_chunks,
        decisions_utc=decisions_utc, audited_at_utc=audited_at_utc,
        fixture_pins=fixture_pins)
    h4 = _native_h4_history(h4_store, h4_manifests, h4_chunks, audited_at_utc)
    d1 = _private_d1_history(original_d1_store, revised_d1_store,
                             revised_d1_times, audited_at_utc)
    contexts = []
    for p in m5.private_prefixes:
        decision = p.decision_utc
        h4_rows = tuple(bar for known, bars in h4 if known <= decision for bar in bars)
        visible = [s for created, s in d1 if created <= decision and s.observed <= decision]
        selected = max(visible, key=lambda s: s.observed) if visible else None
        daily = selected.rows if selected else ()
        context = readiness = None
        if p.private_m5:
            h4_batch, d1_batch = _batch("4h", h4_rows), _batch("1day", daily)
            context = build_six_timeframe_readonly_context(
                p.private_m5[-12:], h4_batch, d1_batch, asof_utc=decision)
            multi = calculate_private_multibar_from_sealed_rows(
                p.private_m5, h4_batch, d1_batch, context, asof_utc=decision)
            pivots = scan_private_sealed_pivot_sensitivity(multi, context)
            micro = compute_private_sealed_m15_microbreak(multi, context, pivots)
            readiness = compute_private_option_b2s2_requirements(
                multi, context, pivots, micro,
                active_d1_source_epoch="P209_PRIVATE_REVISED_D1_RESEARCH_ONLY")
        contexts.append(PrivateObservedContext(
            decision, p.verified_raw_hours, len(h4_rows), len(daily),
            context, readiness))
    return PrivateObservedReplay(
        tuple(contexts), len(h4), len(d1), m5.metadata_pairs, m5.fixture_anchors_used)
