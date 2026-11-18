"""P0.192 actual scheduled writer integration: 18 Nov fresh D1 cutoff.

Scripted repository/cache/provider ports, zero network and no broker.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import json
import os
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.native_d1_epoch_20261118 import audit_fresh_epoch
from test_mfx_p171_d1_fresh_epoch import MemoryEpochStore, original_sha
from test_mfx_p168_independent_h4_d1_hold_cache import (
    D1_LABELS, FakeStore, FakeReadThrough, state, envelope,
)
from tools.run_mfx_native_htf_incremental_commit import main

MODULE="tools.run_mfx_native_htf_incremental_commit"
AFTER=datetime(2026,11,18,14,0,tzinfo=timezone.utc)
BEFORE=datetime(2026,11,18,8,0,tzinfo=timezone.utc)


class P192RealWriterCutoffTests(TestCase):
    def run_job(self,*,clock=AFTER,old_owner="false",cutoff="true",
                missing_nov18=False,revision=False):
        store=MemoryEpochStore()
        if revision:
            from test_mfx_p192_d1_nov18_cutoff import source
            from mfx_cache.native_d1_epoch_20261118 import commit_fresh_epoch
            commit_fresh_epoch(
                store,batch=source(),origin_v1_sha=original_sha(),
                now_utc=AFTER)
        # Keep H4 exactly current in every UTC fixture (no H4 vendor call).
        last_h4=(clock.strftime("%Y-%m-%d")+" 08:00:00"
                 if clock.hour==14 else "2026-11-18 00:00:00")
        archives={
            "4h":state("4h",(last_h4,)),
            "1day":state("1day",D1_LABELS),
        }
        date_labels=D1_LABELS+("2026-11-12","2026-11-17")
        if not missing_nov18:
            date_labels+=("2026-11-18",)
        if revision:
            date_labels+=("2026-11-19",)
        d1=envelope("1day",date_labels,amend=(
            "2026-11-18" if revision else "2026-11-11"))
        calls=[]
        def aud(store,*,symbol,interval):
            calls.append(("audit",interval))
            return archives[interval]
        def get_payload(_,params):
            calls.append(("vendor",params["interval"]))
            if params["interval"] != "1day":
                raise AssertionError("H4 should not be due in this fixture")
            return d1
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,{
                "GITHUB_EVENT_NAME":"schedule",
                "MFX_REAL_CACHE_ENABLED":"true",
                "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
                "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
                "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED":"true",
                "MFX_D1_OWNER_REBASE_20261111":old_owner,
                "MFX_D1_OWNER_CUTOFF_20261118":cutoff,
            }))
            stack.enter_context(patch(MODULE+"._settings",
                                      return_value=("fake-key",{},400)))
            stack.enter_context(patch(MODULE+"._session",return_value="fake-session"))
            stack.enter_context(patch(MODULE+".PrivateNativeDriveStore",FakeStore))
            stack.enter_context(patch(MODULE+".NativeAuditReadThroughWitness",
                                      FakeReadThrough))
            stack.enter_context(patch(MODULE+".audit_native_archive",
                                      side_effect=aud))
            stack.enter_context(patch(MODULE+".PrivateD1Nov18Store",
                                      return_value=store))
            stack.enter_context(patch(MODULE+"._usage",
                                      return_value=(100,400)))
            stack.enter_context(patch(MODULE+"._read_payload",
                                      side_effect=get_payload))
            time=stack.enter_context(patch(MODULE+".datetime"))
            time.now.return_value=clock
            out=StringIO()
            with redirect_stdout(out):
                try:
                    main()
                except ValueError as exc:
                    return str(exc),out.getvalue(),calls,store
        return None,out.getvalue(),calls,store

    def test_01_before_18nov_sydney_close_no_D1_vendor_or_write(self):
        err,log,calls,store=self.run_job(clock=BEFORE)
        self.assertIsNone(err)
        self.assertFalse(any(kind=="vendor" for kind,_ in calls))
        self.assertEqual(store.puts,0)
        self.assertIn("ZERO_VENDOR_CALLS",log)

    def test_02_after_closed_18nov_old_11nov_diff_ignored(self):
        err,log,calls,store=self.run_job()
        self.assertIsNone(err)
        self.assertEqual([tf for k,tf in calls if k=="vendor"],["1day"])
        self.assertEqual(store.puts,2)
        self.assertIn("MFX_P192_D1_20261118_OWNER_CUTOFF_SHA_READBACK_PASS",log)
        safe=json.loads(log.splitlines()[-1])
        self.assertEqual(safe["owner_d1_cutoff_local_date"],"2026-11-18")
        self.assertFalse(safe["pre_cutoff_d1_admitted_into_new_epoch"])
        self.assertEqual(safe["d1"]["total_bars"],1)
        self.assertEqual(safe["d1"]["last_native_open_label"],"2026-11-18")
        self.assertEqual(safe["old_d1_drive_writes"],0)
        self.assertFalse(safe["approved_numeric_signals"])
        self.assertEqual(safe["broker_orders"],0)
        self.assertNotIn("1.1041",log)
        st=audit_fresh_epoch(store,origin_v1_sha=original_sha())
        self.assertEqual(st.last_manifest["total_closed_bars"],1)

    def test_03_when_provider_does_not_include_18_nov_do_not_seed_19(self):
        err,log,calls,store=self.run_job(missing_nov18=True)
        self.assertEqual(err,"P192_FRESH_PROVIDER_MISSING_20261118")
        self.assertEqual(store.puts,0)
        self.assertEqual([tf for k,tf in calls if k=="vendor"],["1day"])

    def test_04_old_and_new_D1_owner_flags_conflict_before_any_io(self):
        err,log,calls,store=self.run_job(old_owner="true")
        self.assertEqual(err,"P192_CONFLICTING_D1_EPOCH_SELECTION")
        self.assertEqual(calls,[])
        self.assertEqual(store.puts,0)

    def test_05_scheduler_rejects_P192_restatement_no_drive_write(self):
        # Drive already holds closed 18Nov; vendor now returns a revision
        # to that same stored 18Nov plus a future 19Nov. It MUST reject.
        err,log,calls,store=self.run_job(
            clock=datetime(2026,11,19,14,0,tzinfo=timezone.utc),
            revision=True)
        self.assertEqual(err,"P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertEqual(store.puts,2)
        self.assertNotIn("MFX_P192_D1_20261118_OWNER_CUTOFF_SHA_READBACK_PASS",log)
