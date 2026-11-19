"""P0.202: keep independently safe H4 alive while owner P192 D1 remains RED.

PURE eligibility only. The writer must separately SHA-audit both original
native archives and the full P192 owner epoch, re-audit just before H4 write,
and use the unchanged native H4 sealed chunk+manifest commit/readback path.
No D1 canonical writes, broker orders, automatic numeric signal permissions.
"""
from __future__ import annotations

from typing import Any

from mfx_cache.native_d1_epoch_20261118 import (
    FreshEpochState, SCHEMA as D1_SCHEMA,
)
from mfx_cache.p200_p192_d1_sha_diff_forensics import VERSION as P200_VERSION

VERSION = "MFX_P202_P192_QUARANTINED_D1_SAFE_H4_ONLY_V1"

EXPECTED_DIAGNOSTIC_KEYS = frozenset((
    "schema", "status", "source_epoch", "conflict_classification",
    "previous_sealed_closed_bars_count", "refetched_closed_native_bars_count",
    "overlap_missing_count", "overlap_sha_changed_count",
    "overlap_sha_unchanged_count", "numeric_ohlc_value_changed_count",
    "metadata_changed_count", "price_text_format_changed_count",
    "provider_vendor_revision_cause_independently_proven",
    "publisher_first_known_verified", "owner_source_rebase_or_revision_approved",
    "may_write_d1", "may_publish_buy_sell", "may_trade",
    "additional_vendor_requests", "drive_reads_added_by_diagnostic",
    "drive_writes", "broker_orders",
))


def eligible_p192_h4_only(report: Any, state: FreshEpochState) -> bool:
    """Only one known 18-Nov P192 numeric D1 source revision, zero write rights.

    Necessary but not sufficient. H4 source SHA, P192 re-read, Drive append
    custody and the original ValueError are independently enforced in writer.
    """
    if (type(report) is not dict or frozenset(report) !=
            EXPECTED_DIAGNOSTIC_KEYS
            or type(state) is not FreshEpochState
            or state.manifests != 1 or state.chunks != 1
            or state.orphan_chunk is not None
            or type(state.last_manifest) is not dict):
        return False
    m = state.last_manifest
    if (m.get("schema") != D1_SCHEMA
            or m.get("owner_rebaseline_date") != "2026-11-18"
            or m.get("last_native_open_label") != "2026-11-18"
            or m.get("total_closed_bars") != 1
            or m.get("batch_count") != 1
            or m.get("owner_approved_cache_rebaseline") is not True
            or m.get("publisher_first_known_verified") is not False
            or m.get("may_publish_buy_sell") is not False
            or type(m.get("recent_native_bar_index")) is not list
            or len(m["recent_native_bar_index"]) != 1
            or m["recent_native_bar_index"][0].get("label") != "2026-11-18"):
        return False
    expected: dict[str, object] = {
        "schema": P200_VERSION,
        "status": "P192_OWNER_D1_OVERLAP_SOURCE_QUARANTINED_NO_COMMIT",
        "source_epoch": "P192_D1_FRESH_20261118",
        "conflict_classification": "NUMERIC_OHLC_VALUE_CHANGED",
        "previous_sealed_closed_bars_count": 1,
        "overlap_missing_count": 0,
        "overlap_sha_changed_count": 1,
        "overlap_sha_unchanged_count": 0,
        "numeric_ohlc_value_changed_count": 1,
        "metadata_changed_count": 0,
        "price_text_format_changed_count": 0,
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
    for key, value in expected.items():
        if type(report.get(key)) is not type(value) or report[key] != value:
            return False
    count = report.get("refetched_closed_native_bars_count")
    return type(count) is int and 1 <= count <= 120
