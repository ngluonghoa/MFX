"""P0.183: no-network H4-only isolation when fresh P171 D1 SHA differs."""
from __future__ import annotations
from contextlib import ExitStack, redirect_stdout
from dataclasses import replace
from datetime import datetime, timezone
from io import StringIO
import json
import os
from unittest import TestCase
from unittest.mock import patch
from mfx_cache.native_d1_fresh_epoch import audit_fresh_epoch, plan_fresh_epoch_seal
from mfx_cache.p180_d1_overlap_diagnosis import diagnose_p171_overlap_source
from mfx_cache.p183_p171_changed_sha_h4_isolation import eligible_for_h4_only,VERSION
from tools.mfx_native_htf_drive_seal import NativeCommitReceipt
from tools.run_mfx_native_htf_incremental_commit import main
from test_mfx_p168_independent_h4_d1_hold_cache import (
    D1_LABELS,FakeStore,FakeReadThrough,batch,state,envelope,
)
from test_mfx_p171_d1_fresh_epoch import prepared,original_sha

MODULE="tools.run_mfx_native_htf_incremental_commit"
NOW=datetime(2026,11,15,12,30,tzinfo=timezone.utc)
H4_OLD="2026-11-15 04:00:00"
H4_NEW="2026-11-15 08:00:00"

def input_state():
    store,_=prepared()
    state_p171=audit_fresh_epoch(store,origin_v1_sha=original_sha())
    # P171's first Nov11 has already been changed vs legacy D1.
    # Only additional Nov12 change is a *new* fresh-epoch conflict.
    bars=batch("1day",D1_LABELS+(
        "2026-11-12","2026-11-13","2026-11-14"),amend="2026-11-11")
    bars=replace(bars,closed_bars=tuple(
        replace(x,high="1.1041") if x.native_open_label=="2026-11-12" else x
        for x in bars.closed_bars))
    try:
        plan_fresh_epoch_seal(bars,state=state_p171,
                              origin_v1_sha=original_sha(),now_utc=NOW)
    except ValueError as e:
        if str(e)!="P171_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE":
            raise
    else:
        raise AssertionError("Revised D1 incorrectly accepted")
    proof=diagnose_p171_overlap_source(bars,state=state_p171)
    return store,state_p171,proof

class P183H4IsolatedOnP171ChangedD1(TestCase):
    def test_01_exact_one_sha_revised_and_no_missing(self):
        _,st,proof=input_state()
        self.assertTrue(eligible_for_h4_only(proof,st))
        self.assertEqual(proof["overlap_sha_changed_count"],1)
        self.assertEqual(proof["overlap_sha_unchanged_count"],2)

    def test_02_all_altered_rights_and_counts_rejected(self):
        _,st,proof=input_state()
        for k,v in {
            "conflict_classification":"MISSING_AND_CHANGED",
            "overlap_sha_changed_count":2,"overlap_sha_unchanged_count":1,
            "overlap_labels_missing_count":1,
            "previous_indexed_labels":4,"refetched_closed_native_bars":1,
            "source_vendor_correction_cause_proven":True,
            "source_publisher_first_known_verified":True,
            "source_promotion_authorized":True,
            "source_quarantine_bypassed":True,
            "original_numeric_rules_approved":True,
            "may_publish_buy_sell":True,
            "provider_price_requests_added":1,
            "drive_reads_added":1,"drive_writes":1,"broker_orders":1,
        }.items():
            with self.subTest(field=k):
                self.assertFalse(eligible_for_h4_only({**proof,k:v},st))
        self.assertFalse(eligible_for_h4_only({**proof,"raw":"private"},st))

    def test_03_orphan_or_not_reaudited_state_rejected(self):
        _,st,proof=input_state()
        for invalid in (replace(st,last_manifest=None),
                        replace(st,orphan_chunk="orphan"),
                        replace(st,manifests=0),replace(st,chunks=3)):
            self.assertFalse(eligible_for_h4_only(proof,invalid))

    def run_fake(self,*,missing=False,two_changes=False,h4_bad=False,
                 h4_not_due=False,source_changed=False,quota=(100,400)):
        p171_store,_,_=input_state()
        existing=(H4_NEW,) if h4_not_due else (H4_OLD,)
        canonical={"4h":state("4h",existing),
                   "1day":state("1day",D1_LABELS)}
        calls=[]
        def audit(store,*,symbol,interval):
            calls.append(("audit",interval))
            if (source_changed and interval=="1day"
                    and calls.count(("audit","1day"))==2):
                return state("1day",D1_LABELS[:-1])
            return canonical[interval]
        d1labels=D1_LABELS+("2026-11-12","2026-11-13","2026-11-14")
        if missing:
            d1labels=tuple(x for x in d1labels if x!="2026-11-13")
        d1=envelope("1day",d1labels,amend="2026-11-11")
        for e in d1["values"]:
            if e["datetime"]=="2026-11-12" or (
                two_changes and e["datetime"]=="2026-11-13"):
                e["high"]="1.1041"
        resp={
            "4h":envelope("4h",(H4_OLD,H4_NEW),
                          amend=H4_OLD if h4_bad else None),
            "1day":d1,
        }
        def fetch(_url,params):
            calls.append(("vendor",params["interval"]))
            return resp[params["interval"]]
        def commit(store,b):
            calls.append(("commit",b.interval))
            return NativeCommitReceipt(
                status="NATIVE_BATCH_COMMITTED",
                symbol="EUR/USD",interval=b.interval,
                last_native_open_label=b.closed_bars[-1].native_open_label,
                newly_closed_native_bars=1,total_closed_native_bars=20,
                manifest_sha256="a"*64,drive_objects_created_max=2)
        with ExitStack() as st:
            st.enter_context(patch.dict(os.environ,{
                "GITHUB_EVENT_NAME":"schedule",
                "MFX_REAL_CACHE_ENABLED":"true",
                "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
                "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
                "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED":"true",
                "MFX_D1_OWNER_REBASE_20261111":"true",
            }))
            st.enter_context(patch(MODULE+"._settings",
                                   return_value=("fake-key",{"type":"test"},400)))
            st.enter_context(patch(MODULE+"._session",return_value="session"))
            st.enter_context(patch(MODULE+".PrivateNativeDriveStore",FakeStore))
            st.enter_context(patch(MODULE+".NativeAuditReadThroughWitness",
                                   FakeReadThrough))
            st.enter_context(patch(MODULE+".audit_native_archive",side_effect=audit))
            st.enter_context(patch(MODULE+".PrivateD1FreshEpochStore",
                                   return_value=p171_store))
            st.enter_context(patch(MODULE+"._usage",return_value=quota))
            st.enter_context(patch(MODULE+"._read_payload",side_effect=fetch))
            st.enter_context(patch(MODULE+".commit_native_batch",
                                   side_effect=commit))
            clock=st.enter_context(patch(MODULE+".datetime"))
            clock.now.return_value=NOW
            log=StringIO()
            with redirect_stdout(log):
                try:
                    main()
                except ValueError as e:
                    return str(e),calls,log.getvalue(),p171_store
        return "NO_EXCEPTION",calls,log.getvalue(),p171_store

    def test_04_H4_only_appends_and_failure_remains_red(self):
        err,calls,log,store=self.run_fake()
        self.assertEqual(err,"P171_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertEqual([x[1] for x in calls if x[0]=="commit"],["4h"])
        self.assertEqual([x[1] for x in calls if x[0]=="vendor"],["4h","1day"])
        self.assertEqual([x[1] for x in calls if x[0]=="audit"],
                         ["4h","1day","4h","1day"])
        self.assertEqual(store.puts,2)
        self.assertIn("MFX_P183_H4_ONLY_P171_D1_CHANGED_SHA_STILL_HELD_RED",log)
        r=json.loads(log.splitlines()[-1])
        self.assertEqual(r["schema"],VERSION)
        self.assertEqual(r["h4_newly_closed_bars"],1)
        self.assertEqual(r["p171_d1_old_writes"],0)
        self.assertEqual(r["p171_d1_fresh_writes"],0)
        self.assertTrue(r["h4_does_not_approve_d1"])
        self.assertFalse(r["may_publish_buy_sell"])
        self.assertEqual(r["broker_orders"],0)

    def test_05_missing_D1_overlap_cannot_commit_H4(self):
        err,calls,log,_=self.run_fake(missing=True)
        self.assertEqual(err,"P171_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertNotIn(("commit","4h"),calls)

    def test_06_two_changed_D1_overlaps_cannot_commit_H4(self):
        err,calls,log,_=self.run_fake(two_changes=True)
        self.assertEqual(err,"P171_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertNotIn(("commit","4h"),calls)

    def test_07_H4_SHA_overlap_revision_blocks_before_D1(self):
        err,calls,log,_=self.run_fake(h4_bad=True)
        self.assertEqual(err,"P059_SOURCE_NATIVE_REVISION_QUARANTINE")
        self.assertNotIn(("commit","4h"),calls)

    def test_08_changed_original_D1_custody_during_fetch_blocks_H4(self):
        err,calls,log,_=self.run_fake(source_changed=True)
        self.assertEqual(err,"P059_NATIVE_ARCHIVE_CHANGED_DURING_FETCH")
        self.assertNotIn(("commit","4h"),calls)

    def test_09_not_enough_quota_means_no_provider_or_H4_write(self):
        err,calls,log,_=self.run_fake(quota=(399,400))
        self.assertEqual(err,"NO_EXCEPTION")
        self.assertFalse(any(k=="vendor" or k=="commit" for k,_ in calls))

    def test_10_H4_not_due_means_D1_red_only(self):
        err,calls,log,_=self.run_fake(h4_not_due=True)
        self.assertEqual(err,"P171_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertNotIn(("commit","4h"),calls)

    def test_11_never_log_private_source_or_credentials(self):
        err,calls,log,_=self.run_fake()
        self.assertEqual(err,"P171_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        for secret in ("1.1000","1.1041","fake-key",
                       "2026-11-11","2026-11-12"):
            self.assertNotIn(secret,log)
