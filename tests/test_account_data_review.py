import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from forex_trading.account_data_review import (
    AccountContractClaim, AccountDataReviewPacket, CandidateStorageLocation,
    DataRetentionClaim, ReviewState, RevocationNoticeClaim, review_account_data_packet,
)
from forex_trading.cache_storage_review import DurableStorageProposal, StorageKind
from forex_trading.market_data import BarSide, Timeframe
from forex_trading.source_qualification import (
    DocumentBasis, FeedModel, LicensedUse, PublicCapabilityClaim,
    RightDecision, UseRightsClaim,
)

UTC=timezone.utc
T=datetime(2026,11,7,9,0,tzinfo=UTC)
PURPOSES=(LicensedUse.API_ACCESS,LicensedUse.STORE_RAW,
          LicensedUse.DERIVE_BARS,LicensedUse.HISTORICAL_REPLAY,
          LicensedUse.INTERNAL_BACKTEST,LicensedUse.CACHE_INCREMENTAL)


def capability(**kw):
    d=dict(provider_id="SYN_VENDOR", product_id="SYN_PRODUCT",
           instrument_version="EURUSD_SYN", feed_model=FeedModel.BID_ASK_CANDLES,
           quote_sides=frozenset({BarSide.BID,BarSide.ASK}),
           timeframes=frozenset({Timeframe.M1,Timeframe.M5,Timeframe.M15}),
           documentation_url="https://example.org/fictional-technical-features",
           documentation_first_known_utc=T-timedelta(days=1),
           timestamp_semantics_documented=True,
           historical_account_price_parity_independently_verified=True)
    d.update(kw)
    return PublicCapabilityClaim(**d)


def account(**kw):
    d=dict(provider_id="SYN_VENDOR",product_id="SYN_PRODUCT",
           jurisdiction_code="SYN_REGION",account_scope_ref="ScopeOpaqueRef",
           plan_ref="DemoPlanRef",contract_revision_ref="ContractRevisionOne",
           effective_from_utc=T-timedelta(days=30),
           expires_utc=T+timedelta(days=180),
           first_seen_by_us_utc=T-timedelta(days=1))
    d.update(kw)
    return AccountContractClaim(**d)


def right(purpose,**kw):
    d=dict(purpose=purpose,decision=RightDecision.ALLOW_CLAIMED,
           document_basis=DocumentBasis.ACCOUNT_TERMS,
           evidence_url="https://example.org/fictional-account-contract",
           evidence_sha256="a"*64,first_known_utc=T-timedelta(days=1),
           expires_utc=T+timedelta(days=180))
    d.update(kw)
    return UseRightsClaim(**d)


def retention(**kw):
    d=dict(maximum_days_claimed=30,
           allowed_storage_regions_claimed=frozenset({"SYN_REGION"}),
           derived_indicators_may_be_retained_claimed=True)
    d.update(kw)
    return DataRetentionClaim(**d)


def storage(**kw):
    d=dict(location_ref="OfflineEncryptedCandidate",
           storage_kind=StorageKind.ENCRYPTED_LOCAL_PROPOSED,
           schema_version="SchemaVOne",
           encrypted_at_rest_claim=True,atomic_commit_claim=True,
           digest_verification_claim=True,restart_recovery_claim=True,
           append_only_audit_claim=True,retention_days_proposed=30,
           revocation_purge_process_documented=True)
    d.update(kw)
    return CandidateStorageLocation("CandidateOfflineStore","SYN_REGION",
                                    DurableStorageProposal(**d))


def packet(**kw):
    d=dict(account=account(),public_capability=capability(),
           rights=tuple(right(x) for x in PURPOSES),
           retention=retention(),storage=storage(),revocation=None)
    d.update(kw)
    return AccountDataReviewPacket(**d)


def review(value=None,*,requested=30,now=T,age=timedelta(days=90)):
    return review_account_data_packet(
        packet() if value is None else value,now,
        requested_cache_retention_days=requested,max_review_age=age)


def notice(*,when=None,first_seen=None):
    return RevocationNoticeClaim(
        first_seen_by_us_utc=first_seen or T-timedelta(seconds=1),
        effective_utc=when or T-timedelta(minutes=1),
        evidence_sha256_claim="f"*64,
    )


class AccountDataReviewTests(unittest.TestCase):
    def test_perfect_claims_only_ready_for_external_review(self):
        r=review()
        self.assertEqual(r.state,ReviewState.READY_FOR_INDEPENDENT_REVIEW)
        self.assertTrue(r.account_specific_claims_consistent)
        self.assertTrue(r.proposed_storage_controls_complete)
        self.assertFalse(r.account_entitlement_independently_verified)
        self.assertFalse(r.storage_host_approved)
        self.assertFalse(r.may_fetch_real_fx_data)
        self.assertFalse(r.may_cache_real_fx_data)
        self.assertFalse(r.may_retain_derived_indicators)
        self.assertFalse(r.may_run_real_backtests)
        self.assertIn("READY_PAPERWORK_ONLY_EXTERNAL_LEGAL_AND_VENDOR_CHECK_REQUIRED",
                      r.reasons)

    def test_public_docs_do_not_prove_account_rights(self):
        rr=list(packet().rights)
        rr[0]=replace(rr[0],document_basis=DocumentBasis.PUBLIC_DOCUMENTATION)
        r=review(packet(rights=tuple(rr)))
        self.assertEqual(r.state,ReviewState.BLOCKED_MISSING_EVIDENCE)

    def test_missing_source_quote_side_rejects_review(self):
        p=packet(public_capability=capability(quote_sides=frozenset({BarSide.MID})))
        self.assertEqual(review(p).state,ReviewState.BLOCKED_MISSING_EVIDENCE)

    def test_provider_scope_mismatch_blocked(self):
        p=packet(account=account(provider_id="OtherProvider"))
        r=review(p)
        self.assertIn("ACCOUNT_PRODUCT_OR_PROVIDER_MISMATCH",r.reasons)

    def test_product_scope_mismatch_blocked(self):
        p=packet(account=account(product_id="OtherProduct"))
        self.assertIn("ACCOUNT_PRODUCT_OR_PROVIDER_MISMATCH",review(p).reasons)

    def test_no_contract_until_effective(self):
        p=packet(account=account(effective_from_utc=T+timedelta(days=1)))
        self.assertIn("ACCOUNT_CONTRACT_NOT_YET_EFFECTIVE",review(p).reasons)

    def test_contract_expired_requires_stop_and_retention_review(self):
        p=packet(account=account(expires_utc=T))
        r=review(p)
        self.assertEqual(r.state,ReviewState.SUSPEND_AND_REVIEW_RETENTION)
        self.assertTrue(r.requires_cessation_and_retention_review)
        self.assertIn("STOP_FETCH_AND_WRITES_PRESERVE_AUDIT_PENDING_REVIEW",r.reasons)

    def test_expired_scope_requires_stop_even_if_contract_active(self):
        rights=list(packet().rights)
        rights[0]=replace(rights[0],expires_utc=T)
        r=review(packet(rights=tuple(rights)))
        self.assertEqual(r.state,ReviewState.SUSPEND_AND_REVIEW_RETENTION)
        self.assertTrue(r.requires_cessation_and_retention_review)

    def test_expired_contract_cannot_self_purge(self):
        r=review(packet(account=account(expires_utc=T)))
        self.assertIn("ACTUAL_QUARANTINE_OR_PURGE_NOT_IMPLEMENTED",r.reasons)
        self.assertFalse(r.may_cache_real_fx_data)

    def test_revocation_seen_and_effective_stops_new_use(self):
        r=review(packet(revocation=notice()))
        self.assertEqual(r.state,ReviewState.SUSPEND_AND_REVIEW_RETENTION)
        self.assertIn("REVOCATION_NOTICED_STOP_ACCESS_AND_REVIEW_RETENTION",r.reasons)

    def test_future_known_revocation_not_retroactive(self):
        r=review(packet(revocation=notice(
            first_seen=T+timedelta(days=1),
            when=T+timedelta(days=2))))
        self.assertIn("REVOCATION_NOTICE_FUTURE_KNOWN",r.reasons)
        self.assertEqual(r.state,ReviewState.BLOCKED_MISSING_EVIDENCE)

    def test_future_effective_known_notice_pending(self):
        r=review(packet(revocation=notice(when=T+timedelta(days=1))))
        self.assertEqual(r.state,ReviewState.READY_FOR_INDEPENDENT_REVIEW)
        self.assertIn("REVOCATION_SCHEDULED_NOT_YET_EFFECTIVE",r.reasons)
        self.assertFalse(r.may_fetch_real_fx_data)

    def test_retention_longer_than_vendor_claim_is_blocked(self):
        r=review(requested=31)
        self.assertIn("REQUESTED_RETENTION_EXCEEDS_VENDOR_CLAIM",r.reasons)
        self.assertEqual(r.state,ReviewState.BLOCKED_MISSING_EVIDENCE)

    def test_retention_unknown_requires_external_answer(self):
        r=review(packet(retention=retention(maximum_days_claimed=None)))
        self.assertIn("VENDOR_RETENTION_LIMIT_NOT_ESTABLISHED",r.reasons)

    def test_storage_proposal_retention_below_requested_blocks(self):
        p=packet(storage=storage(retention_days_proposed=7))
        r=review(p,requested=30)
        self.assertIn("CACHE_RETENTION_EXCEEDS_STORAGE_PROPOSAL",r.reasons)

    def test_storage_geo_residency_not_claimed_blocks(self):
        loc=replace(packet().storage,region_ref="OtherRegion")
        r=review(packet(storage=loc))
        self.assertIn("STORAGE_RESIDENCY_NOT_COVERED_BY_CLAIM",r.reasons)

    def test_missing_derived_indicator_retention_blocks(self):
        r=review(packet(retention=retention(
            derived_indicators_may_be_retained_claimed=False)))
        self.assertIn("DERIVED_INDICATOR_RETENTION_NOT_ESTABLISHED",r.reasons)

    def test_no_source_capability_blocks_even_if_rights_claimed(self):
        r=review(packet(public_capability=None))
        self.assertEqual(r.state,ReviewState.BLOCKED_MISSING_EVIDENCE)
        self.assertIn("ACCOUNT_PRODUCT_OR_PROVIDER_MISMATCH",r.reasons)

    def test_rights_missing_individually_blocks_review(self):
        rights=tuple(x for x in packet().rights if x.purpose is not LicensedUse.CACHE_INCREMENTAL)
        r=review(packet(rights=rights))
        self.assertIn("RIGHT_MISSING:CACHE_INCREMENTAL",r.reasons)

    def test_not_all_rights_can_be_inferred_from_api_access(self):
        r=review(packet(rights=(right(LicensedUse.API_ACCESS),)))
        self.assertFalse(r.account_specific_claims_consistent)

    def test_inmemory_only_not_a_durable_store(self):
        p=packet(storage=storage(storage_kind=StorageKind.MEMORY_SYNTHETIC))
        r=review(p)
        self.assertIn("NOT_PERSISTENT_CACHE_ARCHITECTURE",r.reasons)
        self.assertFalse(r.proposed_storage_controls_complete)

    def test_missing_storage_encryption_blocks(self):
        r=review(packet(storage=storage(encrypted_at_rest_claim=False)))
        self.assertFalse(r.proposed_storage_controls_complete)
        self.assertIn("STORAGE_CONTROLS_NOT_COMPLETE",r.reasons)

    def test_stale_evidence_requires_update(self):
        p=packet(account=account(first_seen_by_us_utc=T-timedelta(days=120)))
        r=review(p)
        self.assertIn("ACCOUNT_ENTITLEMENT_REVIEW_STALE",r.reasons)

    def test_future_obtained_contract_cannot_be_known_at_past_scan(self):
        p=packet(account=account(first_seen_by_us_utc=T+timedelta(days=1)))
        r=review(p)
        self.assertIn("ACCOUNT_EVIDENCE_FUTURE_KNOWN",r.reasons)

    def test_missing_rights_document_is_explicit(self):
        r=review(packet(rights=()))
        self.assertIn("NO_ACCOUNT_RIGHTS_DOCUMENTS",r.reasons)

    def test_untrusted_denial_blocks(self):
        rights=list(packet().rights)
        rights[1]=replace(rights[1],decision=RightDecision.DENY)
        r=review(packet(rights=tuple(rights)))
        self.assertEqual(r.state,ReviewState.BLOCKED_MISSING_EVIDENCE)

    def test_explicit_unknown_backtest_right_blocks(self):
        rights=list(packet().rights)
        rights[4]=replace(rights[4],decision=RightDecision.UNKNOWN)
        r=review(packet(rights=tuple(rights)))
        self.assertFalse(r.may_run_real_backtests)

    def test_no_raw_account_uri_or_credentials_in_meta(self):
        with self.assertRaises(ValueError):
            account(account_scope_ref="https://vendor.example/private")
        with self.assertRaises(ValueError):
            account(account_scope_ref="secretToken")

    def test_invalid_retention_claim_rejected(self):
        with self.assertRaises(ValueError):
            retention(maximum_days_claimed=0)
        with self.assertRaises(ValueError):
            retention(maximum_days_claimed=True)

    def test_invalid_regions_claim_type_rejected(self):
        with self.assertRaises(TypeError):
            retention(allowed_storage_regions_claimed=["SYN_REGION"])

    def test_contract_expiration_invalid_rejected(self):
        with self.assertRaisesRegex(ValueError,"EXPIRES_BEFORE_EFFECTIVE"):
            account(expires_utc=T-timedelta(days=31))

    def test_forged_vendor_attestation_string_cannot_unlock_permissions(self):
        p=packet(account=account(contract_revision_ref="ApprovedByVendorClaim"))
        r=review(p)
        self.assertTrue(r.account_specific_claims_consistent)
        self.assertFalse(r.account_entitlement_independently_verified)
        self.assertFalse(r.may_fetch_real_fx_data)

    def test_empty_storage_region_ref_rejected(self):
        with self.assertRaises(ValueError):
            replace(packet().storage,region_ref="")

    def test_invalid_revocation_digest_rejected(self):
        with self.assertRaisesRegex(ValueError,"DIGEST"):
            RevocationNoticeClaim(T,T,"bad")
    
    def test_invalid_requested_retention_rejected(self):
        for n in (0,True,3651):
            with self.subTest(n=n),self.assertRaises(ValueError):
                review(requested=n)

    def test_naive_asof_time_rejected(self):
        with self.assertRaises(ValueError):
            review(now=datetime(2026,11,7,9,0))

    def test_evidence_age_policy_cannot_be_disabled(self):
        with self.assertRaises(ValueError):
            review(age=timedelta(0))

    def test_storage_candidate_is_never_automatically_selected_or_activated(self):
        r=review()
        self.assertTrue(r.proposed_storage_controls_complete)
        self.assertFalse(r.storage_host_approved)
        self.assertFalse(r.may_cache_real_fx_data)

    def test_review_packet_types_explicit(self):
        with self.assertRaises(TypeError):
            packet(rights=[right(LicensedUse.API_ACCESS)])
        with self.assertRaises(TypeError):
            review_account_data_packet("untrusted",T,requested_cache_retention_days=10)

