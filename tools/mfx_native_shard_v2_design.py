"""A04/P0.74 -- OFFLINE ONLY native H4/D1 V1 -> V2 shard handoff.

This pure review artifact is NOT a Drive adapter/writer, cannot prove an
independent SHA witness, and never relaxes current V1 256-pair limit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from mfx_cache.native_htf_archive import _name, _scope, check_native_manifest
from mfx_cache.td_m5_codec import digest
from tools.mfx_native_htf_drive_seal import MAX_NATIVE_FILES, NativeArchiveState

SCHEMA = "MFX_A04_P74_NATIVE_V2_SHARD_HANDOFF_RESEARCH_V1"
DESIGN_ONLY = "OFFLINE_PROPOSAL_NO_WRITE_OR_ACTIVATION"
SYMBOL = "EUR/USD"
ZONE = "Australia/Sydney"
SHA_CHARS = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class NativeV2ShardProposal:
    schema: str
    status: str
    symbol: str
    interval: str
    legacy_v1_scope: str
    legacy_latest_manifest_name: str
    legacy_latest_manifest_sha256: str
    legacy_latest_open_label: str
    legacy_pairs_verified_by_caller: int
    legacy_remaining_append_pairs: int
    proposed_v2_scope: str
    proposed_shard_number: int
    proposed_anchor_sha256: str
    awaiting_legacy_full_256: bool
    immutable_legacy_history_retained: bool = True
    requires_independent_full_sha_recheck: bool = True
    requires_external_anti_rollback_witness: bool = True
    requires_separate_owner_activation: bool = True
    current_writer_unchanged: bool = True
    estimated_vendor_requests: int = 0
    drive_writes: int = 0
    broker_orders: int = 0


def _sha(value: Any) -> bool:
    return (
        type(value) is str and len(value) == 64
        and all(ch in SHA_CHARS for ch in value)
    )


def propose_native_v2_shard_handoff(
    state: NativeArchiveState, *,
    symbol: str,
    interval: str,
    expected_v1_manifest_sha256: str,
) -> NativeV2ShardProposal:
    """Inert V2 namespace proposal from a *caller-attested* V1 SHA tip.

    Caller must separately prove full V1 historical readback and obtain an
    external independent trusted witness. Those facts cannot be certified
    by a supplied digest or NativeArchiveState dataclass.
    """
    if type(state) is not NativeArchiveState:
        raise ValueError("P074_NATIVE_STATE_REQUIRED")
    if symbol != SYMBOL or interval not in ("4h", "1day"):
        raise ValueError("P074_ONLY_EURUSD_NATIVE_H4_D1")
    if not _sha(expected_v1_manifest_sha256):
        raise ValueError("P074_EXPECTED_V1_SHA_REQUIRED")
    if (type(state.manifest_count) is not int
            or type(state.chunk_count) is not int
            or not 1 <= state.manifest_count <= MAX_NATIVE_FILES
            or state.chunk_count != state.manifest_count
            or type(state.uncommitted_chunk_names) is not tuple
            or state.uncommitted_chunk_names
            or type(state.last_manifest) is not dict
            or type(state.latest_manifest_name) is not str):
        raise ValueError("P074_LEGACY_ARCHIVE_NOT_FULLY_SEALED")
    manifest = state.last_manifest
    check_native_manifest(
        manifest, symbol=symbol, interval=interval, zone=ZONE)
    if manifest["batch_count"] != state.manifest_count:
        raise ValueError("P074_V1_BATCH_COUNT_MISMATCH")
    label = manifest["last_native_open_label"]
    if interval == "4h":
        try:
            parsed = datetime.strptime(label, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise ValueError("P074_NATIVE_H4_OPEN_LABEL_INVALID") from exc
        if (parsed.strftime("%Y-%m-%d %H:%M:%S") != label
                or parsed.hour % 4 or parsed.minute or parsed.second):
            raise ValueError("P074_H4_NOT_UTC_FOUR_HOUR_GRID")
    verified_tip_sha = digest(manifest)
    if verified_tip_sha != expected_v1_manifest_sha256:
        raise ValueError("P074_V1_TIP_SHA_MISMATCH")
    if state.latest_manifest_name != _name(
            "manifest", symbol, interval, label, verified_tip_sha):
        raise ValueError("P074_V1_MANIFEST_NAME_SHA_MISMATCH")
    legacy_scope = _scope(symbol, interval)
    next_scope = legacy_scope.replace("_NATIVE_V1", "_NATIVE_V2_SHARD000001")
    if next_scope == legacy_scope:
        raise ValueError("P074_V2_SCOPE_COLLIDES_WITH_V1")
    remaining = MAX_NATIVE_FILES - state.manifest_count
    anchor = {
        "schema": SCHEMA,
        "symbol": symbol,
        "interval": interval,
        "exchange_timezone": ZONE,
        "price_side": "MID",
        "legacy_scope": legacy_scope,
        "legacy_tip_manifest_name": state.latest_manifest_name,
        "legacy_tip_manifest_sha256": verified_tip_sha,
        "legacy_tip_open_label": label,
        "legacy_pairs": state.manifest_count,
        "v2_namespace": next_scope,
        "v2_shard_number": 1,
        "legacy_history_must_remain_immutable": True,
        "external_witness_required": True,
        "no_live_switch": True,
    }
    return NativeV2ShardProposal(
        schema=SCHEMA,
        status=DESIGN_ONLY,
        symbol=symbol,
        interval=interval,
        legacy_v1_scope=legacy_scope,
        legacy_latest_manifest_name=state.latest_manifest_name,
        legacy_latest_manifest_sha256=verified_tip_sha,
        legacy_latest_open_label=label,
        legacy_pairs_verified_by_caller=state.manifest_count,
        legacy_remaining_append_pairs=remaining,
        proposed_v2_scope=next_scope,
        proposed_shard_number=1,
        proposed_anchor_sha256=digest(anchor),
        awaiting_legacy_full_256=(remaining != 0),
    )


def verify_native_v2_proposal(
    proposal: NativeV2ShardProposal,
    state: NativeArchiveState, *,
    expected_v1_manifest_sha256: str,
) -> None:
    """Recompute exact proposed metadata; still OFFLINE and non-authorizing."""
    if type(proposal) is not NativeV2ShardProposal:
        raise ValueError("P074_PROPOSAL_TYPE")
    expected = propose_native_v2_shard_handoff(
        state, symbol=proposal.symbol, interval=proposal.interval,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256)
    if asdict(expected) != asdict(proposal):
        raise ValueError("P074_PROPOSAL_CHANGED_OR_FORGED")
