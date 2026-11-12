"""MFX P0.59 immutable native H4/D1 revision quarantine metadata.

Inspect the already-retrieved native batch and the existing SHA index
in memory only. Never fetch old raw prices, log OHLC, expose tokens,
write Drive objects, resolve or override a source SHA disagreement.
"""
from __future__ import annotations

from typing import Any

from mfx_cache.native_fx_htf import NativeFXBatch
from mfx_cache.native_htf_archive import (
    RECENT_INDEX_LIMIT, check_native_manifest,
)

QUARANTINE_CODES = frozenset((
    "P059_SOURCE_NATIVE_REVISION_QUARANTINE",
    "P059_SOURCE_MISSING_SHA_OVERLAP",
))


def summarize_native_revision_quarantine(
    *, previous: dict[str, Any], batch: NativeFXBatch,
    error_code: str,
) -> dict[str, Any]:
    """Only diagnostic labels/counts; never a rewrite or causal claim.

    SHA includes vendor metadata provenance and price representation.
    Therefore a changed bar SHA ALONE cannot establish that actual
    numeric OHLC moved; it needs a separately reviewed old/new source
    comparison, which this helper intentionally does not perform.
    """
    if (type(error_code) is not str or error_code not in QUARANTINE_CODES
            or type(batch) is not NativeFXBatch
            or batch.symbol != "EUR/USD"
            or batch.interval not in ("4h", "1day")
            or batch.exchange_timezone != "Australia/Sydney"
            or type(batch.closed_bars) is not tuple):
        raise ValueError("P059_QUARANTINE_DIAGNOSTIC_SCOPE_DENIED")
    check_native_manifest(previous, symbol=batch.symbol,
                          interval=batch.interval,
                          zone=batch.exchange_timezone)
    prior_index = previous["recent_native_bar_index"]
    if len(prior_index) > RECENT_INDEX_LIMIT:
        raise ValueError("P059_QUARANTINE_DIAGNOSTIC_INDEX_BOUND")
    recent = {x["label"]: x["sha256"] for x in prior_index}
    returned = {bar.native_open_label: bar.sha256()
                for bar in batch.closed_bars}
    if len(recent) != len(prior_index) or len(returned) != len(batch.closed_bars):
        raise ValueError("P059_QUARANTINE_DIAGNOSTIC_DUPLICATE_LABEL")
    missing = sorted(label for label in recent if label not in returned)
    changed = sorted(label for label in recent
                     if label in returned and recent[label] != returned[label])
    unchanged = len(recent)-len(missing)-len(changed)
    if ((error_code == "P059_SOURCE_NATIVE_REVISION_QUARANTINE"
         and (missing or not changed))
            or (error_code == "P059_SOURCE_MISSING_SHA_OVERLAP"
                and not missing)):
        raise ValueError("P059_QUARANTINE_DIAGNOSTIC_MISMATCH")
    return {
        "status": "NATIVE_SOURCE_SHA_QUARANTINE_UNRESOLVED_NO_SIGNAL",
        "quarantine_reason": error_code,
        "interval": batch.interval,
        "previous_sha_index_count": len(recent),
        "overlap_sha_unchanged_count": unchanged,
        "overlap_sha_changed_count": len(changed),
        "overlap_labels_missing_count": len(missing),
        "first_changed_label": changed[0] if changed else None,
        "last_changed_label": changed[-1] if changed else None,
        "first_missing_label": missing[0] if missing else None,
        "last_missing_label": missing[-1] if missing else None,
        "current_source_timezone_origin_types": sorted({
            bar.exchange_timezone_origin for bar in batch.closed_bars
        }),
        "raw_ohlc_logged": False,
        "actual_numeric_price_revision_confirmed": False,
        "vendor_metadata_or_format_revision_excluded": False,
        "quarantine_still_enforced": True,
        "source_numeric_signals_approved": False,
        "provider_price_requests_added_by_diagnostic": 0,
        "drive_reads_added_by_diagnostic": 0,
        "drive_writes": 0,
        "broker_orders": 0,
    }
