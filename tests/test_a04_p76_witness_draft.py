"""A04/P0.76: hermetic caller-pinned SHA witness drafts, NOT real trust."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest import TestCase

from mfx_cache.td_m5_codec import digest
from tools.mfx_native_v2_witness_draft import (
    STATUS, draft_genesis, draft_next_witness, verify_witness_draft,
    witness_sha256,
)
from test_a04_p74_native_v2_handoff import v1_state
from test_a04_p75_native_v2_shard_chain import (
    D1, H4, NOW, append, chain, fake_full_v1,
)


def genesis(tf="4h", cap=2):
    s, p, v1 = fake_full_v1(tf)
    w = draft_genesis(
        p, s, expected_v1_manifest_sha256=v1,
        now_utc=NOW, shard_capacity=cap)
    return s,p,v1,w


def next_witness(s,p,v1,w,h,*,pin=None):
    return draft_next_witness(
        w,p,s,expected_v1_manifest_sha256=v1,
        caller_pinned_previous_witness_sha256=(
            witness_sha256(w) if pin is None else pin),
        extended_history=h,now_utc=NOW)


def verify(s,p,v1,w,h,*,pin=None):
    return verify_witness_draft(
        w,p,s,expected_v1_manifest_sha256=v1,
        supplied_history=h,
        caller_pinned_witness_sha256=(
            witness_sha256(w) if pin is None else pin),
        now_utc=NOW)


class A04P076WitnessDraftTests(TestCase):
    def test_01_genesis_is_offline_no_attestation(self):
        s,p,v1,w=genesis()
        r=verify(s,p,v1,w,())
        self.assertEqual(w.status,STATUS)
        self.assertEqual(w.witness_generation,0)
        self.assertEqual(w.committed_v2_pairs,0)
        self.assertIsNone(w.parent_witness_sha256)
        self.assertEqual(w.claimed_v2_tip_sha256,p.proposed_anchor_sha256)
        self.assertEqual(r.verified_full_supplied_chain_pairs,0)
        self.assertFalse(r.independently_authenticated)
        self.assertFalse(r.durable_anti_rollback_verified)
        self.assertFalse(w.live_activation_authorized)
        self.assertEqual((w.google_drive_writes,w.provider_requests,
                          w.broker_orders),(0,0,0))

    def test_02_first_step_forward_only(self):
        s,p,v1,w=genesis()
        h=(append(s,p,v1,(),(H4[0],)),)
        child=next_witness(s,p,v1,w,h)
        self.assertEqual(child.committed_v2_pairs,1)
        self.assertEqual(child.witness_generation,1)
        self.assertEqual(child.parent_witness_sha256,witness_sha256(w))
        self.assertEqual(child.claimed_v2_tip_sha256,h[-1].manifest_sha256)
        self.assertEqual(verify(s,p,v1,child,h).verified_full_supplied_chain_pairs,1)

    def test_03_cross_shard_history_and_forward_step(self):
        s,p,v1,h=chain(labels=H4[:3])
        g=draft_genesis(p,s,expected_v1_manifest_sha256=v1,
                        now_utc=NOW,shard_capacity=2)
        first=next_witness(s,p,v1,g,h[:2])
        second=next_witness(s,p,v1,first,h)
        self.assertEqual(first.committed_v2_pairs,2)
        self.assertEqual(second.committed_v2_pairs,3)
        self.assertEqual(second.witness_generation,2)
        self.assertEqual(second.parent_witness_sha256,witness_sha256(first))
        self.assertIn("SHARD000002",h[-1].manifest_name)
        self.assertEqual(verify(s,p,v1,second,h).verified_full_supplied_chain_pairs,3)

    def test_04_sydney_day_session_unchanged(self):
        s,p,v1,h=chain("1day",D1[:2])
        w=draft_genesis(p,s,expected_v1_manifest_sha256=v1,
                        now_utc=NOW,shard_capacity=2)
        child=next_witness(s,p,v1,w,h)
        self.assertEqual(child.interval,"1day")
        self.assertEqual(child.last_native_open_label,"2026-11-13")
        self.assertEqual(verify(s,p,v1,child,h).verified_full_supplied_chain_pairs,2)

    def test_05_wrong_pinned_parent_hash_denied(self):
        s,p,v1,h=chain(labels=H4[:1])
        _,_,_,g=genesis()
        with self.assertRaisesRegex(ValueError,"CALLER_PIN_MISMATCH"):
            next_witness(s,p,v1,g,h,pin="f"*64)

    def test_06_stale_witness_replay_cannot_advance_same_count(self):
        s,p,v1,h=chain(labels=H4[:2])
        g=draft_genesis(p,s,expected_v1_manifest_sha256=v1,
                        now_utc=NOW,shard_capacity=2)
        w=next_witness(s,p,v1,g,h)
        with self.assertRaisesRegex(ValueError,"NON_MONOTONIC_WITNESS_UPDATE"):
            next_witness(s,p,v1,w,h)

    def test_07_shortened_history_refused_when_existing_pin_kept(self):
        s,p,v1,h=chain(labels=H4[:3])
        g=draft_genesis(p,s,expected_v1_manifest_sha256=v1,
                        now_utc=NOW,shard_capacity=2)
        w=next_witness(s,p,v1,g,h)
        with self.assertRaisesRegex(ValueError,"HISTORY_COUNT_MISMATCH"):
            verify(s,p,v1,w,h[:1])

    def test_08_caller_replaces_both_witness_and_pin_cannot_be_detected(self):
        s,p,v1,h=chain(labels=H4[:3])
        g=draft_genesis(p,s,expected_v1_manifest_sha256=v1,
                        now_utc=NOW,shard_capacity=2)
        shorter=next_witness(s,p,v1,g,h[:1])
        longer=next_witness(s,p,v1,g,h)
        # A forged caller that can replace both the expected digest and
        # witness can present either internally SHA-valid history.
        self.assertEqual(verify(s,p,v1,shorter,h[:1]).verified_full_supplied_chain_pairs,1)
        self.assertEqual(verify(s,p,v1,longer,h).verified_full_supplied_chain_pairs,3)
        self.assertFalse(verify(s,p,v1,shorter,h[:1]).durable_anti_rollback_verified)
        with self.assertRaisesRegex(ValueError,"CALLER_PIN_MISMATCH"):
            verify(s,p,v1,shorter,h[:1],pin=witness_sha256(longer))

    def test_09_corrupt_old_chunk_or_manifest_rejected(self):
        s,p,v1,h=chain(labels=H4[:3])
        g=draft_genesis(p,s,expected_v1_manifest_sha256=v1,
                        now_utc=NOW,shard_capacity=2)
        w=next_witness(s,p,v1,g,h)
        import copy
        broken=copy.deepcopy(h[0])
        broken.chunk["bars"][0]["open"]="9.999"
        with self.assertRaises(ValueError):
            verify(s,p,v1,w,(broken,*h[1:]))

    def test_10_fork_same_count_wrong_previous_parent_denied(self):
        s,p,v1,h=chain(labels=H4[:3])
        g=draft_genesis(p,s,expected_v1_manifest_sha256=v1,
                        now_utc=NOW,shard_capacity=2)
        w1=next_witness(s,p,v1,g,h[:2])
        import copy
        fork=copy.deepcopy(h[1])
        fork.manifest["parent_manifest_sha256"]="e"*64
        with self.assertRaises(ValueError):
            next_witness(s,p,v1,w1,(h[0],fork,h[2]))

    def test_11_replaced_previous_sha_in_record_rejected(self):
        s,p,v1,w=genesis()
        altered=replace(w,v2_root_anchor_sha256="0"*64)
        with self.assertRaisesRegex(ValueError,"FORGED_OR_INVALID_WITNESS"):
            verify(s,p,v1,altered,(),pin=witness_sha256(altered))

    def test_12_fake_external_attestation_flag_denied(self):
        s,p,v1,w=genesis()
        fake=replace(w,independent_external_attestation_verified=True)
        with self.assertRaisesRegex(ValueError,"FORGED_OR_INVALID_WITNESS"):
            verify(s,p,v1,fake,(),pin=witness_sha256(fake))

    def test_13_fake_live_activation_denied(self):
        s,p,v1,w=genesis()
        fake=replace(w,live_activation_authorized=True)
        with self.assertRaisesRegex(ValueError,"FORGED_OR_INVALID_WITNESS"):
            verify(s,p,v1,fake,(),pin=witness_sha256(fake))

    def test_14_wrong_legacy_tip_denied(self):
        s,p,v1,w=genesis()
        with self.assertRaises(ValueError):
            verify_witness_draft(
                w,p,s,expected_v1_manifest_sha256="a"*64,
                supplied_history=(),
                caller_pinned_witness_sha256=witness_sha256(w),now_utc=NOW)

    def test_15_live_short_of_256_v1_cannot_be_genesis(self):
        store,actual=v1_state("4h")
        from tools.mfx_native_shard_v2_design import propose_native_v2_shard_handoff
        proposal=propose_native_v2_shard_handoff(
            actual,symbol="EUR/USD",interval="4h",
            expected_v1_manifest_sha256=digest(actual.last_manifest))
        with self.assertRaisesRegex(ValueError,
                                    "ONLY_SYNTHETIC_FULL_V1_HANDOFF"):
            draft_genesis(proposal,actual,
                expected_v1_manifest_sha256=digest(actual.last_manifest),
                now_utc=NOW)
        self.assertTrue(store.data["manifest"])

    def test_16_invalid_pin_or_non_tuple_history_denied(self):
        s,p,v1,w=genesis()
        with self.assertRaisesRegex(ValueError,"INVALID_WITNESS_OR_PIN"):
            verify(s,p,v1,w,(),pin="NOT_SHA")
        with self.assertRaisesRegex(ValueError,"HISTORY_COUNT_MISMATCH"):
            verify_witness_draft(w,p,s,
                expected_v1_manifest_sha256=v1,
                supplied_history=[],
                caller_pinned_witness_sha256=witness_sha256(w),
                now_utc=NOW)

    def test_17_wrong_interval_or_symbol_record_denied(self):
        s,p,v1,w=genesis()
        for record in (
            replace(w,symbol="GBP/USD"),
            replace(w,interval="1day"),
            replace(w,witness_generation=1),
        ):
            with self.subTest(record=record),self.assertRaisesRegex(
                    ValueError,"FORGED_OR_INVALID_WITNESS"):
                verify(s,p,v1,record,(),pin=witness_sha256(record))

    def test_18_missing_middle_pair_not_waived(self):
        s,p,v1,h=chain(labels=H4[:3])
        g=draft_genesis(p,s,expected_v1_manifest_sha256=v1,
                        now_utc=NOW,shard_capacity=2)
        with self.assertRaises(ValueError):
            next_witness(s,p,v1,g,(h[0],h[2]))

    def test_19_original_v1_workflow_and_provider_stay_untouched(self):
        w=Path(".github/workflows/mfx-native-htf-incremental-commit.yml"
               ).read_text(encoding="utf-8")
        self.assertIn('cron: "25 * * * *"',w)
        self.assertIn("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED",w)
        self.assertNotIn("mfx_native_v2_witness_draft",w)
        native_audit=Path("tools/run_mfx_native_htf_cache_audit.py"
                          ).read_text(encoding="utf-8")
        self.assertNotIn("mfx_native_v2_witness_draft",native_audit)

    def test_20_no_real_keys_or_authenticated_signature_claim(self):
        s,p,v1,w=genesis()
        self.assertEqual((w.google_drive_writes,w.provider_requests,
                          w.broker_orders),(0,0,0))
        report=verify(s,p,v1,w,())
        self.assertEqual(report.google_drive_writes,0)
        self.assertEqual(report.broker_orders,0)
        self.assertFalse(report.independently_authenticated)
        self.assertFalse(report.durable_anti_rollback_verified)


if __name__ == "__main__":
    import unittest
    unittest.main()
