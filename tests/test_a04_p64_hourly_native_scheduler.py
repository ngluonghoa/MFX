"""A04/P0.64: owner-approved unattended hourly H4+D1 native Drive writer.

Hermetic no-network checks of hosted schedule, existing owner gates, common
cross-workflow lock and TRUE automatic-vs-manual receipts/zero-price skips.
No live Twelve Data, Google Drive or broker calls in the test suite.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch
import json
import os

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from tools.mfx_native_htf_drive_seal import NativeArchiveState, NativeCommitReceipt
from tools.run_mfx_native_htf_incremental_commit import main

UTC=timezone.utc
NOW_NO_DUE=datetime(2026,11,11,5,15,tzinfo=UTC)
NOW_H4_DUE=datetime(2026,11,11,9,15,tzinfo=UTC)
NOW_BOTH_DUE=datetime(2026,11,11,13,15,tzinfo=UTC)
H4_00="2026-11-11 00:00:00"
H4_04="2026-11-11 04:00:00"
H4_08="2026-11-11 08:00:00"
D1_10="2026-11-10"
D1_11="2026-11-11"
MODULE="tools.run_mfx_native_htf_incremental_commit"


def batch(tf: str, labels: tuple[str,...]) -> NativeFXBatch:
    axis="UTC_INTRADAY_OPEN" if tf=="4h" else "EXCHANGE_LOCAL_SESSION_DATE"
    return NativeFXBatch(
        symbol="EUR/USD",interval=tf,time_reference=axis,
        exchange_timezone="Australia/Sydney",incomplete_excluded=0,
        closed_bars=tuple(NativeFXBar(
            symbol="EUR/USD",interval=tf,time_reference=axis,
            native_open_label=label,exchange_timezone="Australia/Sydney",
            exchange_timezone_origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT",
            open="1.1000",high="1.1040",low="1.0990",close="1.1030",
        ) for label in labels),
    )


def state(tf: str, label: str) -> NativeArchiveState:
    p=plan_native_sealed(batch(tf,(label,)),previous=None)
    assert p is not None
    return NativeArchiveState(p.manifest,p.manifest_name,1,1,())


def payload(tf: str, labels: tuple[str,...]) -> dict[str,object]:
    return {"meta":{"symbol":"EUR/USD","interval":tf,"type":"Forex"},
            "values":[{"datetime":label,"open":"1.1000","high":"1.1040",
                       "low":"1.0990","close":"1.1030"} for label in labels]}


def receipt(tf: str, last: str, *, stale: bool=False) -> NativeCommitReceipt:
    return NativeCommitReceipt(
        status=("NO_NEW_CLOSED_NATIVE_BAR" if stale else "NATIVE_BATCH_COMMITTED"),
        symbol="EUR/USD",interval=tf,last_native_open_label=last,
        newly_closed_native_bars=0 if stale else 1,
        total_closed_native_bars=1 if stale else 2,
        manifest_sha256="a"*64,
        drive_objects_created_max=0 if stale else 2,
    )


class HourlyP064Tests(TestCase):
    def test_01_schedule_at_25_utc_and_manual_still_available(self) -> None:
        y=Path(".github/workflows/mfx-native-htf-incremental-commit.yml").read_text()
        self.assertEqual(y.count('cron: "25 * * * *"'),1)
        self.assertIn("workflow_dispatch:",y)
        self.assertIn("schedule:",y)
        self.assertIn("timeout-minutes: 12",y)

    def test_02_all_other_hourly_jobs_staggered_and_shared_lock(self) -> None:
        schedules={
            ".github/workflows/twelve-data-cache.yml":'cron: "10 * * * *"',
            ".github/workflows/mfx-hourly-cache-audit.yml":'cron: "35 * * * *"',
            ".github/workflows/mfx-native-htf-cache-audit.yml":'cron: "45 * * * *"',
        }
        schedules[
            ".github/workflows/mfx-native-htf-incremental-commit.yml"
        ]='cron: "25 * * * *"'
        for file,cron in schedules.items():
            with self.subTest(file=file):
                y=Path(file).read_text()
                self.assertIn(cron,y)
                self.assertIn("group: mfx-twelvedata-private-cache",y)
                self.assertIn("cancel-in-progress: false",y)

    def test_03_exact_four_owner_gates_no_broker_and_readonly_repo(self) -> None:
        y=Path(".github/workflows/mfx-native-htf-incremental-commit.yml").read_text()
        for variable in (
            "MFX_REAL_CACHE_ENABLED",
            "MFX_V2_BATCH_CACHE_ACCEPTED",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED",
            "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED",
        ):
            self.assertIn("vars."+variable+" == 'true'",y)
        self.assertIn("contents: read",y)
        self.assertIn("run_mfx_native_htf_incremental_commit",y)
        self.assertNotIn("broker",y.lower().replace("no trading",""))
        self.assertNotIn("order-submit",y)
        self.assertNotIn("cancel-in-progress: true",y)

    def _run(
        self, *, now: datetime, trigger: str,
        h4: str=H4_00, d1: str=D1_10,
        responses: dict[str,object] | None=None,
        result_receipts: dict[str,NativeCommitReceipt] | None=None,
        quota: tuple[int,int]=(100,400),
    ) -> tuple[dict[str,object],str,Mock,Mock,Mock,Mock]:
        archive={"4h":state("4h",h4),"1day":state("1day",d1)}
        source=responses if responses is not None else {
            "4h":payload("4h",(h4,H4_04 if h4==H4_00 else H4_08)),
            "1day":payload("1day",(d1,D1_11)),
        }
        receipts=result_receipts if result_receipts is not None else {
            "4h":receipt("4h",H4_04 if h4==H4_00 else H4_08),
            "1day":receipt("1day",D1_11),
        }
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,{
                "GITHUB_EVENT_NAME":trigger,
                "MFX_REAL_CACHE_ENABLED":"true",
                "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
                "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
                "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED":"true",
            }))
            stack.enter_context(patch(
                f"{MODULE}._settings",return_value=("fake_key",{},400)))
            stack.enter_context(patch(
                f"{MODULE}._session",return_value="fake_session"))
            stack.enter_context(patch(
                f"{MODULE}.PrivateNativeDriveStore",
                side_effect=lambda session,*,symbol,interval: "store_"+interval))
            audit=stack.enter_context(patch(
                f"{MODULE}.audit_native_archive",
                side_effect=lambda store,*,symbol,interval: archive[interval]))
            usage=stack.enter_context(patch(
                f"{MODULE}._usage",return_value=quota))
            vendor=stack.enter_context(patch(
                f"{MODULE}._read_payload",
                side_effect=lambda url,params: source[params["interval"]]))
            commit=stack.enter_context(patch(
                f"{MODULE}.commit_native_batch",
                side_effect=lambda store,b: receipts[b.interval]))
            clock=stack.enter_context(patch(f"{MODULE}.datetime"))
            clock.now.return_value=now
            out=StringIO()
            with redirect_stdout(out):
                main()
            lines=out.getvalue().splitlines()
            return json.loads(lines[-1]),out.getvalue(),usage,vendor,commit,audit

    def test_04_hourly_no_new_slots_zero_vendor_zero_drive(self) -> None:
        d,log,u,v,c,a=self._run(now=NOW_NO_DUE,trigger="schedule")
        self.assertEqual(d["status"],"NO_NATIVE_CLOSED_SLOTS_DUE")
        self.assertTrue(d["automatic_native_schedule_activated"])
        self.assertEqual(d["execution_mode"],"hourly_schedule")
        self.assertEqual(d["provider_price_requests"],0)
        self.assertEqual(d["provider_usage_requests"],0)
        self.assertEqual(d["drive_writes"],0)
        u.assert_not_called()
        v.assert_not_called()
        c.assert_not_called()
        self.assertEqual(a.call_count,2)

    def test_05_manual_no_new_slots_remains_explicitly_manual(self) -> None:
        d,_,u,v,c,_=self._run(now=NOW_NO_DUE,trigger="workflow_dispatch")
        self.assertFalse(d["automatic_native_schedule_activated"])
        self.assertEqual(d["execution_mode"],"manual")
        u.assert_not_called()
        v.assert_not_called()
        c.assert_not_called()

    def test_06_hourly_h4_due_only_one_price_request(self) -> None:
        d,log,u,v,c,_=self._run(now=NOW_H4_DUE,trigger="schedule")
        self.assertTrue(d["automatic_native_schedule_activated"])
        self.assertIn("MFX_A04_P64_HOURLY_NATIVE_INCREMENTAL_SHA_READBACK_PASS",log)
        self.assertEqual(d["intervals_with_new_native_bars"],["4h"])
        self.assertEqual(d["intervals_skipped_no_new_closed_slot"],["1day"])
        self.assertEqual(d["provider_price_requests"],1)
        self.assertEqual(d["total_newly_closed_native_bars"],1)
        self.assertEqual(u.call_count,1)
        self.assertEqual(v.call_count,1)
        self.assertEqual(c.call_count,1)

    def test_07_manual_h4_due_preserves_old_acceptance_marker(self) -> None:
        d,log,u,v,c,_=self._run(now=NOW_H4_DUE,trigger="workflow_dispatch")
        self.assertIn("MFX_A04_P59_NATIVE_INCREMENTAL_MANUAL_SHA_READBACK_PASS",log)
        self.assertNotIn("MFX_A04_P64_HOURLY_NATIVE_INCREMENTAL_SHA_READBACK_PASS",log)
        self.assertEqual(d["execution_mode"],"manual")
        self.assertFalse(d["automatic_native_schedule_activated"])
        self.assertEqual(v.call_count,1)
        self.assertEqual(c.call_count,1)

    def test_08_hourly_both_due_two_prices_no_trades(self) -> None:
        source={
            "4h":payload("4h",(H4_04,H4_08)),
            "1day":payload("1day",(D1_10,D1_11)),
        }
        d,log,u,v,c,_=self._run(
            now=NOW_BOTH_DUE,trigger="schedule",
            h4=H4_04,responses=source)
        self.assertEqual(d["provider_price_requests"],2)
        self.assertEqual(d["provider_usage_requests"],2)
        self.assertEqual(d["total_newly_closed_native_bars"],2)
        self.assertEqual(d["intervals_with_new_native_bars"],["4h","1day"])
        self.assertEqual(d["broker_orders"],0)
        self.assertFalse(d["source_numeric_signals_approved"])
        self.assertTrue(d["automatic_native_schedule_activated"])
        self.assertEqual(v.call_count,2)
        self.assertEqual(u.call_count,2)
        self.assertEqual(c.call_count,2)

    def test_09_hourly_d1_only_exact_one_price_request(self) -> None:
        d,log,u,v,c,_=self._run(
            now=NOW_BOTH_DUE,trigger="schedule",
            h4=H4_08,responses={
                "1day":payload("1day",(D1_10,D1_11)),
            })
        self.assertEqual(d["intervals_with_new_native_bars"],["1day"])
        self.assertEqual(d["intervals_skipped_no_new_closed_slot"],["4h"])
        self.assertEqual(d["provider_price_requests"],1)
        self.assertEqual(d["total_newly_closed_native_bars"],1)
        self.assertEqual(u.call_count,1)
        self.assertEqual(v.call_count,1)
        self.assertEqual(c.call_count,1)

    def test_10_hourly_quota_denied_no_price_or_append(self) -> None:
        d,log,u,v,c,_=self._run(
            now=NOW_H4_DUE,trigger="schedule",quota=(398,400))
        self.assertEqual(d["status"],"NOT_EXECUTED_INSUFFICIENT_QUOTA_HEADROOM")
        self.assertTrue(d["automatic_native_schedule_activated"])
        self.assertEqual(d["execution_mode"],"hourly_schedule")
        self.assertIn("MFX_A04_P59_NATIVE_QUOTA_NO_PRICE_REQUESTS",log)
        self.assertEqual(u.call_count,1)
        v.assert_not_called()
        c.assert_not_called()

    def test_11_schedule_gates_off_no_credentials_or_source(self) -> None:
        with patch.dict(os.environ,{
            "GITHUB_EVENT_NAME":"schedule",
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
            "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED":"false",
        }),patch(f"{MODULE}._settings") as settings,patch(
            f"{MODULE}._usage") as usage,patch(
            f"{MODULE}.PrivateNativeDriveStore") as store:
            out=StringIO()
            with redirect_stdout(out):
                main()
        settings.assert_not_called()
        usage.assert_not_called()
        store.assert_not_called()
        self.assertIn("INCREMENTAL_DISABLED_EXPLICIT_FOUR_GATE",out.getvalue())

    def test_12_hourly_provider_stale_no_false_new_candle_claim(self) -> None:
        d,log,_,v,c,_=self._run(
            now=NOW_H4_DUE,trigger="schedule",
            responses={"4h":payload("4h",(H4_00,))},
            result_receipts={
                "4h":receipt("4h",H4_00,stale=True),
            })
        self.assertTrue(d["automatic_native_schedule_activated"])
        self.assertEqual(d["status"],"NATIVE_INCREMENTAL_PROVIDER_STALE_NO_NEW_BAR")
        self.assertEqual(d["total_newly_closed_native_bars"],0)
        self.assertEqual(d["intervals_provider_stale_no_new_bar"],["4h"])
        self.assertEqual(v.call_count,1)
        self.assertEqual(c.call_count,1)

    def test_13_readonly_audits_and_legacy_native_writer_untouched(self) -> None:
        for p,cron in (
            (".github/workflows/mfx-hourly-cache-audit.yml","35"),
            (".github/workflows/mfx-native-htf-cache-audit.yml","45"),
        ):
            with self.subTest(path=p):
                y=Path(p).read_text()
                self.assertIn('cron: "'+cron+' * * * *"',y)
                self.assertIn("NO vendor",y)
        legacy=Path(".github/workflows/mfx-native-htf-drive-commit.yml").read_text()
        self.assertIn("workflow_dispatch:",legacy)
        self.assertNotIn("schedule:",legacy)


if __name__=="__main__":
    import unittest
    unittest.main()
