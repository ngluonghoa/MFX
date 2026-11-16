"""P0.180: pure, bounded, price-redacted P171 fresh D1 overlap diagnosis.

Called only AFTER the existing full source/archive SHA validation has rejected
a newly refetched source-native D1 overlap. No OAuth, vendor call, Drive write,
broker, source promotion, or relaxation of the original fail-closed exception.
"""
from __future__ import annotations

from typing import Any

from mfx_cache.native_d1_fresh_epoch import (
    FreshEpochState, _source_batch,
)
from mfx_cache.native_fx_htf import NativeFXBatch
from mfx_cache.native_htf_archive import RECENT_INDEX_LIMIT

VERSION = "MFX_P180_FRESH_D1_OVERLAP_SHA_DIAGNOSIS_V1"


def diagnose_p171_overlap_source(
    batch: NativeFXBatch, *, state: FreshEpochState,
) -> dict[str, Any]:
    """Describe exact missing-vs-revised counts WITHOUT private OHLC/labels.

    A caller MUST first independently SHA-audit the existing Drive archive and
    then invoke plan_fresh_epoch_seal on the already-fetched provider response.
    This function has zero I/O and cannot change or approve either source.
    """
    if type(state) is not FreshEpochState or type(state.last_manifest) is not dict:
        raise ValueError("P180_FULL_SHA_AUDITED_EPOCH_STATE_REQUIRED")
    _source_batch(batch)
    index = state.last_manifest.get("recent_native_bar_index")
    if type(index) is not list or not 1 <= len(index) <= RECENT_INDEX_LIMIT:
        raise ValueError("P180_RECENT_SHA_INDEX_REQUIRED")
    prior: dict[str, str] = {}
    for item in index:
        if (type(item) is not dict
                or set(item) != {"label", "sha256"}
                or type(item["label"]) is not str
                or len(item["label"]) != 10
                or type(item["sha256"]) is not str
                or len(item["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in item["sha256"])
                or item["label"] in prior):
            raise ValueError("P180_MALFORMED_OR_DUPLICATE_EPOCH_INDEX")
        prior[item["label"]] = item["sha256"]
    if list(prior) != sorted(prior):
        raise ValueError("P180_UNSORTED_EPOCH_INDEX")
    refetched = {
        bar.native_open_label: bar.sha256() for bar in batch.closed_bars
    }
    missing = sum(label not in refetched for label in prior)
    changed = sum(label in refetched and refetched[label] != sha
                  for label, sha in prior.items())
    matched = len(prior) - missing - changed
    if missing == 0 and changed == 0:
        raise ValueError("P180_DIAGNOSIS_REQUIRES_CONFIRMED_OVERLAP_HOLD")
    if missing and changed:
        kind = "MISSING_AND_CHANGED"
    elif missing:
        kind = "MISSING_OVERLAP_LABELS"
    else:
        kind = "CHANGED_OVERLAP_SHA"
    return {
        "schema": VERSION,
        "status": "P171_D1_OVERLAP_SOURCE_QUARANTINED_NO_COMMIT",
        "conflict_classification": kind,
        "previous_indexed_labels": len(prior),
        "refetched_closed_native_bars": len(batch.closed_bars),
        "overlap_labels_missing_count": missing,
        "overlap_sha_changed_count": changed,
        "overlap_sha_unchanged_count": matched,
        "source_vintage": "ACTIVE_P171_OWNER_FRESH_EPOCH_ONLY",
        "source_vendor_correction_cause_proven": False,
        "source_publisher_first_known_verified": False,
        "original_numeric_rules_approved": False,
        "may_publish_buy_sell": False,
        "source_promotion_authorized": False,
        "source_quarantine_bypassed": False,
        "provider_price_requests_added": 0,
        "drive_reads_added": 0,
        "drive_writes": 0,
        "broker_orders": 0,
    }
