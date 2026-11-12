"""A04/P0.94 — pure source-version/calendar-snapshot custody admission RESEARCH.

A matching SHA256 proves only that these *supplied bytes* equal a supplied
digest. It DOES NOT authenticate the publisher, a feed version, a specific
EUR/USD M5 candle gap, licensing, external monotonicity or owner approval.
P0.93 public Forex-v2 documentation describes feed service availability,
not source-issued exact M5 session closures. Therefore all output verdicts
deny actual calendar waivers and H4/native-D1 production changes.

No network, local persistence, GitHub/Drive, vendor or broker IO.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
from typing import Any

from tools.mfx_fx_calendar_provenance import (
    OFFICIAL_REFERENCES, WRITER_BLOB_SHA, WRITER_ENDPOINT,
)

SCHEMA = "MFX_A04_P94_CANDIDATE_SNAPSHOT_V1"
RECEIPT = "MFX_A04_P94_CONTENT_CUSTODY_RESEARCH_RECEIPT_V1"
MAX_BYTES = 32768
MAX_H4_SLOTS = 72
H4 = timedelta(hours=4)
FIELDS = frozenset({
    "schema", "issuer", "product_id", "feed_version", "route", "symbol",
    "interval", "timezone", "price_side", "claim_scope",
    "effective_start_utc", "effective_end_utc", "closed_h4_starts_utc",
    "sequence", "parent_snapshot_sha256", "issued_at_utc",
})
PROVIDER_REFERENCES = frozenset({
    "TWELVE_DATA_FOREX_V2", "TWELVE_DATA_FOREX_TZ",
})
CLAIMS = frozenset({
    "FEED_SERVICE_AVAILABILITY", "EXACT_PROVIDER_M5_SESSION_CLOSURE",
})


def _stamp(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError("P094_TYPED_EXACT_UTC_REQUIRED")
    try:
        x = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("P094_EXACT_UTC_INVALID") from exc
    if (x.tzinfo is None or x.utcoffset() != timedelta(0)
            or x.isoformat() != value
            or x.second or x.microsecond):
        raise ValueError("P094_EXACT_UTC_REQUIRED")
    return x


def _sha(value: object) -> bool:
    return (type(value) is str and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _exact_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("P094_DUPLICATE_JSON_KEY")
        out[k] = v
    return out


@dataclass(frozen=True, slots=True)
class SnapshotCandidate:
    # Both contents and metadata are caller-supplied, NOT publisher-attested.
    raw_json: bytes
    declared_sha256: str
    publication_reference_id: str
    publication_url: str
    captured_at_utc: str
    writer_blob_sha: str = WRITER_BLOB_SHA


@dataclass(frozen=True, slots=True)
class SnapshotCustodyReceipt:
    schema: str
    status: str
    snapshot_sha256: str
    sequence: int
    parent_snapshot_sha256: str | None
    captured_at_utc: str
    effective_end_utc: str
    reference_id: str
    documented_reference_scope: str
    claim_scope: str
    submitted_gap_count: int
    exact_label_overlap_count: int
    chain_structurally_consistent: bool
    raw_bytes_match_declared_sha256: bool
    canonical_json_and_scope_valid: bool
    published_page_content_sha_verified: bool = False
    publisher_signature_verified: bool = False
    actual_mfx_feed_version_verified: bool = False
    separately_licensed_data_usage_verified: bool = False
    actual_provider_m5_session_calendar_verified: bool = False
    trusted_external_monotonic_witness_verified: bool = False
    owner_calendar_exception_go: bool = False
    automatic_weekend_gap_waiver: bool = False
    may_replace_native_h4: bool = False
    may_reduce_native_h4_requests: bool = False
    may_change_sydney_native_d1: bool = False
    numeric_buy_sell_authorized: bool = False
    broker_orders_authorized: bool = False
    network_calls: int = 0
    drive_writes: int = 0
    broker_orders: int = 0


def inspect_calendar_candidate(
    candidate: SnapshotCandidate, missing_h4_starts_utc: tuple[str, ...], *,
    reviewed_at_utc: str,
    prior_receipt: SnapshotCustodyReceipt | None = None,
) -> SnapshotCustodyReceipt:
    """Reject malformed evidence; even well-formed evidence is NO-WAIVER.

    The claimed publication URL is cross-referenced to a known public page,
    but the raw JSON is an UNATTESTED candidate; self-asserted source issuer
    and chain linkage never constitute publisher signature or anchor.
    """
    if type(candidate) is not SnapshotCandidate:
        raise ValueError("P094_CANDIDATE_TYPED_REQUIRED")
    if (type(candidate.raw_json) is not bytes or not candidate.raw_json
            or len(candidate.raw_json) > MAX_BYTES
            or not _sha(candidate.declared_sha256)
            or sha256(candidate.raw_json).hexdigest()
            != candidate.declared_sha256):
        raise ValueError("P094_RAW_CONTENT_OR_SHA_INVALID")
    if (type(candidate.publication_reference_id) is not str
            or candidate.publication_reference_id not in PROVIDER_REFERENCES
            or type(candidate.publication_url) is not str
            or candidate.publication_url !=
            OFFICIAL_REFERENCES[candidate.publication_reference_id].url
            or candidate.writer_blob_sha != WRITER_BLOB_SHA):
        raise ValueError("P094_SOURCE_REFERENCE_OR_WRITER_BLOB_MISMATCH")
    captured, reviewed = (_stamp(candidate.captured_at_utc),
                          _stamp(reviewed_at_utc))
    if captured > reviewed:
        raise ValueError("P094_CAPTURE_AFTER_REVIEW")
    if (type(missing_h4_starts_utc) is not tuple
            or len(missing_h4_starts_utc) > MAX_H4_SLOTS):
        raise ValueError("P094_BOUNDED_TYPED_GAPS_REQUIRED")
    missing = tuple(_stamp(x) for x in missing_h4_starts_utc)
    if (any(x.hour % 4 for x in missing)
            or any(a >= b for a, b in zip(missing, missing[1:]))
            or any(x + H4 > reviewed for x in missing)):
        raise ValueError("P094_GAP_ALIGNMENT_OR_CLOCK_INVALID")
    try:
        data = json.loads(candidate.raw_json.decode("utf-8"),
                          object_pairs_hook=_exact_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              ValueError("P094_NONFINITE_JSON_DENIED")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("P094_CANONICAL_JSON_REQUIRED") from exc
    if (type(data) is not dict or set(data) != FIELDS
            or json.dumps(data, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
            != candidate.raw_json):
        raise ValueError("P094_CANONICAL_JSON_AND_SCHEMA_REQUIRED")
    if (data["schema"] != SCHEMA or data["issuer"] != "TWELVE_DATA"
            or data["product_id"] != "FOREX_COMPOSITE_MID"
            or data["feed_version"] != "FOREX_API_V2"
            or data["route"] != WRITER_ENDPOINT
            or data["symbol"] != "EUR/USD"
            or data["interval"] != "5min"
            or data["timezone"] != "UTC" or data["price_side"] != "MID"
            or type(data["claim_scope"]) is not str
            or data["claim_scope"] not in CLAIMS):
        raise ValueError("P094_EXACT_PROVIDER_PRODUCT_ROUTE_SCOPE_REQUIRED")
    lo, hi, issued = (_stamp(data["effective_start_utc"]),
                      _stamp(data["effective_end_utc"]),
                      _stamp(data["issued_at_utc"]))
    if (lo.hour % 4 or hi.hour % 4 or hi <= lo
            or hi - lo > MAX_H4_SLOTS * H4
            or issued > captured):
        raise ValueError("P094_WINDOW_BOUNDS_OR_ISSUE_CLOCK_INVALID")
    labels_raw = data["closed_h4_starts_utc"]
    if (type(labels_raw) is not list or len(labels_raw) > MAX_H4_SLOTS):
        raise ValueError("P094_TYPED_BOUNDED_CLOSURE_LABELS_REQUIRED")
    labels = tuple(_stamp(x) for x in labels_raw)
    if (any(x.hour % 4 or not (lo <= x and x + H4 <= hi) for x in labels)
            or any(a >= b for a, b in zip(labels, labels[1:]))):
        raise ValueError("P094_CLOSURE_GRID_OR_SEQUENCE_INVALID")
    sequence = data["sequence"]
    parent = data["parent_snapshot_sha256"]
    if type(sequence) is not int or not 1 <= sequence <= 10000:
        raise ValueError("P094_SEQUENCE_INVALID")
    if sequence == 1:
        if parent is not None or prior_receipt is not None:
            raise ValueError("P094_GENESIS_PARENT_CONFLICT")
        chain = True
    else:
        if (not _sha(parent) or type(prior_receipt)
                is not SnapshotCustodyReceipt
                or prior_receipt.sequence + 1 != sequence
                or parent != prior_receipt.snapshot_sha256
                or candidate.declared_sha256 == parent
                or prior_receipt.reference_id != candidate.publication_reference_id
                or captured <= _stamp(prior_receipt.captured_at_utc)
                or hi < _stamp(prior_receipt.effective_end_utc)):
            raise ValueError("P094_SELF_ASSERTED_CHAIN_LINK_INVALID")
        chain = True  # Internal linkage only, not trusted monotonicity.
    overlap = sum(t in set(labels) for t in missing
                  if lo <= t and t + H4 <= hi)
    ref_scope = OFFICIAL_REFERENCES[
        candidate.publication_reference_id].scope
    if not missing:
        status = "P094_NO_GAP_RESEARCH_RECEIPT_ONLY"
    elif overlap < len(missing):
        status = "P094_INCOMPLETE_CANDIDATE_CLOSURE_COVERAGE"
    elif data["claim_scope"] != "EXACT_PROVIDER_M5_SESSION_CLOSURE":
        status = "P094_SERVICE_AVAILABILITY_NOT_M5_SESSION_EVIDENCE"
    elif ref_scope != "EXACT_PROVIDER_M5_SESSION_CLOSURE":
        status = "P094_PUBLIC_PAGE_SCOPE_NOT_EXACT_PROVIDER_M5_CLOSURE"
    else:
        status = "P094_UNAUTHENTICATED_SOURCE_BYTES_OWNER_GO_MISSING"
    return SnapshotCustodyReceipt(
        schema=RECEIPT, status=status,
        snapshot_sha256=candidate.declared_sha256,
        sequence=sequence, parent_snapshot_sha256=parent,
        captured_at_utc=candidate.captured_at_utc,
        effective_end_utc=data["effective_end_utc"],
        reference_id=candidate.publication_reference_id,
        documented_reference_scope=ref_scope,
        claim_scope=data["claim_scope"],
        submitted_gap_count=len(missing),
        exact_label_overlap_count=overlap,
        chain_structurally_consistent=chain,
        raw_bytes_match_declared_sha256=True,
        canonical_json_and_scope_valid=True,
    )
