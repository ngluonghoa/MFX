"""P0.95 hermetic reviewer separation, provenance and future-capture QA."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from tools.mfx_fx_calendar_content_custody import SnapshotCustodyReceipt
from tools.mfx_fx_calendar_owner_review import (
    EVIDENCE_KIND, PROPOSED_USE, SIGNATURE_SCHEME, SCHEMA,
    ReviewSeparation, UnverifiedProviderReviewClaim,
    review_external_calendar_packet,
)
from tools.mfx_fx_calendar_provenance import (
    OFFICIAL_REFERENCES, WRITER_BLOB_SHA, WRITER_ENDPOINT,
)
from test_a04_p94_fx_calendar_content_custody import check as p94_check

NOW = "2026-11-12T12:00:00+00:00"
SAT = "2026-11-07T08:00:00+00:00"
SUN = "2026-11-08T08:00:00+00:00"


def roles():
    return ReviewSeparation(
        submitter_id="submitter01",
        custodian_id="custodian02",
        publisher_key_reviewer_id="security03",
        licensing_reviewer_id="licensing04",
        owner_decision_reviewer_id="owner05",
    )


def claim():
    return UnverifiedProviderReviewClaim(
        evidence_kind=EVIDENCE_KIND,
        source_reference_id="TWELVE_DATA_FOREX_V2",
        source_document_url=OFFICIAL_REFERENCES["TWELVE_DATA_FOREX_V2"].url,
        source_writer_blob_sha=WRITER_BLOB_SHA,
        issuer_claimed="TWELVE_DATA",
        product_claimed="FOREX_COMPOSITE_MID",
        feed_version_claimed="FOREX_API_V2",
        route_claimed=WRITER_ENDPOINT,
        symbol_claimed="EUR/USD", interval_claimed="5min",
        timezone_claimed="UTC", price_side_claimed="MID",
        signed_payload_sha256_claimed="1"*64,
        signing_public_key_sha256_claimed="2"*64,
        detached_signature_sha256_claimed="3"*64,
        account_feed_mapping_sha256_claimed="4"*64,
        licensing_document_sha256_claimed="5"*64,
        licensing_purpose_claimed=PROPOSED_USE,
        signature_scheme_claimed=SIGNATURE_SCHEME,
        effective_start_utc="2026-11-07T00:00:00+00:00",
        effective_end_utc="2026-11-11T00:00:00+00:00",
        issuer_issued_utc="2026-11-07T00:00:00+00:00",
        evidence_collected_utc="2026-11-12T11:00:00+00:00",
        evidence_expires_utc="2026-12-01T00:00:00+00:00",
        owner_request="PENDING_REVIEW",
    )


def evaluate(*, custody=None, proposal=None, actors=None,
             gaps=(SAT,SUN), now=NOW):
    return review_external_calendar_packet(
        p94_check() if custody is None else custody,
        claim() if proposal is None else proposal,
        roles() if actors is None else actors,
        gaps, reviewed_at_utc=now,
    )


class P95ExternalCalendarReviewTests(TestCase):
    def test_01_complete_packet_is_only_research(self):
        self.assertEqual(evaluate().status,
                         "P095_COMPLETE_UNVERIFIED_REVIEW_PACKET_NO_PRODUCTION_AUTHORITY")

    def test_02_research_schema(self):
        self.assertEqual(evaluate().schema, SCHEMA)

    def test_03_snapshot_sha_is_p94_receipt(self):
        self.assertEqual(evaluate().candidate_snapshot_sha256,
                         p94_check().snapshot_sha256)

    def test_04_claimed_roles_are_separate(self):
        self.assertTrue(evaluate().independent_roles_claimed)

    def test_05_roles_are_not_actually_authenticated(self):
        self.assertFalse(evaluate().reviewer_identity_and_roles_independently_authenticated)

    def test_06_claimed_signatures_never_verified(self):
        r=evaluate()
        self.assertFalse(r.actual_publisher_signature_cryptographically_verified)
        self.assertFalse(r.trusted_publisher_public_key_verified)

    def test_07_claimed_plan_mapping_not_verified(self):
        self.assertFalse(evaluate().source_feed_account_mapping_verified)

    def test_08_claimed_license_not_proven(self):
        self.assertFalse(evaluate().actual_subscription_license_grant_verified)

    def test_09_explicit_data_rights_claim_presence_only(self):
        self.assertTrue(evaluate().claimed_data_rights_artifact_structurally_present)

    def test_10_self_asserted_witness_not_authority(self):
        self.assertFalse(evaluate().external_monotonic_custody_witness_verified)

    def test_11_h4_gap_labels_not_cryptographically_bound(self):
        self.assertFalse(evaluate().exact_gap_labels_proven_by_snapshot_sha)

    def test_12_no_authenticated_calendar(self):
        self.assertFalse(evaluate().real_provider_session_calendar_verified)

    def test_13_no_owner_go(self):
        self.assertFalse(evaluate().owner_operational_go)

    def test_14_weekend_no_auto_waiver(self):
        self.assertFalse(evaluate().automatic_weekend_gap_waiver)

    def test_15_h4_native_no_replace_or_reduction(self):
        r=evaluate()
        self.assertFalse(r.may_replace_native_h4)
        self.assertFalse(r.may_reduce_native_h4_requests)

    def test_16_sydney_d1_unchanged(self):
        self.assertFalse(evaluate().may_change_sydney_native_d1)

    def test_17_no_numeric_buy_sell(self):
        self.assertFalse(evaluate().numeric_buy_sell_authorized)

    def test_18_no_broker_trade(self):
        self.assertFalse(evaluate().broker_orders_authorized)

    def test_19_zero_live_io(self):
        r=evaluate()
        self.assertEqual((r.network_calls,r.drive_writes,r.broker_orders),(0,0,0))

    def test_20_no_ohlc_or_secrets_in_receipt(self):
        r=repr(evaluate())
        self.assertNotIn("1.10000",r)
        self.assertNotIn("refresh_token",r)

    def test_21_wrong_custody_type_denied(self):
        with self.assertRaisesRegex(ValueError,"PRIOR_P94"):
            evaluate(custody={})

    def test_22_custody_unverified_sha_denied(self):
        with self.assertRaisesRegex(ValueError,"PRIOR_P94"):
            evaluate(custody=replace(p94_check(),raw_bytes_match_declared_sha256=False))

    def test_23_custody_fake_issuer_signature_denied(self):
        with self.assertRaisesRegex(ValueError,"PRIOR_P94"):
            evaluate(custody=replace(p94_check(),publisher_signature_verified=True))

    def test_24_custody_false_chain_denied(self):
        with self.assertRaisesRegex(ValueError,"PRIOR_P94"):
            evaluate(custody=replace(p94_check(),chain_structurally_consistent=False))

    def test_25_custody_fake_go_denied(self):
        with self.assertRaisesRegex(ValueError,"PRIOR_P94"):
            evaluate(custody=replace(p94_check(),owner_calendar_exception_go=True))

    def test_26_wrong_proposal_type_denied(self):
        with self.assertRaisesRegex(ValueError,"TYPED_PROPOSAL"):
            evaluate(proposal={})

    def test_27_wrong_actors_type_denied(self):
        with self.assertRaisesRegex(ValueError,"TYPED_SEPARATION"):
            evaluate(actors={})

    def test_28_same_owner_as_submitter_denied(self):
        a=roles()
        with self.assertRaisesRegex(ValueError,"REVIEWERS_NOT_INDEPENDENT"):
            evaluate(actors=replace(a,owner_decision_reviewer_id=a.submitter_id))

    def test_29_same_security_as_custodian_denied(self):
        a=roles()
        with self.assertRaisesRegex(ValueError,"REVIEWERS_NOT_INDEPENDENT"):
            evaluate(actors=replace(a,publisher_key_reviewer_id=a.custodian_id))

    def test_30_same_license_as_owner_denied(self):
        a=roles()
        with self.assertRaisesRegex(ValueError,"REVIEWERS_NOT_INDEPENDENT"):
            evaluate(actors=replace(a,licensing_reviewer_id=a.owner_decision_reviewer_id))

    def test_31_principal_empty_or_whitespace_denied(self):
        for bad in ("", " user", "user name"):
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,"REVIEWERS_NOT_INDEPENDENT"):
                evaluate(actors=replace(roles(),submitter_id=bad))

    def test_32_principal_bool_denied(self):
        with self.assertRaisesRegex(ValueError,"REVIEWERS_NOT_INDEPENDENT"):
            evaluate(actors=replace(roles(),submitter_id=True))

    def test_33_unsafe_owner_approval_denied(self):
        with self.assertRaisesRegex(ValueError,"UNSAFE_ACTION"):
            evaluate(proposal=replace(claim(),owner_request="PRODUCTION_GO"))

    def test_34_request_research_review_only(self):
        r=evaluate(proposal=replace(claim(),owner_request="REQUEST_RESEARCH_REVIEW"))
        self.assertFalse(r.owner_operational_go)

    def test_35_wrong_issuer_denied(self):
        with self.assertRaisesRegex(ValueError,"WRONG_SOURCE"):
            evaluate(proposal=replace(claim(),issuer_claimed="OANDA"))

    def test_36_wrong_feed_version_denied(self):
        with self.assertRaisesRegex(ValueError,"WRONG_SOURCE"):
            evaluate(proposal=replace(claim(),feed_version_claimed="FOREX_V1"))

    def test_37_wrong_provider_document_denied(self):
        with self.assertRaisesRegex(ValueError,"WRONG_SOURCE"):
            evaluate(proposal=replace(claim(),source_document_url="https://example.invalid"))

    def test_38_wrong_writer_blob_denied(self):
        with self.assertRaisesRegex(ValueError,"WRONG_SOURCE"):
            evaluate(proposal=replace(claim(),source_writer_blob_sha="0"*40))

    def test_39_wrong_symbol_denied(self):
        with self.assertRaisesRegex(ValueError,"WRONG_SOURCE"):
            evaluate(proposal=replace(claim(),symbol_claimed="GBP/USD"))

    def test_40_wrong_interval_denied(self):
        with self.assertRaisesRegex(ValueError,"WRONG_SOURCE"):
            evaluate(proposal=replace(claim(),interval_claimed="4h"))

    def test_41_wrong_timezone_denied(self):
        with self.assertRaisesRegex(ValueError,"WRONG_SOURCE"):
            evaluate(proposal=replace(claim(),timezone_claimed="Australia/Sydney"))

    def test_42_wrong_price_side_denied(self):
        with self.assertRaisesRegex(ValueError,"WRONG_SOURCE"):
            evaluate(proposal=replace(claim(),price_side_claimed="BID"))

    def test_43_rights_claimed_public_redistribution_denied(self):
        with self.assertRaisesRegex(ValueError,"UNSAFE_ACTION"):
            evaluate(proposal=replace(claim(),licensing_purpose_claimed="PUBLIC_REDISTRIBUTION"))

    def test_44_unverified_algorithm_only(self):
        with self.assertRaisesRegex(ValueError,"UNSAFE_ACTION"):
            evaluate(proposal=replace(claim(),signature_scheme_claimed="VERIFIED_ED25519"))

    def test_45_missing_signing_key_sha_denied(self):
        with self.assertRaisesRegex(ValueError,"SHA_MISSING"):
            evaluate(proposal=replace(claim(),signing_public_key_sha256_claimed=""))

    def test_46_duplicate_signature_sha_denied(self):
        with self.assertRaisesRegex(ValueError,"SHA_MISSING"):
            evaluate(proposal=replace(claim(),
                detached_signature_sha256_claimed=claim().signed_payload_sha256_claimed))

    def test_47_claim_sha_same_as_snapshot_sha_denied(self):
        with self.assertRaisesRegex(ValueError,"SHA_MISSING"):
            evaluate(proposal=replace(claim(),signed_payload_sha256_claimed=p94_check().snapshot_sha256))

    def test_48_future_collected_denied(self):
        with self.assertRaisesRegex(ValueError,"EXPIRED_REPLAYED"):
            evaluate(proposal=replace(claim(),evidence_collected_utc="2026-11-12T13:00:00+00:00"))

    def test_49_expired_at_review_denied(self):
        with self.assertRaisesRegex(ValueError,"EXPIRED_REPLAYED"):
            evaluate(proposal=replace(claim(),evidence_expires_utc=NOW))

    def test_50_seven_day_old_collection_still_allowed(self):
        r=evaluate(now="2026-11-19T11:00:00+00:00")
        self.assertFalse(r.owner_operational_go)

    def test_51_more_than_seven_days_stale(self):
        with self.assertRaisesRegex(ValueError,"EXPIRED_REPLAYED"):
            evaluate(now="2026-11-19T11:01:00+00:00")

    def test_52_issuer_issued_after_capture_denied(self):
        with self.assertRaisesRegex(ValueError,"EXPIRED_REPLAYED"):
            evaluate(proposal=replace(claim(),issuer_issued_utc="2026-11-12T11:30:00+00:00"))

    def test_53_wrong_effective_end_denied(self):
        with self.assertRaisesRegex(ValueError,"EXPIRED_REPLAYED"):
            evaluate(proposal=replace(claim(),effective_end_utc="2026-11-12T00:00:00+00:00"))

    def test_54_effective_start_bad_minute_denied(self):
        with self.assertRaisesRegex(ValueError,"EXPIRED_REPLAYED"):
            evaluate(proposal=replace(claim(),effective_start_utc="2026-11-07T00:05:00+00:00"))

    def test_55_naive_utc_review_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_UTC"):
            evaluate(now="2026-11-12T12:00:00")

    def test_56_non_utc_capture_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_UTC"):
            evaluate(proposal=replace(claim(),evidence_collected_utc="2026-11-12T18:00:00+07:00"))

    def test_57_wrong_gap_type_denied(self):
        with self.assertRaisesRegex(ValueError,"BOUNDED_TYPED"):
            evaluate(gaps=[SAT])

    def test_58_unaligned_gap_minute_denied(self):
        with self.assertRaisesRegex(ValueError,"GAP_GRID"):
            evaluate(gaps=("2026-11-07T08:05:00+00:00",))

    def test_59_duplicate_h4_gaps_denied(self):
        with self.assertRaisesRegex(ValueError,"GAP_GRID"):
            evaluate(gaps=(SAT,SAT))

    def test_60_unsorted_h4_gaps_denied(self):
        with self.assertRaisesRegex(ValueError,"GAP_GRID"):
            evaluate(gaps=(SUN,SAT))

    def test_61_gap_outside_claimed_window_denied(self):
        with self.assertRaisesRegex(ValueError,"GAP_GRID"):
            evaluate(gaps=("2026-11-11T04:00:00+00:00",))

    def test_62_missing_source_gap_claim_never_go(self):
        r=evaluate(gaps=(SAT,))
        self.assertFalse(r.exact_gap_count_consistent)
        self.assertEqual(r.status,"P095_GAP_COUNTS_OR_PRIOR_SCOPE_INCOMPLETE_NO_GO")

    def test_63_no_gap_claim_never_go(self):
        r=evaluate(gaps=())
        self.assertFalse(r.exact_gap_count_consistent)
        self.assertFalse(r.owner_operational_go)

    def test_64_no_role_attestation_even_correct_name(self):
        r=evaluate()
        self.assertTrue(r.independent_roles_claimed)
        self.assertFalse(r.reviewer_identity_and_roles_independently_authenticated)

    def test_65_input_immutability(self):
        p,a,c=claim(),roles(),p94_check()
        evaluate(custody=c,proposal=p,actors=a)
        self.assertEqual(p,claim())
        self.assertEqual(a,roles())
        self.assertEqual(c,p94_check())

    def test_66_no_api_credential_leak(self):
        r=repr(evaluate())
        self.assertNotIn("MFX_GDRIVE_OAUTH",r)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY",r)

    def test_67_unhashable_owner_request_rejected(self):
        with self.assertRaisesRegex(ValueError,"UNSAFE_ACTION"):
            evaluate(proposal=replace(claim(),owner_request=[]))

    def test_68_prior_claimed_feed_auth_denied(self):
        with self.assertRaisesRegex(ValueError,"PRIOR_P94"):
            evaluate(custody=replace(p94_check(),
                                   actual_mfx_feed_version_verified=True))

    def test_69_prior_claimed_live_native_change_denied(self):
        with self.assertRaisesRegex(ValueError,"PRIOR_P94"):
            evaluate(custody=replace(p94_check(),may_replace_native_h4=True))
