"""MFX A04/P0.78: pure, fenced V2 witness CAS/recovery RESEARCH contract.

No trusted authority, signature, Google Drive mutation, lease service,
credentials or broker access is implemented. The 'observed' head is
CALLER-SUPPLIED. Only an external independently authenticated and atomic
service can execute the conditional compare-and-swap described here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tools.mfx_native_htf_drive_seal import NativeArchiveState
from tools.mfx_native_shard_v2_design import NativeV2ShardProposal
from tools.mfx_native_v2_shard_chain import V2SealedPair, audit_v2_chain
from tools.mfx_native_v2_witness_draft import (
    NativeV2WitnessDraft, draft_next_witness, verify_witness_draft,
    witness_sha256,
)

SCHEMA = "MFX_A04_P78_FENCED_WITNESS_CAS_OFFLINE_V1"
STATUS = "PURE_CONDITIONAL_CAS_PROPOSAL_UNAUTHENTICATED"
RECOVERY_STATUSES = frozenset((
    "NO_OBJECTS_PREPARE_NOT_PUBLISHED",
    "EXACT_CHUNK_ORPHAN_MANUAL_REVALIDATION",
    "EXACT_PAIR_UNPUBLISHED_MANUAL_CAS_REVALIDATION",
    "COMMITTED_EXACT_PAIR_READBACK_ONLY",
))
SHA_CHARS = frozenset("0123456789abcdef")


def _sha(value: Any) -> bool:
    return (type(value) is str and len(value) == 64
            and all(c in SHA_CHARS for c in value))


@dataclass(frozen=True, slots=True)
class WitnessAuthorityHead:
    """Caller snapshot. Not a real signed, durable or authenticated head."""

    schema: str
    symbol: str
    interval: str
    epoch: int
    fence_token: int
    generation: int
    witness_sha256: str


@dataclass(frozen=True, slots=True)
class V2FencedCASProposal:
    status: str
    expected_head: WitnessAuthorityHead
    proposed_head: WitnessAuthorityHead
    previous_witness_sha256: str
    next_witness_sha256: str
    next_witness: NativeV2WitnessDraft
    candidate_pair: V2SealedPair
    external_atomic_cas_required: bool = True
    independent_external_authority_verified: bool = False
    live_drive_writer_authorized: bool = False
    real_drive_writes: int = 0
    provider_requests: int = 0
    broker_orders: int = 0


@dataclass(frozen=True, slots=True)
class V2RecoveryAssessment:
    status: str
    observed_chunk_count: int
    observed_manifest_count: int
    manual_authenticated_head_recheck_required: bool = True
    may_auto_publish_manifest: bool = False
    may_auto_advance_witness: bool = False
    real_drive_writes: int = 0
    broker_orders: int = 0


def draft_authority_genesis(
    proposal: NativeV2ShardProposal,
    witness: NativeV2WitnessDraft, *,
    epoch: int,
    initial_fence_token: int,
) -> WitnessAuthorityHead:
    """Make an untrusted genesis snapshot; never an actual external anchor."""
    if (type(witness) is not NativeV2WitnessDraft
            or witness.witness_generation != 0
            or witness.committed_v2_pairs != 0
            or witness.parent_witness_sha256 is not None
            or witness.v2_root_anchor_sha256 !=
            proposal.proposed_anchor_sha256
            or witness.v1_tip_manifest_sha256 !=
            proposal.legacy_latest_manifest_sha256
            or witness.symbol != proposal.symbol
            or witness.interval != proposal.interval
            or type(epoch) is not int or epoch < 1
            or type(initial_fence_token) is not int
            or initial_fence_token < 1):
        raise ValueError("P078_INVALID_UNTRUSTED_GENESIS")
    return WitnessAuthorityHead(
        schema=SCHEMA, symbol=proposal.symbol,
        interval=proposal.interval, epoch=epoch,
        fence_token=initial_fence_token, generation=0,
        witness_sha256=witness_sha256(witness),
    )


def _validate_head(head: WitnessAuthorityHead, *,
                   proposal: NativeV2ShardProposal) -> None:
    if (type(head) is not WitnessAuthorityHead
            or head.schema != SCHEMA or head.symbol != proposal.symbol
            or head.interval != proposal.interval
            or type(head.epoch) is not int or head.epoch < 1
            or type(head.fence_token) is not int or head.fence_token < 1
            or type(head.generation) is not int or head.generation < 0
            or not _sha(head.witness_sha256)):
        raise ValueError("P078_INVALID_UNTRUSTED_AUTHORITY_HEAD")


def prepare_fenced_v2_cas(
    previous_witness: NativeV2WitnessDraft,
    expected_head: WitnessAuthorityHead,
    proposal: NativeV2ShardProposal,
    legacy: NativeArchiveState, *,
    expected_v1_manifest_sha256: str,
    committed_history: tuple[V2SealedPair, ...],
    candidate_pair: V2SealedPair,
    requested_epoch: int,
    allocated_fence_token: int,
    now_utc: datetime,
) -> V2FencedCASProposal:
    """Plan EXACTLY one V2 pair extension, never write any object.

    Fencing token and head are untrusted inputs. A production authority
    must issue non-replayable tokens and atomically CAS an authenticated
    head outside the mutable Drive price-data archive.
    """
    _validate_head(expected_head, proposal=proposal)
    if type(previous_witness) is not NativeV2WitnessDraft:
        raise ValueError("P078_PREVIOUS_WITNESS_REQUIRED")
    if (type(requested_epoch) is not int
            or requested_epoch != expected_head.epoch
            or type(allocated_fence_token) is not int
            or allocated_fence_token <= expected_head.fence_token):
        raise ValueError("P078_STALE_EPOCH_OR_FENCE")
    if (type(committed_history) is not tuple
            or type(candidate_pair) is not V2SealedPair
            or len(committed_history) !=
            previous_witness.committed_v2_pairs
            or expected_head.generation !=
            previous_witness.witness_generation
            or expected_head.witness_sha256 !=
            witness_sha256(previous_witness)):
        raise ValueError("P078_HEAD_OR_HISTORY_NOT_CURRENT")
    verify_witness_draft(
        previous_witness, proposal, legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
        supplied_history=committed_history,
        caller_pinned_witness_sha256=expected_head.witness_sha256,
        now_utc=now_utc,
    )
    next_history = (*committed_history, candidate_pair)
    if type(candidate_pair.manifest) is not dict:
        raise ValueError("P078_CANDIDATE_MANIFEST_TYPE_INVALID")
    audit_v2_chain(
        proposal, legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
        pairs=next_history,
        expected_v2_tip_sha256=candidate_pair.manifest_sha256,
        now_utc=now_utc,
        shard_capacity=previous_witness.shard_capacity,
    )
    next_witness = draft_next_witness(
        previous_witness, proposal, legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
        caller_pinned_previous_witness_sha256=
        expected_head.witness_sha256,
        extended_history=next_history, now_utc=now_utc,
    )
    if (next_witness.witness_generation != expected_head.generation+1
            or next_witness.parent_witness_sha256 !=
            expected_head.witness_sha256
            or next_witness.committed_v2_pairs !=
            len(committed_history)+1):
        raise ValueError("P078_WITNESS_MONOTONICITY_VIOLATION")
    proposed = WitnessAuthorityHead(
        schema=SCHEMA, symbol=expected_head.symbol,
        interval=expected_head.interval, epoch=expected_head.epoch,
        fence_token=allocated_fence_token,
        generation=expected_head.generation+1,
        witness_sha256=witness_sha256(next_witness),
    )
    return V2FencedCASProposal(
        status=STATUS, expected_head=expected_head,
        proposed_head=proposed,
        previous_witness_sha256=expected_head.witness_sha256,
        next_witness_sha256=proposed.witness_sha256,
        next_witness=next_witness,
        candidate_pair=candidate_pair,
    )


def assert_conditional_cas_preconditions(
    prepared: V2FencedCASProposal,
    observed_authenticated_head: WitnessAuthorityHead,
    *,
    externally_allocated_epoch: int,
    externally_current_fence_token: int,
) -> None:
    """Pure guard on a CALLER-supplied snapshot, NOT an atomic CAS.

    Test doubles can use this before an atomic fake-state update. A real
    backend MUST provide atomicity, authenticated identity and freshness.
    """
    if (type(prepared) is not V2FencedCASProposal
            or prepared.status != STATUS
            or prepared.external_atomic_cas_required is not True
            or prepared.independent_external_authority_verified is not False
            or prepared.live_drive_writer_authorized is not False
            or prepared.real_drive_writes != 0
            or prepared.provider_requests != 0
            or prepared.broker_orders != 0
            or type(prepared.next_witness) is not NativeV2WitnessDraft
            or witness_sha256(prepared.next_witness) !=
            prepared.next_witness_sha256
            or prepared.previous_witness_sha256 !=
            prepared.expected_head.witness_sha256
            or prepared.proposed_head.witness_sha256 !=
            prepared.next_witness_sha256):
        raise ValueError("P078_FORGED_OR_INVALID_CAS_PROPOSAL")
    # This is intentionally an EXACT compare, not >= or a fresh
    # re-read from a mutable caller variable.
    if (type(observed_authenticated_head) is not WitnessAuthorityHead
            or observed_authenticated_head != prepared.expected_head):
        raise ValueError("P078_CAS_CONFLICT_EXPECTED_HEAD_CHANGED")
    if (type(externally_allocated_epoch) is not int
            or externally_allocated_epoch !=
            prepared.expected_head.epoch
            or type(externally_current_fence_token) is not int
            or externally_current_fence_token !=
            prepared.proposed_head.fence_token
            or externally_current_fence_token <=
            prepared.expected_head.fence_token):
        raise ValueError("P078_FENCE_REVOKED_OR_EPOCH_CHANGED")
    if (prepared.proposed_head.schema != SCHEMA
            or prepared.proposed_head.symbol !=
            prepared.expected_head.symbol
            or prepared.proposed_head.interval !=
            prepared.expected_head.interval
            or prepared.proposed_head.epoch !=
            prepared.expected_head.epoch
            or prepared.proposed_head.generation !=
            prepared.expected_head.generation+1
            or prepared.next_witness.witness_generation !=
            prepared.proposed_head.generation
            or prepared.next_witness.parent_witness_sha256 !=
            prepared.expected_head.witness_sha256):
        raise ValueError("P078_CAS_EPOCH_OR_GENERATION_INVALID")


def assess_recovery_after_interruption(
    prepared: V2FencedCASProposal, *,
    observed_chunk_names: tuple[str, ...],
    observed_manifest_names: tuple[str, ...],
    current_head: WitnessAuthorityHead,
) -> V2RecoveryAssessment:
    """Classify only exact in-flight objects, never repair/write/activate.

    Recovery after concurrent, missing or altered objects requires
    authority-verified readback and human-controlled quarantine.
    """
    if (type(prepared) is not V2FencedCASProposal
            or type(observed_chunk_names) is not tuple
            or type(observed_manifest_names) is not tuple
            or any(type(n) is not str for n in
                   (*observed_chunk_names, *observed_manifest_names))
            or type(current_head) is not WitnessAuthorityHead):
        raise ValueError("P078_RECOVERY_INPUT_INVALID")
    if (len(observed_chunk_names) > 1
            or len(observed_manifest_names) > 1
            or any(n != prepared.candidate_pair.chunk_name
                   for n in observed_chunk_names)
            or any(n != prepared.candidate_pair.manifest_name
                   for n in observed_manifest_names)):
        raise ValueError("P078_UNKNOWN_OR_FORKED_OBJECT_QUARANTINE")
    chunk_count = len(observed_chunk_names)
    manifest_count = len(observed_manifest_names)
    if manifest_count and not chunk_count:
        raise ValueError("P078_MANIFEST_WITHOUT_CHUNK_QUARANTINE")
    if current_head not in (prepared.expected_head,prepared.proposed_head):
        raise ValueError("P078_UNRECOGNIZED_AUTHORITY_HEAD_QUARANTINE")
    if current_head == prepared.proposed_head:
        if (chunk_count,manifest_count)!=(1,1):
            raise ValueError("P078_WITNESS_ADVANCED_BEFORE_PAIR_COMPLETE")
        status="COMMITTED_EXACT_PAIR_READBACK_ONLY"
    elif manifest_count:
        status="EXACT_PAIR_UNPUBLISHED_MANUAL_CAS_REVALIDATION"
    elif chunk_count:
        status="EXACT_CHUNK_ORPHAN_MANUAL_REVALIDATION"
    else:
        status="NO_OBJECTS_PREPARE_NOT_PUBLISHED"
    assert status in RECOVERY_STATUSES
    return V2RecoveryAssessment(
        status=status,
        observed_chunk_count=chunk_count,
        observed_manifest_count=manifest_count,
    )
