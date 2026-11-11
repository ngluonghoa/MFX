"""A04/P0.76: OFFLINE-ONLY monotonic native V2 witness *draft* protocol.

A hash stored beside its data is NOT an external anti-rollback witness.
Here, the expected witness SHA is CALLER-SELECTED, not authenticated.
These functions model necessary consistency checks ONLY: no trusted
key, signed checkpoint, persistence, Google Drive, price or broker calls.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from mfx_cache.td_m5_codec import digest
from tools.mfx_native_htf_drive_seal import NativeArchiveState
from tools.mfx_native_shard_v2_design import (
    NativeV2ShardProposal, verify_native_v2_proposal,
)
from tools.mfx_native_v2_shard_chain import (
    MAX_PAIRS_PER_SHARD, V2SealedPair, audit_v2_chain,
)

SCHEMA = "MFX_A04_P76_NATIVE_V2_WITNESS_DRAFT_V1"
STATUS = "OFFLINE_CANDIDATE_UNATTESTED_NO_ROLLBACK_AUTHORITY"
LOWER_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class NativeV2WitnessDraft:
    schema: str
    status: str
    symbol: str
    interval: str
    v1_tip_manifest_sha256: str
    v2_root_anchor_sha256: str
    shard_capacity: int
    witness_generation: int
    committed_v2_pairs: int
    last_native_open_label: str
    claimed_v2_tip_sha256: str
    parent_witness_sha256: str | None
    independent_external_attestation_verified: bool = False
    live_activation_authorized: bool = False
    google_drive_writes: int = 0
    provider_requests: int = 0
    broker_orders: int = 0


@dataclass(frozen=True, slots=True)
class NativeV2WitnessReadback:
    status: str
    verified_full_supplied_chain_pairs: int
    caller_expected_digest_matches: bool
    independently_authenticated: bool = False
    durable_anti_rollback_verified: bool = False
    google_drive_writes: int = 0
    broker_orders: int = 0


def _is_sha(value: Any) -> bool:
    return (type(value) is str and len(value) == 64
            and all(x in LOWER_HEX for x in value))


def witness_sha256(record: NativeV2WitnessDraft) -> str:
    """Canonical draft SHA; no signature, notarization or trust semantics."""
    if type(record) is not NativeV2WitnessDraft:
        raise ValueError("P076_WITNESS_TYPE_REQUIRED")
    return digest(asdict(record))


def _context(
    proposal: NativeV2ShardProposal, legacy: NativeArchiveState, *,
    expected_v1_manifest_sha256: str,
) -> None:
    verify_native_v2_proposal(
        proposal, legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
    )
    if (proposal.legacy_remaining_append_pairs != 0
            or proposal.awaiting_legacy_full_256):
        raise ValueError("P076_ONLY_SYNTHETIC_FULL_V1_HANDOFF")


def _build(
    proposal: NativeV2ShardProposal, *,
    shard_capacity: int, generation: int, pair_count: int,
    last_label: str, tip_sha: str, parent_sha: str | None,
) -> NativeV2WitnessDraft:
    return NativeV2WitnessDraft(
        schema=SCHEMA, status=STATUS,
        symbol=proposal.symbol, interval=proposal.interval,
        v1_tip_manifest_sha256=proposal.legacy_latest_manifest_sha256,
        v2_root_anchor_sha256=proposal.proposed_anchor_sha256,
        shard_capacity=shard_capacity,
        witness_generation=generation,
        committed_v2_pairs=pair_count,
        last_native_open_label=last_label,
        claimed_v2_tip_sha256=tip_sha,
        parent_witness_sha256=parent_sha,
    )


def draft_genesis(
    proposal: NativeV2ShardProposal, legacy: NativeArchiveState, *,
    expected_v1_manifest_sha256: str,
    now_utc: datetime,
    shard_capacity: int = MAX_PAIRS_PER_SHARD,
) -> NativeV2WitnessDraft:
    """Return an unauthenticated 0-pair candidate; never publish it."""
    _context(
        proposal, legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
    )
    receipt = audit_v2_chain(
        proposal, legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
        pairs=(), expected_v2_tip_sha256=proposal.proposed_anchor_sha256,
        now_utc=now_utc, shard_capacity=shard_capacity,
    )
    return _build(
        proposal, shard_capacity=shard_capacity, generation=0,
        pair_count=0, last_label=receipt.last_native_open_label,
        tip_sha=receipt.latest_manifest_sha256, parent_sha=None,
    )


def verify_witness_draft(
    record: NativeV2WitnessDraft,
    proposal: NativeV2ShardProposal, legacy: NativeArchiveState, *,
    expected_v1_manifest_sha256: str,
    supplied_history: tuple[V2SealedPair, ...],
    caller_pinned_witness_sha256: str,
    now_utc: datetime,
) -> NativeV2WitnessReadback:
    """Readback with caller pin, NOT a cryptographic external witness.

    If an attacker can replace BOTH the data and caller pin, rollback
    cannot be detected; the returned flags explicitly say as much.
    """
    _context(
        proposal, legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
    )
    if (type(record) is not NativeV2WitnessDraft
            or not _is_sha(caller_pinned_witness_sha256)):
        raise ValueError("P076_INVALID_WITNESS_OR_PIN")
    if (record.schema != SCHEMA or record.status != STATUS
            or record.symbol != proposal.symbol
            or record.interval != proposal.interval
            or record.v1_tip_manifest_sha256 !=
            proposal.legacy_latest_manifest_sha256
            or record.v2_root_anchor_sha256 !=
            proposal.proposed_anchor_sha256
            or type(record.shard_capacity) is not int
            or type(record.witness_generation) is not int
            or type(record.committed_v2_pairs) is not int
            or record.witness_generation < 0
            or record.committed_v2_pairs < record.witness_generation
            or (record.witness_generation == 0) !=
            (record.committed_v2_pairs == 0)
            or (record.witness_generation == 0) !=
            (record.parent_witness_sha256 is None)
            or (record.parent_witness_sha256 is not None
                and not _is_sha(record.parent_witness_sha256))
            or record.independent_external_attestation_verified is not False
            or record.live_activation_authorized is not False
            or record.google_drive_writes != 0
            or record.provider_requests != 0
            or record.broker_orders != 0):
        raise ValueError("P076_FORGED_OR_INVALID_WITNESS_METADATA")
    if witness_sha256(record) != caller_pinned_witness_sha256:
        raise ValueError("P076_CALLER_PIN_MISMATCH")
    if type(supplied_history) is not tuple or (
            len(supplied_history) != record.committed_v2_pairs):
        raise ValueError("P076_SUPPLIED_HISTORY_COUNT_MISMATCH")
    receipt = audit_v2_chain(
        proposal, legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
        pairs=supplied_history,
        expected_v2_tip_sha256=record.claimed_v2_tip_sha256,
        now_utc=now_utc,
        shard_capacity=record.shard_capacity,
    )
    if (receipt.last_native_open_label != record.last_native_open_label
            or receipt.pair_count != record.committed_v2_pairs
            or receipt.complete_supplied_chain_sha_verified is not True):
        raise ValueError("P076_DRAFT_OR_HISTORY_MISMATCH")
    return NativeV2WitnessReadback(
        status="CALLER_PIN_MATCHES_BUT_NO_EXTERNAL_ATTESTATION",
        verified_full_supplied_chain_pairs=receipt.pair_count,
        caller_expected_digest_matches=True,
    )


def draft_next_witness(
    previous: NativeV2WitnessDraft,
    proposal: NativeV2ShardProposal, legacy: NativeArchiveState, *,
    expected_v1_manifest_sha256: str,
    caller_pinned_previous_witness_sha256: str,
    extended_history: tuple[V2SealedPair, ...],
    now_utc: datetime,
) -> NativeV2WitnessDraft:
    """Plan forward-only step; recheck the FULL prior-prefix and new chain."""
    if type(extended_history) is not tuple:
        raise ValueError("P076_HISTORY_MUST_BE_TUPLE")
    if type(previous) is not NativeV2WitnessDraft:
        raise ValueError("P076_PREVIOUS_WITNESS_REQUIRED")
    old_count = previous.committed_v2_pairs
    verify_witness_draft(
        previous, proposal, legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
        supplied_history=extended_history[:old_count],
        caller_pinned_witness_sha256=caller_pinned_previous_witness_sha256,
        now_utc=now_utc,
    )
    if not old_count < len(extended_history):
        raise ValueError("P076_NON_MONOTONIC_WITNESS_UPDATE")
    current_tip = extended_history[-1].manifest_sha256
    receipt = audit_v2_chain(
        proposal, legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
        pairs=extended_history,
        expected_v2_tip_sha256=current_tip,
        now_utc=now_utc, shard_capacity=previous.shard_capacity,
    )
    if receipt.last_native_open_label <= previous.last_native_open_label:
        raise ValueError("P076_WITNESS_NATIVE_TIME_REGRESSION")
    return _build(
        proposal, shard_capacity=previous.shard_capacity,
        generation=previous.witness_generation + 1,
        pair_count=len(extended_history),
        last_label=receipt.last_native_open_label,
        tip_sha=receipt.latest_manifest_sha256,
        parent_sha=witness_sha256(previous),
    )
