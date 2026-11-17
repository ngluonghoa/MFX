"""P0.185 — PRIVATE P171 changed-SHA D1 owner-review candidate, pure/no I/O.

The caller MUST independently full-SHA-audit the immutable P171 Drive epoch
and use the already-fetched, closed provider-native D1 batch which was refused
by P171's original overlap guard. This module cannot validate vendor publisher
first-known, account licence, economic validity, or source ownership.
It NEVER revises a candle, writes Drive, calls vendor, or permits BUY/SELL.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from mfx_cache.native_d1_fresh_epoch import FreshEpochState, SCHEMA as P171_SCHEMA
from mfx_cache.native_fx_htf import NativeFXBatch
from mfx_cache.p180_d1_overlap_diagnosis import (
    VERSION as P180_VERSION, diagnose_p171_overlap_source,
)
from mfx_cache.td_m5_codec import digest

VERSION = "MFX_P185_P171_D1_SHA_REVISION_OWNER_REVIEW_V1"
_STATUS = "APPEND_ONLY_REVIEW_PROPOSAL_NOT_SOURCE_ADMISSION"
_FIELDS = frozenset({
    "schema", "status", "source_vintage", "original_epoch_manifest_tip_sha256",
    "runner_observed_utc", "revised_source_sha_pair", "redacted_diagnostic",
    "publisher_first_known_verified", "source_account_rights_verified",
    "owner_canonical_revision_approved", "historical_asof_rewrite_allowed",
    "may_write_d1", "may_publish_buy_sell", "broker_orders",
    "proposal_content_sha256",
})
_DIAGNOSTIC_FIELDS = frozenset({
    "schema", "status", "conflict_classification",
    "previous_indexed_labels", "refetched_closed_native_bars",
    "overlap_labels_missing_count", "overlap_sha_changed_count",
    "overlap_sha_unchanged_count", "source_vintage",
    "source_vendor_correction_cause_proven",
    "source_publisher_first_known_verified", "original_numeric_rules_approved",
    "may_publish_buy_sell", "source_promotion_authorized",
    "source_quarantine_bypassed", "provider_price_requests_added",
    "drive_reads_added", "drive_writes", "broker_orders",
})
_PAIR_FIELDS = frozenset(("label", "stored_sha256", "refetched_sha256"))


def _utc(stamp: Any) -> datetime:
    if (type(stamp) is not datetime or stamp.tzinfo is None
            or stamp.utcoffset() != timedelta(0)):
        raise ValueError("P185_EXACT_UTC_RUNNER_OBSERVATION_REQUIRED")
    return stamp


def _sha(s: Any) -> bool:
    return (type(s) is str and len(s) == 64
            and all(c in "0123456789abcdef" for c in s))


def build_p171_revision_review(
    *, state: FreshEpochState, refetched: NativeFXBatch,
    runner_observed_utc: datetime,
) -> dict[str, Any]:
    """Make an untrusted private candidate; admit ZERO canonical source rows.

    Exactly ONE changed P171 overlap SHA and ZERO missing labels are permitted
    by the current real incident. A more complex revision needs another
    explicit scope review rather than automatic interpretation.
    """
    stamp = _utc(runner_observed_utc)
    if (type(state) is not FreshEpochState
            or type(state.last_manifest) is not dict
            or type(state.manifests) is not int or state.manifests < 1
            or type(state.chunks) is not int
            or state.chunks != state.manifests
            or state.orphan_chunk is not None):
        raise ValueError("P185_INDEPENDENT_SHA_AUDITED_P171_STATE_REQUIRED")
    previous = state.last_manifest
    if (previous.get("schema") != P171_SCHEMA
            or previous.get("owner_approved_cache_rebaseline") is not True
            or previous.get("publisher_first_known_verified") is not False
            or previous.get("may_publish_buy_sell") is not False):
        raise ValueError("P185_P171_UNAPPROVED_SOURCE_STATE")
    first = previous.get("first_observed_runner_utc")
    if type(first) is not str:
        raise ValueError("P185_P171_FIRST_RUNNER_OBSERVATION_REQUIRED")
    try:
        first_stamp = _utc(datetime.fromisoformat(first))
    except ValueError as exc:
        raise ValueError("P185_P171_FIRST_RUNNER_OBSERVATION_REQUIRED") from exc
    if stamp < first_stamp:
        raise ValueError("P185_RUNNER_OBSERVATION_CLOCK_ROLLBACK")
    diagnostic = diagnose_p171_overlap_source(refetched, state=state)
    if (diagnostic["schema"] != P180_VERSION
            or diagnostic["conflict_classification"] != "CHANGED_OVERLAP_SHA"
            or diagnostic["overlap_sha_changed_count"] != 1
            or diagnostic["overlap_labels_missing_count"] != 0):
        raise ValueError("P185_ONLY_ONE_REVISED_AND_ZERO_MISSING_SHA")
    previous_rows = {
        item["label"]: item["sha256"]
        for item in previous["recent_native_bar_index"]
    }
    changed = [
        {
            "label": bar.native_open_label,
            "stored_sha256": previous_rows[bar.native_open_label],
            "refetched_sha256": bar.sha256(),
        }
        for bar in refetched.closed_bars
        if (bar.native_open_label in previous_rows
            and bar.sha256() != previous_rows[bar.native_open_label])
    ]
    if len(changed) != 1:
        raise ValueError("P185_DIAGNOSTIC_PRIVATE_SHA_MISMATCH")
    body: dict[str, Any] = {
        "schema": VERSION,
        "status": _STATUS,
        "source_vintage": "P171_OWNER_20261111_FRESH_EPOCH",
        "original_epoch_manifest_tip_sha256": digest(previous),
        "runner_observed_utc": stamp.isoformat(),
        "revised_source_sha_pair": changed[0],
        "redacted_diagnostic": diagnostic,
        "publisher_first_known_verified": False,
        "source_account_rights_verified": False,
        "owner_canonical_revision_approved": False,
        "historical_asof_rewrite_allowed": False,
        "may_write_d1": False,
        "may_publish_buy_sell": False,
        "broker_orders": 0,
    }
    body["proposal_content_sha256"] = digest(body)
    return validate_p171_revision_review(body)


def validate_p171_revision_review(candidate: Any) -> dict[str, Any]:
    """Recheck private SHA lineage. Digest is NOT an owner signature."""
    if type(candidate) is not dict or frozenset(candidate) != _FIELDS:
        raise ValueError("P185_EXACT_PROPOSAL_SCHEMA_REQUIRED")
    if (candidate["schema"] != VERSION
            or candidate["status"] != _STATUS
            or candidate["source_vintage"] != "P171_OWNER_20261111_FRESH_EPOCH"
            or not _sha(candidate["original_epoch_manifest_tip_sha256"])
            or any(candidate[k] is not False for k in (
                "publisher_first_known_verified",
                "source_account_rights_verified",
                "owner_canonical_revision_approved",
                "historical_asof_rewrite_allowed",
                "may_write_d1", "may_publish_buy_sell"))
            or type(candidate["broker_orders"]) is not int
            or candidate["broker_orders"] != 0):
        raise ValueError("P185_PROPOSAL_CANNOT_GRANT_AUTHORITY")
    observed = candidate["runner_observed_utc"]
    if type(observed) is not str:
        raise ValueError("P185_EXACT_OBSERVED_CLOCK")
    try:
        parsed = _utc(datetime.fromisoformat(observed))
    except ValueError as exc:
        raise ValueError("P185_EXACT_OBSERVED_CLOCK") from exc
    if parsed.isoformat() != observed:
        raise ValueError("P185_EXACT_OBSERVED_CLOCK")
    pair = candidate["revised_source_sha_pair"]
    if type(pair) is not dict or frozenset(pair) != _PAIR_FIELDS:
        raise ValueError("P185_PRIVATE_REVISED_SHA_PAIR_REQUIRED")
    label = pair["label"]
    if type(label) is not str:
        raise ValueError("P185_PRIVATE_REVISED_SHA_PAIR_REQUIRED")
    try:
        parsed_day = date.fromisoformat(label)
    except ValueError as exc:
        raise ValueError("P185_PRIVATE_REVISED_SHA_PAIR_REQUIRED") from exc
    if (parsed_day.isoformat() != label or label < "2026-11-11"
            or not _sha(pair["stored_sha256"])
            or not _sha(pair["refetched_sha256"])
            or pair["stored_sha256"] == pair["refetched_sha256"]):
        raise ValueError("P185_PRIVATE_REVISED_SHA_PAIR_REQUIRED")
    diag = candidate["redacted_diagnostic"]
    if (type(diag) is not dict
            or frozenset(diag) != _DIAGNOSTIC_FIELDS
            or diag["schema"] != P180_VERSION
            or diag["status"] != "P171_D1_OVERLAP_SOURCE_QUARANTINED_NO_COMMIT"
            or diag["source_vintage"] != "ACTIVE_P171_OWNER_FRESH_EPOCH_ONLY"
            or diag["conflict_classification"] != "CHANGED_OVERLAP_SHA"
            or any(type(diag[k]) is not int or diag[k] != expected
                   for k, expected in (
                       ("overlap_sha_changed_count", 1),
                       ("overlap_labels_missing_count", 0),
                       ("provider_price_requests_added", 0),
                       ("drive_reads_added", 0), ("drive_writes", 0),
                       ("broker_orders", 0)))
            or any(diag[k] is not False for k in (
                "source_vendor_correction_cause_proven",
                "source_publisher_first_known_verified",
                "original_numeric_rules_approved",
                "source_promotion_authorized",
                "source_quarantine_bypassed",
                "may_publish_buy_sell"))
            or any(type(diag[k]) is not int for k in (
                "previous_indexed_labels", "refetched_closed_native_bars",
                "overlap_sha_unchanged_count"))
            or diag["previous_indexed_labels"] < 1
            or diag["refetched_closed_native_bars"] < diag["previous_indexed_labels"]
            or diag["overlap_sha_unchanged_count"] != diag["previous_indexed_labels"] - 1):
        raise ValueError("P185_REDACTED_DIAGNOSTIC_NOT_FAIL_CLOSED")
    if (not _sha(candidate["proposal_content_sha256"])
            or candidate["proposal_content_sha256"] != digest({
                k: v for k, v in candidate.items()
                if k != "proposal_content_sha256"
            })):
        raise ValueError("P185_PROPOSAL_CONTENT_SHA_INVALID")
    return candidate


def public_p171_revision_review(candidate: dict[str, Any]) -> dict[str, Any]:
    """ONLY safe aggregate fields for public GitHub issue/Actions logs."""
    valid = validate_p171_revision_review(candidate)
    diag = valid["redacted_diagnostic"]
    return {
        "schema": VERSION,
        "status": _STATUS,
        "source_revision_rows_under_review": 1,
        "previous_overlap_sha_rows": diag["previous_indexed_labels"],
        "overlap_sha_changed_count": diag["overlap_sha_changed_count"],
        "overlap_labels_missing_count": 0,
        "private_source_version_retained": True,
        "publisher_first_known_verified": False,
        "source_account_rights_verified": False,
        "owner_canonical_revision_approved": False,
        "historical_asof_rewrite_allowed": False,
        "may_write_d1": False,
        "may_publish_buy_sell": False,
        "provider_price_requests_added": 0,
        "drive_reads_added": 0,
        "drive_writes": 0,
        "broker_orders": 0,
    }
