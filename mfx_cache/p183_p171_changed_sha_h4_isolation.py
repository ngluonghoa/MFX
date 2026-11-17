"""P0.183 exact source-custody gate: independent H4 while P171 D1 stays HOLD.

PURE sha-only eligibility: necessary, not sufficient. Caller must re-audit
both frozen native archives and the complete P171 D1 fresh epoch before H4.
No real provider/Drive operation, D1 mutation, signal or broker permissions.
"""
from __future__ import annotations
from typing import Any
from mfx_cache.native_d1_fresh_epoch import FreshEpochState
from mfx_cache.native_htf_archive import RECENT_INDEX_LIMIT
from mfx_cache.p180_d1_overlap_diagnosis import VERSION as P180_VERSION

VERSION="MFX_P183_ONE_REVISED_D1_SHA_H4_ISOLATION_V1"
_KEYS=frozenset((
    "schema","status","conflict_classification",
    "previous_indexed_labels","refetched_closed_native_bars",
    "overlap_labels_missing_count","overlap_sha_changed_count",
    "overlap_sha_unchanged_count","source_vintage",
    "source_vendor_correction_cause_proven",
    "source_publisher_first_known_verified",
    "original_numeric_rules_approved","may_publish_buy_sell",
    "source_promotion_authorized","source_quarantine_bypassed",
    "provider_price_requests_added","drive_reads_added","drive_writes",
    "broker_orders",
))

def eligible_for_h4_only(report: Any, state: FreshEpochState) -> bool:
    """Allow exactly one content SHA revision, zero lost P171 overlap labels.

    Does NOT permit D1 acceptance. No arbitrary dates/market numbers used.
    """
    if (type(report) is not dict or frozenset(report)!=_KEYS
            or type(state) is not FreshEpochState
            or type(state.last_manifest) is not dict
            or type(state.manifests) is not int or state.manifests<1
            or type(state.chunks) is not int or state.chunks!=state.manifests
            or state.orphan_chunk is not None):
        return False
    recent=state.last_manifest.get("recent_native_bar_index")
    if type(recent) is not list or not 1<=len(recent)<=RECENT_INDEX_LIMIT:
        return False
    expect={
        "schema":P180_VERSION,
        "status":"P171_D1_OVERLAP_SOURCE_QUARANTINED_NO_COMMIT",
        "conflict_classification":"CHANGED_OVERLAP_SHA",
        "source_vintage":"ACTIVE_P171_OWNER_FRESH_EPOCH_ONLY",
        "source_vendor_correction_cause_proven":False,
        "source_publisher_first_known_verified":False,
        "original_numeric_rules_approved":False,
        "may_publish_buy_sell":False,
        "source_promotion_authorized":False,
        "source_quarantine_bypassed":False,
        "provider_price_requests_added":0,"drive_reads_added":0,
        "drive_writes":0,"broker_orders":0,
        "overlap_labels_missing_count":0,
        "overlap_sha_changed_count":1,
        "overlap_sha_unchanged_count":len(recent)-1,
        "previous_indexed_labels":len(recent),
    }
    if any(type(report.get(k)) is not type(v) or report[k]!=v
           for k,v in expect.items()):
        return False
    n=report.get("refetched_closed_native_bars")
    return type(n) is int and len(recent)<=n<=120
