"""A04/P0.78: 26 in-memory negative tests, NEVER a live CAS service.

The simulated authority serializes calls inside this test process only.
Neither caller-supplied heads nor generated fence integers are trusted.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest import TestCase

from mfx_cache.td_m5_codec import digest
from tools.mfx_native_v2_cas_recovery_contract import (
    SCHEMA, STATUS, assert_conditional_cas_preconditions,
    assess_recovery_after_interruption, draft_authority_genesis,
    prepare_fenced_v2_cas,
)
from tools.mfx_native_v2_witness_draft import (
    draft_genesis, witness_sha256,
)
from test_a04_p74_native_v2_handoff import v1_state
from test_a04_p75_native_v2_shard_chain import (
    D1, H4, NOW, append, fake_full_v1,
)


class SimulatedAtomicWitnessAuthority:
    """Test fake; owner, durable authentication and external CAS UNPROVEN."""
    def __init__(self, head):
        self.head=head
        self.epoch=head.epoch
        self.current_fence=head.fence_token
        self.cas_calls=0
    def reserve(self):
        self.current_fence+=1
        return self.current_fence
    def compare_and_swap(self, prepared):
        self.cas_calls+=1
        assert_conditional_cas_preconditions(
            prepared,self.head,
            externally_allocated_epoch=self.epoch,
            externally_current_fence_token=self.current_fence,
        )
        self.head=prepared.proposed_head
    def rotate_epoch(self):
        self.epoch+=1


def fixture(tf="4h", *, cap=2):
    legacy,proposal,v1=fake_full_v1(tf)
    genesis=draft_genesis(
        proposal,legacy,
        expected_v1_manifest_sha256=v1,
        now_utc=NOW,shard_capacity=cap,
    )
    head=draft_authority_genesis(
        proposal,genesis,epoch=3,initial_fence_token=4,
    )
    return legacy,proposal,v1,genesis,head


def prepare(f, *, labels=None, history=(), previous_witness=None,
            head=None, fence=None, epoch=None):
    legacy,p,v1,g,initial_head=f
    if labels is None:
        labels=(H4[0],) if p.interval=="4h" else (D1[0],)
    witness=g if previous_witness is None else previous_witness
    current=initial_head if head is None else head
    candidate=append(legacy,p,v1,history,labels,cap=2)
    return prepare_fenced_v2_cas(
        witness,current,p,legacy,
        expected_v1_manifest_sha256=v1,
        committed_history=tuple(history),
        candidate_pair=candidate,
        requested_epoch=current.epoch if epoch is None else epoch,
        allocated_fence_token=(
            current.fence_token+1 if fence is None else fence
        ),
        now_utc=NOW,
    )


def recovery(prepared, chunks=(), manifests=(), head=None):
    return assess_recovery_after_interruption(
        prepared,
        observed_chunk_names=tuple(chunks),
        observed_manifest_names=tuple(manifests),
        current_head=(
            prepared.expected_head if head is None else head
        ),
    )


class A04P078FencedCASRecoveryTests(TestCase):
    def test_01_genesis_is_pure_and_not_external_auth(self):
        f=fixture()
        head=f[-1]
        self.assertEqual((head.epoch,head.fence_token,head.generation),
                         (3,4,0))
        self.assertEqual(head.schema,SCHEMA)
        self.assertEqual(head.witness_sha256,witness_sha256(f[3]))

    def test_02_h4_one_new_pair_prepared(self):
        f=fixture()
        p=prepare(f)
        self.assertEqual(p.status,STATUS)
        self.assertEqual(p.candidate_pair.manifest["global_pair_index"],1)
        self.assertEqual(p.next_witness.committed_v2_pairs,1)
        self.assertEqual(p.next_witness.witness_generation,1)
        self.assertEqual(p.proposed_head.generation,1)
        self.assertEqual(p.next_witness.parent_witness_sha256,
                         p.previous_witness_sha256)
        self.assertTrue(p.external_atomic_cas_required)
        self.assertFalse(p.independent_external_authority_verified)
        self.assertFalse(p.live_drive_writer_authorized)
        self.assertEqual((p.real_drive_writes,p.provider_requests,
                          p.broker_orders),(0,0,0))

    def test_03_d1_sydney_date_prepared(self):
        f=fixture("1day")
        p=prepare(f)
        self.assertEqual(p.next_witness.last_native_open_label,D1[0])
        self.assertEqual(p.proposed_head.interval,"1day")

    def test_04_clean_no_objects_requires_manual_decision(self):
        p=prepare(fixture())
        r=recovery(p)
        self.assertEqual(r.status,"NO_OBJECTS_PREPARE_NOT_PUBLISHED")
        self.assertTrue(r.manual_authenticated_head_recheck_required)
        self.assertFalse(r.may_auto_publish_manifest)
        self.assertFalse(r.may_auto_advance_witness)

    def test_05_single_exact_chunk_orphan_is_not_auto_repaired(self):
        p=prepare(fixture())
        r=recovery(p,(p.candidate_pair.chunk_name,))
        self.assertEqual(r.status,"EXACT_CHUNK_ORPHAN_MANUAL_REVALIDATION")
        self.assertFalse(r.may_auto_publish_manifest)
        self.assertFalse(r.may_auto_advance_witness)

    def test_06_exact_pair_before_witness_is_unpublished(self):
        p=prepare(fixture())
        r=recovery(p,(p.candidate_pair.chunk_name,),
                   (p.candidate_pair.manifest_name,))
        self.assertEqual(
            r.status,"EXACT_PAIR_UNPUBLISHED_MANUAL_CAS_REVALIDATION")
        self.assertTrue(r.manual_authenticated_head_recheck_required)
        self.assertFalse(r.may_auto_advance_witness)

    def test_07_complete_pair_after_cas_can_only_readback(self):
        p=prepare(fixture())
        r=recovery(p,(p.candidate_pair.chunk_name,),
                   (p.candidate_pair.manifest_name,),
                   head=p.proposed_head)
        self.assertEqual(r.status,"COMMITTED_EXACT_PAIR_READBACK_ONLY")
        self.assertFalse(r.may_auto_advance_witness)
        self.assertEqual((r.real_drive_writes,r.broker_orders),(0,0))

    def test_08_manifest_without_chunk_is_quarantined(self):
        p=prepare(fixture())
        with self.assertRaisesRegex(
                ValueError,"MANIFEST_WITHOUT_CHUNK"):
            recovery(p,(),(p.candidate_pair.manifest_name,))

    def test_09_witness_advance_before_manifest_is_denied(self):
        p=prepare(fixture())
        with self.assertRaisesRegex(
                ValueError,"WITNESS_ADVANCED_BEFORE_PAIR_COMPLETE"):
            recovery(p,(p.candidate_pair.chunk_name,),head=p.proposed_head)

    def test_10_witness_advance_before_any_objects_is_denied(self):
        p=prepare(fixture())
        with self.assertRaisesRegex(
                ValueError,"WITNESS_ADVANCED_BEFORE_PAIR_COMPLETE"):
            recovery(p,head=p.proposed_head)

    def test_11_unknown_chunk_is_quarantined(self):
        p=prepare(fixture())
        with self.assertRaisesRegex(
                ValueError,"UNKNOWN_OR_FORKED_OBJECT"):
            recovery(p,("fake-chunk.json",))

    def test_12_unknown_manifest_is_quarantined(self):
        p=prepare(fixture())
        with self.assertRaisesRegex(
                ValueError,"UNKNOWN_OR_FORKED_OBJECT"):
            recovery(p,(p.candidate_pair.chunk_name,),("foreign.json",))

    def test_13_multiple_orphan_chunks_not_allowed(self):
        p=prepare(fixture())
        with self.assertRaisesRegex(
                ValueError,"UNKNOWN_OR_FORKED_OBJECT"):
            recovery(p,(p.candidate_pair.chunk_name,
                        p.candidate_pair.chunk_name))

    def test_14_replaced_or_stale_witness_head_refused(self):
        p=prepare(fixture())
        stale=replace(p.expected_head,epoch=2)
        with self.assertRaisesRegex(
                ValueError,"CAS_CONFLICT_EXPECTED_HEAD_CHANGED"):
            assert_conditional_cas_preconditions(
                p,stale,externally_allocated_epoch=3,
                externally_current_fence_token=5)

    def test_15_stale_fence_refused(self):
        p=prepare(fixture())
        with self.assertRaisesRegex(
                ValueError,"FENCE_REVOKED_OR_EPOCH_CHANGED"):
            assert_conditional_cas_preconditions(
                p,p.expected_head,externally_allocated_epoch=3,
                externally_current_fence_token=6)

    def test_16_rotated_authority_epoch_refused(self):
        p=prepare(fixture())
        with self.assertRaisesRegex(
                ValueError,"FENCE_REVOKED_OR_EPOCH_CHANGED"):
            assert_conditional_cas_preconditions(
                p,p.expected_head,externally_allocated_epoch=4,
                externally_current_fence_token=5)

    def test_17_stale_fence_in_preparation_refused(self):
        f=fixture()
        with self.assertRaisesRegex(ValueError,"STALE_EPOCH_OR_FENCE"):
            prepare(f,fence=4)
        with self.assertRaisesRegex(ValueError,"STALE_EPOCH_OR_FENCE"):
            prepare(f,epoch=5)

    def test_18_bool_epoch_or_fence_rejected(self):
        f=fixture()
        with self.assertRaisesRegex(ValueError,"INVALID_UNTRUSTED_GENESIS"):
            draft_authority_genesis(
                f[1],f[3],epoch=True,initial_fence_token=4)
        with self.assertRaisesRegex(ValueError,"STALE_EPOCH_OR_FENCE"):
            prepare(f,fence=True)

    def test_19_competing_writers_cannot_both_win_fake_cas(self):
        f=fixture()
        authority=SimulatedAtomicWitnessAuthority(f[-1])
        token=authority.reserve()
        a=prepare(f,fence=token)
        b=prepare(f,labels=(H4[1],),fence=token)
        authority.compare_and_swap(a)
        with self.assertRaisesRegex(
                ValueError,"CAS_CONFLICT_EXPECTED_HEAD_CHANGED"):
            authority.compare_and_swap(b)
        self.assertEqual(authority.head,a.proposed_head)
        self.assertEqual(authority.cas_calls,2)

    def test_20_new_fence_fences_out_older_pending_writer(self):
        f=fixture()
        authority=SimulatedAtomicWitnessAuthority(f[-1])
        a=prepare(f,fence=authority.reserve())
        b=prepare(f,labels=(H4[1],),fence=authority.reserve())
        with self.assertRaisesRegex(
                ValueError,"FENCE_REVOKED_OR_EPOCH_CHANGED"):
            authority.compare_and_swap(a)
        authority.compare_and_swap(b)
        self.assertEqual(authority.head,b.proposed_head)

    def test_21_successful_two_step_chain_into_next_shard(self):
        f=fixture()
        authority=SimulatedAtomicWitnessAuthority(f[-1])
        first=prepare(f,fence=authority.reserve())
        authority.compare_and_swap(first)
        second=prepare(
            f,labels=(H4[1],),history=(first.candidate_pair,),
            previous_witness=first.next_witness,head=authority.head,
            fence=authority.reserve())
        authority.compare_and_swap(second)
        self.assertEqual((second.proposed_head.generation,
                          second.next_witness.committed_v2_pairs),(2,2))
        third=prepare(
            f,labels=(H4[2],),
            history=(first.candidate_pair,second.candidate_pair),
            previous_witness=second.next_witness,
            head=authority.head,fence=authority.reserve())
        authority.compare_and_swap(third)
        self.assertIn("SHARD000002",third.candidate_pair.manifest_name)
        self.assertEqual(authority.head.generation,3)

    def test_22_malicious_altered_pair_fails_full_sha_before_cas(self):
        f=fixture()
        original=prepare(f)
        from copy import deepcopy
        corrupted=deepcopy(original.candidate_pair)
        corrupted.chunk["bars"][0]["close"]="6.6600"
        with self.assertRaises(ValueError):
            prepare_fenced_v2_cas(
                f[3],f[-1],f[1],f[0],
                expected_v1_manifest_sha256=f[2],
                committed_history=(),candidate_pair=corrupted,
                requested_epoch=3,allocated_fence_token=5,now_utc=NOW)

    def test_23_wrong_pinned_witness_before_extension_fails(self):
        f=fixture()
        head=replace(f[-1],witness_sha256="f"*64)
        with self.assertRaisesRegex(
                ValueError,"HEAD_OR_HISTORY_NOT_CURRENT"):
            prepare(f,head=head)

    def test_24_replay_previous_pair_cannot_be_extended(self):
        f=fixture()
        first=prepare(f)
        with self.assertRaises(ValueError):
            prepare(
                f,labels=(H4[0],),
                history=(first.candidate_pair,),
                previous_witness=first.next_witness,
                head=first.proposed_head,
                fence=first.proposed_head.fence_token+1)

    def test_25_fake_authority_replacement_remains_untrusted(self):
        f=fixture()
        p=prepare(f)
        authority_a=SimulatedAtomicWitnessAuthority(f[-1])
        authority_b=SimulatedAtomicWitnessAuthority(f[-1])
        authority_a.reserve()
        authority_b.reserve()
        authority_a.compare_and_swap(p)
        # Two independent fake services can BOTH "commit" the same
        # predecessor. Without a real single trusted authority, there
        # is no global anti-fork or durable anti-rollback guarantee.
        authority_b.compare_and_swap(p)
        self.assertEqual(authority_a.head,authority_b.head)
        self.assertFalse(p.independent_external_authority_verified)

    def test_26_no_workflow_connected_and_no_authorized_write(self):
        src=Path(
            ".github/workflows/mfx-native-htf-incremental-commit.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('cron: "25 * * * *"',src)
        self.assertNotIn("mfx_native_v2_cas_recovery_contract",src)
        audit=Path("tools/run_mfx_native_htf_cache_audit.py").read_text(
            encoding="utf-8")
        self.assertNotIn("mfx_native_v2_cas_recovery_contract",audit)
        p=prepare(fixture())
        self.assertFalse(p.live_drive_writer_authorized)
        self.assertEqual((p.real_drive_writes,p.provider_requests,
                          p.broker_orders),(0,0,0))
