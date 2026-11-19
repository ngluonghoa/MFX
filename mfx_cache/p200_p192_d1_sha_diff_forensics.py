"""P0.200: SHA-bound P192 owner 18-Nov D1 overlap forensics, price-redacted.

The caller already full-SHA audited P192 Drive and fetched ONE provider D1
batch. Read the already SEALED last chunk only on original source-revision
quarantine and report counts, never private OHLC/labels/source SHA values.
This module itself performs no I/O and NEVER approves an amended candle.
"""
from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Any

from mfx_cache.native_d1_epoch_20261118 import (
    FreshEpochState, SCHEMA, _source_batch, _validate_chunk,
)
from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.td_m5_codec import digest

VERSION = "MFX_P200_P192_OWNER_D1_SHA_DIFF_REDACTED_FORENSICS_V1"
PRICES = ("open", "high", "low", "close")


def diagnose_p192_owner_overlap(
    *, state: FreshEpochState, sealed_chunk: dict[str, Any],
    refetched: NativeFXBatch, origin_v1_sha: str,
) -> dict[str, Any]:
    """Categorize overlap SHA conflict without revealing any values.

    Restrict this diagnostic to the existing single-root P192 epoch only.
    Multiple archived source chunks require a separate independent forensic
    plan, not a guessed reconstruction of a complete historical context.
    """
    if (type(state) is not FreshEpochState
            or state.manifests != 1 or state.chunks != 1
            or state.orphan_chunk is not None
            or type(state.last_manifest) is not dict
            or state.last_manifest.get("schema") != SCHEMA
            or state.last_manifest.get("owner_approved_cache_rebaseline") is not True
            or state.last_manifest.get("may_publish_buy_sell") is not False
            or state.last_manifest.get("origin_v1_manifest_sha256") != origin_v1_sha
            or type(sealed_chunk) is not dict):
        raise ValueError("P200_FULL_SHA_ATTESTED_SINGLE_ROOT_P192_REQUIRED")
    _source_batch(refetched)
    manifest = state.last_manifest
    stored_bars = _validate_chunk(
        sealed_chunk, manifest["chunk_name"], origin_v1_sha,
    )
    if (digest(sealed_chunk) != manifest["chunk_sha256"]
            or len(stored_bars) != manifest["total_closed_bars"]
            or manifest["batch_count"] != 1):
        raise ValueError("P200_SEALED_LAST_CHUNK_SHA_OR_COUNT_DRIFT")
    index = manifest["recent_native_bar_index"]
    if (type(index) is not list or len(index) != len(stored_bars)
            or {x["label"]: x["sha256"] for x in index} !=
                {bar.native_open_label: bar.sha256() for bar in stored_bars}):
        raise ValueError("P200_ORIGINAL_P192_SHA_INDEX_DRIFT")

    current = {bar.native_open_label: bar
               for bar in refetched.closed_bars}
    if len(current) != len(refetched.closed_bars):
        raise ValueError("P200_DUPLICATE_FETCHED_SOURCE_LABEL")
    missing = 0
    changed = 0
    unchanged = 0
    numeric_value_changed = 0
    metadata_changed = 0
    number_format_changed = 0
    for saved in stored_bars:
        fresh = current.get(saved.native_open_label)
        if fresh is None:
            missing += 1
            continue
        if fresh.sha256() == saved.sha256():
            unchanged += 1
            continue
        changed += 1
        old_fields = asdict(saved)
        new_fields = asdict(fresh)
        if any(Decimal(old_fields[key]) != Decimal(new_fields[key])
               for key in PRICES):
            numeric_value_changed += 1
        elif any(old_fields[key] != new_fields[key] for key in PRICES):
            number_format_changed += 1
        if any(old_fields[key] != new_fields[key]
               for key in old_fields if key not in PRICES):
            metadata_changed += 1
    if missing == 0 and changed == 0:
        raise ValueError("P200_QUARANTINE_SHOULD_PRECEDE_FORENSICS")

    if missing and changed:
        category = "MISSING_AND_CHANGED_OVERLAP"
    elif missing:
        category = "MISSING_OVERLAP"
    elif numeric_value_changed and metadata_changed:
        category = "NUMERIC_OHLC_AND_METADATA_CHANGED"
    elif numeric_value_changed:
        category = "NUMERIC_OHLC_VALUE_CHANGED"
    elif metadata_changed and number_format_changed:
        category = "METADATA_AND_PRICE_TEXT_FORMAT_CHANGED"
    elif metadata_changed:
        category = "METADATA_ONLY_CHANGED"
    elif number_format_changed:
        category = "PRICE_TEXT_FORMAT_ONLY_CHANGED"
    else:
        raise ValueError("P200_UNCLASSIFIED_SHA_MISMATCH")

    return {
        "schema": VERSION,
        "status": "P192_OWNER_D1_OVERLAP_SOURCE_QUARANTINED_NO_COMMIT",
        "source_epoch": "P192_D1_FRESH_20261118",
        "conflict_classification": category,
        "previous_sealed_closed_bars_count": len(stored_bars),
        "refetched_closed_native_bars_count": len(refetched.closed_bars),
        "overlap_missing_count": missing,
        "overlap_sha_changed_count": changed,
        "overlap_sha_unchanged_count": unchanged,
        "numeric_ohlc_value_changed_count": numeric_value_changed,
        "metadata_changed_count": metadata_changed,
        "price_text_format_changed_count": number_format_changed,
        "provider_vendor_revision_cause_independently_proven": False,
        "publisher_first_known_verified": False,
        "owner_source_rebase_or_revision_approved": False,
        "may_write_d1": False,
        "may_publish_buy_sell": False,
        "may_trade": False,
        "additional_vendor_requests": 0,
        "drive_reads_added_by_diagnostic": 1,
        "drive_writes": 0,
        "broker_orders": 0,
    }
