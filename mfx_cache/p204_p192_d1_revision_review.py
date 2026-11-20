"""P0.204: private, non-authorizing P192 18-Nov D1 numeric revision review.

Build ONLY from full-SHA-audited immutable P192 chunk and the SAME refused
native D1 provider batch. The private SHA pair is NEVER emitted to GitHub logs.
A content SHA is not an owner signature, publisher timestamp or market licence.
No I/O, no canonical revisions, no trading, no extra provider or Drive calls.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from mfx_cache.native_d1_epoch_20261118 import (
    FreshEpochState, SCHEMA as P192_SCHEMA,
)
from mfx_cache.native_fx_htf import NativeFXBatch
from mfx_cache.p200_p192_d1_sha_diff_forensics import (
    VERSION as P200_VERSION, diagnose_p192_owner_overlap,
)
from mfx_cache.td_m5_codec import digest

VERSION = "MFX_P204_P192_D1_NUMERIC_REVISION_PRIVATE_OWNER_REVIEW_V1"
STATUS = "RESEARCH_ONLY_REVISION_PROPOSAL_NO_SOURCE_ADMISSION"
ROOT_DATE = "2026-11-18"
FIELDS = frozenset((
    "schema", "status", "source_epoch", "original_epoch_manifest_sha256",
    "origin_v1_manifest_sha256", "runner_observed_utc",
    "private_revised_source_sha_pair", "redacted_diagnostic",
    "source_publisher_first_known_verified", "source_account_rights_verified",
    "owner_canonical_revision_approved", "historical_asof_rewrite_allowed",
    "may_write_d1", "may_publish_buy_sell", "may_trade",
    "provider_price_requests_added", "drive_reads_added_by_candidate",
    "drive_writes", "broker_orders", "proposal_content_sha256",
))
PAIR_FIELDS = frozenset(("label", "stored_sha256", "refetched_sha256"))
DIAGNOSTIC_FIELDS = frozenset((
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


def _sha(value: Any) -> bool:
    return (type(value) is str and len(value) == 64
            and all(ch in "0123456789abcdef" for ch in value))


def _utc(value: Any) -> datetime:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P204_STRICT_UTC_OBSERVATION_REQUIRED")
    return value


def _validate_diagnostic(value: Any) -> None:
    if type(value) is not dict or frozenset(value) != DIAGNOSTIC_FIELDS:
        raise ValueError("P204_EXACT_P200_DIAGNOSTIC_REQUIRED")
    want = {
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
    for key, expected in want.items():
        if type(value.get(key)) is not type(expected) or value[key] != expected:
            raise ValueError("P204_UNAPPROVED_SOURCE_DIAGNOSTIC")
    n = value.get("refetched_closed_native_bars_count")
    if type(n) is not int or not 1 <= n <= 120:
        raise ValueError("P204_BOUNDED_REFETCHED_D1_COUNT_REQUIRED")


def build_p192_revision_review(
    *, state: FreshEpochState, sealed_chunk: dict[str, Any],
    refetched: NativeFXBatch, origin_v1_sha: str,
    runner_observed_utc: datetime,
) -> dict[str, Any]:
    """Private SHA pair for review; all source promotion flags stay FALSE."""
    now = _utc(runner_observed_utc)
    if (type(state) is not FreshEpochState
            or state.manifests != 1 or state.chunks != 1
            or state.orphan_chunk is not None
            or type(state.last_manifest) is not dict):
        raise ValueError("P204_EXACT_SHA_AUDITED_SINGLE_P192_ROOT_REQUIRED")
    m = state.last_manifest
    if (m.get("schema") != P192_SCHEMA
            or m.get("owner_rebaseline_date") != ROOT_DATE
            or m.get("last_native_open_label") != ROOT_DATE
            or m.get("total_closed_bars") != 1
            or m.get("batch_count") != 1
            or m.get("owner_approved_cache_rebaseline") is not True
            or m.get("publisher_first_known_verified") is not False
            or m.get("may_publish_buy_sell") is not False
            or m.get("origin_v1_manifest_sha256") != origin_v1_sha
            or not _sha(origin_v1_sha)):
        raise ValueError("P204_UNVERIFIED_OWNER_P192_ROOT")
    first = m.get("first_observed_runner_utc")
    if type(first) is not str:
        raise ValueError("P204_SEALED_RUNNER_OBSERVATION_REQUIRED")
    try:
        then = _utc(datetime.fromisoformat(first))
    except ValueError as exc:
        raise ValueError("P204_SEALED_RUNNER_OBSERVATION_REQUIRED") from exc
    if then.isoformat() != first or now < then:
        raise ValueError("P204_RUNNER_CLOCK_BEFORE_SOURCE_FIRST_OBSERVATION")
    diag = diagnose_p192_owner_overlap(
        state=state, sealed_chunk=sealed_chunk, refetched=refetched,
        origin_v1_sha=origin_v1_sha,
    )
    _validate_diagnostic(diag)
    index = m.get("recent_native_bar_index")
    if (type(index) is not list or len(index) != 1
            or type(index[0]) is not dict
            or frozenset(index[0]) != {"label", "sha256"}
            or index[0]["label"] != ROOT_DATE
            or not _sha(index[0]["sha256"])):
        raise ValueError("P204_INVALID_ONE_ROW_ORIGINAL_SHA_INDEX")
    rows = tuple(bar for bar in refetched.closed_bars
                 if bar.native_open_label == ROOT_DATE)
    if len(rows) != 1 or rows[0].sha256() == index[0]["sha256"]:
        raise ValueError("P204_SINGLE_CHANGED_SOURCE_ROW_REQUIRED")

    candidate: dict[str, Any] = {
        "schema": VERSION,
        "status": STATUS,
        "source_epoch": "P192_D1_FRESH_20261118",
        "original_epoch_manifest_sha256": digest(m),
        "origin_v1_manifest_sha256": origin_v1_sha,
        "runner_observed_utc": now.isoformat(),
        "private_revised_source_sha_pair": {
            "label": ROOT_DATE,
            "stored_sha256": index[0]["sha256"],
            "refetched_sha256": rows[0].sha256(),
        },
        "redacted_diagnostic": diag,
        "source_publisher_first_known_verified": False,
        "source_account_rights_verified": False,
        "owner_canonical_revision_approved": False,
        "historical_asof_rewrite_allowed": False,
        "may_write_d1": False,
        "may_publish_buy_sell": False,
        "may_trade": False,
        "provider_price_requests_added": 0,
        "drive_reads_added_by_candidate": 0,
        "drive_writes": 0,
        "broker_orders": 0,
    }
    candidate["proposal_content_sha256"] = digest(candidate)
    return validate_p192_revision_review(candidate)


def validate_p192_revision_review(candidate: Any) -> dict[str, Any]:
    """Reject forged authority; private digest is evidence, not approval."""
    if type(candidate) is not dict or frozenset(candidate) != FIELDS:
        raise ValueError("P204_EXACT_PRIVATE_REVIEW_SCHEMA_REQUIRED")
    expected = {
        "schema": VERSION,
        "status": STATUS,
        "source_epoch": "P192_D1_FRESH_20261118",
        "source_publisher_first_known_verified": False,
        "source_account_rights_verified": False,
        "owner_canonical_revision_approved": False,
        "historical_asof_rewrite_allowed": False,
        "may_write_d1": False,
        "may_publish_buy_sell": False,
        "may_trade": False,
        "provider_price_requests_added": 0,
        "drive_reads_added_by_candidate": 0,
        "drive_writes": 0,
        "broker_orders": 0,
    }
    for key, val in expected.items():
        if type(candidate.get(key)) is not type(val) or candidate[key] != val:
            raise ValueError("P204_PRIVATE_REVIEW_CAN_NEVER_APPROVE_SOURCE")
    if (not _sha(candidate.get("original_epoch_manifest_sha256"))
            or not _sha(candidate.get("origin_v1_manifest_sha256"))):
        raise ValueError("P204_PRIVATE_ROOT_SHA_REQUIRED")
    observed = candidate.get("runner_observed_utc")
    if type(observed) is not str:
        raise ValueError("P204_STRICT_OBSERVED_CLOCK_REQUIRED")
    try:
        stamp = _utc(datetime.fromisoformat(observed))
    except ValueError as exc:
        raise ValueError("P204_STRICT_OBSERVED_CLOCK_REQUIRED") from exc
    if stamp.isoformat() != observed:
        raise ValueError("P204_STRICT_OBSERVED_CLOCK_REQUIRED")
    pair = candidate.get("private_revised_source_sha_pair")
    if (type(pair) is not dict or frozenset(pair) != PAIR_FIELDS
            or pair.get("label") != ROOT_DATE
            or not _sha(pair.get("stored_sha256"))
            or not _sha(pair.get("refetched_sha256"))
            or pair["stored_sha256"] == pair["refetched_sha256"]):
        raise ValueError("P204_EXACT_PRIVATE_SHA_REVISION_PAIR_REQUIRED")
    _validate_diagnostic(candidate.get("redacted_diagnostic"))
    if (not _sha(candidate.get("proposal_content_sha256"))
            or candidate["proposal_content_sha256"] != digest({
                key: value for key, value in candidate.items()
                if key != "proposal_content_sha256"
            })):
        raise ValueError("P204_PRIVATE_PROPOSAL_SHA_MISMATCH")
    return candidate


def public_p192_revision_review(candidate: dict[str, Any]) -> dict[str, Any]:
    """Price/row-date/SHA-free GitHub logs; source still quarantined."""
    body = validate_p192_revision_review(candidate)
    return {
        "schema": VERSION,
        "status": STATUS,
        "source_epoch": "P192_D1_FRESH_20261118",
        "revision_numeric_ohlc_rows_under_review": 1,
        "original_sha_audited_overlap_rows": 1,
        "source_variant_private_sha_pair_retained_in_memory_only": True,
        "provider_first_known_not_established": True,
        "source_publisher_first_known_verified": False,
        "source_account_rights_verified": False,
        "owner_canonical_revision_approved": False,
        "historical_asof_rewrite_allowed": False,
        "may_write_d1": False,
        "may_publish_buy_sell": False,
        "may_trade": False,
        "provider_price_requests_added": 0,
        "drive_reads_added_by_candidate": 0,
        "drive_writes": 0,
        "broker_orders": 0,
        "redacted_diagnostic_status": body["redacted_diagnostic"]["status"],
    }
