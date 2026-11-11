"""A04/P0.69 — root-pinned, rolling H4 M5 SHA audit beyond 256 hourly pairs.

A full cryptographic audit of OLD sealed M5 chunks cannot be claimed if they
are intentionally not re-read. Verify every immutable manifest SHA/parent
to a repo-pinned, previously full-audited ROOT; independently re-read and
verify exactly the latest 256 M5 Chunk/Manifest pairs, which can cover seven
days of complete H4 candles. This mode is *not* a full history chunk audit.

No API/network on import, Drive writes, OHLC log, signals or broker.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_cache.v2_engine import validate_m5, derive_intraday
from mfx_cache.v2_batch_commit import (
    CHUNK_PREFIX, _validate_chunk, _validate_manifest,
)

ROLLING_HOURS = 256
MAX_ROOTED_MANIFESTS = 1024

# This exact original root was independently SHA-audited by P0.66 real
# GitHub Actions #43013931317 (and #43016355660) while M5 archive
# contained 14 manifests / 168 original M5 source bars. It is a review-
# controlled Git anchor, NOT an automatically trusted Drive self-assertion.
ROOT_UTC = "2026-11-10T18:00:00+00:00"
ROOT_MANIFEST_SHA256 = (
    "47320a77ba8a615cd043dbba55b6bc2d4e02ad0f88adf4b229143aca5dde93c0"
)
HOUR = timedelta(hours=1)


def audit_rooted_rolling_m5(
    store: Any, *, now_utc: datetime,
    root_sha256: str = ROOT_MANIFEST_SHA256,
    root_hour_utc: str = ROOT_UTC,
) -> tuple[tuple[ClosedM5Bar, ...], dict[str, Any]]:
    """Full SHA-parent audit of manifest chain + full SHA last 256 chunks.

    Does NOT certify historical raw chunks outside the rolling tail.
    The root pin must be a separately accepted GitHub immutable evidence
    decision. Never pin a hash supplied only by the untrusted Drive API.
    """
    if (type(now_utc) is not datetime or now_utc.tzinfo is None
            or now_utc.utcoffset() != timedelta(0)):
        raise ValueError("P069_UTC_NOW_REQUIRED")
    if (type(root_sha256) is not str or len(root_sha256) != 64
            or any(c not in "0123456789abcdef" for c in root_sha256)
            or type(root_hour_utc) is not str):
        raise ValueError("P069_ROOT_ATTESTATION_REQUIRED")

    names = tuple(store.list_names("manifest"))
    chunks = set(store.list_names("chunk"))
    if len(names) <= ROLLING_HOURS:
        raise ValueError("P069_USE_EXISTING_FULL_M5_AUDITOR_UNDER_256")
    if len(names) > MAX_ROOTED_MANIFESTS:
        raise ValueError("P069_HISTORY_CAPACITY_REQUIRE_NEW_REVIEWED_ANCHOR")
    if len(chunks) != len(names) or len(set(names)) != len(names):
        raise ValueError("P069_M5_ORPHAN_OR_MISSING_CHUNK")

    previous: dict[str, Any] | None = None
    referenced: set[str] = set()
    tail: list[tuple[dict[str, Any], str]] = []
    root_name: str | None = None
    head_name: str | None = None
    head_sha: str | None = None
    for idx, name in enumerate(names):
        manifest = store.read("manifest", name)
        hour = _validate_manifest(name, manifest)
        sha = digest(manifest)
        chunk_name = manifest["chunk_name"]
        if chunk_name not in chunks or not chunk_name.startswith(CHUNK_PREFIX):
            raise ValueError("P069_MISSING_CHUNK_IN_ARCHIVE_ENUMERATION")
        if chunk_name in referenced:
            raise ValueError("P069_DUPLICATE_CHUNK_REFERENCE")
        referenced.add(chunk_name)

        if previous is None:
            if (hour != root_hour_utc or sha != root_sha256
                    or manifest["parent_manifest_sha256"] is not None
                    or manifest["total_batches"] != 1
                    or manifest["gap_prior_hours_unverified"] != 0
                    or manifest["continuity_status"] !=
                    "BOOTSTRAP_HISTORY_UNVERIFIED"):
                raise ValueError("P069_TRUSTED_ROOT_SHA_OR_LABEL_CHANGED")
            root_name = name
        else:
            gap = (datetime.fromisoformat(hour)
                   - datetime.fromisoformat(previous["hour_utc"]))
            if gap <= timedelta(0) or gap % HOUR != timedelta(0):
                raise ValueError("P069_UNORDERED_HOURLY_MANIFEST")
            missing = int(gap/HOUR)-1
            if (manifest["parent_manifest_sha256"] != digest(previous)
                    or manifest["total_batches"] != idx+1
                    or manifest["gap_prior_hours_unverified"] != missing
                    or manifest["continuity_status"] != (
                        "MISSING_PRIOR_HOURS_UNVERIFIED" if missing
                        else "CONTIGUOUS_WITH_PRIOR_BATCH")):
                raise ValueError("P069_SHA_PARENT_OR_GAP_DRIFT")
        if idx >= len(names)-ROLLING_HOURS:
            tail.append((manifest, chunk_name))
        head_name = name
        head_sha = sha
        previous = manifest

    if referenced != chunks or len(tail) != ROLLING_HOURS:
        raise ValueError("P069_ORPHAN_OR_INVALID_TAIL")
    rows: list[ClosedM5Bar] = []
    for manifest, chunk_name in tail:
        chunk = store.read("chunk", chunk_name)
        hour = _validate_chunk(chunk_name, chunk)
        if (digest(chunk) != manifest["chunk_sha256"]
                or hour != manifest["hour_utc"]
                or chunk["parent_manifest_sha256"] !=
                manifest["parent_manifest_sha256"]):
            raise ValueError("P069_RECENT_CHUNK_SHA_OR_PARENT_MISMATCH")
        try:
            bars = tuple(ClosedM5Bar(**r) for r in chunk["bars"])
        except (TypeError, ValueError) as exc:
            raise ValueError("P069_RECENT_M5_BAR_MALFORMED") from exc
        validate_m5(bars, asof_utc=now_utc)
        expected = tuple(
            (datetime.fromisoformat(hour)+timedelta(minutes=5*i)).isoformat()
            for i in range(12))
        if tuple(b.start_utc for b in bars) != expected:
            raise ValueError("P069_RECENT_HOUR_NOT_EXACT_12_CLOSED_M5")
        for frame, count in (("M15",4),("M30",2),("H1",1)):
            fresh = derive_intraday(bars,frame,asof_utc=now_utc)
            if (len(fresh.candles) != count
                    or [asdict(c) for c in fresh.candles]
                    != chunk["derived"][frame]):
                raise ValueError("P069_RECENT_DERIVED_LINEAGE_DRIFT")
        rows.extend(bars)

    # Guard against a cooperative Drive writer changing the head or
    # immutable root during the multi-GET scan. Same GitHub lock applies.
    if (root_name is None or head_name is None or head_sha is None
            or digest(store.read("manifest",root_name)) != root_sha256
            or digest(store.read("manifest",head_name)) != head_sha
            or tuple(store.list_names("manifest")) != names
            or set(store.list_names("chunk")) != chunks):
        raise ValueError("P069_PARENT_ARCHIVE_CHANGED_DURING_AUDIT")
    assert previous is not None
    return tuple(rows), {
        "m5_manifest_chunk_pairs_full_sha_verified": ROLLING_HOURS,
        "m5_manifest_full_sha_parent_chain_verified": len(names),
        "m5_total_archived_manifest_chunk_pairs": len(names),
        "m5_closed_bars": len(rows),
        "m5_total_archived_closed_bars": previous["total_closed_m5"],
        "m5_latest_hour_utc": previous["hour_utc"],
        "m5_latest_manifest_sha256": head_sha,
        "m5_root_hour_utc": root_hour_utc,
        "m5_pinned_root_manifest_sha256": root_sha256,
        "m5_full_bounded_chain_verified": False,
        "m5_rolling_256_chunk_sha_verified": True,
        "m5_historical_unread_chunks": len(names)-ROLLING_HOURS,
        "m5_old_raw_chunks_not_reverified_this_run": True,
        "m5_full_history_raw_sha_not_approved_for_cutover": True,
        "m5_audit_mode": "ROOT_PINNED_ALL_MANIFESTS_LATEST_256_CHUNKS",
    }
