"""A04/P0.85: root + reviewed-checkpoint anchored full bounded M5 SHA audit.

Pure store-protocol adapter. Existing P0.66 scans ALL raw M5 chunks and
derived bars when <=256. This adds independently GitHub-pinned genesis and
31-pair checkpoints, bounded enumeration and before/after readback.
No network, Drive mutation, provider request, broker action or live authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from mfx_cache.td_m5_codec import digest
from mfx_cache.v2_batch_commit import _name, _validate_manifest
from tools.mfx_m5_rolling_manifest_audit import (
    ROOT_UTC, ROOT_MANIFEST_SHA256,
)
from tools.run_mfx_m5_h4_live_parity_audit import (
    MAX_M5_ARCHIVE_HOURS, _m5_archive,
)

SCHEMA = "MFX_A04_P85_ROOT_CHECKPOINT_FULL_M5_SHA_V1"
REVIEWED_CHECKPOINT_UTC = "2026-11-12T00:00:00+00:00"
REVIEWED_CHECKPOINT_SHA256 = (
    "9e27346ebcef2d292f0ce519acffd46d7c01e45b1e31906e31bbda12f38fc629"
)
REVIEWED_CHECKPOINT_PAIRS = 31


def _hex_sha(value: str) -> bool:
    return (type(value) is str and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def audit_root_checkpoint_full_m5(
    store: Any, *, now_utc: datetime,
    root_hour_utc: str = ROOT_UTC,
    root_sha256: str = ROOT_MANIFEST_SHA256,
    checkpoint_hour_utc: str = REVIEWED_CHECKPOINT_UTC,
    checkpoint_sha256: str = REVIEWED_CHECKPOINT_SHA256,
    checkpoint_pairs: int = REVIEWED_CHECKPOINT_PAIRS,
) -> dict[str, Any]:
    """Verify every bounded M5 chunk under two Git-reviewed SHA anchors.

    Customized anchors are solely for synthetic tests. A production
    attestation MUST use the source-controlled default review decisions.
    """
    if (type(now_utc) is not datetime or now_utc.tzinfo is None
            or now_utc.utcoffset() != timedelta(0)
            or type(root_hour_utc) is not str
            or type(checkpoint_hour_utc) is not str
            or not _hex_sha(root_sha256)
            or not _hex_sha(checkpoint_sha256)
            or type(checkpoint_pairs) is not int
            or not 1 <= checkpoint_pairs <= MAX_M5_ARCHIVE_HOURS):
        raise ValueError("P085_PINNED_SHA_AND_UTC_REQUIRED")
    try:
        first_hour = datetime.fromisoformat(root_hour_utc)
        anchor_hour = datetime.fromisoformat(checkpoint_hour_utc)
    except ValueError as exc:
        raise ValueError("P085_INVALID_PINNED_HOURS") from exc
    if (first_hour.tzinfo is None or first_hour.utcoffset() != timedelta(0)
            or anchor_hour.tzinfo is None
            or anchor_hour.utcoffset() != timedelta(0)
            or first_hour.minute or first_hour.second or first_hour.microsecond
            or anchor_hour.minute or anchor_hour.second or anchor_hour.microsecond
            or anchor_hour < first_hour
            or (anchor_hour - first_hour) % timedelta(hours=1)):
        raise ValueError("P085_PINNED_UTC_GRID_REQUIRED")

    names = tuple(sorted(store.list_names("manifest")))
    chunks = tuple(sorted(store.list_names("chunk")))
    if (len(names) < checkpoint_pairs
            or len(names) > MAX_M5_ARCHIVE_HOURS
            or len(names) != len(chunks)
            or len(names) != len(set(names))
            or len(chunks) != len(set(chunks))):
        raise ValueError("P085_ARCHIVE_ROLLBACK_OR_FORK_OR_BOUND")

    root_name = _name("manifest", root_hour_utc, root_sha256)
    checkpoint_name = _name("manifest", checkpoint_hour_utc, checkpoint_sha256)
    if (names[0] != root_name
            or names[checkpoint_pairs-1] != checkpoint_name):
        raise ValueError("P085_REVIEWED_ROOT_OR_CHECKPOINT_NOT_PRESENT")

    first = store.read("manifest", root_name)
    anchor = store.read("manifest", checkpoint_name)
    if (_validate_manifest(root_name, first) != root_hour_utc
            or digest(first) != root_sha256
            or _validate_manifest(checkpoint_name, anchor) != checkpoint_hour_utc
            or digest(anchor) != checkpoint_sha256
            or anchor["total_batches"] != checkpoint_pairs
            or anchor["total_closed_m5"] != 12*checkpoint_pairs):
        raise ValueError("P085_REVIEWED_SHA_ANCHOR_MISMATCH")

    bars, receipt = _m5_archive(store, now_utc=now_utc)
    head_name = names[-1]
    head = store.read("manifest", head_name)
    if (not receipt["m5_full_bounded_chain_verified"]
            or receipt["m5_manifest_chunk_pairs_full_sha_verified"] != len(names)
            or receipt["m5_closed_bars"] != len(bars)
            or receipt["m5_latest_manifest_sha256"] != digest(head)
            or head["total_batches"] != len(names)
            or digest(store.read("manifest", root_name)) != root_sha256
            or digest(store.read("manifest", checkpoint_name)) != checkpoint_sha256
            or digest(store.read("manifest", head_name)) != digest(head)
            or tuple(sorted(store.list_names("manifest"))) != names
            or tuple(sorted(store.list_names("chunk"))) != chunks):
        raise ValueError("P085_SNAPSHOT_CHANGED_DURING_READONLY_AUDIT")

    return {
        "schema": SCHEMA,
        "status": "FULL_BOUNDED_RAW_SHA_AND_TWO_GIT_PINS_VERIFIED",
        "root_hour_utc": root_hour_utc,
        "root_manifest_sha256": root_sha256,
        "checkpoint_hour_utc": checkpoint_hour_utc,
        "checkpoint_manifest_sha256": checkpoint_sha256,
        "checkpoint_pairs": checkpoint_pairs,
        "total_manifest_chunk_pairs_full_sha_verified": len(names),
        "total_closed_m5_full_sha_verified": len(bars),
        "last_hour_utc": head["hour_utc"],
        "last_manifest_sha256": digest(head),
        "m5_full_bounded_chain_verified": True,
        "source_history_before_root_proven": False,
        "externally_authenticated_monotonic_witness": False,
        "vendor_license_and_session_calendar_verified": False,
        "source_h4_replacement_authorized": False,
        "live_v2_authorized": False,
        "numeric_trade_signals_authorized": False,
        "provider_calls": 0,
        "drive_writes": 0,
        "broker_orders": 0,
    }
