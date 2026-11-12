"""MFX A04/P0.95 — OFFLINE owner review packet for claimed provider evidence.

This module checks *structure* and separation-of-duties of user-supplied
claims. It does NOT fetch, verify cryptographic signatures, authenticate role
identities, prove an API plan or license, establish a trusted key/witness or
enable a provider calendar gap waiver. Existing P0.93/P0.94 remain untouched.
No I/O, persistence, clock access, network credentials, trading or cache edits.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re

from tools.mfx_fx_calendar_content_custody import (
    RECEIPT as CUSTODY_SCHEMA, SnapshotCustodyReceipt,
)
from tools.mfx_fx_calendar_provenance import (
    OFFICIAL_REFERENCES, WRITER_BLOB_SHA, WRITER_ENDPOINT,
)

SCHEMA = "MFX_A04_P95_EXTERNAL_CALENDAR_OWNER_REVIEW_PACKET_V1"
UTC4 = timedelta(hours=4)
MAX_H4_SLOTS = 72
REVIEW_MAX_AGE = timedelta(days=7)
ACTOR_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{2,63}$")
SOURCE_REF = "TWELVE_DATA_FOREX_V2"
EVIDENCE_KIND = "UNVERIFIED_PROVIDER_CALENDAR_CLAIM"
PROPOSED_USE = "PRIVATE_INTERNAL_RESEARCH_CLAIM"
SIGNATURE_SCHEME = "ED25519_CLAIMED_NOT_VERIFIED"
ALLOWED_OWNER_REQUESTS = frozenset(("PENDING_REVIEW", "REQUEST_RESEARCH_REVIEW"))


def _sha(value: object) -> bool:
    return (type(value) is str and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _utc(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError("P095_EXACT_UTC_REQUIRED")
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("P095_EXACT_UTC_INVALID") from exc
    if (stamp.tzinfo is None or stamp.utcoffset() != timedelta(0)
            or stamp.isoformat() != value or stamp.second
            or stamp.microsecond or stamp.fold):
        raise ValueError("P095_EXACT_UTC_REQUIRED")
    return stamp


@dataclass(frozen=True, slots=True)
class ReviewSeparation:
    submitter_id: str
    custodian_id: str
    publisher_key_reviewer_id: str
    licensing_reviewer_id: str
    owner_decision_reviewer_id: str


@dataclass(frozen=True, slots=True)
class UnverifiedProviderReviewClaim:
    # These fields are declarations, NOT evidence authenticated here.
    evidence_kind: str
    source_reference_id: str
    source_document_url: str
    source_writer_blob_sha: str
    issuer_claimed: str
    product_claimed: str
    feed_version_claimed: str
    route_claimed: str
    symbol_claimed: str
    interval_claimed: str
    timezone_claimed: str
    price_side_claimed: str
    signed_payload_sha256_claimed: str
    signing_public_key_sha256_claimed: str
    detached_signature_sha256_claimed: str
    account_feed_mapping_sha256_claimed: str
    licensing_document_sha256_claimed: str
    licensing_purpose_claimed: str
    signature_scheme_claimed: str
    effective_start_utc: str
    effective_end_utc: str
    issuer_issued_utc: str
    evidence_collected_utc: str
    evidence_expires_utc: str
    owner_request: str


@dataclass(frozen=True, slots=True)
class CalendarReviewPacketReceipt:
    schema: str
    status: str
    candidate_snapshot_sha256: str
    candidate_sequence: int
    expected_source: str
    exact_gap_count: int
    exact_gap_count_consistent: bool
    independent_roles_claimed: bool
    claimed_signed_artifacts_structurally_present: bool
    claimed_data_rights_artifact_structurally_present: bool
    claimed_issuer_and_feed_scope_structurally_consistent: bool
    review_asof_utc: str
    # These stay false EVEN IF every claim has a valid-looking SHA and role.
    actual_publisher_signature_cryptographically_verified: bool = False
    trusted_publisher_public_key_verified: bool = False
    reviewer_identity_and_roles_independently_authenticated: bool = False
    source_feed_account_mapping_verified: bool = False
    actual_subscription_license_grant_verified: bool = False
    external_monotonic_custody_witness_verified: bool = False
    exact_gap_labels_proven_by_snapshot_sha: bool = False
    real_provider_session_calendar_verified: bool = False
    owner_operational_go: bool = False
    automatic_weekend_gap_waiver: bool = False
    may_reduce_native_h4_requests: bool = False
    may_replace_native_h4: bool = False
    may_change_sydney_native_d1: bool = False
    numeric_buy_sell_authorized: bool = False
    broker_orders_authorized: bool = False
    network_calls: int = 0
    drive_writes: int = 0
    broker_orders: int = 0


def review_external_calendar_packet(
    custody: SnapshotCustodyReceipt,
    proposal: UnverifiedProviderReviewClaim,
    actors: ReviewSeparation,
    requested_gap_h4_starts_utc: tuple[str, ...], *,
    reviewed_at_utc: str,
) -> CalendarReviewPacketReceipt:
    """Strict scoped review of *proposed* evidence, never an approval API."""
    if (type(custody) is not SnapshotCustodyReceipt
            or custody.schema != CUSTODY_SCHEMA
            or custody.raw_bytes_match_declared_sha256 is not True
            or custody.canonical_json_and_scope_valid is not True
            or custody.chain_structurally_consistent is not True
            or custody.publisher_signature_verified is not False
            or custody.actual_provider_m5_session_calendar_verified is not False
            or custody.automatic_weekend_gap_waiver is not False
            or custody.owner_calendar_exception_go is not False
            or custody.actual_mfx_feed_version_verified is not False
            or custody.separately_licensed_data_usage_verified is not False
            or custody.trusted_external_monotonic_witness_verified is not False
            or custody.may_replace_native_h4 is not False
            or custody.may_reduce_native_h4_requests is not False
            or custody.may_change_sydney_native_d1 is not False
            or custody.numeric_buy_sell_authorized is not False
            or custody.broker_orders_authorized is not False
            or custody.network_calls != 0
            or custody.drive_writes != 0
            or custody.broker_orders != 0
            or not _sha(custody.snapshot_sha256)
            or type(custody.sequence) is not int
            or custody.sequence < 1):
        raise ValueError("P095_PRIOR_P94_CUSTODY_RECEIPT_UNTRUSTED")
    if type(proposal) is not UnverifiedProviderReviewClaim:
        raise ValueError("P095_TYPED_PROPOSAL_REQUIRED")
    if type(actors) is not ReviewSeparation:
        raise ValueError("P095_TYPED_SEPARATION_REQUIRED")
    principals = (
        actors.submitter_id, actors.custodian_id,
        actors.publisher_key_reviewer_id, actors.licensing_reviewer_id,
        actors.owner_decision_reviewer_id,
    )
    if (any(type(x) is not str or not ACTOR_PATTERN.fullmatch(x)
            for x in principals)
            or len(set(principals)) != len(principals)):
        raise ValueError("P095_CLAIMED_REVIEWERS_NOT_INDEPENDENT")
    if (proposal.evidence_kind != EVIDENCE_KIND
            or proposal.source_reference_id != SOURCE_REF
            or proposal.source_document_url !=
            OFFICIAL_REFERENCES[SOURCE_REF].url
            or proposal.source_writer_blob_sha != WRITER_BLOB_SHA
            or proposal.issuer_claimed != "TWELVE_DATA"
            or proposal.product_claimed != "FOREX_COMPOSITE_MID"
            or proposal.feed_version_claimed != "FOREX_API_V2"
            or proposal.route_claimed != WRITER_ENDPOINT
            or proposal.symbol_claimed != "EUR/USD"
            or proposal.interval_claimed != "5min"
            or proposal.timezone_claimed != "UTC"
            or proposal.price_side_claimed != "MID"
            or proposal.licensing_purpose_claimed != PROPOSED_USE
            or proposal.signature_scheme_claimed != SIGNATURE_SCHEME
            or type(proposal.owner_request) is not str
            or proposal.owner_request not in ALLOWED_OWNER_REQUESTS):
        raise ValueError("P095_EXTERNAL_CLAIM_WRONG_SOURCE_OR_UNSAFE_ACTION")
    hashes = (
        proposal.signed_payload_sha256_claimed,
        proposal.signing_public_key_sha256_claimed,
        proposal.detached_signature_sha256_claimed,
        proposal.account_feed_mapping_sha256_claimed,
        proposal.licensing_document_sha256_claimed,
    )
    if (any(not _sha(s) for s in hashes)
            or len(set(hashes + (custody.snapshot_sha256,))) != 6):
        raise ValueError("P095_CLAIMED_EVIDENCE_SHA_MISSING_OR_REUSED")
    now, begin, end = (_utc(reviewed_at_utc),
                       _utc(proposal.effective_start_utc),
                       _utc(proposal.effective_end_utc))
    issued, captured, expires = (
        _utc(proposal.issuer_issued_utc),
        _utc(proposal.evidence_collected_utc),
        _utc(proposal.evidence_expires_utc),
    )
    custody_capture, custody_end = (
        _utc(custody.captured_at_utc), _utc(custody.effective_end_utc))
    if (begin.hour % 4 or begin.minute
            or end.hour % 4 or end.minute
            or not begin < end or end - begin > MAX_H4_SLOTS * UTC4
            or end != custody_end
            or issued > captured or issued > custody_capture
            or not custody_capture <= captured <= now < expires
            or now - captured > REVIEW_MAX_AGE
            or now < end or expires <= issued):
        raise ValueError("P095_EXPIRED_REPLAYED_OR_MISSCOPED_CLOCK")
    if (type(requested_gap_h4_starts_utc) is not tuple
            or len(requested_gap_h4_starts_utc) > MAX_H4_SLOTS):
        raise ValueError("P095_BOUNDED_TYPED_GAP_LABELS_REQUIRED")
    gaps = tuple(_utc(x) for x in requested_gap_h4_starts_utc)
    if (any(x.hour % 4 or x.minute or not (begin <= x and x + UTC4 <= end)
            for x in gaps)
            or any(a >= b for a, b in zip(gaps, gaps[1:]))
            or any(x + UTC4 > now for x in gaps)):
        raise ValueError("P095_GAP_GRID_OR_EFFECTIVE_SCOPE_INVALID")
    same_count = (custody.submitted_gap_count == len(gaps)
                  and custody.exact_label_overlap_count == len(gaps))
    # P0.94 stores counts, not hashed individual gaps. Even if counts match,
    # this module cannot prove these exact labels were in the source bytes.
    status = (
        "P095_GAP_COUNTS_OR_PRIOR_SCOPE_INCOMPLETE_NO_GO"
        if not same_count else
        "P095_COMPLETE_UNVERIFIED_REVIEW_PACKET_NO_PRODUCTION_AUTHORITY"
    )
    return CalendarReviewPacketReceipt(
        schema=SCHEMA, status=status,
        candidate_snapshot_sha256=custody.snapshot_sha256,
        candidate_sequence=custody.sequence, expected_source=SOURCE_REF,
        exact_gap_count=len(gaps), exact_gap_count_consistent=same_count,
        independent_roles_claimed=True,
        claimed_signed_artifacts_structurally_present=True,
        claimed_data_rights_artifact_structurally_present=True,
        claimed_issuer_and_feed_scope_structurally_consistent=True,
        review_asof_utc=reviewed_at_utc,
    )
