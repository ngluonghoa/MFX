"""A04/P0.59 hermetic incremental H4/D1 selective-call and quarantine tests."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Any
import copy
import os
import unittest

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from mfx_cache.native_htf_incremental import (
    plan_native_fetch, validate_incremental_source,
)
from tools.mfx_native_htf_drive_seal import NativeArchiveState
from tools.run_mfx_native_htf_incremental_commit import main

UTC=timezone.utc
NOW=datetime(2026,11,11,5,15,tzinfo=UTC)
H4=("2026-11-10 20:00:00","2026-11-11 00:00:00")
D1=("2026-11-09","2026-11-10")


def batch(interval: str, labels: tuple[str,...]) -> NativeFXBatch:
    axis="UTC_INTRADAY_OPEN" if interval=="4h" else "EXCHANGE_LOCAL_SESSION_DATE"
    return NativeFXBatch(
        symbol="EUR/USD",interval=interval,
        exchange_timezone="Australia/Sydney",time_reference=axis,
        incomplete_excluded=0,closed_bars=tuple(
            NativeFXBar(
                symbol="EUR/USD",interval=interval,
                exchange_timezone="Australia/Sydney",time_reference=axis,
                native_open_label=label,open="1.1000",high="1.1040",
                low="1.0990",close="1.1030",
                exchange_timezone_origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT",
            ) for label in labels),
    )


def root(interval: str, labels: tuple[str,...]) -> dict[str,Any]:
    proposal=plan_native_sealed(batch(interval,labels),previous=None)
    assert proposal is not None
    return proposal.manifest


def vendor_envelope(interval: str, labels: tuple[str,...]) -> dict[str,Any]:
    return {"meta":{"type":"Forex","interval":interval,"symbol":"EUR/USD"},
            "values":[{"datetime":label,"open":"1.1000",
                       "high":"1.1040","low":"1.0990","close":"1.1030"}
                      for label in labels]}


class P059Tests(unittest.TestCase):
    def test_01_h4_no_new_closed_slot_no_vendor(self) -> None:
        p=plan_native_fetch(interval="4h",previous=root("4h",H4),now_utc=NOW)
        self.assertEqual(p.status,"NO_NEW_CLOSED_SLOT_NO_VENDOR_CALL")
        self.assertIsNone(p.request)
        self.assertEqual(p.provider_requests_planned,0)

    def test_02_d1_no_new_exchange_local_day_no_vendor(self) -> None:
        p=plan_native_fetch(interval="1day",previous=root("1day",D1),now_utc=NOW)
        self.assertIsNone(p.request)
        self.assertEqual(p.latest_expected_closed_label,"2026-11-10")

    def test_03_h4_one_due_uses_small_window_and_UTC(self) -> None:
        t=NOW+timedelta(hours=4)
        p=plan_native_fetch(interval="4h",previous=root("4h",H4),now_utc=t)
        self.assertEqual(p.status,"INCREMENTAL_FETCH_REQUIRED")
        self.assertEqual(p.calendar_slots_behind,1)
        self.assertEqual(p.request["outputsize"],"24")
        self.assertEqual(p.request["timezone"],"UTC")

    def test_04_d1_due_uses_local_date_no_UTC_override(self) -> None:
        t=NOW+timedelta(days=1)
        p=plan_native_fetch(interval="1day",previous=root("1day",D1),now_utc=t)
        self.assertEqual(p.calendar_slots_behind,1)
        self.assertEqual(p.request["outputsize"],"24")
        self.assertNotIn("timezone",p.request)

    def test_05_initial_bootstrap_is_bounded_120(self) -> None:
        for tf in ("4h","1day"):
            p=plan_native_fetch(interval=tf,previous=None,now_utc=NOW)
            self.assertEqual(p.status,"BOOTSTRAP_FULL_NATIVE_WINDOW")
            self.assertEqual(p.request["outputsize"],"120")

    def test_06_h4_long_outage_fails_before_vendor(self) -> None:
        with self.assertRaisesRegex(ValueError,"HISTORY_WINDOW_EXCEEDED"):
            plan_native_fetch(
                interval="4h",previous=root("4h",H4),
                now_utc=NOW+timedelta(days=60))

    def test_07_d1_long_outage_fails_before_vendor(self) -> None:
        with self.assertRaisesRegex(ValueError,"HISTORY_WINDOW_EXCEEDED"):
            plan_native_fetch(
                interval="1day",previous=root("1day",D1),
                now_utc=NOW+timedelta(days=130))

    def test_08_h4_future_cache_tail_fail_closed(self) -> None:
        m=root("4h",("2026-11-11 04:00:00",))
        with self.assertRaisesRegex(ValueError,"FUTURE_OR_UNCLOSED"):
            plan_native_fetch(interval="4h",previous=m,now_utc=NOW)

    def test_09_d1_future_cache_tail_fail_closed(self) -> None:
        m=root("1day",("2026-11-11",))
        with self.assertRaisesRegex(ValueError,"FUTURE_OR_UNCLOSED"):
            plan_native_fetch(interval="1day",previous=m,now_utc=NOW)

    def test_10_h4_15_second_close_grace_boundary(self) -> None:
        m=root("4h",H4)
        early=plan_native_fetch(interval="4h",previous=m,
            now_utc=datetime(2026,11,11,8,0,10,tzinfo=UTC))
        late=plan_native_fetch(interval="4h",previous=m,
            now_utc=datetime(2026,11,11,8,0,16,tzinfo=UTC))
        self.assertIsNone(early.request)
        self.assertIsNotNone(late.request)

    def test_11_d1_dst_sydney_local_calendar_not_UTC(self) -> None:
        m=root("1day",("2026-04-04",))
        p=plan_native_fetch(
            interval="1day",previous=m,
            now_utc=datetime(2026,4,5,12,0,tzinfo=UTC))
        self.assertIsNone(p.request)
        self.assertEqual(p.latest_expected_closed_label,"2026-04-04")

    def test_12_naive_timestamp_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"REQUIRES_UTC"):
            plan_native_fetch(interval="4h",previous=None,
                              now_utc=datetime(2026,11,11,9))

    def test_13_non_utc_timestamp_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"REQUIRES_UTC"):
            plan_native_fetch(interval="4h",previous=None,
                now_utc=datetime(2026,11,11,9,tzinfo=timezone(timedelta(hours=7))))

    def test_14_unapproved_tf_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"UNSUPPORTED_NATIVE"):
            plan_native_fetch(interval="5min",previous=None,now_utc=NOW)

    def test_15_h4_wrong_grid_previous_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"OFF_GRID"):
            plan_native_fetch(interval="4h",
                previous=root("4h",("2026-11-10 21:00:00",)),now_utc=NOW)

    def test_16_source_exact_overlap_plus_new_valid(self) -> None:
        m=root("4h",H4)
        now=NOW+timedelta(hours=4)
        p=plan_native_fetch(interval="4h",previous=m,now_utc=now)
        validate_incremental_source(
            batch("4h",H4+("2026-11-11 04:00:00",)),
            previous=m,plan=p)

    def test_17_source_d1_overlap_plus_new_valid(self) -> None:
        m=root("1day",D1)
        p=plan_native_fetch(
            interval="1day",previous=m,now_utc=NOW+timedelta(days=1))
        validate_incremental_source(
            batch("1day",D1+("2026-11-11",)),previous=m,plan=p)

    def test_18_source_missing_one_sha_overlap_denied(self) -> None:
        m=root("4h",H4)
        p=plan_native_fetch(
            interval="4h",previous=m,now_utc=NOW+timedelta(hours=4))
        with self.assertRaisesRegex(ValueError,"MISSING_SHA_OVERLAP"):
            validate_incremental_source(
                batch("4h",(H4[-1],"2026-11-11 04:00:00")),
                previous=m,plan=p)

    def test_19_native_price_revision_denied_even_when_new(self) -> None:
        m=root("4h",H4)
        p=plan_native_fetch(
            interval="4h",previous=m,now_utc=NOW+timedelta(hours=4))
        x=batch("4h",H4+("2026-11-11 04:00:00",))
        changed=list(x.closed_bars)
        changed[0]=NativeFXBar(
            symbol="EUR/USD",interval="4h",
            native_open_label=H4[0],time_reference="UTC_INTRADAY_OPEN",
            exchange_timezone="Australia/Sydney",
            exchange_timezone_origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT",
            open="1.1000",high="1.1040",low="1.0990",close="1.1010")
        x=NativeFXBatch(
            symbol=x.symbol,interval=x.interval,
            exchange_timezone=x.exchange_timezone,
            time_reference=x.time_reference,
            closed_bars=tuple(changed),incomplete_excluded=0)
        with self.assertRaisesRegex(ValueError,"REVISION_QUARANTINE"):
            validate_incremental_source(x,previous=m,plan=p)

    def test_20_wrong_symbol_or_interval_not_accepted(self) -> None:
        m=root("4h",H4)
        p=plan_native_fetch(
            interval="4h",previous=m,now_utc=NOW+timedelta(hours=4))
        with self.assertRaisesRegex(ValueError,"INVALID_SOURCE_OR_PLAN"):
            validate_incremental_source(batch("1day",D1),
                                       previous=m,plan=p)

    def test_21_p59_four_way_disabled_short_circuits_before_secrets(self) -> None:
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
            "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED":"false"}),patch(
            "tools.run_mfx_native_htf_incremental_commit._settings"
        ) as settings:
            out=StringIO()
            with redirect_stdout(out):
                main()
        settings.assert_not_called()
        self.assertIn("DISABLED_EXPLICIT_FOUR_GATE",out.getvalue())

    def test_22_main_cached_both_skips_all_api_and_drive_writes(self) -> None:
        from tools.run_mfx_native_htf_incremental_commit import main
        archives=[
            NativeArchiveState(root("4h",H4),"h4",1,1,()),
            NativeArchiveState(root("1day",D1),"d1",1,1,())]
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
            "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED":"true"}),patch(
            "tools.run_mfx_native_htf_incremental_commit._settings",
            return_value=("key",{"type":"test"},400)),patch(
            "tools.run_mfx_native_htf_incremental_commit._session",
            return_value="session"),patch(
            "tools.run_mfx_native_htf_incremental_commit.PrivateNativeDriveStore",
            side_effect=["store_h4","store_d1"]),patch(
            "tools.run_mfx_native_htf_incremental_commit.audit_native_archive",
            side_effect=archives),patch(
            "tools.run_mfx_native_htf_incremental_commit._usage"
        ) as usage,patch(
            "tools.run_mfx_native_htf_incremental_commit._read_payload"
        ) as vendor,patch(
            "tools.run_mfx_native_htf_incremental_commit.commit_native_batch"
        ) as write,patch(
            "tools.run_mfx_native_htf_incremental_commit.datetime"
        ) as clock:
            clock.now.return_value=NOW
            out=StringIO()
            with redirect_stdout(out):
                main()
        usage.assert_not_called()
        vendor.assert_not_called()
        write.assert_not_called()
        self.assertIn("ZERO_VENDOR_CALLS",out.getvalue())

    def test_23_manual_workflow_new_gate_no_cron_and_shared_lock(self) -> None:
        y=Path(".github/workflows/mfx-native-htf-incremental-commit.yml").read_text()
        self.assertIn("workflow_dispatch:",y)
        self.assertNotIn("schedule:",y)
        self.assertIn("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED",y)
        self.assertIn("mfx-twelvedata-private-cache",y)
        self.assertIn("contents: read",y)
        self.assertIn("run_mfx_native_htf_incremental_commit",y)

    def test_24_original_native_writer_stays_manual_and_unchanged(self) -> None:
        y=Path(".github/workflows/mfx-native-htf-drive-commit.yml").read_text()
        self.assertIn("workflow_dispatch:",y)
        self.assertNotIn("schedule:",y)
        self.assertNotIn("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED",y)

    def test_25_no_fake_short_window_if_more_than_24_rows_needed(self) -> None:
        m=root("4h",H4)
        p=plan_native_fetch(
            interval="4h",previous=m,now_utc=NOW+timedelta(hours=4*30))
        self.assertGreater(int(p.request["outputsize"]),24)
        self.assertLessEqual(int(p.request["outputsize"]),120)

    def test_26_no_new_bar_in_overlap_is_valid_vendor_staleness(self) -> None:
        m=root("4h",H4)
        p=plan_native_fetch(
            interval="4h",previous=m,now_utc=NOW+timedelta(hours=4))
        validate_incremental_source(batch("4h",H4),previous=m,plan=p)


if __name__=="__main__":
    unittest.main()
