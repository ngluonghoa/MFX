"""P0.168: H4 can append independently ONLY on exact documented D1 HOLD.

The actual existing hourly workflow, quotas and two-object SHA writer are
reused. All tests are scripted offline; no real Twelve Data or Drive calls.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
import os
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from tools.mfx_native_htf_drive_seal import NativeArchiveState, NativeCommitReceipt
from tools.run_mfx_native_htf_incremental_commit import (
    _confirmed_known_d1_hold, main,
)

MODULE="tools.run_mfx_native_htf_incremental_commit"
NOW=datetime(2026,11,15,6,14,tzinfo=timezone.utc)
H4_LABELS=("2026-11-12 08:00:00",)
D1_LABELS=tuple(
    (datetime(2026,10,27,tzinfo=timezone.utc)+timedelta(days=i)).date().isoformat()
    for i in range(16)
)
assert D1_LABELS[-1] == "2026-11-11"


def batch(tf,labels,*,amend=None):
    axis="UTC_INTRADAY_OPEN" if tf=="4h" else "EXCHANGE_LOCAL_SESSION_DATE"
    rows=[]
    for label in labels:
        rows.append(NativeFXBar(
            symbol="EUR/USD",interval=tf,
            exchange_timezone="Australia/Sydney",time_reference=axis,
            native_open_label=label,
            exchange_timezone_origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT",
            open="1.1000",high=(
                "1.1041" if label==amend else "1.1040"),
            low="1.0990",close="1.1030",
        ))
    return NativeFXBatch(
        symbol="EUR/USD",interval=tf,
        exchange_timezone="Australia/Sydney",time_reference=axis,
        closed_bars=tuple(rows),incomplete_excluded=0,
    )


def state(tf,labels):
    p=plan_native_sealed(batch(tf,labels),previous=None)
    assert p is not None
    return NativeArchiveState(
        last_manifest=p.manifest,latest_manifest_name=p.manifest_name,
        manifest_count=1,chunk_count=1,uncommitted_chunk_names=(),
    )


def envelope(tf,labels,*,amend=None):
    return {
        "meta":{"type":"Forex","interval":tf,"symbol":"EUR/USD"},
        "values":[{
            "datetime":v,"open":"1.1000",
            "high":"1.1041" if v==amend else "1.1040",
            "low":"1.0990","close":"1.1030",
        } for v in labels],
    }


def diagnostic():
    return {
        "interval":"1day",
        "first_changed_label":"2026-11-11",
        "last_changed_label":"2026-11-11",
        "quarantine_reason":"P059_SOURCE_NATIVE_REVISION_QUARANTINE",
        "numeric_ohlc_changed_count":1,
        "overlap_sha_changed_count":1,
        "overlap_sha_unchanged_count":15,
        "overlap_labels_missing_count":0,
        "previous_sha_index_count":16,
        "full_sha_audited_old_raw_overlap_compared":True,
        "stored_vs_refetched_numeric_ohlc_difference_observed":True,
        "source_vendor_revision_cause_independently_attributed":False,
        "source_mutation_or_quarantine_override_authorized":False,
        "drive_writes":0,"additional_vendor_calls":0,
        "additional_drive_gets":0,"broker_orders":0,
    }


class FakeStore:
    def __init__(self,_session,*,symbol,interval):
        self.interval=interval


class FakeReadThrough:
    def __init__(self,store):
        self.store=store

    def verified_recent_rows(self,_state,*,symbol,interval):
        return batch(interval,D1_LABELS).closed_bars if interval=="1day" else (
            batch("4h",H4_LABELS).closed_bars
        )


class P168IndependentH4OnKnownD1Hold(TestCase):
    def test_01_exact_proof_accepts_only_scoped_h4_independence(self):
        self.assertTrue(_confirmed_known_d1_hold(diagnostic()))

    def test_02_missing_or_forged_evidence_fails(self):
        for key,value in (
            ("interval","4h"),("first_changed_label","2026-11-10"),
            ("last_changed_label","2026-11-12"),
            ("quarantine_reason","DIFFERENT_HOLD"),
            ("numeric_ohlc_changed_count",0),
            ("overlap_sha_changed_count",2),
            ("overlap_sha_unchanged_count",14),
            ("overlap_labels_missing_count",1),
            ("previous_sha_index_count",15),
            ("full_sha_audited_old_raw_overlap_compared",False),
            ("stored_vs_refetched_numeric_ohlc_difference_observed",False),
            ("source_vendor_revision_cause_independently_attributed",True),
            ("source_mutation_or_quarantine_override_authorized",True),
            ("drive_writes",1),("additional_vendor_calls",1),
            ("additional_drive_gets",1),("broker_orders",1),
        ):
            with self.subTest(key=key):
                sample=diagnostic()
                sample[key]=value
                self.assertFalse(_confirmed_known_d1_hold(sample))
        self.assertFalse(_confirmed_known_d1_hold(None))
        self.assertFalse(_confirmed_known_d1_hold([]))

    def _drive(self,*,d1_diagnostic=None,h4_invalid=False,
               changed_parent=False,quota=(100,400)):
        states={
            "4h":state("4h",H4_LABELS),
            "1day":state("1day",D1_LABELS),
        }
        calls=[]
        def audit(store,*,symbol,interval):
            calls.append(("audit",interval))
            if changed_parent and len([x for x in calls
                                      if x==("audit","1day")])==2:
                return state("1day",D1_LABELS[:-1])
            return states[interval]
        responses={
            "4h":envelope("4h",H4_LABELS+("2026-11-12 12:00:00",),
                          amend=H4_LABELS[0] if h4_invalid else None),
            "1day":envelope("1day",D1_LABELS+("2026-11-12",),
                            amend="2026-11-11"),
        }
        def emit(url,params):
            calls.append(("vendor",params["interval"]))
            return responses[params["interval"]]
        def commit(store,b):
            calls.append(("commit",b.interval))
            return NativeCommitReceipt(
                status="NATIVE_BATCH_COMMITTED",symbol="EUR/USD",
                interval=b.interval,last_native_open_label=b.closed_bars[-1].native_open_label,
                newly_closed_native_bars=1,total_closed_native_bars=10,
                manifest_sha256="a"*64,drive_objects_created_max=2,
            )
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,{
                "GITHUB_EVENT_NAME":"schedule",
                "MFX_REAL_CACHE_ENABLED":"true",
                "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
                "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
                "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED":"true",
            }))
            stack.enter_context(patch(f"{MODULE}._settings",return_value=(
                "test-key",{"type":"test"},400)))
            stack.enter_context(patch(f"{MODULE}._session",return_value="session"))
            stack.enter_context(patch(f"{MODULE}.PrivateNativeDriveStore",FakeStore))
            stack.enter_context(patch(f"{MODULE}.NativeAuditReadThroughWitness",
                                      FakeReadThrough))
            stack.enter_context(patch(f"{MODULE}.audit_native_archive",
                                      side_effect=audit))
            stack.enter_context(patch(f"{MODULE}._usage",return_value=quota))
            stack.enter_context(patch(f"{MODULE}._read_payload",side_effect=emit))
            stack.enter_context(patch(f"{MODULE}.commit_native_batch",
                                      side_effect=commit))
            stack.enter_context(patch(f"{MODULE}.classify_stored_vs_refetched_native",
                return_value=diagnostic() if d1_diagnostic is None
                else d1_diagnostic))
            clock=stack.enter_context(patch(f"{MODULE}.datetime"))
            clock.now.return_value=NOW
            output=StringIO()
            with redirect_stdout(output):
                try:
                    main()
                except ValueError as exc:
                    return str(exc),calls,output.getvalue()
        return "NO_EXCEPTION",calls,output.getvalue()

    def test_03_exact_d1_numeric_hold_h4_appends_and_job_stays_red(self):
        err,calls,log=self._drive()
        self.assertIn("P059_SOURCE_NATIVE_REVISION_QUARANTINE",err)
        self.assertIn(("commit","4h"),calls)
        self.assertNotIn(("commit","1day"),calls)
        self.assertIn("MFX_P168_H4_ISOLATED_D1_STILL_QUARANTINED_NONZERO",log)
        self.assertNotIn("SHA_READBACK_PASS",log)
        record=json.loads(log.splitlines()[-1])
        self.assertEqual(record["h4_newly_closed_bars"],1)
        self.assertEqual(record["d1_drive_writes"],0)
        self.assertTrue(record["h4_append_does_not_clear_d1_hold"])
        self.assertFalse(record["source_numeric_signals_approved"])

    def test_04_forged_d1_diagnostic_refuses_any_append(self):
        fake=diagnostic()
        fake["numeric_ohlc_changed_count"]=0
        err,calls,log=self._drive(d1_diagnostic=fake)
        self.assertEqual(err,"P059_SOURCE_NATIVE_REVISION_QUARANTINE")
        self.assertNotIn(("commit","4h"),calls)
        self.assertNotIn(("commit","1day"),calls)
        self.assertNotIn("MFX_P168_H4_ISOLATED",log)

    def test_05_h4_overlap_changes_refuses_both_commits(self):
        err,calls,log=self._drive(h4_invalid=True)
        self.assertEqual(err,"P059_SOURCE_NATIVE_REVISION_QUARANTINE")
        self.assertNotIn(("commit","4h"),calls)
        self.assertNotIn(("commit","1day"),calls)

    def test_06_d1_parent_changes_during_fetch_refuses_h4(self):
        err,calls,log=self._drive(changed_parent=True)
        self.assertIn("P059_NATIVE_ARCHIVE_CHANGED_DURING_FETCH",err)
        self.assertNotIn(("commit","4h"),calls)
        self.assertNotIn(("commit","1day"),calls)

    def test_07_quota_insufficient_prevents_both_vendor_and_drive(self):
        err,calls,log=self._drive(quota=(399,400))
        self.assertEqual(err,"NO_EXCEPTION")
        self.assertNotIn(("vendor","4h"),calls)
        self.assertNotIn(("vendor","1day"),calls)
        self.assertNotIn(("commit","4h"),calls)
        self.assertNotIn(("commit","1day"),calls)
        self.assertIn("NOT_EXECUTED_INSUFFICIENT_QUOTA_HEADROOM",log)

    def test_08_no_price_or_credentials_in_h4_partial_receipt(self):
        err,calls,log=self._drive()
        self.assertIn("P059_SOURCE_NATIVE_REVISION_QUARANTINE",err)
        for private in ("1.1000","1.1041","test-key","EUR/USD"):
            self.assertNotIn(private,log)

    def test_09_expected_h4_then_d1_vendor_fetch_order(self):
        err,calls,log=self._drive()
        self.assertEqual([tf for kind,tf in calls if kind=="vendor"],
                         ["4h","1day"])
        self.assertEqual([tf for kind,tf in calls if kind=="commit"],["4h"])
        # D1 full SHA re-audit is required after detecting quarantine.
        self.assertEqual([tf for kind,tf in calls if kind=="audit"],
                         ["4h","1day","4h","1day"])
