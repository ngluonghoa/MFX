import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from forex_trading.synthetic_source_custody import (
    make_synthetic_source_receipt, validate_synthetic_source_custody,
    select_synthetic_receipt_asof, assess_synthetic_custody,
)

T=datetime(2026,11,7,10,tzinfo=timezone.utc)
M=timedelta(minutes=1)


def receipt(*, previous=None, provider_rev="claim-r1", vendor_clock=None,
            observed=None, first_seen=None, partition="part-eurusd",
            payload="1"*64):
    if observed is None:
        observed=T if previous is None else T+5*M
    if first_seen is None:
        first_seen=observed+timedelta(seconds=1)
    if vendor_clock is None:
        vendor_clock=T-timedelta(days=10)
    return make_synthetic_source_receipt(
        partition,provider_rev,vendor_clock,observed,first_seen,payload,
        previous=previous,
    )


class SyntheticSourceCustodyTests(unittest.TestCase):
    def test_genesis_hash_chain_integrity(self):
        r=receipt()
        self.assertEqual(r.ordinal,1)
        self.assertEqual(len(r.receipt_sha256),64)
        self.assertTrue(validate_synthetic_source_custody(r))

    def test_second_receipt_has_new_first_seen_even_if_vendor_old(self):
        first=receipt()
        second=receipt(previous=first,provider_rev="claim-r2",payload="2"*64)
        self.assertEqual(second.ordinal,2)
        self.assertEqual(second.previous_receipt_sha256,first.receipt_sha256)
        self.assertEqual(second.vendor_event_utc_claim,
                         first.vendor_event_utc_claim)
        self.assertGreater(second.first_seen_by_us_utc,
                           first.first_seen_by_us_utc)
        self.assertTrue(validate_synthetic_source_custody(second,first))

    def test_asof_never_looks_ahead_to_late_source_revision(self):
        first=receipt()
        late=receipt(previous=first,provider_rev="r2",payload="2"*64)
        self.assertEqual(select_synthetic_receipt_asof(
            (first,late),T+2*M),first)
        self.assertEqual(select_synthetic_receipt_asof(
            (first,late),T+6*M),late)

    def test_vendor_claimed_earlier_publication_is_not_our_first_seen(self):
        first=receipt(vendor_clock=T-timedelta(days=100))
        late=receipt(previous=first,provider_rev="r2",
                     vendor_clock=T-timedelta(days=90),payload="2"*64)
        self.assertIsNone(select_synthetic_receipt_asof(
            (first,late),T-timedelta(days=5)))
        self.assertEqual(select_synthetic_receipt_asof(
            (first,late),T+4*M),first)

    def test_empty_receipts_returns_none(self):
        self.assertIsNone(select_synthetic_receipt_asof((),T))

    def test_missing_vendor_signature_always_blocks_real_replay(self):
        first=receipt()
        verdict=assess_synthetic_custody(first)
        self.assertTrue(verdict.local_chain_consistent)
        self.assertFalse(verdict.independently_signed_by_vendor)
        self.assertFalse(verdict.data_retention_rights_verified)
        self.assertFalse(verdict.may_replay_for_real_backtest)

    def test_future_vendor_clock_rejected(self):
        with self.assertRaisesRegex(ValueError,"FUTURE_OF_OBSERVATION"):
            receipt(vendor_clock=T+M)

    def test_local_first_seen_cannot_precede_observation(self):
        with self.assertRaisesRegex(ValueError,"PREDATE_OBSERVATION"):
            receipt(first_seen=T-timedelta(seconds=1))

    def test_stale_observed_clock_is_rejected(self):
        first=receipt()
        with self.assertRaisesRegex(ValueError,"OBSERVATION_CLOCK_ROLLBACK"):
            receipt(previous=first,observed=T-M,first_seen=T+6*M,provider_rev="r2")

    def test_monotonic_first_seen_required(self):
        first=receipt()
        with self.assertRaisesRegex(ValueError,"FIRST_SEEN_CLOCK_ROLLBACK"):
            receipt(previous=first,observed=T,first_seen=T,provider_rev="r2")

    def test_cross_partition_parent_rejected(self):
        first=receipt()
        with self.assertRaisesRegex(ValueError,"CROSS_PARTITION"):
            receipt(previous=first,partition="part-gbpusd",provider_rev="r2")

    def test_same_vendor_revision_different_body_is_conflict(self):
        first=receipt()
        with self.assertRaisesRegex(ValueError,"SAME_VENDOR_REVISION"):
            receipt(previous=first,provider_rev="claim-r1",payload="2"*64)

    def test_same_vendor_revision_same_body_may_be_reobserved(self):
        first=receipt()
        second=receipt(previous=first,provider_rev="claim-r1",payload="1"*64)
        self.assertTrue(validate_synthetic_source_custody(second,first))

    def test_bad_sha_shape_rejected(self):
        with self.assertRaisesRegex(ValueError,"SHA256"):
            receipt(payload="no-digest")

    def test_tampered_receipt_body_detected(self):
        first=receipt()
        modified=replace(first,vendor_revision_claim="attacker")
        with self.assertRaisesRegex(ValueError,"DIGEST_MISMATCH"):
            validate_synthetic_source_custody(modified)

    def test_tampered_receipt_parent_detected(self):
        first=receipt()
        second=receipt(previous=first,provider_rev="r2",payload="2"*64)
        altered=replace(second,previous_receipt_sha256="f"*64)
        with self.assertRaisesRegex(ValueError,"PARENT_MISMATCH"):
            validate_synthetic_source_custody(altered,first)

    def test_ordinal_gap_or_rollback_detected(self):
        first=receipt()
        second=receipt(previous=first,provider_rev="r2",payload="2"*64)
        with self.assertRaisesRegex(ValueError,"ORDINAL_ROLLBACK_OR_GAP"):
            validate_synthetic_source_custody(replace(second,ordinal=9),first)

    def test_invalid_genesis_detected(self):
        first=receipt()
        with self.assertRaisesRegex(ValueError,"GENESIS_CONFLICT"):
            validate_synthetic_source_custody(replace(first,ordinal=2))

    def test_future_receipt_in_chain_still_validated_before_asof(self):
        first=receipt()
        second=receipt(previous=first,provider_rev="r2",payload="2"*64)
        bad=replace(second,payload_sha256_claim="f"*64)
        with self.assertRaisesRegex(ValueError,"DIGEST_MISMATCH"):
            select_synthetic_receipt_asof((first,bad),T+2*M)

    def test_wrong_sequence_input_type_rejected(self):
        with self.assertRaises(TypeError):
            select_synthetic_receipt_asof([receipt()],T)

    def test_aware_utc_decision_required(self):
        with self.assertRaises(ValueError):
            select_synthetic_receipt_asof((receipt(),),datetime(2026,11,7,10))

    def test_payload_content_can_be_same_after_revision_change(self):
        first=receipt()
        second=receipt(previous=first,provider_rev="r2",payload="1"*64)
        self.assertNotEqual(first.receipt_sha256,second.receipt_sha256)

    def test_trust_cannot_be_self_granted_by_recomputed_hash(self):
        first=receipt(payload="f"*64)
        second=receipt(previous=first,provider_rev="later",payload="1"*64)
        self.assertTrue(validate_synthetic_source_custody(second,first))
        self.assertFalse(assess_synthetic_custody(second,first).independently_signed_by_vendor)
