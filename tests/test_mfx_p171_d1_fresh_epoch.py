"""P0.171 hermetic fresh-D1 epoch tests: no OAuth, price API, or broker.

The old D1 SHA chain is never changed. Fresh 11 Nov requires a NEW provider
envelope with that day and uses a new namespace for all following appends.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from dataclasses import replace
from pathlib import Path

from mfx_cache.native_d1_fresh_epoch import (
    PREFIX, SCHEMA, INCIDENT, PrivateD1FreshEpochStore,
    audit_fresh_epoch, plan_fresh_epoch_fetch,
    plan_fresh_epoch_seal, commit_fresh_epoch,
)
from mfx_cache.td_m5_codec import digest
from test_mfx_p168_independent_h4_d1_hold_cache import (
    D1_LABELS, batch, state,
)

NOW=datetime(2026,11,15,12,30,tzinfo=timezone.utc)


class MemoryEpochStore:
    def __init__(self):
        self.files={"chunk":{},"manifest":{}}
        self.puts=0

    def list_names(self,bucket):
        return tuple(sorted(self.files[bucket]))

    def read(self,bucket,name):
        return deepcopy(self.files[bucket][name])

    def put_if_absent(self,bucket,name,value):
        if name in self.files[bucket]:
            if self.files[bucket][name]!=value:
                raise ValueError("IMMUTABLE_DRIVE")
            return
        self.files[bucket][name]=deepcopy(value)
        self.puts+=1


def original_sha():
    return digest(state("1day",D1_LABELS).last_manifest)


def fresh():
    return batch("1day", D1_LABELS+("2026-11-12","2026-11-13"),
                 amend="2026-11-11")


def prepared():
    store=MemoryEpochStore()
    result=commit_fresh_epoch(
        store,batch=fresh(),origin_v1_sha=original_sha(),now_utc=NOW)
    return store,result


class OwnerFreshD1EpochTests(TestCase):
    def test_01_new_root_contains_changed_11_nov_and_later_only(self):
        store,r=prepared()
        self.assertEqual(r["status"],"D1_FRESH_EPOCH_SHA_COMMITTED")
        self.assertEqual(r["new_bars"],3)
        self.assertEqual(store.puts,2)
        c=next(iter(store.files["chunk"].values()))
        self.assertEqual([x["native_open_label"] for x in c["bars"]],
                         ["2026-11-11","2026-11-12","2026-11-13"])
        self.assertTrue(c["bars"][0]["close"])
        self.assertEqual(c["origin_v1_manifest_sha256"],original_sha())

    def test_02_independent_full_sha_audit(self):
        store,r=prepared()
        s=audit_fresh_epoch(store,origin_v1_sha=original_sha())
        self.assertEqual(s.manifests,1)
        self.assertEqual(s.chunks,1)
        self.assertIsNone(s.orphan_chunk)
        self.assertEqual(s.last_manifest["last_native_open_label"],"2026-11-13")
        self.assertEqual(s.last_manifest["total_closed_bars"],3)
        self.assertEqual(r["manifest_sha256"],digest(s.last_manifest))

    def test_03_idempotent_source_refetch_never_overwrites(self):
        store,_=prepared()
        original=deepcopy(store.files)
        again=commit_fresh_epoch(
            store,batch=fresh(),origin_v1_sha=original_sha(),
            now_utc=NOW+timedelta(hours=1))
        self.assertEqual(again["new_bars"],0)
        self.assertEqual(store.puts,2)
        self.assertEqual(original,store.files)

    def test_04_later_closed_native_day_append_monotonic(self):
        store,_=prepared()
        new=batch("1day",D1_LABELS+(
            "2026-11-12","2026-11-13","2026-11-14"),
            amend="2026-11-11")
        r=commit_fresh_epoch(
            store,batch=new,origin_v1_sha=original_sha(),
            now_utc=NOW+timedelta(days=1))
        self.assertEqual(r["new_bars"],1)
        st=audit_fresh_epoch(store,origin_v1_sha=original_sha())
        self.assertEqual(st.manifests,2)
        self.assertEqual(st.last_manifest["total_closed_bars"],4)
        self.assertEqual(st.last_manifest["last_native_open_label"],"2026-11-14")

    def test_05_wrong_old_v1_sha_rejected_before_staging(self):
        store,_=prepared()
        with self.assertRaisesRegex(ValueError,"ORIGINAL_V1_SHA|INVALID_EPOCH_CHUNK"):
            audit_fresh_epoch(store,origin_v1_sha="a"*64)

    def test_06_old_manifest_is_unmodified_external_evidence(self):
        original=deepcopy(state("1day",D1_LABELS).last_manifest)
        store,_=prepared()
        self.assertEqual(original,state("1day",D1_LABELS).last_manifest)
        self.assertEqual(store.puts,2)

    def test_07_fresh_source_must_include_11_nov(self):
        source=batch("1day",D1_LABELS[:-1]+("2026-11-12",))
        with self.assertRaisesRegex(ValueError,"FRESH_PROVIDER_MISSING"):
            plan_fresh_epoch_seal(
                source,state=audit_fresh_epoch(MemoryEpochStore(),
                           origin_v1_sha=original_sha()),
                origin_v1_sha=original_sha(),now_utc=NOW)

    def test_08_wrong_origin_can_never_alias_existing_epoch(self):
        store,_=prepared()
        with self.assertRaises(ValueError):
            commit_fresh_epoch(
                store,batch=fresh(),origin_v1_sha="b"*64,now_utc=NOW)

    def test_09_second_revision_of_11_nov_fails_closed(self):
        store,_=prepared()
        newer=batch("1day",D1_LABELS+("2026-11-12","2026-11-13"),
                    amend="2026-11-12")
        with self.assertRaisesRegex(ValueError,"NEW_EPOCH_OVERLAP_REVISION"):
            commit_fresh_epoch(store,batch=newer,
                               origin_v1_sha=original_sha(),now_utc=NOW)
        self.assertEqual(store.puts,2)

    def test_10_missing_overlap_refetch_denied(self):
        store,_=prepared()
        source=batch("1day",("2026-11-12","2026-11-13","2026-11-14"))
        with self.assertRaisesRegex(ValueError,"NEW_EPOCH_OVERLAP_REVISION"):
            commit_fresh_epoch(store,batch=source,
                               origin_v1_sha=original_sha(),now_utc=NOW)
        self.assertEqual(store.puts,2)

    def test_11_no_side_scope_or_invalid_meta(self):
        store=MemoryEpochStore()
        for invalid in (replace(fresh(),symbol="GBP/USD"),
                        replace(fresh(),source="MYSTERY")):
            with self.assertRaises(ValueError):
                commit_fresh_epoch(
                    store,batch=invalid,origin_v1_sha=original_sha(),
                    now_utc=NOW)

    def test_12_original_latest_D1_is_source_only_not_carried_forward(self):
        s=MemoryEpochStore()
        commit_fresh_epoch(s,batch=fresh(),
                           origin_v1_sha=original_sha(),now_utc=NOW)
        c=next(iter(s.files["chunk"].values()))
        self.assertFalse(any(x["native_open_label"]<INCIDENT
                             for x in c["bars"]))

    def test_13_tampered_price_sha_fails_audit(self):
        store,_=prepared()
        key=next(iter(store.files["chunk"]))
        store.files["chunk"][key]["bars"][0]["close"]="1.0001"
        with self.assertRaises(ValueError):
            audit_fresh_epoch(store,origin_v1_sha=original_sha())

    def test_14_tampered_manifest_parent_fails_audit(self):
        store,_=prepared()
        key=next(iter(store.files["manifest"]))
        store.files["manifest"][key]["parent_manifest_sha256"]="a"*64
        with self.assertRaisesRegex(ValueError,"CHAIN_OR_PARENT"):
            audit_fresh_epoch(store,origin_v1_sha=original_sha())

    def test_15_missing_chunk_or_reused_chunk_denied(self):
        store,_=prepared()
        store.files["chunk"].clear()
        with self.assertRaisesRegex(ValueError,"MISSING_OR_REUSED_CHUNK"):
            audit_fresh_epoch(store,origin_v1_sha=original_sha())

    def test_16_uncertain_old_source_explicitly_not_released(self):
        store,_=prepared()
        m=next(iter(store.files["manifest"].values()))
        self.assertFalse(m["publisher_first_known_verified"])
        self.assertFalse(m["may_publish_buy_sell"])
        self.assertEqual(m["broker_orders"],0)
        self.assertTrue(m["owner_approved_cache_rebaseline"])

    def test_17_runner_clock_must_be_utc(self):
        with self.assertRaisesRegex(ValueError,"UTC_RUNNER"):
            plan_fresh_epoch_seal(
                fresh(),state=audit_fresh_epoch(
                    MemoryEpochStore(),origin_v1_sha=original_sha()),
                origin_v1_sha=original_sha(),
                now_utc=datetime(2026,11,15,12,30))

    def test_18_no_due_D1_source_call_after_root(self):
        store,_=prepared()
        assert plan_fresh_epoch_fetch(
            state=audit_fresh_epoch(store,origin_v1_sha=original_sha()),
            now_utc=datetime(2026,11,14,3,0,tzinfo=timezone.utc)) is None

    def test_19_new_day_requests_bounded_overlap(self):
        store,_=prepared()
        result=plan_fresh_epoch_fetch(
            state=audit_fresh_epoch(store,origin_v1_sha=original_sha()),
            now_utc=NOW+timedelta(days=2))
        self.assertIsNotNone(result)
        self.assertEqual(result["interval"],"1day")
        self.assertTrue(24<=int(result["outputsize"])<=120)

    def test_20_separate_drive_prefixes_no_legacy_write(self):
        s=PrivateD1FreshEpochStore(session="offline")
        self.assertEqual(s._bucket("chunk")[1],PREFIX+"chunk_")
        self.assertEqual(s._bucket("manifest")[1],PREFIX+"manifest_")
        self.assertNotIn("NATIVE_V1",PREFIX)
        self.assertNotIn("P169",PREFIX)
        with self.assertRaisesRegex(ValueError,"EPOCH_BUCKET_DENIED"):
            s._bucket("quote")

    def test_21_owner_cutoff_replaces_old_schedule_without_changing_cadence(self):
        y=Path(".github/workflows/mfx-native-htf-incremental-commit.yml").read_text()
        # P171 old epoch is preserved only as historical SHA archive;
        # P192 is the explicitly selected NEW writer source since 18 Nov.
        self.assertIn('MFX_D1_OWNER_CUTOFF_20261118: "true"',y)
        self.assertNotIn('MFX_D1_OWNER_REBASE_20261111: "true"',y)
        self.assertIn('cron: "25 * * * *"',y)
        self.assertIn("mfx-twelvedata-private-cache",y)
        read=Path(".github/workflows/mfx-native-htf-cache-audit.yml").read_text()
        self.assertIn('MFX_D1_OWNER_REBASE_20261111: "true"',read)
        self.assertIn('MFX_D1_OWNER_CUTOFF_20261118: "true"',read)

    def test_22_public_code_prohibits_source_rewrite(self):
        y=Path("tools/run_mfx_native_htf_incremental_commit.py").read_text()
        self.assertIn("old_d1_drive_writes",y)
        self.assertIn("MFX_P171_D1_OWNER_FRESH_EPOCH_SHA_READBACK_PASS",y)
        self.assertIn("NO_SIGNAL",Path(
            "docs/MFX_P171_D1_OWNER_REBASE_20261111.md").read_text())

    def test_23_conflicting_duplicate_manifest_name_denied(self):
        store,_=prepared()
        x=next(iter(store.files["manifest"]))
        store.files["manifest"][x+"_fake"]=deepcopy(store.files["manifest"][x])
        with self.assertRaises(ValueError):
            audit_fresh_epoch(store,origin_v1_sha=original_sha())

    def test_24_partial_write_orphan_cannot_be_silently_accepted(self):
        store,_=prepared()
        store.files["chunk"][PREFIX+"chunk_20261115_"+"a"*64+".json"]={}
        st=audit_fresh_epoch(store,origin_v1_sha=original_sha())
        self.assertIsNotNone(st.orphan_chunk)
        with self.assertRaisesRegex(ValueError,"UNRELATED_EPOCH_ORPHAN"):
            commit_fresh_epoch(store,batch=batch(
                "1day",D1_LABELS+(
                    "2026-11-12","2026-11-13","2026-11-14"),
                amend="2026-11-11"),
                origin_v1_sha=original_sha(),
                now_utc=NOW+timedelta(days=1))

    def test_25_owner_epoch_stays_independent_from_p169_observation(self):
        self.assertNotIn("P169_EURUSD",PREFIX)
        store,_=prepared()
        for bucket in ("chunk","manifest"):
            self.assertTrue(all(name.startswith(PREFIX)
                                for name in store.files[bucket]))
