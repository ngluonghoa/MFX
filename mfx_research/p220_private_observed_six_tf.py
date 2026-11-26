"""P220: join M5 archive-time prefixes, native H4 and private D1 vintages.

Current metadata proxy only, not historical publisher first-known.
No market-side conversion, synthetic relabeling of actual bars, or release.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from mfx_cache.native_d1_epoch_20261118 import audit_fresh_epoch
from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_research.p227_pretrigger_h1 import (
    PrivatePretriggerH1, calculate_pretrigger_h1,
)
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
    SixTimeframeResearchReceipt, _native_utc_start, _expected_last_closed,
    GRACE, MAX_H4_AGE, MAX_D1_SESSION_DATE_AGE,
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
# SOURCE_LOCKED_03 B2/S2 REQUIRED lines; M5 is optional/ARMED.
B2S2_STRUCTURAL_FRAMES = ("D1", "H4", "H1", "M15")
_INTRADAY_WIDTHS = (("M5", 5), ("M15", 15), ("M30", 30), ("H1", 60))


@dataclass(frozen=True, slots=True)
class ArchiveFreshnessCensus:
    sampled_commit_instants: int
    fresh_by_frame: tuple[tuple[str, int], ...]
    four_structural_frames_fresh: int
    all_six_frames_fresh: int
    four_structural_fresh_m5_stale: int
    private_core_cutoffs: tuple[datetime, ...] = field(default=(), repr=False)

    def public_summary(self) -> dict[str, object]:
        return {
            "sample_basis": "DISTINCT_CURRENT_METADATA_COMMIT_TIMES_VERIFIED_M5_RAW_TAIL",
            "sampled_commit_instants": self.sampled_commit_instants,
            "fresh_by_frame": dict(self.fresh_by_frame),
            "b2s2_structural_frames": list(B2S2_STRUCTURAL_FRAMES),
            "four_structural_frames_fresh": self.four_structural_frames_fresh,
            "all_six_frames_fresh": self.all_six_frames_fresh,
            "four_structural_fresh_m5_stale": self.four_structural_fresh_m5_stale,
            "d1_calendar_qualified": False,
            "source_first_known_verified": False,
            "signal_eligibility_assessed": False,
            "historical_oos_qualified": False,
        }


def _archive_freshness_census(
    commits: tuple[tuple[datetime, datetime], ...],
    h4: tuple[tuple[datetime, tuple[NativeFXBar, ...]], ...],
    d1: tuple[tuple[datetime, PrivateSnapshot], ...],
    *, cutoff: datetime,
) -> ArchiveFreshnessCensus:
    """Time-label coverage only. Never evaluate direction or strategy here.

    Every M5 hour was already independently SHA-verified this run.
    At a shared commit instant use the newest sealed source hour, not
    multiple decisions on the same instant. No raw older than that tail.
    """
    by_time: dict[datetime, datetime] = {}
    for known, end in commits:
        if known <= cutoff:
            by_time[known] = max(end, by_time.get(known, end))
    counts = dict.fromkeys(("M5", "M15", "M30", "H1", "H4", "D1"), 0)
    required = six = optional_m5_stale = 0
    core_cutoffs: list[datetime] = []
    for known, end in sorted(by_time.items()):
        fresh = {f for f, width in _INTRADAY_WIDTHS
                 if end == _expected_last_closed(known, width)}
        visible_h4 = tuple(b for observed, bars in h4 if observed <= known
                           for b in bars)
        if visible_h4:
            h4_end = _native_utc_start(visible_h4[-1].native_open_label) + timedelta(hours=4)
            if GRACE <= known-h4_end <= MAX_H4_AGE:
                fresh.add("H4")
        visible_d1 = [snap for created, snap in d1
                      if created <= known and snap.observed <= known]
        if visible_d1:
            selected = max(visible_d1, key=lambda snap: snap.observed)
            today = known.astimezone(ZoneInfo("Australia/Sydney")).date()
            age = (today - date.fromisoformat(selected.rows[-1].native_open_label)).days
            if 1 <= age <= MAX_D1_SESSION_DATE_AGE:
                fresh.add("D1")
        for frame in fresh:
            counts[frame] += 1
        core = set(B2S2_STRUCTURAL_FRAMES) <= fresh
        required += int(core)
        if core:
            core_cutoffs.append(known)
        six += int(len(fresh) == 6)
        optional_m5_stale += int(core and "M5" not in fresh)
    return ArchiveFreshnessCensus(len(by_time), tuple(counts.items()),
                                  required, six, optional_m5_stale, tuple(core_cutoffs))



@dataclass(frozen=True, slots=True, repr=False)
class PrivateObservedContext:
    decision_utc: datetime = field(repr=False)
    m5_verified_hours: int
    h4_visible_rows: int
    d1_visible_rows: int
    context: SixTimeframeResearchReceipt | None = field(repr=False)
    readiness: PrivateB2S2Readiness | None = field(repr=False)
    pretrigger_h1: PrivatePretriggerH1 | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateObservedReplay:
    private_contexts: tuple[PrivateObservedContext, ...] = field(repr=False)
    h4_pairs_verified: int
    d1_snapshots_verified: int
    m5_pairs_metadata_checked: int
    fixture_anchors_used: bool
    archive_freshness_census: ArchiveFreshnessCensus | None = None
    private_core_contexts: tuple[PrivateObservedContext, ...] = field(default=(), repr=False)
    replay_io_counts: tuple[int, int, int] | None = None

    def public_summary(self) -> dict[str, object]:
        summary: dict[str, object] = {
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
        if self.archive_freshness_census is not None:
            summary["archive_freshness_census"] = self.archive_freshness_census.public_summary()
            summary["core_structural_replay"] = _core_summary(
                self.archive_freshness_census, self.private_core_contexts)
        if self.replay_io_counts is not None:
            first, replay, reused = self.replay_io_counts
            if any(type(n) is not int or n < 0 for n in (first, replay, reused)):
                raise ValueError("P224_REPLAY_IO_COUNT_DRIFT")
            summary["replay_io"] = {
                "first_audit_gets_including_metadata": first,
                "replay_live_gets": replay,
                "replay_recorded_payload_reads": reused,
                "second_independent_raw_download": False,
            }
        return summary


MAX_CORE_REPLAY = 32
# No directional counts or price-derived levels are exported.
_CORE_DATA_REQUIREMENTS = (
    "D1_NOT_ENOUGH_OBSERVED_CLOSED_ROWS",
    "H4_TWO_CONFIRMED_HIGHS_AND_LOWS_MISSING",
    "H1_DRAFT_TR_PERIOD_NOT_CLOSED",
    "M15_PRETRIGGER_CONFIRMED_LEVEL_MISSING",
)


def _core_summary(census: ArchiveFreshnessCensus,
                  rows: tuple[PrivateObservedContext, ...]) -> dict[str, object]:
    if (len(rows) > MAX_CORE_REPLAY
            or tuple(r.decision_utc for r in rows) !=
                census.private_core_cutoffs[-MAX_CORE_REPLAY:]):
        raise ValueError("P223_CORE_SAMPLE_ACCOUNTING_DRIFT")
    data_complete = 0
    core_technical = 0
    pretrigger_ready = 0
    for r in rows:
        if r.context is None or r.readiness is None:
            raise ValueError("P223_MISSING_REPLAY_RECEIPT")
        if (r.readiness.public_action != "NO_SIGNAL" or r.readiness.may_trade
                or r.readiness.may_publish_buy_sell or r.readiness.d1_calendar_qualified
                or r.readiness.publisher_first_known_verified
                or tuple(g.rule_id for g in r.readiness.gates) != ("B2", "S2")):
            raise ValueError("P223_PRIVATE_RESEARCH_AUTHORITY_DRIFT")
        pretrigger = r.pretrigger_h1
        if (pretrigger is None or pretrigger.action != "NO_SIGNAL"
                or pretrigger.numeric_policy_approved or pretrigger.may_trade
                or pretrigger.may_publish_buy_sell or pretrigger.publisher_first_known_verified):
            raise ValueError("P227_PRETRIGGER_RESEARCH_AUTHORITY_DRIFT")
        pretrigger_ready += int(pretrigger.status == "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED")
        present = {f.frame for f in r.context.frames}
        core_technical += int(set(B2S2_STRUCTURAL_FRAMES) <= present)
        # Counts only availability of structural ingredients, not direction,
        # event triggers, approved D1 trend or an actionable signal.
        data_complete += int(any(not set(_CORE_DATA_REQUIREMENTS).intersection(
            g.missing_preconditions) for g in r.readiness.gates))
    return {
        "selection": "LATEST_UP_TO_32_DISTINCT_CORE_FRESH_COMMIT_INSTANTS",
        "core_fresh_cutoffs_total": census.four_structural_frames_fresh,
        "core_cutoffs_replayed": len(rows),
        "core_cutoffs_not_replayed_due_to_limit":
            census.four_structural_frames_fresh-len(rows),
        "core_technical_receipts_complete": core_technical,
        "pretrigger_h1_draft_contexts_computed": pretrigger_ready,
        "pretrigger_h1_basis": "ARCHIVE_METADATA_PROXY_BEFORE_FIRST_OF_TWO_M15_BARS",
        "cutoffs_with_basic_structural_ingredients_one_or_both_sides": data_complete,
        "d1_trend_calendar_qualified": False,
        "numeric_strategy_approved": False,
        "market_signal_eligibility_assessed": False,
        "historical_oos_qualified": False,
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
    def context_at(decision: datetime, raw: tuple[ClosedM5Bar, ...], hours: int) -> PrivateObservedContext:
        h4_rows = tuple(bar for known, bars in h4 if known <= decision for bar in bars)
        visible = [s for created, s in d1 if created <= decision and s.observed <= decision]
        selected = max(visible, key=lambda s: s.observed) if visible else None
        daily = selected.rows if selected else ()
        context = readiness = pretrigger = None
        if raw:
            h4_batch, d1_batch = _batch("4h", h4_rows), _batch("1day", daily)
            context = build_six_timeframe_readonly_context(
                raw[-12:], h4_batch, d1_batch, asof_utc=decision)
            multi = calculate_private_multibar_from_sealed_rows(
                raw, h4_batch, d1_batch, context, asof_utc=decision)
            pivots = scan_private_sealed_pivot_sensitivity(multi, context)
            micro = compute_private_sealed_m15_microbreak(multi, context, pivots)
            readiness = compute_private_option_b2s2_requirements(
                multi, context, pivots, micro,
                active_d1_source_epoch="P209_PRIVATE_REVISED_D1_RESEARCH_ONLY")
            m15 = next((frame for frame in context.frames if frame.frame == "M15"), None)
            if m15 is not None:
                pretrigger = calculate_pretrigger_h1(
                    raw, m5.private_raw_hour_commits[:hours],
                    latest_m15_open=datetime.fromisoformat(m15.source_label),
                    decision_utc=decision)
        return PrivateObservedContext(
            decision, hours, len(h4_rows), len(daily), context, readiness, pretrigger)

    contexts = tuple(context_at(p.decision_utc, p.private_m5, p.verified_raw_hours)
                     for p in m5.private_prefixes)
    census = _archive_freshness_census(
        m5.private_raw_hour_commits, h4, d1, cutoff=decisions_utc[-1])
    # Reuse already SHA-audited raw history at the final cutoff; do not
    # reread Drive or fetch prices. Restrict each replay to its known prefix.
    final_raw = m5.private_prefixes[-1].private_m5
    prior_contexts = {r.decision_utc: r for r in contexts}
    core = []
    for decision in census.private_core_cutoffs[-MAX_CORE_REPLAY:]:
        hours = sum(known <= decision for known, _ in m5.private_raw_hour_commits)
        if not 0 < hours*12 <= len(final_raw):
            raise ValueError("P223_CORE_RAW_PREFIX_ACCOUNTING_DRIFT")
        row = prior_contexts.get(decision)
        if row is None:
            row = context_at(decision, final_raw[:hours*12], hours)
        core.append(row)
    _core_summary(census, tuple(core))
    return PrivateObservedReplay(
        contexts, len(h4), len(d1), m5.metadata_pairs,
        m5.fixture_anchors_used, census, tuple(core))
