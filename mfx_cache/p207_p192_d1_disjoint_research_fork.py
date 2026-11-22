"""P0.207: in-memory-only disjoint P192 revised-D1 research fork.

A refetched 18-Nov numeric OHLC revision can be inspected *alongside*
later truly closed Sydney D1 rows without overwriting the SHA-sealed source.
Caller supplies SAME already fetched batch and P204 private review; this code
has no vendor, Drive, broker, output/commit or scheduler entrypoint.
A research fork cannot establish publisher first-known, licensed rights, or
authorise any canonical/historical-as-of BUY/SELL decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from mfx_cache.native_d1_epoch_20261118 import (
    FreshEpochState, INCIDENT, PUBLICATION_BUFFER, _source_batch,
)
from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.p204_p192_d1_revision_review import (
    validate_p192_revision_review,
)
from mfx_cache.td_m5_codec import digest

VERSION = "MFX_P207_P192_DISJOINT_REVISED_D1_PRIVATE_RESEARCH_FORK_V1"
STATUS = "IN_MEMORY_ONLY_REVISED_VINTAGE_NOT_SOURCE_ADMITTED"
FIRST_LABEL = INCIDENT
UTC = timedelta(0)


def _utc(value: Any) -> datetime:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != UTC):
        raise ValueError("P207_UTC_RUNNER_OBSERVATION_REQUIRED")
    return value


@dataclass(frozen=True, slots=True, repr=False)
class PrivateD1ResearchFork:
    version: str
    status: str
    parent_source_epoch: str
    original_manifest_sha256: str
    original_18nov_bar_sha256: str
    revised_18nov_bar_sha256: str
    runner_observed_utc: str
    private_source_bars: tuple[NativeFXBar, ...] = field(repr=False)
    private_chain_sha256: tuple[str, ...] = field(repr=False)
    fork_digest_sha256: str
    owner_canonical_revision_approved: bool = False
    source_account_rights_verified: bool = False
    publisher_first_known_verified: bool = False
    historical_asof_rewrite_allowed: bool = False
    may_write_d1: bool = False
    may_write_drive: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    additional_vendor_requests: int = 0
    additional_drive_reads: int = 0
    drive_writes: int = 0
    broker_orders: int = 0

    def public_summary(self) -> dict[str, Any]:
        """Safe production receipt: no raw prices, dates, SHA or runner clock."""
        return {
            "schema": VERSION, "status": STATUS,
            "revision_numeric_ohlc_overlap_under_review": 1,
            "private_research_d1_rows": len(self.private_source_bars),
            "private_later_closed_d1_rows": len(self.private_source_bars)-1,
            "original_p192_sha_preserved": True,
            "research_fork_persisted": False,
            "publisher_first_known_verified": False,
            "source_account_rights_verified": False,
            "owner_canonical_revision_approved": False,
            "historical_asof_rewrite_allowed": False,
            "may_write_d1": False, "may_write_drive": False,
            "may_publish_buy_sell": False, "may_trade": False,
            "additional_vendor_requests": 0,
            "additional_drive_reads": 0, "drive_writes": 0,
            "broker_orders": 0, "action": "NO_SIGNAL",
        }


def build_p192_disjoint_research_fork(
    *, state: FreshEpochState, refetched: NativeFXBatch,
    validated_review: dict[str, Any], now_utc: datetime,
) -> PrivateD1ResearchFork:
    """Private revised 18-Nov + later closed D1, not a cache/source admission."""
    now = _utc(now_utc)
    review = validate_p192_revision_review(validated_review)
    if (type(state) is not FreshEpochState
            or state.manifests != 1 or state.chunks != 1
            or state.orphan_chunk is not None
            or type(state.last_manifest) is not dict):
        raise ValueError("P207_SINGLE_IMMUTABLE_P192_SOURCE_ROOT_REQUIRED")
    original = state.last_manifest
    if (digest(original) != review["original_epoch_manifest_sha256"]
            or original.get("last_native_open_label") != FIRST_LABEL
            or original.get("owner_rebaseline_date") != FIRST_LABEL
            or original.get("total_closed_bars") != 1
            or original.get("publisher_first_known_verified") is not False
            or original.get("may_publish_buy_sell") is not False):
        raise ValueError("P207_P192_ORIGINAL_MANIFEST_SHA_OR_GATE_CHANGED")
    original_index = original.get("recent_native_bar_index")
    pair = review["private_revised_source_sha_pair"]
    if (type(original_index) is not list or len(original_index) != 1
            or type(original_index[0]) is not dict
            or original_index[0].get("label") != FIRST_LABEL
            or original_index[0].get("sha256") != pair["stored_sha256"]
            or pair["label"] != FIRST_LABEL
            or review["origin_v1_manifest_sha256"] !=
            original.get("origin_v1_manifest_sha256")
            or review["runner_observed_utc"] != now.isoformat()):
        raise ValueError("P207_P204_REVIEW_DOES_NOT_MATCH_ORIGINAL_SOURCE")
    _source_batch(refetched)
    if type(refetched.closed_bars) is not tuple:
        raise ValueError("P207_TYPED_NATIVE_CLOSED_SOURCE_REQUIRED")
    allowed_last_label = (
        now-PUBLICATION_BUFFER
    ).astimezone(ZoneInfo("Australia/Sydney")).date()-timedelta(days=1)
    if any(date.fromisoformat(bar.native_open_label) > allowed_last_label
           for bar in refetched.closed_bars):
        raise ValueError("P207_UNCLOSED_OR_UNPUBLISHED_D1_ROW")
    rows = tuple(bar for bar in refetched.closed_bars
                 if bar.native_open_label >= FIRST_LABEL)
    if (not rows or len(rows) > 120
            or rows[0].native_open_label != FIRST_LABEL
            or any(type(bar) is not NativeFXBar for bar in rows)
            or [b.native_open_label for b in rows] !=
            sorted({b.native_open_label for b in rows})
            or rows[0].sha256() != pair["refetched_sha256"]
            or rows[0].sha256() == pair["stored_sha256"]):
        raise ValueError("P207_EXACT_CHANGED_18NOV_AND_ORDERED_LATER_ROWS")
    parent = review["original_epoch_manifest_sha256"]
    chain: list[str] = []
    for bar in rows:
        parent = digest({
            "schema": VERSION,
            "previous_sha256": parent,
            "observed_utc": now.isoformat(),
            "source_label": bar.native_open_label,
            "provider_source_row_sha256": bar.sha256(),
            "source_admitted": False,
        })
        chain.append(parent)
    fork_digest = digest({
        "schema": VERSION, "source_admitted": False,
        "original_manifest_sha256": review["original_epoch_manifest_sha256"],
        "original_bar_sha256": pair["stored_sha256"],
        "revised_bar_sha256": pair["refetched_sha256"],
        "runner_observed_utc": now.isoformat(),
        "private_chain_sha256": chain,
    })
    return PrivateD1ResearchFork(
        version=VERSION, status=STATUS,
        parent_source_epoch=review["source_epoch"],
        original_manifest_sha256=review["original_epoch_manifest_sha256"],
        original_18nov_bar_sha256=pair["stored_sha256"],
        revised_18nov_bar_sha256=pair["refetched_sha256"],
        runner_observed_utc=now.isoformat(),
        private_source_bars=rows,
        private_chain_sha256=tuple(chain),
        fork_digest_sha256=fork_digest,
    )


def verify_p192_disjoint_research_fork(
    receipt: PrivateD1ResearchFork, *, state: FreshEpochState,
    refetched: NativeFXBatch, validated_review: dict[str, Any],
    now_utc: datetime,
) -> bool:
    """Deterministic full source replay; a content SHA is not a signature."""
    if type(receipt) is not PrivateD1ResearchFork:
        raise TypeError("P207_TYPED_PRIVATE_FORK_RECEIPT_REQUIRED")
    expected = build_p192_disjoint_research_fork(
        state=state, refetched=refetched,
        validated_review=validated_review, now_utc=now_utc,
    )
    if receipt != expected:
        raise ValueError("P207_FORK_PROVENANCE_OR_PERMISSION_DRIFT")
    return True
