"""P0.208: separate revision-vintage DRY RUN, original P192 root remains sealed."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from unittest import TestCase

from mfx_cache.native_d1_epoch_20261118 import (
    PREFIX as P192_PREFIX,
)
from mfx_cache.native_d1_fresh_epoch import PREFIX as P171_PREFIX
from mfx_cache.p207_p192_d1_disjoint_research_fork import (
    build_p192_disjoint_research_fork,
)
from mfx_cache.p208_p192_revision_vintage_dryrun import (
    PREFIX, STATUS, VERSION,
    prepare_disjoint_p192_revision_vintage,
    verify_disjoint_p192_revision_vintage,
)
from test_mfx_p192_d1_nov18_cutoff import AFTER, NEXT, source
from test_mfx_p192_native_writer_nov18 import P192RealWriterCutoffTests
from test_mfx_p207_p192_disjoint_research_fork import prepared


def candidate(*, clock=NEXT):
    store,state,batch,review=prepared(clock=clock)
    fork=build_p192_disjoint_research_fork(
        state=state,refetched=batch,validated_review=review,
        now_utc=clock)
    draft=prepare_disjoint_p192_revision_vintage(
        fork=fork,state=state,refetched=batch,
        validated_review=review,now_utc=clock)
    return store,state,batch,review,fork,draft


class P208RevisionForkPreparationTests(TestCase):
    def test_01_reserved_namespace_disjoint_from_p192_and_p171(self):
        self.assertIn("P208",PREFIX)
        self.assertIn("REVIEW_ONLY",PREFIX)
        self.assertNotEqual(PREFIX,P192_PREFIX)
        self.assertNotEqual(PREFIX,P171_PREFIX)
        self.assertFalse(PREFIX.startswith(P192_PREFIX))
        self.assertFalse(PREFIX.startswith(P171_PREFIX))
        self.assertFalse(P192_PREFIX.startswith(PREFIX))
        self.assertFalse(P171_PREFIX.startswith(PREFIX))

    def test_02_exact_p207_provenance_unchanged_orig_parent(self):
        store,state,batch,review,fork,draft=candidate()
        self.assertEqual(draft.version,VERSION)
        self.assertEqual(draft.status,STATUS)
        self.assertEqual(draft.canonical_p192_source_root_sha256,
                         fork.original_manifest_sha256)
        self.assertEqual(draft.original_18nov_native_bar_sha256,
                         fork.original_18nov_bar_sha256)
        self.assertEqual(draft.proposed_revised_18nov_bar_sha256,
                         fork.revised_18nov_bar_sha256)
        self.assertNotEqual(draft.original_18nov_native_bar_sha256,
                            draft.proposed_revised_18nov_bar_sha256)
        self.assertEqual(state.last_manifest["last_native_open_label"],
                         "2026-11-18")

    def test_03_private_row_index_is_sha_only_and_no_old_archive_splice(self):
        _,_,_,_,fork,draft=candidate()
        self.assertEqual(tuple(label for label,_ in draft.candidate_row_index),
                         ("2026-11-18","2026-11-19"))
        self.assertEqual(tuple(sha for _,sha in draft.candidate_row_index),
                         tuple(b.sha256() for b in fork.private_source_bars))
        self.assertEqual(len(draft.candidate_row_index),2)
        self.assertTrue(all(len(sha)==64 for _,sha in draft.candidate_row_index))

    def test_04_chunk_manifest_proposal_identities_sha_addressed_but_private(self):
        _,_,_,_,_,draft=candidate()
        for kind,name,sha in (
            ("chunk",draft.proposed_chunk_outline_name,
             draft.proposed_chunk_outline_sha256),
            ("manifest",draft.proposed_manifest_outline_name,
             draft.proposed_manifest_outline_sha256),
        ):
            self.assertTrue(name.startswith(PREFIX+kind+"_"))
            self.assertTrue(name.endswith("_"+sha+".json"))
        self.assertNotEqual(draft.proposed_chunk_outline_sha256,
                            draft.proposed_manifest_outline_sha256)
        self.assertEqual(len(draft.proposal_fingerprint_sha256),64)

    def test_05_repeat_dryrun_is_bitwise_deterministic(self):
        _,state,batch,review,fork,draft=candidate()
        other=prepare_disjoint_p192_revision_vintage(
            fork=fork,state=state,refetched=batch,
            validated_review=review,now_utc=NEXT)
        self.assertEqual(draft,other)
        self.assertTrue(verify_disjoint_p192_revision_vintage(
            draft,fork=fork,state=state,refetched=batch,
            validated_review=review,now_utc=NEXT))

    def test_06_forged_authorization_must_not_survive_full_replay(self):
        _,state,batch,review,fork,draft=candidate()
        for key in (
            "source_admission","source_first_known_verified",
            "owner_canonical_revision_approved",
            "vendor_retention_rights_verified",
            "historical_asof_rewrite_allowed",
            "drive_namespace_allocated","may_write_drive",
            "may_select_as_active_d1","may_publish_buy_sell","may_trade",
        ):
            with self.subTest(key=key),self.assertRaisesRegex(
                    ValueError,"P208_PROPOSAL_SHA_OR_AUTHORITY_DRIFT"):
                verify_disjoint_p192_revision_vintage(
                    replace(draft,**{key:True}),fork=fork,state=state,
                    refetched=batch,validated_review=review,now_utc=NEXT)

    def test_07_write_or_vendor_counter_tamper_rejected(self):
        _,state,batch,review,fork,draft=candidate()
        for key in ("provider_requests_added","drive_reads_added",
                    "drive_writes","broker_orders"):
            with self.subTest(key=key),self.assertRaises(ValueError):
                verify_disjoint_p192_revision_vintage(
                    replace(draft,**{key:1}),fork=fork,state=state,
                    refetched=batch,validated_review=review,now_utc=NEXT)

    def test_08_altered_sha_namespace_or_row_index_rejected(self):
        _,state,batch,review,fork,draft=candidate()
        for fake in (
            replace(draft,proposed_namespace=P192_PREFIX),
            replace(draft,proposed_chunk_outline_sha256="a"*64),
            replace(draft,proposed_manifest_outline_name="collision.json"),
            replace(draft,candidate_row_index=draft.candidate_row_index[:1]),
            replace(draft,proposal_fingerprint_sha256="b"*64),
        ):
            with self.assertRaises(ValueError):
                verify_disjoint_p192_revision_vintage(
                    fake,fork=fork,state=state,refetched=batch,
                    validated_review=review,now_utc=NEXT)

    def test_09_proposal_no_raw_price_custody(self):
        _,_,_,_,fork,draft=candidate()
        self.assertFalse(hasattr(draft,"private_source_bars"))
        self.assertFalse(hasattr(draft,"chunk"))
        self.assertFalse(hasattr(draft,"manifest"))
        self.assertNotIn(fork.original_manifest_sha256,repr(draft))
        self.assertNotIn(fork.revised_18nov_bar_sha256,repr(draft))

    def test_10_public_receipt_redacts_all_source_identifiers(self):
        _,_,_,_,fork,draft=candidate()
        pub=draft.public_summary()
        self.assertEqual(pub["status"],STATUS)
        self.assertEqual(pub["action"],"NO_SIGNAL")
        self.assertEqual(pub["private_proposal_rows"],2)
        self.assertEqual(pub["private_later_closed_rows"],1)
        self.assertFalse(pub["drive_namespace_allocated"])
        self.assertFalse(pub["may_write_drive"])
        s=json.dumps(pub,sort_keys=True)
        for secret in (
            "2026-11-18","2026-11-19",fork.runner_observed_utc,
            draft.proposed_namespace,draft.proposed_chunk_outline_name,
            draft.proposed_manifest_outline_name,
            fork.original_manifest_sha256,fork.revised_18nov_bar_sha256,
            draft.proposal_fingerprint_sha256,
            '"open"', '"high"', '"low"', '"close"',
        ):
            self.assertNotIn(secret,s)

    def test_11_preexisting_p192_manifest_is_unchanged_after_plan(self):
        store,state,batch,review,fork,draft=candidate()
        orig=deepcopy(state.last_manifest)
        prior=(store.list_names("chunk"),store.list_names("manifest"),
               store.puts)
        other=prepare_disjoint_p192_revision_vintage(
            fork=fork,state=state,refetched=batch,
            validated_review=review,now_utc=NEXT)
        self.assertEqual(state.last_manifest,orig)
        self.assertEqual((store.list_names("chunk"),store.list_names("manifest"),
                          store.puts),prior)
        self.assertEqual(other,draft)

    def test_12_no_persistent_drive_writer_api_exists_in_p208(self):
        import mfx_cache.p208_p192_revision_vintage_dryrun as module
        for symbol in ("commit_fresh_epoch","commit_revision",
                       "write_to_drive","PrivateD1FreshEpochStore",
                       "PrivateNativeDriveStore","requests","httpx"):
            self.assertFalse(hasattr(module,symbol),symbol)

    def test_13_future_sydney_d1_still_excluded(self):
        store,state,batch,review=prepared(clock=AFTER)
        with self.assertRaisesRegex(ValueError,"UNCLOSED_OR_UNPUBLISHED"):
            fork=build_p192_disjoint_research_fork(
                state=state,refetched=batch,
                validated_review=review,now_utc=AFTER)
            prepare_disjoint_p192_revision_vintage(
                fork=fork,state=state,refetched=batch,
                validated_review=review,now_utc=AFTER)

    def test_14_unmodified_or_missing_revised_nov18_cannot_be_proposed(self):
        _,state,batch,review,fork,draft=candidate()
        with self.assertRaises(ValueError):
            prepare_disjoint_p192_revision_vintage(
                fork=fork,state=state,refetched=source(include19=True),
                validated_review=review,now_utc=NEXT)
        with self.assertRaises(ValueError):
            prepare_disjoint_p192_revision_vintage(
                fork=fork,state=state,
                refetched=source(include18=False,include19=True),
                validated_review=review,now_utc=NEXT)

    def test_15_forged_canonical_root_or_private_source_rejected(self):
        _,state,batch,review,fork,draft=candidate()
        state.last_manifest["total_closed_bars"]=2
        with self.assertRaises(ValueError):
            prepare_disjoint_p192_revision_vintage(
                fork=fork,state=state,refetched=batch,
                validated_review=review,now_utc=NEXT)

    def test_16_source_fork_cannot_be_promoted_to_origin_by_boolean(self):
        _,state,batch,review,fork,draft=candidate()
        with self.assertRaises(ValueError):
            prepare_disjoint_p192_revision_vintage(
                fork=replace(fork,owner_canonical_revision_approved=True),
                state=state,refetched=batch,
                validated_review=review,now_utc=NEXT)

    def test_17_real_mocked_native_writer_emits_only_redacted_dryrun(self):
        err,logs,calls,store=P192RealWriterCutoffTests().run_job(
            clock=NEXT,revision=True)
        self.assertEqual(err,"P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertEqual(store.puts,2)
        self.assertEqual([tf for k,tf in calls if k=="vendor"],["1day"])
        marker="MFX_P208_D1_REVISED_VINTAGE_DRYRUN_NO_STORAGE"
        lines=logs.splitlines()
        self.assertEqual(lines.count(marker),1)
        i=lines.index(marker)
        pub=json.loads(lines[i+1])
        self.assertEqual(pub["status"],STATUS)
        self.assertEqual(pub["private_proposal_rows"],2)
        self.assertEqual(pub["private_later_closed_rows"],1)
        self.assertFalse(pub["drive_namespace_allocated"])
        self.assertFalse(pub["may_write_drive"])
        self.assertEqual(pub["drive_writes"],0)
        self.assertEqual(pub["provider_requests_added"],0)
        self.assertEqual(pub["action"],"NO_SIGNAL")
        self.assertLess(lines.index("MFX_P204_P192_REDACTED_OWNER_REVIEW_ONLY"),
                        lines.index("MFX_P207_P192_REVISED_D1_FORK_INMEMORY_ONLY"))
        self.assertLess(lines.index("MFX_P207_P192_REVISED_D1_FORK_INMEMORY_ONLY"),i)
        self.assertLess(i,lines.index("MFX_P200_P192_D1_SHA_DIFF_REDACTED_NO_COMMIT"))
        self.assertNotIn('"candidate_row_index"',logs)
        self.assertNotIn('"proposed_chunk_outline_name"',logs)
        self.assertNotIn('"private_source_bars"',logs)

    def test_18_wrong_type_or_unapproved_d1_source_cannot_be_dryrun(self):
        _,state,batch,review,fork,draft=candidate()
        with self.assertRaises(TypeError):
            verify_disjoint_p192_revision_vintage(
                object(),fork=fork,state=state,refetched=batch,
                validated_review=review,now_utc=NEXT)
        fake=deepcopy(review)
        fake["owner_canonical_revision_approved"]=True
        with self.assertRaises(ValueError):
            prepare_disjoint_p192_revision_vintage(
                fork=fork,state=state,refetched=batch,
                validated_review=fake,now_utc=NEXT)

    def test_19_no_broker_signal_or_drive_write_permission(self):
        _,_,_,_,_,draft=candidate()
        self.assertFalse(draft.may_trade)
        self.assertFalse(draft.may_publish_buy_sell)
        self.assertFalse(draft.may_select_as_active_d1)
        self.assertFalse(draft.may_write_drive)
        self.assertFalse(draft.drive_namespace_allocated)
        self.assertFalse(draft.source_admission)
        self.assertFalse(draft.vendor_retention_rights_verified)
        self.assertEqual((draft.provider_requests_added,
                          draft.drive_reads_added,draft.drive_writes,
                          draft.broker_orders),(0,0,0,0))
