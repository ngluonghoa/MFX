"""P0.192: isolated 18 Nov Sydney-local D1 source epoch, hermetic tests.

No vendor/Drive OAuth or live quotes. Original P171 and V1 archives preserved.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from unittest import TestCase

from mfx_cache.native_d1_epoch_20261118 import (
    PREFIX, SCHEMA, INCIDENT, PUBLICATION_BUFFER, audit_fresh_epoch,
    plan_fresh_epoch_fetch, plan_fresh_epoch_seal, commit_fresh_epoch,
    PrivateD1FreshEpochStore,
)
from test_mfx_p171_d1_fresh_epoch import MemoryEpochStore, original_sha
from test_mfx_p168_independent_h4_d1_hold_cache import D1_LABELS, batch

BEFORE=datetime(2026,11,18,8,0,tzinfo=timezone.utc)
AFTER=datetime(2026,11,18,14,0,tzinfo=timezone.utc)
NEXT=datetime(2026,11,19,14,0,tzinfo=timezone.utc)
NOV18=("2026-11-18",)
NOV19=("2026-11-19",)


def source(*, include18=True, include19=False, revised=None):
    days=D1_LABELS+("2026-11-12","2026-11-17")
    if include18:
        days+=NOV18
    if include19:
        days+=NOV19
    return batch("1day",days,amend=revised)


def new_store():
    s=MemoryEpochStore()
    return s,audit_fresh_epoch(s,origin_v1_sha=original_sha())


class P192OwnerD1Nov18EpochTests(TestCase):
    def test_01_cutoff_exact_sydney_date_and_distinct_namespace(self):
        self.assertEqual(INCIDENT,"2026-11-18")
        self.assertIn("20261118",PREFIX)
        self.assertIn("P192",SCHEMA)
        self.assertNotIn("P171",PREFIX)
        self.assertNotIn("P169",PREFIX)
        self.assertIsNotNone(PrivateD1FreshEpochStore)

    def test_02_no_vendor_request_before_nov18_session_closes_and_grace(self):
        _,st=new_store()
        self.assertIsNone(plan_fresh_epoch_fetch(state=st,now_utc=BEFORE))
        # Sydney 19-Nov midnight is 2026-11-18 13:00 UTC.
        # Retain the preexisting 2m15s publication grace.
        self.assertIsNone(plan_fresh_epoch_fetch(
            state=st,now_utc=datetime(2026,11,18,13,2,14,
                                      tzinfo=timezone.utc)))
        self.assertIsNotNone(plan_fresh_epoch_fetch(
            state=st,now_utc=datetime(2026,11,18,13,2,15,
                                      tzinfo=timezone.utc)))
        self.assertEqual(PUBLICATION_BUFFER,timedelta(minutes=2,seconds=15))

    def test_03_first_valid_fresh_fetch_seals_only_nov18_no_legacy(self):
        store,state=new_store()
        plan=plan_fresh_epoch_seal(
            source(),state=state,origin_v1_sha=original_sha(),
            now_utc=AFTER)
        self.assertIsNotNone(plan)
        self.assertEqual([b["native_open_label"] for b in plan[1]["bars"]],
                         ["2026-11-18"])
        self.assertEqual(plan[3]["owner_rebaseline_date"],"2026-11-18")
        result=commit_fresh_epoch(
            store,batch=source(),origin_v1_sha=original_sha(),now_utc=AFTER)
        self.assertEqual(result["status"],"D1_FRESH_EPOCH_SHA_COMMITTED")
        self.assertEqual(result["new_bars"],1)
        self.assertEqual(store.puts,2)
        audited=audit_fresh_epoch(store,origin_v1_sha=original_sha())
        self.assertEqual(audited.manifests,1)
        self.assertEqual(audited.last_manifest["total_closed_bars"],1)
        self.assertEqual(audited.last_manifest["last_native_open_label"],INCIDENT)
        self.assertEqual(audited.last_manifest["publisher_first_known_verified"],False)
        self.assertEqual(audited.last_manifest["may_publish_buy_sell"],False)

    def test_04_old_source_11nov_can_change_without_entering_new_epoch(self):
        store,_=new_store()
        one=source(revised="2026-11-11")
        result=commit_fresh_epoch(
            store,batch=one,origin_v1_sha=original_sha(),now_utc=AFTER)
        self.assertEqual(result["total_bars"],1)
        self.assertEqual(
            next(iter(store.files["chunk"].values()))["bars"][0]["native_open_label"],
            "2026-11-18")

    def test_05_after_nov18_only_monotonic_append_and_idempotent_fetch(self):
        store,_=new_store()
        first=commit_fresh_epoch(
            store,batch=source(),origin_v1_sha=original_sha(),now_utc=AFTER)
        same=commit_fresh_epoch(
            store,batch=source(),origin_v1_sha=original_sha(),
            now_utc=AFTER+timedelta(hours=1))
        self.assertEqual(same["new_bars"],0)
        self.assertEqual(store.puts,2)
        later=commit_fresh_epoch(
            store,batch=source(include19=True),
            origin_v1_sha=original_sha(),now_utc=NEXT)
        self.assertEqual(later["new_bars"],1)
        self.assertEqual(later["total_bars"],2)
        self.assertEqual(store.puts,4)
        state=audit_fresh_epoch(store,origin_v1_sha=original_sha())
        self.assertEqual(state.manifests,2)
        self.assertEqual(first["last_native_open_label"],"2026-11-18")
        self.assertEqual(later["last_native_open_label"],"2026-11-19")

    def test_06_revision_of_new_nov18_candle_is_still_quarantined(self):
        store,_=new_store()
        commit_fresh_epoch(
            store,batch=source(),origin_v1_sha=original_sha(),now_utc=AFTER)
        saved=deepcopy(store.files)
        changed=source(include19=True,revised="2026-11-18")
        with self.assertRaisesRegex(ValueError,"P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE"):
            commit_fresh_epoch(store,batch=changed,
                               origin_v1_sha=original_sha(),now_utc=NEXT)
        self.assertEqual(store.files,saved)

    def test_07_missing_first_nov18_bar_must_not_promote_nov19(self):
        store,state=new_store()
        with self.assertRaisesRegex(ValueError,"P192_FRESH_PROVIDER_MISSING_20261118"):
            plan_fresh_epoch_seal(
                source(include18=False,include19=True),state=state,
                origin_v1_sha=original_sha(),now_utc=NEXT)
        self.assertEqual(store.puts,0)

    def test_08_sha_original_binding_bad_origin_or_unknown_archive_denied(self):
        store,_=new_store()
        with self.assertRaises(ValueError):
            audit_fresh_epoch(store,origin_v1_sha="x"*64)
        commit_fresh_epoch(
            store,batch=source(),origin_v1_sha=original_sha(),now_utc=AFTER)
        with self.assertRaises(ValueError):
            audit_fresh_epoch(store,origin_v1_sha="a"*64)

    def test_09_invalid_timestamp_and_malformed_prices_fail_closed(self):
        store,st=new_store()
        with self.assertRaises(ValueError):
            plan_fresh_epoch_fetch(
                state=st,now_utc=datetime(2026,11,18,13,2,15))
        changed=source()
        altered=replace(changed,closed_bars=tuple(
            replace(bar,high="NaN") if bar.native_open_label=="2026-11-18"
            else bar for bar in changed.closed_bars))
        with self.assertRaises(ValueError):
            commit_fresh_epoch(store,batch=altered,
                               origin_v1_sha=original_sha(),now_utc=AFTER)
        self.assertEqual(store.puts,0)

    def test_10_recent_sha_continuity_detects_missing_18_overlap(self):
        store,_=new_store()
        commit_fresh_epoch(
            store,batch=source(),origin_v1_sha=original_sha(),now_utc=AFTER)
        with self.assertRaisesRegex(ValueError,"P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE"):
            commit_fresh_epoch(
                store,batch=source(include18=False,include19=True),
                origin_v1_sha=original_sha(),now_utc=NEXT)
        self.assertEqual(store.puts,2)
