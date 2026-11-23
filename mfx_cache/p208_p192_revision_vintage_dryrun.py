"""P0.208: prepare an immutable, disjoint revised D1 *vintage proposal* in RAM.

Owner approved PREPARATION ONLY. This module has no Drive store, file writer,
network call, vendor fetch or broker. The proposed object identifiers and
row hashes are PRIVATE REVIEW OUTLINES, not persisted chunk/manifest objects
or permission to store/approve revised Forex source data. The P192 original
18-Nov source and the P207 memory-only fork are unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mfx_cache.native_d1_epoch_20261118 import PREFIX as P192_PREFIX
from mfx_cache.native_d1_fresh_epoch import PREFIX as P171_PREFIX
from mfx_cache.p207_p192_d1_disjoint_research_fork import (
    PrivateD1ResearchFork, STATUS as P207_STATUS,
    verify_p192_disjoint_research_fork,
)
from mfx_cache.native_d1_epoch_20261118 import FreshEpochState
from mfx_cache.native_fx_htf import NativeFXBatch
from mfx_cache.td_m5_codec import digest
from datetime import datetime

VERSION = "MFX_P208_P192_SEPARATE_REVISED_D1_VINTAGE_DRYRUN_V1"
STATUS = "SEPARATE_REVISED_D1_VINTAGE_PROPOSED_NOT_PERSISTED"
PREFIX = "MFX_P208_EURUSD_D1_20261118_REVISED_VINTAGE_REVIEW_ONLY_V1_"
CHUNK_SCHEMA = "MFX_P208_REVISED_D1_VINTAGE_CHUNK_OUTLINE_V1"
MANIFEST_SCHEMA = "MFX_P208_REVISED_D1_VINTAGE_MANIFEST_OUTLINE_V1"
NO_SIGNAL = "NO_SIGNAL"
REQUIRED_LABEL = "2026-11-18"


def _sha(s: Any) -> bool:
    return (type(s) is str and len(s) == 64
            and all(c in "0123456789abcdef" for c in s))


def _proposal_name(kind: str, last_label: str, content_sha: str) -> str:
    if (kind not in ("chunk", "manifest")
            or type(last_label) is not str
            or not _sha(content_sha)
            or len(last_label) != 10
            or last_label[4] != "-" or last_label[7] != "-"):
        raise ValueError("P208_PRIVATE_OUTLINE_NAME_INPUT_INVALID")
    return (PREFIX + kind + "_" + last_label.replace("-", "") + "_"
            + content_sha + ".json")


@dataclass(frozen=True, slots=True, repr=False)
class PrivateRevisedD1VintageProposal:
    """All SHA and source labels are PRIVATE, never emitted in public logs."""

    version: str
    status: str
    proposed_namespace: str
    canonical_p192_source_root_sha256: str
    original_18nov_native_bar_sha256: str
    proposed_revised_18nov_bar_sha256: str
    source_observed_runner_utc: str
    candidate_row_index: tuple[tuple[str, str], ...] = field(repr=False)
    proposed_chunk_outline_sha256: str
    proposed_chunk_outline_name: str
    proposed_manifest_outline_sha256: str
    proposed_manifest_outline_name: str
    proposal_fingerprint_sha256: str
    source_admission: bool = False
    source_first_known_verified: bool = False
    owner_canonical_revision_approved: bool = False
    vendor_retention_rights_verified: bool = False
    historical_asof_rewrite_allowed: bool = False
    drive_namespace_allocated: bool = False
    may_write_drive: bool = False
    may_select_as_active_d1: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    provider_requests_added: int = 0
    drive_reads_added: int = 0
    drive_writes: int = 0
    broker_orders: int = 0

    def public_summary(self) -> dict[str, Any]:
        """Redacted one-line receipt, with NO private prices, date or hashes."""
        return {
            "schema": VERSION,
            "status": STATUS,
            "separate_namespace_design_only": True,
            "private_proposal_rows": len(self.candidate_row_index),
            "private_later_closed_rows": len(self.candidate_row_index) - 1,
            "original_p192_sha_preserved": True,
            "source_admission": False,
            "source_first_known_verified": False,
            "owner_canonical_revision_approved": False,
            "vendor_retention_rights_verified": False,
            "historical_asof_rewrite_allowed": False,
            "drive_namespace_allocated": False,
            "may_write_drive": False,
            "may_select_as_active_d1": False,
            "may_publish_buy_sell": False,
            "may_trade": False,
            "provider_requests_added": 0,
            "drive_reads_added": 0,
            "drive_writes": 0,
            "broker_orders": 0,
            "action": NO_SIGNAL,
        }


def prepare_disjoint_p192_revision_vintage(
    *, fork: PrivateD1ResearchFork,
    state: FreshEpochState, refetched: NativeFXBatch,
    validated_review: dict[str, Any], now_utc: datetime,
) -> PrivateRevisedD1VintageProposal:
    """Dry-run immutable *outline*; NEVER materializes source objects in Drive."""
    if type(fork) is not PrivateD1ResearchFork:
        raise TypeError("P208_EXACT_P207_PRIVATE_FORK_REQUIRED")
    verify_p192_disjoint_research_fork(
        fork, state=state, refetched=refetched,
        validated_review=validated_review, now_utc=now_utc,
    )
    if (fork.status != P207_STATUS
            or fork.parent_source_epoch != "P192_D1_FRESH_20261118"
            or fork.owner_canonical_revision_approved
            or fork.source_account_rights_verified
            or fork.publisher_first_known_verified
            or fork.historical_asof_rewrite_allowed
            or fork.may_write_d1 or fork.may_write_drive
            or fork.may_publish_buy_sell or fork.may_trade
            or fork.drive_writes or fork.broker_orders
            or fork.additional_vendor_requests or fork.additional_drive_reads):
        raise ValueError("P208_ONLY_UNAPPROVED_P207_PRIVATE_SOURCE_FORK")
    if (PREFIX.startswith(P192_PREFIX) or PREFIX.startswith(P171_PREFIX)
            or P192_PREFIX.startswith(PREFIX) or P171_PREFIX.startswith(PREFIX)
            or not PREFIX.endswith("REVIEW_ONLY_V1_")):
        raise ValueError("P208_PROPOSED_NAMESPACE_OVERLAPS_CANONICAL")
    original = state.last_manifest
    if (type(original) is not dict
            or original.get("last_native_open_label") != REQUIRED_LABEL
            or original.get("total_closed_bars") != 1
            or fork.original_manifest_sha256 != digest(original)):
        raise ValueError("P208_CANONICAL_PARENT_NOT_SINGLE_SEALED_NOV18")
    rows = fork.private_source_bars
    if (len(rows) < 1 or len(rows) > 120
            or rows[0].native_open_label != REQUIRED_LABEL
            or rows[0].sha256() != fork.revised_18nov_bar_sha256
            or fork.revised_18nov_bar_sha256 ==
            fork.original_18nov_bar_sha256):
        raise ValueError("P208_REVISED_18NOV_SOURCE_NOT_PROVEN")
    row_index = tuple((row.native_open_label, row.sha256()) for row in rows)
    if (len({label for label, _ in row_index}) != len(row_index)
            or tuple(sorted(row_index)) != row_index
            or any(not _sha(rowsha) for _, rowsha in row_index)):
        raise ValueError("P208_EXACT_ORDERED_CLOSED_SOURCE_ROWS_REQUIRED")

    # Outlines intentionally hold only SHA identities, never raw OHLC
    # and never a write-ready P192 or P208 source payload.
    chunk_outline = {
        "schema": CHUNK_SCHEMA,
        "parent_canonical_p192_manifest_sha256": fork.original_manifest_sha256,
        "original_18nov_bar_sha256": fork.original_18nov_bar_sha256,
        "revised_18nov_bar_sha256": fork.revised_18nov_bar_sha256,
        "source_observed_utc_not_publisher_first_known":
            fork.runner_observed_utc,
        "row_index": row_index,
        "source_admission": False,
        "may_write_drive": False,
    }
    chunk_sha = digest(chunk_outline)
    chunk_name = _proposal_name("chunk", row_index[-1][0], chunk_sha)
    manifest_outline = {
        "schema": MANIFEST_SCHEMA,
        "separate_proposed_namespace": PREFIX,
        "parent_canonical_p192_manifest_sha256": fork.original_manifest_sha256,
        "proposed_chunk_outline_sha256": chunk_sha,
        "proposed_chunk_outline_name": chunk_name,
        "source_fork_private_digest_sha256": fork.fork_digest_sha256,
        "source_first_known_verified": False,
        "source_account_rights_verified": False,
        "owner_canonical_revision_approved": False,
        "drive_namespace_allocated": False,
        "source_admission": False,
        "may_select_as_active_d1": False,
        "may_write_drive": False,
        "may_publish_buy_sell": False,
    }
    manifest_sha = digest(manifest_outline)
    manifest_name = _proposal_name("manifest", row_index[-1][0], manifest_sha)
    fingerprint = digest({
        "schema": VERSION, "status": STATUS,
        "namespace": PREFIX, "chunk_outline_sha256": chunk_sha,
        "manifest_outline_sha256": manifest_sha,
        "canonical_p192_manifest_sha256": fork.original_manifest_sha256,
        "p207_fork_sha256": fork.fork_digest_sha256,
        "may_write_drive": False, "source_admission": False,
    })
    return PrivateRevisedD1VintageProposal(
        version=VERSION, status=STATUS, proposed_namespace=PREFIX,
        canonical_p192_source_root_sha256=fork.original_manifest_sha256,
        original_18nov_native_bar_sha256=fork.original_18nov_bar_sha256,
        proposed_revised_18nov_bar_sha256=fork.revised_18nov_bar_sha256,
        source_observed_runner_utc=fork.runner_observed_utc,
        candidate_row_index=row_index,
        proposed_chunk_outline_sha256=chunk_sha,
        proposed_chunk_outline_name=chunk_name,
        proposed_manifest_outline_sha256=manifest_sha,
        proposed_manifest_outline_name=manifest_name,
        proposal_fingerprint_sha256=fingerprint,
    )


def verify_disjoint_p192_revision_vintage(
    proposal: PrivateRevisedD1VintageProposal,
    *, fork: PrivateD1ResearchFork,
    state: FreshEpochState, refetched: NativeFXBatch,
    validated_review: dict[str, Any], now_utc: datetime,
) -> bool:
    """Replay exact input SHA; detect forged authority, dates or outline IDs."""
    if type(proposal) is not PrivateRevisedD1VintageProposal:
        raise TypeError("P208_EXACT_PRIVATE_PROPOSAL_TYPE_REQUIRED")
    expected = prepare_disjoint_p192_revision_vintage(
        fork=fork, state=state, refetched=refetched,
        validated_review=validated_review, now_utc=now_utc,
    )
    if proposal != expected:
        raise ValueError("P208_PROPOSAL_SHA_OR_AUTHORITY_DRIFT")
    return True
