"""A04/P0.61: every source-native H4 candle MUST align with UTC 4h.

Hermetic full due-branch integration QA for the staged four-gated native
writer: one/both due, quota block, second-source failure, SHA revision,
source-stale valid receipt, changing parent and incomplete/orphan preflight.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from unittest import TestCase
from unittest.mock import Mock, patch
import os

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch, parse_native_forex
from mfx_cache.native_htf_archive import plan_native_sealed
from tools.mfx_native_htf_drive_seal import NativeArchiveState, NativeCommitReceipt
from tools.run_mfx_native_htf_incremental_commit import main

UTC=timezone.utc
NOW=datetime(2026,11,12,9,15,tzinfo=UTC)
H4=("2026-11-10 20:00:00","2026-11-11 00:00:00")
D1=("2026-11-09","2026-11-10")
H4_NEW="2026-11-11 04:00:00"
D1_NEW="2026-11-11"
MODULE="tools.run_mfx_native_htf_incremental_commit"


def native_batch(interval: str, labels: tuple[str,...]) -> NativeFXBatch:
    axis="UTC_INTRADAY_OPEN" if interval=="4h" else "EXCHANGE_LOCAL_SESSION_DATE"
    return NativeFXBatch(
        symbol="EUR/USD",interval=interval,time_reference=axis,
        exchange_timezone="Australia/Sydney",incomplete_excluded=0,
        closed_bars=tuple(NativeFXBar(
            symbol="EUR/USD",interval=interval,time_reference=axis,
            native_open_label=label,exchange_timezone="Australia/Sydney",
            exchange_timezone_origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT",
            open="1.1000",high="1.1040",low="1.0990",close="1.1030",
        ) for label in labels),
    )


def root(interval: str) -> NativeArchiveState:
    old=native_batch(interval,H4 if interval=="4h" else D1)
    plan=plan_native_sealed(old,previous=None)
    assert plan is not None
    return NativeArchiveState(plan.manifest,plan.manifest_name,1,1,())


def envelope(interval: str, labels: tuple[str,...]) -> dict[str,object]:
    return {"meta":{"symbol":"EUR/USD","interval":interval,"type":"Forex"},
            "values":[{"datetime":label,"open":"1.1000","high":"1.1040",
                       "low":"1.0990","close":"1.1030"} for label in labels]}


def receipt(interval: str, *, newly: int, stale: bool=False) -> NativeCommitReceipt:
    return NativeCommitReceipt(
        status="NO_NEW_CLOSED_NATIVE_BAR" if stale else "NATIVE_BATCH_COMMITTED",
        symbol="EUR/USD",interval=interval,
        last_native_open_label=H4_NEW if interval=="4h" else D1_NEW,
        newly_closed_native_bars=newly,
        total_closed_native_bars=2+newly,
        manifest_sha256="a"*64,drive_objects_created_max=0 if stale else 2,
    )


class NativeP061QA(TestCase):
    def test_01_source_h4_01_utc_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"P061_H4_UTC_4H_GRID_REQUIRED"):
            parse_native_forex(
                envelope("4h",("2026-11-11 01:00:00",)),
                symbol="EUR/USD",interval="4h",
                now_utc=NOW,requested_timezone="UTC")

    def test_02_source_h4_23_utc_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"P061_H4_UTC_4H_GRID_REQUIRED"):
            parse_native_forex(
                envelope("4h",("2026-11-10 23:00:00",)),
                symbol="EUR/USD",interval="4h",
                now_utc=NOW,requested_timezone="UTC")

    def test_03_source_valid_h4_grid_passes(self) -> None:
        got=parse_native_forex(
            envelope("4h",H4+(H4_NEW,)),
            symbol="EUR/USD",interval="4h",
            now_utc=NOW,requested_timezone="UTC")
        self.assertEqual(len(got.closed_bars),3)

    def test_04_off_grid_archived_root_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"P061_H4_UTC_4H_GRID_REQUIRED"):
            plan_native_sealed(
                native_batch("4h",("2026-11-11 01:00:00",)),
                previous=None)

    def test_05_offgrid_in_middle_of_archived_batch_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"P061_H4_UTC_4H_GRID_REQUIRED"):
            plan_native_sealed(
                native_batch("4h",(
                    "2026-11-10 20:00:00","2026-11-11 01:00:00",
                    "2026-11-11 04:00:00")),
                previous=None)

    def test_06_native_d1_source_dates_not_forced_to_utc_grid(self) -> None:
        got=parse_native_forex(
            envelope("1day",D1+(D1_NEW,)),
            symbol="EUR/USD",interval="1day",
            now_utc=NOW,requested_timezone=None)
        self.assertEqual(len(got.closed_bars),3)

    def _context(
        self, *, now: datetime=NOW,
        archives: list[NativeArchiveState] | None=None,
        usage: list[tuple[int,int]] | None=None,
        vendor: list[object] | None=None,
        commits: list[NativeCommitReceipt] | None=None,
    ) -> tuple[ExitStack,Mock,Mock,Mock,Mock,Mock]:
        stack=ExitStack()
        stack.enter_context(patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
            "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED":"true",
        }))
        stack.enter_context(patch(f"{MODULE}._settings",
            return_value=("fake_key",{"type":"fake_oauth"},400)))
        stack.enter_context(patch(f"{MODULE}._session",return_value="fake_session"))
        stack.enter_context(patch(f"{MODULE}.PrivateNativeDriveStore",
            side_effect=lambda session,*,symbol,interval: "store_"+interval))
        states=archives if archives is not None else [
            root("4h"),root("1day"),root("4h"),root("1day")]
        au=stack.enter_context(patch(
            f"{MODULE}.audit_native_archive",side_effect=states))
        us=stack.enter_context(patch(
            f"{MODULE}._usage",side_effect=usage if usage is not None
            else [(100,400),(102,400)]))
        vd=stack.enter_context(patch(
            f"{MODULE}._read_payload",side_effect=vendor if vendor is not None
            else [envelope("4h",H4+(H4_NEW,)),
                  envelope("1day",D1+(D1_NEW,))]))
        co=stack.enter_context(patch(
            f"{MODULE}.commit_native_batch",side_effect=commits if commits is not None
            else [receipt("4h",newly=1),receipt("1day",newly=1)]))
        clock=stack.enter_context(patch(f"{MODULE}.datetime"))
        clock.now.return_value=now
        return stack,au,us,vd,co,clock

    def test_07_two_due_sources_validated_before_first_write(self) -> None:
        events: list[str]=[]
        stack,_,us,vd,co,_=self._context()
        # Verify the two separate source envelopes are validated before
        # commit_native_batch is even first invoked.
        def get(url: str, params: dict[str,str]) -> dict[str,object]:
            interval=params["interval"]
            events.append("vendor_"+interval)
            return envelope(
                interval,H4+(H4_NEW,) if interval=="4h" else D1+(D1_NEW,))
        def commit(store: str, batch: NativeFXBatch) -> NativeCommitReceipt:
            events.append("commit_"+batch.interval)
            return receipt(batch.interval,newly=1)
        vd.side_effect=get
        co.side_effect=commit
        with stack:
            out=StringIO()
            with redirect_stdout(out):
                main()
        self.assertEqual(events,[
            "vendor_4h","vendor_1day","commit_4h","commit_1day"])
        self.assertEqual(vd.call_count,2)
        self.assertEqual(us.call_count,2)
        self.assertEqual(co.call_count,2)
        self.assertIn("NATIVE_INCREMENTAL_NEW_BARS_COMMITTED",out.getvalue())
        self.assertIn('"total_newly_closed_native_bars": 2',out.getvalue())
        self.assertIn('"requested_outputsize_by_interval": {"1day": 24, "4h": 24}',out.getvalue())
        self.assertNotIn("1.1030",out.getvalue())

    def test_08_h4_only_due_d1_skipped_without_price(self) -> None:
        only_one=[root("4h"),root("1day"),root("4h")]
        stack,_,us,vd,co,_=self._context(
            now=datetime(2026,11,11,9,15,tzinfo=UTC),
            archives=only_one,usage=[(100,400)],
            vendor=[envelope("4h",H4+(H4_NEW,))],
            commits=[receipt("4h",newly=1)])
        with stack:
            out=StringIO()
            with redirect_stdout(out):
                main()
        self.assertEqual(vd.call_count,1)
        self.assertEqual(us.call_count,1)
        self.assertEqual(co.call_count,1)
        self.assertIn('"intervals_skipped_no_new_closed_slot": ["1day"]',out.getvalue())

    def test_09_source_stale_after_due_no_false_commit(self) -> None:
        only_one=[root("4h"),root("1day"),root("4h")]
        stack,_,_,vd,co,_=self._context(
            now=datetime(2026,11,11,9,15,tzinfo=UTC),
            archives=only_one,usage=[(100,400)],
            vendor=[envelope("4h",H4)],
            commits=[receipt("4h",newly=0,stale=True)])
        with stack:
            out=StringIO()
            with redirect_stdout(out):
                main()
        self.assertEqual(vd.call_count,1)
        self.assertEqual(co.call_count,1)
        self.assertIn("NATIVE_INCREMENTAL_PROVIDER_STALE_NO_NEW_BAR",out.getvalue())
        self.assertIn('"total_newly_closed_native_bars": 0',out.getvalue())

    def test_10_second_vendor_invalid_zero_commits(self) -> None:
        stack,_,_,vd,co,_=self._context(vendor=[
            envelope("4h",H4+(H4_NEW,)),
            {"meta":{"symbol":"EUR/USD","interval":"1day","type":"Forex"},
             "values":[{"datetime":"2026-11-11","open":"0","high":"0",
                        "low":"0","close":"0"}]}])
        with stack:
            with self.assertRaises(ValueError):
                main()
        self.assertEqual(vd.call_count,2)
        co.assert_not_called()

    def test_11_first_vendor_SHA_revision_zero_commits(self) -> None:
        revised=envelope("4h",H4+(H4_NEW,))
        revised["values"][0]["close"]="1.1020"
        stack,_,_,vd,co,_=self._context(vendor=[
            revised,envelope("1day",D1+(D1_NEW,))])
        with stack:
            with self.assertRaisesRegex(ValueError,"REVISION_QUARANTINE"):
                main()
        self.assertEqual(vd.call_count,1)
        co.assert_not_called()

    def test_12_quota_denied_prevents_all_price_calls(self) -> None:
        stack,_,us,vd,co,_=self._context(usage=[(398,400)])
        with stack:
            out=StringIO()
            with redirect_stdout(out):
                main()
        self.assertEqual(us.call_count,1)
        vd.assert_not_called()
        co.assert_not_called()
        self.assertIn("QUOTA_NO_PRICE_REQUESTS",out.getvalue())

    def test_13_quota_second_recheck_blocks_both_writes(self) -> None:
        stack,_,us,vd,co,_=self._context(usage=[(100,400),(399,400)])
        with stack:
            with self.assertRaisesRegex(ValueError,"QUOTA_RECHECK"):
                main()
        self.assertEqual(vd.call_count,1)
        co.assert_not_called()

    def test_14_changed_parent_after_vendor_blocks_writes(self) -> None:
        oldh,oldd=root("4h"),root("1day")
        changed=NativeArchiveState(oldh.last_manifest,oldh.latest_manifest_name,2,2,())
        stack,au,_,vd,co,_=self._context(
            archives=[oldh,oldd,changed,oldd])
        with stack:
            with self.assertRaisesRegex(ValueError,"ARCHIVE_CHANGED_DURING_FETCH"):
                main()
        self.assertEqual(vd.call_count,2)
        self.assertEqual(au.call_count,3)
        co.assert_not_called()

    def test_15_existing_orphan_blocks_before_vendor(self) -> None:
        h=root("4h")
        orphan=NativeArchiveState(
            h.last_manifest,h.latest_manifest_name,1,2,("one_uncommitted_chunk",))
        stack,au,us,vd,co,_=self._context(
            archives=[orphan,root("1day")])
        with stack:
            with self.assertRaisesRegex(ValueError,"ORPHAN_REQUIRES_SEPARATE"):
                main()
        self.assertEqual(au.call_count,1)
        us.assert_not_called()
        vd.assert_not_called()
        co.assert_not_called()

    def test_16_future_native_H4_source_filtered_before_commit(self) -> None:
        # Future/open 08:00 bar must NOT enter a 09:15 UTC H4 archive:
        # it is not closed until 12:00:15 UTC. Only 04:00 can append.
        got=parse_native_forex(
            envelope("4h",H4+(H4_NEW,"2026-11-11 08:00:00")),
            symbol="EUR/USD",interval="4h",
            now_utc=datetime(2026,11,11,9,15,tzinfo=UTC),
            requested_timezone="UTC")
        self.assertEqual(got.incomplete_excluded,1)
        self.assertEqual(got.closed_bars[-1].native_open_label,H4_NEW)


if __name__=="__main__":
    import unittest
    unittest.main()
