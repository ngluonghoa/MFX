"""MFX A04/P0.66 — authenticated READ-ONLY M5-derived H4 vs native H4 audit.

The only live I/O is authenticated Google Drive GET/list; no Twelve Data key,
network price request, Drive mutation, local cache persistence, broker, signal.
Run in GitHub Actions with the same cooperative cache concurrency lock.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any

from mfx_cache.h4_shadow import compare_shadow_to_native, derive_h4_shadow
from mfx_cache.native_fx_htf import NativeFXBar
from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_cache.v2_batch_commit import (
    CHUNK_PREFIX, MANIFEST_PREFIX, _validate_chunk, _validate_manifest,
)
from mfx_cache.v2_engine import derive_intraday, validate_m5
from tools.mfx_native_htf_drive_seal import (
    PrivateNativeDriveStore, _batch_from_chunk, audit_native_archive,
)
from tools.run_a04_p45_cloud_twelve_data_cache import (
    _drive_auth_info, _require_oauth_cache_folders, _session,
)
from tools.run_a04_p46_cloud_batch_cache import PrivateDriveBatchStore

UTC = timezone.utc
SYMBOL = "EUR/USD"
MAX_M5_ARCHIVE_HOURS = 256
MIN_PARITY_WINDOWS = 30
MIN_SPAN = timedelta(days=7)
HOUR = timedelta(hours=1)
H4 = timedelta(hours=4)


def _utc(instant: datetime) -> None:
    if (type(instant) is not datetime or instant.tzinfo is None
            or instant.utcoffset() != timedelta(0)):
        raise ValueError("P066_EXACT_UTC_NOW_REQUIRED")


def _m5_archive(
    store: Any, *, now_utc: datetime,
) -> tuple[tuple[ClosedM5Bar, ...], dict[str, Any]]:
    """Verify the ENTIRE bounded hourly M5 immutable chain, not just its tail.

    Never treat an orphan, missing hour, non-contiguous 12-bar hour, altered
    H1/M15/M30 derivation or a changed old parent as reliable source history.
    Sparse hourly data remains auditable, but cannot make complete 4h bars
    across the gap. The root is explicitly not proof of earlier history.
    """
    _utc(now_utc)
    manifests = tuple(sorted(store.list_names("manifest")))
    chunks = set(store.list_names("chunk"))
    if not manifests:
        raise ValueError("P066_NO_M5_ARCHIVE")
    if (len(manifests) > MAX_M5_ARCHIVE_HOURS
            or len(chunks) > MAX_M5_ARCHIVE_HOURS):
        raise ValueError("P066_M5_HISTORY_TOO_LARGE_FULL_PROOF_REQUIRED")
    if len(manifests) != len(chunks):
        raise ValueError("P066_M5_ORPHAN_OR_MISSING_CHUNK")
    previous: dict[str, Any] | None = None
    referenced: set[str] = set()
    rows: list[ClosedM5Bar] = []
    for filename in manifests:
        if not filename.startswith(MANIFEST_PREFIX):
            raise ValueError("P066_M5_UNEXPECTED_MANIFEST_PREFIX")
        manifest = store.read("manifest",filename)
        hour_label = _validate_manifest(filename,manifest)
        chunk_name = manifest["chunk_name"]
        if not chunk_name.startswith(CHUNK_PREFIX) or chunk_name not in chunks:
            raise ValueError("P066_M5_MISSING_REFERENCED_CHUNK")
        chunk = store.read("chunk",chunk_name)
        _validate_chunk(chunk_name,chunk)
        if (digest(chunk) != manifest["chunk_sha256"]
                or chunk["hour_utc"] != hour_label
                or chunk["parent_manifest_sha256"] !=
                manifest["parent_manifest_sha256"]):
            raise ValueError("P066_M5_SHA_OR_PARENT_CHUNK_MISMATCH")
        if chunk_name in referenced:
            raise ValueError("P066_M5_REUSED_CHUNK")
        referenced.add(chunk_name)
        if previous is None:
            if (manifest["parent_manifest_sha256"] is not None
                    or manifest["total_batches"] != 1
                    or manifest["gap_prior_hours_unverified"] != 0
                    or manifest["continuity_status"] !=
                    "BOOTSTRAP_HISTORY_UNVERIFIED"):
                raise ValueError("P066_M5_ROOT_INVALID")
        else:
            delta = (datetime.fromisoformat(hour_label)
                     - datetime.fromisoformat(previous["hour_utc"]))
            if delta <= timedelta(0) or delta % HOUR != timedelta(0):
                raise ValueError("P066_M5_UNORDERED_HOUR")
            missing_hours = int(delta / HOUR) - 1
            if (manifest["parent_manifest_sha256"] != digest(previous)
                    or manifest["total_batches"] !=
                    previous["total_batches"] + 1
                    or manifest["gap_prior_hours_unverified"] != missing_hours
                    or manifest["continuity_status"] != (
                        "MISSING_PRIOR_HOURS_UNVERIFIED"
                        if missing_hours else "CONTIGUOUS_WITH_PRIOR_BATCH")):
                raise ValueError("P066_M5_CHAIN_OR_GAP_FALSE")
        try:
            current = tuple(ClosedM5Bar(**record) for record in chunk["bars"])
        except (TypeError, ValueError) as exc:
            raise ValueError("P066_M5_BAR_DECODE_INVALID") from exc
        validate_m5(current,asof_utc=now_utc)
        hour = datetime.fromisoformat(hour_label)
        expected = tuple((hour+timedelta(minutes=5*i)).isoformat()
                         for i in range(12))
        if tuple(b.start_utc for b in current) != expected:
            raise ValueError("P066_M5_CHUNK_NOT_EXACT_12_UTC")
        # P0.46 source+derived fingerprints must remain mutually consistent.
        for frame, count in (("M15",4),("M30",2),("H1",1)):
            actual = derive_intraday(current,frame,asof_utc=now_utc)
            if (len(actual.candles) != count
                    or [asdict(c) for c in actual.candles]
                    != chunk["derived"][frame]):
                raise ValueError("P066_M5_DERIVED_LINEAGE_DRIFT")
        rows.extend(current)
        previous = manifest
    if chunks != referenced:
        raise ValueError("P066_M5_ORPHAN_CHUNK")
    assert previous is not None
    return tuple(rows), {
        "m5_manifest_chunk_pairs_full_sha_verified": len(manifests),
        "m5_closed_bars": len(rows),
        "m5_latest_hour_utc": previous["hour_utc"],
        "m5_latest_manifest_sha256": digest(previous),
        "m5_full_bounded_chain_verified": True,
    }


def _native_h4_archive(
    store: Any,
) -> tuple[tuple[NativeFXBar, ...], dict[str, Any]]:
    """Audit full native SHA/parents first; then decode every original bar."""
    state = audit_native_archive(store,symbol=SYMBOL,interval="4h")
    if (state.last_manifest is None or state.manifest_count < 1
            or state.uncommitted_chunk_names
            or state.chunk_count != state.manifest_count):
        raise ValueError("P066_NATIVE_H4_INCOMPLETE_ARCHIVE")
    rows: list[NativeFXBar] = []
    for filename in store.list_names("manifest"):
        manifest = store.read("manifest",filename)
        if type(manifest) is not dict:
            raise ValueError("P066_NATIVE_MANIFEST_SHAPE")
        chunk = store.read("chunk",manifest["chunk_name"])
        batch = _batch_from_chunk(chunk)
        if batch.interval != "4h" or batch.symbol != SYMBOL:
            raise ValueError("P066_NATIVE_UNEXPECTED_SCOPE")
        rows.extend(batch.closed_bars)
    if len(rows) != state.last_manifest["total_closed_native_bars"]:
        raise ValueError("P066_NATIVE_BAR_COUNT_MISMATCH")
    return tuple(rows), {
        "h4_native_manifest_chunk_pairs_full_sha_verified": state.manifest_count,
        "h4_native_closed_bars": len(rows),
        "h4_native_latest_manifest_sha256": digest(state.last_manifest),
        "h4_native_full_bounded_chain_verified": True,
    }


def audit_live_m5_h4_parity(
    m5_store: Any, native_store: Any, *, now_utc: datetime,
) -> dict[str, Any]:
    """Return source-verified RESEARCH evidence; never source replacement."""
    _utc(now_utc)
    rows, m5_evidence = _m5_archive(m5_store,now_utc=now_utc)
    native, native_evidence = _native_h4_archive(native_store)
    shadow = derive_h4_shadow(rows,asof_utc=now_utc)
    observed = compare_shadow_to_native(shadow,native)
    labels = [datetime.fromisoformat(row.start_utc) for row in observed.rows]
    complete_chain = bool(labels) and all(
        after-before == H4 for before,after in zip(labels,labels[1:]))
    spans_week = bool(labels) and labels[-1]-labels[0] >= MIN_SPAN
    enough_windows = len(labels) >= MIN_PARITY_WINDOWS
    no_mismatch = observed.mismatches == 0 and observed.missing_native == 0
    sufficient = (complete_chain and spans_week and enough_windows
                  and no_mismatch
                  and not shadow.skipped_incomplete_windows)
    # P0.65's "fully_verified" remains FALSE by design. This audit
    # verifies archived sources, NOT account license, broker or cutover.
    status = (
        "SOURCE_PARITY_REVIEW_REQUIRED"
        if not no_mismatch else
        "INCOMPLETE_M5_WINDOWS_REVIEW_REQUIRED"
        if not complete_chain or (
            shadow.skipped_incomplete_windows
            and enough_windows) else
        "SOURCE_PARITY_WINDOW_MET_OWNER_CUTOVER_STILL_DENIED"
        if sufficient else
        "OBSERVATION_WINDOW_NOT_YET_QUALIFIED"
    )
    return {
        "status": status,
        "symbol": SYMBOL,
        "price_side": "MID",
        "source": "TWELVE_DATA_COMPOSITE_MID",
        "shadow_interval": "M5_DERIVED_4H_UTC",
        "reference_interval": "4h_NATIVE_UTC",
        **m5_evidence, **native_evidence,
        "m5_h4_complete_windows": len(observed.rows),
        "m5_h4_incomplete_windows": len(shadow.skipped_incomplete_windows),
        "m5_h4_incomplete_window_samples_utc":
            list(shadow.skipped_incomplete_windows[:8]),
        "h4_compared_match": observed.matches,
        "h4_compared_mismatch": observed.mismatches,
        "h4_native_missing": observed.missing_native,
        "h4_mismatch_sample_fields_only": [
            {"window_utc": r.start_utc, "fields": list(r.differing_fields),
             "source_input_sha256": r.m5_window_sha256,
             "native_bar_sha256": r.native_bar_sha256}
            for r in observed.rows if r.status == "MISMATCH"
        ][:8],
        "h4_native_missing_sample_utc": [
            r.start_utc for r in observed.rows if r.status == "NATIVE_MISSING"
        ][:8],
        "observed_first_h4_utc": labels[0].isoformat() if labels else None,
        "observed_last_h4_utc": labels[-1].isoformat() if labels else None,
        "h4_consecutive_4h_grid": bool(complete_chain),
        "h4_span_at_least_7_days": bool(spans_week),
        "min_required_complete_h4_windows": MIN_PARITY_WINDOWS,
        "h4_parity_observation_threshold_met": bool(sufficient),
        "may_reduce_native_h4_requests": False,
        "may_replace_native_h4": False,
        "d1_native_untouched": True,
        "read_only": True,
        "provider_api_calls": 0,
        "drive_writes": 0,
        "broker_orders": 0,
        "source_numeric_signals_approved": False,
        "raw_ohlc_logged": False,
    }


def main() -> None:
    if (os.environ.get("MFX_REAL_CACHE_ENABLED") != "true"
            or os.environ.get("MFX_V2_BATCH_CACHE_ACCEPTED") != "true"
            or os.environ.get("MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED") != "true"):
        print("MFX_A04_P66_PARITY_AUDIT_DISABLED_EXISTING_GATES")
        return
    auth = _drive_auth_info()
    _require_oauth_cache_folders(auth)
    session = _session(auth)
    result = audit_live_m5_h4_parity(
        PrivateDriveBatchStore(session),
        PrivateNativeDriveStore(session,symbol=SYMBOL,interval="4h"),
        now_utc=datetime.now(UTC),
    )
    print("MFX_A04_P66_READONLY_SOURCE_SHA_PARITY_AUDIT_PASS")
    print(json.dumps(result,sort_keys=True))


if __name__ == "__main__":
    main()
