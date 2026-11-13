"""MFX P059 — OFFLINE D1 source-revision *candidate* chain, never a writer.

This module is intentionally not imported by production cache jobs.
Its output proves only structured, tamper-evident candidate bytes; SHA is
NOT a trusted timestamp, publisher signature, license, or trading approval.
Original sealed H4/D1/M5 archives and schedules remain untouched.
"""
from __future__ import annotations

from dataclasses import asdict, fields
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import (
    RECENT_INDEX_LIMIT, _bar_valid, check_native_manifest,
)
from mfx_cache.td_m5_codec import digest

SCHEMA = "MFX_P059_D1_SOURCE_REVISION_CANDIDATE_V1"
SCOPE = ("EUR/USD", "1day", "Australia/Sydney")
INCIDENT_LABEL = "2026-11-11"
SHA_ALPHABET = frozenset("0123456789abcdef")
PRICE_KEYS = ("open", "high", "low", "close")
METADATA_KEYS = tuple(
    field.name for field in fields(NativeFXBar)
    if field.name not in PRICE_KEYS
)

# Deliberately exact. No optional trade gate, owner approval state,
# revised canonical price, or provider first-known assertion is modeled.
FIELDS = frozenset({
    "schema", "state", "symbol", "interval", "exchange_timezone",
    "native_open_label", "original_manifest_sha256",
    "original_bar_sha256", "candidate_bar_sha256",
    "changed_numeric_ohlc_fields", "changed_nonprice_metadata_fields",
    "source_observation_time_utc", "source_observation_time_quality",
    "revision_sequence", "previous_candidate_receipt_sha256",
    "previous_candidate_observed_utc", "source_full_archive_audit_by_caller_required",
    "publisher_revision_cause_verified", "provider_first_known_verified",
    "publisher_data_rights_verified", "owner_source_policy_approved",
    "may_mutate_canonical_archive", "may_publish_buy_sell",
    "approved_numeric_signals", "provider_requests_by_planner",
    "drive_reads_by_planner", "drive_writes_by_planner", "broker_orders",
    "receipt_sha256",
})


def _sha(value: Any) -> bool:
    return (type(value) is str and len(value) == 64
            and all(char in SHA_ALPHABET for char in value))


def _timestamp(value: Any) -> datetime:
    if type(value) is not str:
        raise ValueError("P059_CANDIDATE_EXACT_UTC_REQUIRED")
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("P059_CANDIDATE_EXACT_UTC_REQUIRED") from exc
    if (stamp.tzinfo is None or stamp.utcoffset() != timedelta(0)
            or stamp.isoformat() != value):
        raise ValueError("P059_CANDIDATE_EXACT_UTC_REQUIRED")
    return stamp


def validate_revision_candidate(
    candidate: Any, *, parent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a HOLD-only receipt/lineage; never promote source authority.

    A digest/parent relation proves local integrity only, NOT independent
    publisher first-known, external attestation or real historical truth.
    """
    if type(candidate) is not dict or frozenset(candidate) != FIELDS:
        raise ValueError("P059_CANDIDATE_SCHEMA_DENIED")
    if (candidate["schema"] != SCHEMA
            or candidate["state"] != "DRAFT_REQUIRES_OWNER_SOURCE_REVIEW"
            or (candidate["symbol"], candidate["interval"],
                candidate["exchange_timezone"]) != SCOPE
            or candidate["native_open_label"] != INCIDENT_LABEL
            or candidate["source_observation_time_quality"] !=
                "CALLER_CLAIM_NOT_INDEPENDENT_PROVIDER_FIRST_KNOWN"
            or candidate["source_full_archive_audit_by_caller_required"] is not True
            or any(candidate[k] is not False for k in (
                "publisher_revision_cause_verified",
                "provider_first_known_verified",
                "publisher_data_rights_verified",
                "owner_source_policy_approved",
                "may_mutate_canonical_archive", "may_publish_buy_sell",
                "approved_numeric_signals"))
            or any(type(candidate[k]) is not int or candidate[k] != 0
                   for k in ("provider_requests_by_planner",
                             "drive_reads_by_planner",
                             "drive_writes_by_planner", "broker_orders"))
            or type(candidate["revision_sequence"]) is not int
            or candidate["revision_sequence"] < 1
            or not all(_sha(candidate[k]) for k in (
                "original_manifest_sha256", "original_bar_sha256",
                "candidate_bar_sha256", "receipt_sha256"))
            or candidate["original_bar_sha256"] == candidate["candidate_bar_sha256"]):
        raise ValueError("P059_CANDIDATE_POLICY_AND_SCOPE_DENIED")

    now = _timestamp(candidate["source_observation_time_utc"])
    numeric = candidate["changed_numeric_ohlc_fields"]
    meta = candidate["changed_nonprice_metadata_fields"]
    if (type(numeric) is not list or not numeric
            or any(type(x) is not str for x in numeric)
            or numeric != [k for k in PRICE_KEYS if k in numeric]
            or len(numeric) != len(set(numeric))
            or type(meta) is not list
            or any(type(x) is not str for x in meta)
            or meta != [k for k in METADATA_KEYS if k in meta]
            or len(meta) != len(set(meta))):
        raise ValueError("P059_CANDIDATE_NUMERIC_DELTA_REQUIRED")

    if parent is None:
        if (candidate["revision_sequence"] != 1
                or candidate["previous_candidate_receipt_sha256"] is not None
                or candidate["previous_candidate_observed_utc"] is not None):
            raise ValueError("P059_CANDIDATE_ROOT_LINK_REQUIRED")
    else:
        validate_revision_candidate(parent)
        if (candidate["revision_sequence"] != 2
                or candidate["previous_candidate_receipt_sha256"] !=
                    parent["receipt_sha256"]
                or candidate["previous_candidate_observed_utc"] !=
                    parent["source_observation_time_utc"]
                or candidate["original_manifest_sha256"] !=
                    parent["original_manifest_sha256"]
                or candidate["original_bar_sha256"] !=
                    parent["original_bar_sha256"]
                or candidate["candidate_bar_sha256"] ==
                    parent["candidate_bar_sha256"]
                or now <= _timestamp(parent["source_observation_time_utc"])):
            raise ValueError("P059_CANDIDATE_PARENT_OR_ANTIROLLBACK_DENIED")
    body = {k: v for k, v in candidate.items() if k != "receipt_sha256"}
    if digest(body) != candidate["receipt_sha256"]:
        raise ValueError("P059_CANDIDATE_RECEIPT_SHA_MISMATCH")
    return candidate


def draft_d1_revision_candidate(
    *, original_manifest: dict[str, Any],
    sha_verified_recent: tuple[NativeFXBar, ...],
    refetched_batch: NativeFXBatch,
    observed_at_utc: datetime,
    parent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Draft an inert proposal from a caller-audited prior SHA index.

    The caller MUST have completed full unmodified archive SHA audit and
    provider retrieval independently. This planner never does either.
    It refuses multi-bar drift, absent index, incomplete overlap, unsupported
    symbol/timezone, or a price-side change.
    """
    symbol, interval, zone = SCOPE
    check_native_manifest(original_manifest, symbol=symbol,
                          interval=interval, zone=zone)
    if (type(observed_at_utc) is not datetime
            or observed_at_utc.tzinfo is None
            or observed_at_utc.utcoffset() != timedelta(0)):
        raise ValueError("P059_CANDIDATE_EXACT_UTC_REQUIRED")
    observed = observed_at_utc.isoformat()
    _timestamp(observed)
    # The D1 label is a Sydney-local session date, NOT UTC midnight.
    # Even a caller-provided source observation may not precede the
    # first possible moment the historical D1 candle was closed.
    if (observed_at_utc.astimezone(ZoneInfo(zone)).date()
            <= date.fromisoformat(INCIDENT_LABEL)):
        raise ValueError("P059_CANDIDATE_OBSERVATION_BEFORE_D1_CLOSE")
    if (type(sha_verified_recent) is not tuple
            or len(sha_verified_recent) !=
                len(original_manifest["recent_native_bar_index"])
            or len(sha_verified_recent) > RECENT_INDEX_LIMIT
            or type(refetched_batch) is not NativeFXBatch
            or type(refetched_batch.closed_bars) is not tuple
            or (refetched_batch.symbol, refetched_batch.interval,
                refetched_batch.exchange_timezone) != SCOPE
            or refetched_batch.time_reference !=
                "EXCHANGE_LOCAL_SESSION_DATE"
            or refetched_batch.source != "TWELVE_DATA_COMPOSITE_MID"
            or refetched_batch.is_provider_native is not True
            or refetched_batch.vendor_calls_made_by_parser != 0
            or refetched_batch.google_drive_writes != 0
            or refetched_batch.confirmed_buy_sell_signals != 0
            or refetched_batch.broker_orders != 0):
        raise ValueError("P059_CANDIDATE_UNATTESTED_SOURCE_SCOPE")

    index = original_manifest["recent_native_bar_index"]
    old_index = tuple((b.native_open_label, b.sha256())
                      for b in sha_verified_recent)
    if old_index != tuple((e["label"], e["sha256"]) for e in index):
        raise ValueError("P059_CANDIDATE_PRIOR_INDEX_SHA_MISMATCH")
    for bar in sha_verified_recent + refetched_batch.closed_bars:
        _bar_valid(bar, symbol=symbol, interval=interval, zone=zone)
        if (date.fromisoformat(bar.native_open_label) >=
                observed_at_utc.astimezone(ZoneInfo(zone)).date()):
            raise ValueError("P059_CANDIDATE_UNCLOSED_SOURCE_LABEL")
    current = refetched_batch.closed_bars
    if (type(current) is not tuple
            or tuple(b.native_open_label for b in current) !=
                tuple(sorted(set(b.native_open_label for b in current)))):
        raise ValueError("P059_CANDIDATE_UNSORTED_OR_DUPLICATE_FRESH")

    new_by_label = {b.native_open_label: b for b in current}
    if any(label not in new_by_label for label, _ in old_index):
        raise ValueError("P059_CANDIDATE_INCOMPLETE_SOURCE_OVERLAP")
    changed = [
        (old, new_by_label[old.native_open_label])
        for old in sha_verified_recent
        if old.sha256() != new_by_label[old.native_open_label].sha256()
    ]
    if (len(changed) != 1
            or changed[0][0].native_open_label != INCIDENT_LABEL):
        raise ValueError("P059_CANDIDATE_SINGLE_D1_INCIDENT_ONLY")
    old, new = changed[0]
    altered_numeric = [
        key for key in PRICE_KEYS
        if Decimal(getattr(old, key)) != Decimal(getattr(new, key))
    ]
    if not altered_numeric:
        raise ValueError("P059_CANDIDATE_NUMERIC_OHLC_REQUIRED")
    changed_metadata = [
        key for key in METADATA_KEYS
        if getattr(old, key) != getattr(new, key)
    ]

    if parent is not None:
        validate_revision_candidate(parent)
        if (parent["original_manifest_sha256"] != digest(original_manifest)
                or parent["original_bar_sha256"] != old.sha256()
                or parent["candidate_bar_sha256"] == new.sha256()
                or observed_at_utc <= _timestamp(
                    parent["source_observation_time_utc"])):
            raise ValueError("P059_CANDIDATE_PARENT_SOURCE_OR_CLOCK_DRIFT")
    record = {
        "schema": SCHEMA,
        "state": "DRAFT_REQUIRES_OWNER_SOURCE_REVIEW",
        "symbol": symbol,
        "interval": interval,
        "exchange_timezone": zone,
        "native_open_label": INCIDENT_LABEL,
        "original_manifest_sha256": digest(original_manifest),
        "original_bar_sha256": old.sha256(),
        "candidate_bar_sha256": new.sha256(),
        "changed_numeric_ohlc_fields": altered_numeric,
        "changed_nonprice_metadata_fields": changed_metadata,
        "source_observation_time_utc": observed,
        "source_observation_time_quality":
            "CALLER_CLAIM_NOT_INDEPENDENT_PROVIDER_FIRST_KNOWN",
        "revision_sequence": 1 if parent is None else 2,
        "previous_candidate_receipt_sha256": (
            None if parent is None else parent["receipt_sha256"]),
        "previous_candidate_observed_utc": (
            None if parent is None else parent["source_observation_time_utc"]),
        "source_full_archive_audit_by_caller_required": True,
        "publisher_revision_cause_verified": False,
        "provider_first_known_verified": False,
        "publisher_data_rights_verified": False,
        "owner_source_policy_approved": False,
        "may_mutate_canonical_archive": False,
        "may_publish_buy_sell": False,
        "approved_numeric_signals": False,
        "provider_requests_by_planner": 0,
        "drive_reads_by_planner": 0,
        "drive_writes_by_planner": 0,
        "broker_orders": 0,
    }
    record["receipt_sha256"] = digest(record)
    return validate_revision_candidate(record, parent=parent)
