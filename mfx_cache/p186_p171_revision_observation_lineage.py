"""P0.186 — pure, PRIVATE P171 D1 source-version observation lineage.

A hash-linked in-memory *proposal* for review, not a persisted event journal.
Entries carry runner-observed time only: NEVER publisher first-known, signed
ownership, licensed retention, canonical admission, as-of price truth, or trade.
No network/Drive/broker access, no mutation of original P171/legacy D1 source.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from mfx_cache.p185_p171_d1_revision_review import (
    validate_p171_revision_review,
)
from mfx_cache.td_m5_codec import digest

SCHEMA = "MFX_P186_P171_SHA_VERSION_OBSERVATION_LINEAGE_V1"
STATE = "PRIVATE_PROPOSAL_NOT_PERSISTED_OR_CANONICAL"
MAX_ENTRIES = 64
_KEYS = frozenset({
    "schema", "state", "sequence", "origin_p171_manifest_sha256",
    "native_open_label", "original_stored_bar_sha256",
    "refetched_bar_sha256", "first_runner_observed_utc",
    "candidate_receipt_sha256", "previous_lineage_entry_sha256",
    "source_publisher_first_known_verified", "source_account_rights_verified",
    "owner_canonical_revision_approved", "historical_asof_rewrite_allowed",
    "may_write_drive", "may_publish_buy_sell", "broker_orders",
    "entry_sha256",
})
_FALSE_FIELDS = (
    "source_publisher_first_known_verified", "source_account_rights_verified",
    "owner_canonical_revision_approved", "historical_asof_rewrite_allowed",
    "may_write_drive", "may_publish_buy_sell",
)


def _sha(value: Any) -> bool:
    return (type(value) is str and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _utc(when: Any) -> datetime:
    if (type(when) is not datetime or when.tzinfo is None
            or when.utcoffset() != timedelta(0)):
        raise ValueError("P186_STRICT_UTC_TIMESTAMP_REQUIRED")
    return when


def _read_utc(text: Any) -> datetime:
    if type(text) is not str:
        raise ValueError("P186_STRICT_UTC_TIMESTAMP_REQUIRED")
    try:
        when = _utc(datetime.fromisoformat(text))
    except ValueError as exc:
        raise ValueError("P186_STRICT_UTC_TIMESTAMP_REQUIRED") from exc
    if when.isoformat() != text:
        raise ValueError("P186_NONCANONICAL_UTC_TIMESTAMP")
    return when


def verify_private_p171_lineage(
    entries: Any, *, expected_p171_manifest_sha256: str,
) -> tuple[dict[str, Any], ...]:
    """Revalidate every prior hash/parent/time/source identity; no I/O.

    The expected P171 archive tip digest MUST come from the separately
    independently full-SHA-audited P171 source, not from this ledger itself.
    """
    if not _sha(expected_p171_manifest_sha256):
        raise ValueError("P186_PINNED_P171_MANIFEST_SHA_REQUIRED")
    if type(entries) is not tuple or len(entries) > MAX_ENTRIES:
        raise ValueError("P186_BOUNDED_TUPLE_LINEAGE_REQUIRED")
    last_sha: str | None = None
    last_time: datetime | None = None
    anchor_label: str | None = None
    anchor_original: str | None = None
    prior_observed_sha: str | None = None
    for pos, entry in enumerate(entries, 1):
        if type(entry) is not dict or frozenset(entry) != _KEYS:
            raise ValueError("P186_EXACT_PRIVATE_ENTRY_SCHEMA_REQUIRED")
        if (entry["schema"] != SCHEMA or entry["state"] != STATE
                or type(entry["sequence"]) is not int
                or entry["sequence"] != pos
                or entry["origin_p171_manifest_sha256"]
                    != expected_p171_manifest_sha256
                or entry["previous_lineage_entry_sha256"] != last_sha
                or not all(_sha(entry[key]) for key in (
                    "original_stored_bar_sha256", "refetched_bar_sha256",
                    "candidate_receipt_sha256", "entry_sha256"))
                or entry["original_stored_bar_sha256"]
                    == entry["refetched_bar_sha256"]
                or any(entry[field] is not False for field in _FALSE_FIELDS)
                or type(entry["broker_orders"]) is not int
                or entry["broker_orders"] != 0):
            raise ValueError("P186_PRIVATE_CHAIN_INTEGRITY_OR_AUTHORITY_DENIED")
        label = entry["native_open_label"]
        if (type(label) is not str or len(label) != 10
                or label < "2026-11-11"):
            raise ValueError("P186_INVALID_P171_SESSION_LABEL")
        # P185 checked this date's valid ISO day. Recheck for untrusted input.
        from datetime import date
        try:
            if date.fromisoformat(label).isoformat() != label:
                raise ValueError("P186_INVALID_P171_SESSION_LABEL")
        except ValueError as exc:
            raise ValueError("P186_INVALID_P171_SESSION_LABEL") from exc
        observed = _read_utc(entry["first_runner_observed_utc"])
        if last_time is not None and observed <= last_time:
            raise ValueError("P186_RUNNER_TIME_NOT_STRICTLY_INCREASING")
        if anchor_label is not None and (
                label != anchor_label
                or entry["original_stored_bar_sha256"] != anchor_original):
            raise ValueError("P186_DIFFERENT_LABEL_OR_STORED_SHA_IN_ONE_LINEAGE")
        if prior_observed_sha is not None and (
                entry["refetched_bar_sha256"] == prior_observed_sha):
            raise ValueError("P186_CONSECUTIVE_DUPLICATE_VERSION_NOT_ALLOWED")
        if entry["entry_sha256"] != digest({
            key: value for key, value in entry.items()
            if key != "entry_sha256"
        }):
            raise ValueError("P186_HASH_CHAIN_TAMPERED")
        last_sha = entry["entry_sha256"]
        last_time = observed
        anchor_label = label
        anchor_original = entry["original_stored_bar_sha256"]
        prior_observed_sha = entry["refetched_bar_sha256"]
    return tuple(deepcopy(entry) for entry in entries)


def append_private_p171_observation(
    entries: Any, *, candidate: dict[str, Any],
    expected_p171_manifest_sha256: str,
) -> tuple[dict[str, Any], ...]:
    """Append ONE new runner-observed SHA version, or idempotently reuse tail.

    This function never stores the proposal or picks a canonical D1 revision.
    Publisher first-known is unknown; runner UTC is only a custody observation.
    """
    c = validate_p171_revision_review(candidate)
    current = verify_private_p171_lineage(
        entries, expected_p171_manifest_sha256=expected_p171_manifest_sha256,
    )
    if c["original_epoch_manifest_tip_sha256"] != expected_p171_manifest_sha256:
        raise ValueError("P186_CANDIDATE_DIFFERENT_P171_MANIFEST")
    if len(current) >= MAX_ENTRIES:
        raise ValueError("P186_REVIEW_CAPACITY_HOLD")
    pair = c["revised_source_sha_pair"]
    stamp = _read_utc(c["runner_observed_utc"])
    if current:
        previous = current[-1]
        if (pair["label"] != previous["native_open_label"]
                or pair["stored_sha256"]
                    != previous["original_stored_bar_sha256"]):
            raise ValueError("P186_DIFFERENT_SOURCE_VERSION_LINEAGE")
        if stamp < _read_utc(previous["first_runner_observed_utc"]):
            raise ValueError("P186_RUNNER_CLOCK_ROLLBACK")
        if pair["refetched_sha256"] == previous["refetched_bar_sha256"]:
            return current  # same version observed again; KEEP FIRST known runner time
        if stamp == _read_utc(previous["first_runner_observed_utc"]):
            raise ValueError("P186_NEW_VERSION_NEEDS_NEW_RUNNER_TIME")
    entry: dict[str, Any] = {
        "schema": SCHEMA,
        "state": STATE,
        "sequence": len(current) + 1,
        "origin_p171_manifest_sha256": expected_p171_manifest_sha256,
        "native_open_label": pair["label"],
        "original_stored_bar_sha256": pair["stored_sha256"],
        "refetched_bar_sha256": pair["refetched_sha256"],
        "first_runner_observed_utc": c["runner_observed_utc"],
        "candidate_receipt_sha256": c["proposal_content_sha256"],
        "previous_lineage_entry_sha256": (
            current[-1]["entry_sha256"] if current else None
        ),
        "source_publisher_first_known_verified": False,
        "source_account_rights_verified": False,
        "owner_canonical_revision_approved": False,
        "historical_asof_rewrite_allowed": False,
        "may_write_drive": False,
        "may_publish_buy_sell": False,
        "broker_orders": 0,
    }
    entry["entry_sha256"] = digest(entry)
    return verify_private_p171_lineage(
        (*current, entry), expected_p171_manifest_sha256=expected_p171_manifest_sha256,
    )


def private_p171_versions_known_by_runner_asof(
    entries: Any, *, expected_p171_manifest_sha256: str, asof_utc: datetime,
) -> tuple[dict[str, Any], ...]:
    """PRIVATE runner-observation prefix, not publisher-known source truth.

    Never substitutes any member for an approved canonical D1 price.
    """
    when = _utc(asof_utc)
    audited = verify_private_p171_lineage(
        entries, expected_p171_manifest_sha256=expected_p171_manifest_sha256,
    )
    return tuple(deepcopy(x) for x in audited if
                 _read_utc(x["first_runner_observed_utc"]) <= when)


def public_p171_lineage_status(
    entries: Any, *, expected_p171_manifest_sha256: str,
) -> dict[str, Any]:
    """Safe public counters only. Never expose SHA, date, quote, or object ID."""
    checked = verify_private_p171_lineage(
        entries, expected_p171_manifest_sha256=expected_p171_manifest_sha256,
    )
    return {
        "schema": SCHEMA,
        "status": STATE,
        "private_revision_observations": len(checked),
        "versioned_private_lineage_validated": True,
        "source_publisher_first_known_verified": False,
        "source_account_rights_verified": False,
        "owner_canonical_revision_approved": False,
        "historical_asof_rewrite_allowed": False,
        "may_write_drive": False,
        "may_publish_buy_sell": False,
        "drive_reads": 0,
        "drive_writes": 0,
        "vendor_price_requests": 0,
        "broker_orders": 0,
    }
