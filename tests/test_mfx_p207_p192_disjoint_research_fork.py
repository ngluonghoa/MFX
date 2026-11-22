"""P0.207 offline private D1 dual-vintage research fork and live fail-closed seam."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from unittest import TestCase

from mfx_cache.p204_p192_d1_revision_review import (
    build_p192_revision_review,
)
from mfx_cache.p207_p192_d1_disjoint_research_fork import (
    STATUS, VERSION, build_p192_disjoint_research_fork,
    verify_p192_disjoint_research_fork,
)
from mfx_cache.td_m5_codec import digest
from test_mfx_p171_d1_fresh_epoch import original_sha
from test_mfx_p192_d1_nov18_cutoff import AFTER, NEXT, source
from test_mfx_p192_native_writer_nov18 import P192RealWriterCutoffTests
from test_mfx_p200_p192_d1_redacted_sha_forensics import fixture


def prepared(*, batch=None, clock=NEXT):
    store, state, chunk = fixture()
    fetched = batch if batch is not None else source(
        include19=True, revised="2026-11-18",
    )
    review = build_p192_revision_review(
        state=state, sealed_chunk=chunk,
        refetched=fetched, origin_v1_sha=original_sha(),
        runner_observed_utc=clock,
    )
    return store, state, fetched, review


class P207PrivateD1ForkTests(TestCase):
    def test_01_original_sha_root_preserved_revision_stays_private(self):
        store,state,batch,review = prepared()
        before = deepcopy(state.last_manifest)
        prior = (store.list_names("chunk"),store.list_names("manifest"))
        fork = build_p192_disjoint_research_fork(
            state=state, refetched=batch, validated_review=review,
            now_utc=NEXT,
        )
        self.assertEqual(fork.status, STATUS)
        self.assertEqual(fork.version, VERSION)
        self.assertEqual(fork.original_manifest_sha256, digest(before))
        self.assertNotEqual(fork.original_18nov_bar_sha256,
                            fork.revised_18nov_bar_sha256)
        self.assertEqual(state.last_manifest, before)
        self.assertEqual((store.list_names("chunk"),store.list_names("manifest")),prior)

    def test_02_only_changed_18nov_and_later_source_rows_no_old_splice(self):
        _,state,batch,review = prepared()
        fork = build_p192_disjoint_research_fork(
            state=state, refetched=batch,validated_review=review,
            now_utc=NEXT,
        )
        self.assertEqual(
            [b.native_open_label for b in fork.private_source_bars],
            ["2026-11-18","2026-11-19"],
        )
        self.assertEqual(fork.private_source_bars[0].sha256(),
                         fork.revised_18nov_bar_sha256)

    def test_03_public_markers_redact_prices_sha_dates_runner(self):
        _,state,batch,review=prepared()
        fork=build_p192_disjoint_research_fork(
            state=state,refetched=batch,validated_review=review,now_utc=NEXT)
        public=fork.public_summary()
        self.assertEqual(public["action"], "NO_SIGNAL")
        self.assertEqual(public["private_later_closed_d1_rows"],1)
        self.assertFalse(public["research_fork_persisted"])
        self.assertFalse(public["may_write_d1"])
        self.assertFalse(public["may_publish_buy_sell"])
        data=json.dumps(public,sort_keys=True)
        for secret in (
            "2026-11-18","2026-11-19",
            fork.original_manifest_sha256,
            fork.original_18nov_bar_sha256,
            fork.revised_18nov_bar_sha256,
            fork.runner_observed_utc,
            fork.fork_digest_sha256,
            '"open"', '"high"', '"low"', '"close"',
        ):
            self.assertNotIn(secret,data)

    def test_04_replay_exact_private_fork_chain(self):
        _,state,batch,review=prepared()
        fork=build_p192_disjoint_research_fork(
            state=state,refetched=batch,validated_review=review,now_utc=NEXT)
        self.assertTrue(verify_p192_disjoint_research_fork(
            fork,state=state,refetched=batch,
            validated_review=review,now_utc=NEXT))
        self.assertEqual(len(fork.private_chain_sha256),2)
        self.assertNotEqual(fork.private_chain_sha256[0],
                            fork.private_chain_sha256[1])

    def test_05_forged_public_authority_cannot_be_launched(self):
        _,state,batch,review=prepared()
        for key in (
            "owner_canonical_revision_approved", "source_account_rights_verified",
            "publisher_first_known_verified", "historical_asof_rewrite_allowed",
            "may_write_d1", "may_write_drive", "may_publish_buy_sell",
            "may_trade",
        ):
            fork=build_p192_disjoint_research_fork(
                state=state,refetched=batch,validated_review=review,now_utc=NEXT)
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_p192_disjoint_research_fork(
                    replace(fork,**{key:True}),state=state,
                    refetched=batch,validated_review=review,now_utc=NEXT)

    def test_06_private_fork_digest_tamper_rejected(self):
        _,state,batch,review=prepared()
        fork=build_p192_disjoint_research_fork(
            state=state,refetched=batch,validated_review=review,now_utc=NEXT)
        with self.assertRaises(ValueError):
            verify_p192_disjoint_research_fork(
                replace(fork,fork_digest_sha256="a"*64),
                state=state,refetched=batch,
                validated_review=review,now_utc=NEXT)
        with self.assertRaises(ValueError):
            verify_p192_disjoint_research_fork(
                replace(fork,private_source_bars=fork.private_source_bars[:1]),
                state=state,refetched=batch,
                validated_review=review,now_utc=NEXT)

    def test_07_p204_review_private_sha_must_match_source(self):
        _,state,batch,review=prepared()
        fake=deepcopy(review)
        fake["private_revised_source_sha_pair"]["refetched_sha256"]="b"*64
        fake["proposal_content_sha256"]=digest({
            k:v for k,v in fake.items() if k!="proposal_content_sha256"})
        with self.assertRaises(ValueError):
            build_p192_disjoint_research_fork(
                state=state,refetched=batch,
                validated_review=fake,now_utc=NEXT)

    def test_08_origin_manifest_tamper_rejected(self):
        _,state,batch,review=prepared()
        state.last_manifest["total_closed_bars"]=2
        with self.assertRaises(ValueError):
            build_p192_disjoint_research_fork(
                state=state,refetched=batch,
                validated_review=review,now_utc=NEXT)

    def test_09_wrong_revision_or_metadata_only_rejected(self):
        _,state,batch,review=prepared()
        unchanged=source(include19=True)
        with self.assertRaises(ValueError):
            build_p192_disjoint_research_fork(
                state=state,refetched=unchanged,
                validated_review=review,now_utc=NEXT)
        mod=replace(batch,closed_bars=tuple(
            replace(b,exchange_timezone_origin="SIM_BAD")
            if b.native_open_label=="2026-11-18" else b
            for b in batch.closed_bars))
        with self.assertRaises(ValueError):
            build_p192_disjoint_research_fork(
                state=state,refetched=mod,
                validated_review=review,now_utc=NEXT)

    def test_10_future_sydney_d1_not_eligible(self):
        # Review observation clock matches this earlier post-18Nov seal;
        # 19Nov is not a CLOSED Sydney D1 until the next source session.
        _,state,batch,review=prepared(clock=AFTER)
        with self.assertRaisesRegex(ValueError,"UNCLOSED_OR_UNPUBLISHED"):
            build_p192_disjoint_research_fork(
                state=state,refetched=batch,
                validated_review=review,now_utc=AFTER)

    def test_11_non_utc_or_wrong_utc_asof_rejected(self):
        _,state,batch,review=prepared()
        with self.assertRaises(ValueError):
            build_p192_disjoint_research_fork(
                state=state,refetched=batch,
                validated_review=review,now_utc=NEXT.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            build_p192_disjoint_research_fork(
                state=state,refetched=batch,
                validated_review=review,now_utc=NEXT+timedelta(seconds=1))

    def test_12_missing_nov18_refetch_cannot_create_fork(self):
        _,state,batch,review=prepared()
        bad=source(include18=False,include19=True)
        with self.assertRaises(ValueError):
            build_p192_disjoint_research_fork(
                state=state,refetched=bad,
                validated_review=review,now_utc=NEXT)

    def test_13_wrong_input_type_and_no_private_repr(self):
        _,state,batch,review=prepared()
        fork=build_p192_disjoint_research_fork(
            state=state,refetched=batch,
            validated_review=review,now_utc=NEXT)
        self.assertNotIn(fork.original_manifest_sha256,repr(fork))
        with self.assertRaises(TypeError):
            verify_p192_disjoint_research_fork(
                object(),state=state,refetched=batch,
                validated_review=review,now_utc=NEXT)

    def test_14_public_operation_never_claims_external_data_rights(self):
        _,state,batch,review=prepared()
        s=build_p192_disjoint_research_fork(
            state=state,refetched=batch,
            validated_review=review,now_utc=NEXT).public_summary()
        for k in ("publisher_first_known_verified","source_account_rights_verified",
                  "owner_canonical_revision_approved","may_write_drive",
                  "may_publish_buy_sell","may_trade"):
            self.assertFalse(s[k])
        for k in ("additional_vendor_requests","additional_drive_reads",
                  "drive_writes","broker_orders"):
            self.assertEqual(s[k],0)

    def test_15_existing_real_writer_still_fails_closed_no_extra_writes(self):
        err,logs,calls,store=P192RealWriterCutoffTests().run_job(
            clock=NEXT,revision=True)
        self.assertEqual(err,"P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertEqual(store.puts,2)
        self.assertEqual([tf for kind,tf in calls if kind=="vendor"],["1day"])
        marker="MFX_P207_P192_REVISED_D1_FORK_INMEMORY_ONLY"
        lines=logs.splitlines()
        self.assertEqual(lines.count(marker),1)
        pub=json.loads(lines[lines.index(marker)+1])
        self.assertEqual(pub["status"], STATUS)
        self.assertEqual(pub["private_research_d1_rows"],2)
        self.assertEqual(pub["private_later_closed_d1_rows"],1)
        self.assertFalse(pub["research_fork_persisted"])
        self.assertEqual(pub["drive_writes"],0)
        self.assertIn("MFX_P204_P192_REDACTED_OWNER_REVIEW_ONLY",logs)
        self.assertIn("MFX_P200_P192_D1_SHA_DIFF_REDACTED_NO_COMMIT",logs)
        self.assertNotIn('"private_source_bars"',logs)
        self.assertNotIn('"private_revised_source_sha_pair"',logs)
        self.assertLess(lines.index("MFX_P204_P192_REDACTED_OWNER_REVIEW_ONLY"),
                        lines.index(marker))
        self.assertLess(lines.index(marker),
                        lines.index("MFX_P200_P192_D1_SHA_DIFF_REDACTED_NO_COMMIT"))

    def test_16_invalid_review_sealed_origin_cannot_bypass_existing_hold(self):
        _,state,batch,review=prepared()
        fake=deepcopy(review)
        fake["owner_canonical_revision_approved"]=True
        fake["proposal_content_sha256"]=digest({
            k:v for k,v in fake.items() if k!="proposal_content_sha256"})
        with self.assertRaises(ValueError):
            build_p192_disjoint_research_fork(
                state=state,refetched=batch,
                validated_review=fake,now_utc=NEXT)
