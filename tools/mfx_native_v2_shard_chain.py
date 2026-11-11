"""A04/P0.75: pure, bounded SHA-linked native V2 shard chain (OFFLINE ONLY).

This does NOT read/write Google Drive or authorize a V2 workflow. Both the
V1 metadata and expected V2 tail are supplied by the caller; the algorithm
cannot establish an independently trusted anti-rollback witness.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch, PROVIDER
from mfx_cache.native_htf_incremental import SOURCE_PUBLICATION_BUFFER
from mfx_cache.native_htf_archive import (
    MAX_BATCH_BARS, _axis, _bar_valid, _stamp,
)
from mfx_cache.td_m5_codec import digest
from tools.mfx_native_htf_drive_seal import NativeArchiveState
from tools.mfx_native_shard_v2_design import (
    DESIGN_ONLY, NativeV2ShardProposal, ZONE,
    verify_native_v2_proposal,
)

SCHEMA = "MFX_A04_P75_NATIVE_V2_SHARD_SEALED_RESEARCH_V1"
MAX_PAIRS_PER_SHARD = 64
MAX_RESEARCH_SHARDS = 8
PUBLICATION_BUFFER = SOURCE_PUBLICATION_BUFFER  # exact P0.59/P0.71 writer guard
SHA_CHARS = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class V2SealedPair:
    chunk_name: str
    chunk_sha256: str
    chunk: dict[str, Any]
    manifest_name: str
    manifest_sha256: str
    manifest: dict[str, Any]


@dataclass(frozen=True, slots=True)
class V2ReadOnlyAudit:
    status: str
    pair_count: int
    shard_count: int
    latest_manifest_sha256: str
    last_native_open_label: str
    total_native_bars: int
    complete_supplied_chain_sha_verified: bool
    independent_external_tail_witness_verified: bool = False
    real_drive_writes: int = 0
    provider_requests: int = 0
    broker_orders: int = 0
    v2_live_activation_authorized: bool = False


def _is_sha(value: Any) -> bool:
    return (type(value) is str and len(value) == 64
            and all(c in SHA_CHARS for c in value))


def _context(
    proposal: NativeV2ShardProposal, legacy: NativeArchiveState, *,
    expected_v1_manifest_sha256: str, now_utc: datetime,
    shard_capacity: int,
) -> None:
    if (type(shard_capacity) is not int
            or not 1 <= shard_capacity <= MAX_PAIRS_PER_SHARD):
        raise ValueError("P075_INVALID_SHARD_CAPACITY")
    if (type(now_utc) is not datetime or now_utc.tzinfo is None
            or now_utc.utcoffset() != timedelta(0)):
        raise ValueError("P075_EXACT_UTC_NOW_REQUIRED")
    verify_native_v2_proposal(
        proposal, legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
    )
    if (proposal.status != DESIGN_ONLY
            or proposal.legacy_remaining_append_pairs != 0
            or proposal.awaiting_legacy_full_256
            or proposal.requires_separate_owner_activation is not True
            or proposal.requires_external_anti_rollback_witness is not True):
        raise ValueError("P075_V1_NOT_FULL_OR_PROPOSAL_NOT_INERT")
    if (proposal.legacy_v1_scope.endswith("_NATIVE_V1") is not True
            or proposal.proposed_v2_scope !=
            proposal.legacy_v1_scope.replace(
                "_NATIVE_V1", "_NATIVE_V2_SHARD000001")):
        raise ValueError("P075_INVALID_V2_NAMESPACE")


def _scope(proposal: NativeV2ShardProposal, shard: int) -> str:
    if not 1 <= shard <= MAX_RESEARCH_SHARDS:
        raise ValueError("P075_MAX_RESEARCH_SHARDS_EXCEEDED")
    return proposal.proposed_v2_scope[:-6] + f"{shard:06d}"


def _ready(bar: NativeFXBar, now_utc: datetime) -> None:
    safe = now_utc - PUBLICATION_BUFFER
    if bar.interval == "4h":
        opened = datetime.strptime(
            bar.native_open_label, "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
        if opened + timedelta(hours=4) > safe:
            raise ValueError("P075_H4_NOT_YET_PUBLICATION_ELIGIBLE")
    else:
        session_day = date.fromisoformat(bar.native_open_label)
        if session_day >= safe.astimezone(ZoneInfo(ZONE)).date():
            raise ValueError("P075_D1_NOT_YET_PUBLICATION_ELIGIBLE")


def _make_pair(
    proposal: NativeV2ShardProposal, batch: NativeFXBatch,
    prior: V2SealedPair | None, *,
    pair_count: int, shard_capacity: int, now_utc: datetime,
) -> V2SealedPair:
    if (type(batch) is not NativeFXBatch
            or batch.symbol != proposal.symbol
            or batch.interval != proposal.interval
            or batch.exchange_timezone != ZONE
            or batch.time_reference != _axis(proposal.interval)
            or batch.source != PROVIDER
            or batch.is_provider_native is not True
            or batch.vendor_calls_made_by_parser != 0
            or batch.google_drive_writes != 0
            or batch.confirmed_buy_sell_signals != 0
            or batch.broker_orders != 0
            or type(batch.incomplete_excluded) is not int
            or batch.incomplete_excluded != 0
            or type(batch.closed_bars) is not tuple
            or not 1 <= len(batch.closed_bars) <= MAX_BATCH_BARS):
        raise ValueError("P075_NATIVE_CLOSED_BATCH_REQUIRED")
    if pair_count >= MAX_RESEARCH_SHARDS * shard_capacity:
        raise ValueError("P075_MAX_RESEARCH_SHARDS_EXCEEDED")
    last = (proposal.legacy_latest_open_label if prior is None else
            prior.manifest["last_native_open_label"])
    labels: list[str] = []
    for bar in batch.closed_bars:
        _bar_valid(bar, symbol=proposal.symbol, interval=proposal.interval,
                   zone=ZONE)
        _ready(bar, now_utc)
        if bar.native_open_label <= last:
            raise ValueError("P075_DUPLICATE_OR_ROLLBACK_NATIVE_LABEL")
        labels.append(bar.native_open_label)
        last = bar.native_open_label
    if labels != sorted(set(labels)):
        raise ValueError("P075_NON_MONOTONIC_BATCH")
    shard = pair_count // shard_capacity + 1
    position = pair_count % shard_capacity + 1
    scope = _scope(proposal, shard)
    parent_sha = (
        proposal.proposed_anchor_sha256 if prior is None
        else prior.manifest_sha256
    )
    shard_bridge_sha = (
        parent_sha if position == 1
        else prior.manifest["shard_bridge_sha256"]
    )
    first, last = labels[0], labels[-1]
    chunk: dict[str, Any] = {
        "schema": SCHEMA, "symbol": proposal.symbol,
        "interval": proposal.interval, "exchange_timezone": ZONE,
        "time_reference": _axis(proposal.interval), "source": PROVIDER,
        "source_side": "MID", "scope": scope,
        "shard_number": shard, "shard_pair_index": position,
        "global_pair_index": pair_count + 1,
        "v1_tip_manifest_sha256": proposal.legacy_latest_manifest_sha256,
        "v2_root_anchor_sha256": proposal.proposed_anchor_sha256,
        "parent_manifest_sha256": parent_sha,
        "shard_bridge_sha256": shard_bridge_sha,
        "bars": [asdict(b) for b in batch.closed_bars],
        "numeric_signals_approved": False, "broker_orders": 0,
    }
    chunk_sha = digest(chunk)
    chunk_name = (
        f"{scope}_chunk_{position:04d}_{_stamp(last, proposal.interval)}"
        f"_{chunk_sha}.json"
    )
    total = (0 if prior is None else
             prior.manifest["total_native_bars"]) + len(labels)
    manifest: dict[str, Any] = {
        "schema": SCHEMA, "symbol": proposal.symbol,
        "interval": proposal.interval, "exchange_timezone": ZONE,
        "time_reference": _axis(proposal.interval), "source": PROVIDER,
        "source_side": "MID", "scope": scope,
        "shard_number": shard, "shard_pair_index": position,
        "global_pair_index": pair_count + 1,
        "v1_tip_manifest_sha256": proposal.legacy_latest_manifest_sha256,
        "v2_root_anchor_sha256": proposal.proposed_anchor_sha256,
        "parent_manifest_sha256": parent_sha,
        "shard_bridge_sha256": shard_bridge_sha,
        "chunk_name": chunk_name, "chunk_sha256": chunk_sha,
        "first_native_open_label": first,
        "last_native_open_label": last,
        "total_native_bars": total, "bar_count": len(labels),
        "numeric_signals_approved": False, "broker_orders": 0,
    }
    manifest_sha = digest(manifest)
    manifest_name = (
        f"{scope}_manifest_{position:04d}_"
        f"{_stamp(last, proposal.interval)}_{manifest_sha}.json"
    )
    return V2SealedPair(
        chunk_name=chunk_name, chunk_sha256=chunk_sha, chunk=chunk,
        manifest_name=manifest_name, manifest_sha256=manifest_sha,
        manifest=manifest,
    )


def audit_v2_chain(
    proposal: NativeV2ShardProposal, legacy: NativeArchiveState, *,
    expected_v1_manifest_sha256: str,
    pairs: tuple[V2SealedPair, ...],
    expected_v2_tip_sha256: str,
    now_utc: datetime,
    shard_capacity: int = MAX_PAIRS_PER_SHARD,
) -> V2ReadOnlyAudit:
    """Rebuild ALL supplied V2 pairs, including inter-shard SHA bridges.

    The expected V2 tip value is CALLER-SUPPLIED, not a trusted external
    witness; it detects truncation only if compared against a separately
    persisted and trustworthy expected head.
    """
    _context(proposal, legacy,
             expected_v1_manifest_sha256=expected_v1_manifest_sha256,
             now_utc=now_utc, shard_capacity=shard_capacity)
    if type(pairs) is not tuple:
        raise ValueError("P075_V2_PAIRS_MUST_BE_TUPLE")
    if (not _is_sha(expected_v2_tip_sha256)
            or len(pairs) > MAX_RESEARCH_SHARDS * shard_capacity):
        raise ValueError("P075_INVALID_EXPECTED_TIP_OR_CAPACITY")
    prior: V2SealedPair | None = None
    for i, pair in enumerate(pairs):
        if (type(pair) is not V2SealedPair
                or type(pair.chunk) is not dict
                or type(pair.manifest) is not dict):
            raise ValueError("P075_INVALID_PAIR_SHAPE")
        rows = pair.chunk.get("bars")
        if type(rows) is not list or not rows:
            raise ValueError("P075_INVALID_CHUNK_BARS")
        try:
            batch = NativeFXBatch(
                symbol=proposal.symbol, interval=proposal.interval,
                exchange_timezone=ZONE,
                time_reference=_axis(proposal.interval),
                closed_bars=tuple(NativeFXBar(**r) for r in rows),
                incomplete_excluded=0,
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError("P075_UNDECODABLE_CHUNK") from exc
        rebuilt = _make_pair(
            proposal, batch, prior, pair_count=i,
            shard_capacity=shard_capacity, now_utc=now_utc,
        )
        if rebuilt != pair:
            raise ValueError("P075_IMMUTABLE_V2_SHA_OR_PARENT_MISMATCH")
        prior = rebuilt
    computed_tail = (
        proposal.proposed_anchor_sha256 if prior is None
        else prior.manifest_sha256
    )
    if computed_tail != expected_v2_tip_sha256:
        raise ValueError("P075_V2_TIP_ROLLBACK_OR_FORK")
    return V2ReadOnlyAudit(
        status="OFFLINE_CHAIN_RECOMPUTED_NO_EXTERNAL_WITNESS",
        pair_count=len(pairs),
        shard_count=0 if not pairs else (
            (len(pairs) - 1) // shard_capacity + 1
        ),
        latest_manifest_sha256=computed_tail,
        last_native_open_label=(
            proposal.legacy_latest_open_label if prior is None
            else prior.manifest["last_native_open_label"]
        ),
        total_native_bars=(
            0 if prior is None else prior.manifest["total_native_bars"]
        ),
        complete_supplied_chain_sha_verified=True,
    )


def plan_v2_append(
    proposal: NativeV2ShardProposal, legacy: NativeArchiveState, *,
    expected_v1_manifest_sha256: str,
    history: tuple[V2SealedPair, ...],
    expected_history_tip_sha256: str,
    batch: NativeFXBatch,
    now_utc: datetime,
    shard_capacity: int = MAX_PAIRS_PER_SHARD,
) -> V2SealedPair:
    """Pure candidate construction, never a Drive append or owner approval."""
    audit_v2_chain(
        proposal, legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
        pairs=history, expected_v2_tip_sha256=expected_history_tip_sha256,
        now_utc=now_utc, shard_capacity=shard_capacity,
    )
    return _make_pair(
        proposal, batch,
        prior=history[-1] if history else None,
        pair_count=len(history), shard_capacity=shard_capacity,
        now_utc=now_utc,
    )
