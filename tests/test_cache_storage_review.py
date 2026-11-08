import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from forex_trading.cache_core import CachePartition, CandleSnapshot
from forex_trading.cache_storage_review import (
    StorageKind, DurableStorageProposal, assess_durable_cache_proposal,
    make_synthetic_generation, validate_synthetic_generation_chain,
)
from forex_trading.market_data import BarSide, Timeframe
from forex_trading.source_qualification import SourceQualification


T = datetime(2026, 11, 7, tzinfo=timezone.utc)
M = timedelta(minutes=1)


def partition(**kw):
    d=dict(provider_id="synthetic-provider",broker_product_ref="SYNTH",
           instrument_version="EURUSD-v1",side=BarSide.BID,
           timeframe=Timeframe.M5,calendar_version="SYN-CAL",
           aggregation_version="SYN-AGG",source_timezone_policy="UTC-SYN",
           rights_policy_ref="NO_VENDOR_RIGHT",schema_version="v1")
    d.update(kw)
    return CachePartition(**d)


def snap(**kw):
    d=dict(partition=partition(),closed_bars=(),
           checked_at_utc=T,source_head_claim="synthetic-r1")
    d.update(kw)
    return CandleSnapshot(**d)


def proposal(**kw):
    d=dict(location_ref="CANDIDATE-OFFLINE-STORE",storage_kind=StorageKind.ENCRYPTED_LOCAL_PROPOSED,
           schema_version="v1",encrypted_at_rest_claim=True,
           atomic_commit_claim=True,digest_verification_claim=True,
           restart_recovery_claim=True,append_only_audit_claim=True,
           retention_days_proposed=30,revocation_purge_process_documented=True)
    d.update(kw)
    return DurableStorageProposal(**d)


def qual(**kw):
    d=dict(public_api_candidate_fit=True,stated_rights_complete_for_review=True,
           review_packet_ready=True,vendor_entitlement_independently_verified=False,
           may_ingest_real_data=False,may_cache_or_store_real_data=False,
           may_run_real_backtest=False,reasons=())
    d.update(kw)
    return SourceQualification(**d)


class CacheStorageReviewTests(unittest.TestCase):
    def test_positive_control_claims_still_no_storage_grant(self):
        got=assess_durable_cache_proposal(proposal(),qual())
        self.assertTrue(got.control_claims_complete)
        self.assertFalse(got.provider_retention_right_independently_verified)
        self.assertFalse(got.host_security_approved)
        self.assertFalse(got.may_write_real_data)
        self.assertFalse(got.may_restore_real_data)
        self.assertIn("NO_PRODUCTION_IO_BACKEND_PRESENT",got.outstanding)

    def test_memory_synthetic_not_durable(self):
        got=assess_durable_cache_proposal(
            proposal(storage_kind=StorageKind.MEMORY_SYNTHETIC),qual())
        self.assertFalse(got.control_claims_complete)
        self.assertIn("NOT_DURABLE_STORAGE",got.outstanding)

    def test_missing_encryption_blocks_readiness(self):
        got=assess_durable_cache_proposal(
            proposal(encrypted_at_rest_claim=False),qual())
        self.assertFalse(got.control_claims_complete)
        self.assertIn("STORAGE_CONTROL_MISSING:encrypted_at_rest_claim",got.outstanding)

    def test_missing_atomic_commit_blocks_readiness(self):
        self.assertFalse(assess_durable_cache_proposal(
            proposal(atomic_commit_claim=False),qual()).control_claims_complete)

    def test_missing_restart_recovery_blocks_readiness(self):
        self.assertFalse(assess_durable_cache_proposal(
            proposal(restart_recovery_claim=False),qual()).control_claims_complete)

    def test_missing_revocation_purge_blocks_readiness(self):
        self.assertFalse(assess_durable_cache_proposal(
            proposal(revocation_purge_process_documented=False),qual()).control_claims_complete)

    def test_invalid_retention_rejected(self):
        for n in (0,-1,3651,True,1.5):
            with self.subTest(n=n),self.assertRaisesRegex(ValueError,"RETENTION"):
                proposal(retention_days_proposed=n)

    def test_credentials_and_raw_storage_uri_rejected(self):
        for location in ("https://blob.vendor/secret", "user@storage", "s3://bucket"):
            with self.subTest(location=location),self.assertRaises(ValueError):
                proposal(location_ref=location)

    def test_legacy_source_allow_claims_never_override_external_review(self):
        got=assess_durable_cache_proposal(proposal(),qual(
            vendor_entitlement_independently_verified=True,
            may_cache_or_store_real_data=True))
        self.assertFalse(got.may_write_real_data)
        self.assertFalse(got.host_security_approved)

    def test_empty_synthetic_snapshot_can_generate_metadata_only(self):
        first=make_synthetic_generation(snap(),T+M)
        self.assertEqual(first.generation,1)
        self.assertEqual(first.previous_manifest_sha256,None)
        self.assertTrue(validate_synthetic_generation_chain(first))
        self.assertEqual(len(first.manifest_sha256),64)

    def test_new_generation_points_to_prior_hash(self):
        first=make_synthetic_generation(snap(),T+M)
        second=make_synthetic_generation(snap(source_head_claim="rev2"),T+2*M,first)
        self.assertEqual(second.generation,2)
        self.assertEqual(second.previous_manifest_sha256,first.manifest_sha256)
        self.assertNotEqual(first.manifest_sha256,second.manifest_sha256)
        self.assertTrue(validate_synthetic_generation_chain(second,first))

    def test_reject_mismatched_partition_parent(self):
        first=make_synthetic_generation(snap(),T+M)
        with self.assertRaisesRegex(ValueError,"CROSS_PARTITION"):
            make_synthetic_generation(snap(partition=partition(side=BarSide.ASK)),
                                      T+2*M,first)

    def test_schema_change_requires_migration_review(self):
        first=make_synthetic_generation(snap(),T+M)
        with self.assertRaisesRegex(ValueError,"SCHEMA_MIGRATION"):
            make_synthetic_generation(snap(partition=partition(schema_version="v2")),
                                      T+2*M,first)

    def test_generation_backdated_rejected(self):
        first=make_synthetic_generation(snap(),T+2*M)
        with self.assertRaisesRegex(ValueError,"CLOCK_ROLLBACK"):
            make_synthetic_generation(snap(),T+M,first)

    def test_generated_manifest_must_not_precede_snapshot(self):
        with self.assertRaisesRegex(ValueError,"PREDATES"):
            make_synthetic_generation(snap(checked_at_utc=T+3*M),T+M)

    def test_tampered_cache_digest_detected(self):
        first=make_synthetic_generation(snap(),T+M)
        bad=replace(first,cache_fingerprint="attacker-changed")
        with self.assertRaisesRegex(ValueError,"CHECKSUM"):
            validate_synthetic_generation_chain(bad)

    def test_tampered_parent_digest_detected(self):
        first=make_synthetic_generation(snap(),T+M)
        second=make_synthetic_generation(snap(),T+2*M,first)
        bad=replace(second,previous_manifest_sha256="f"*64)
        with self.assertRaisesRegex(ValueError,"PARENT_MISMATCH"):
            validate_synthetic_generation_chain(bad,first)

    def test_snapshot_generation_gap_detected(self):
        first=make_synthetic_generation(snap(),T+M)
        second=make_synthetic_generation(snap(),T+2*M,first)
        bad=replace(second,generation=4)
        with self.assertRaisesRegex(ValueError,"SEQUENCE_GAP"):
            validate_synthetic_generation_chain(bad,first)

    def test_manifest_not_authority_and_has_no_storage_methods(self):
        m=make_synthetic_generation(snap(),T+M)
        self.assertFalse(hasattr(m,"write"))
        self.assertFalse(hasattr(m,"restore"))
        self.assertFalse(hasattr(m,"authorization_token"))
