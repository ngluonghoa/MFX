"""A04/P0.60: provider-stale receipt truth + private Drive-only plan preview."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from typing import Any
import copy
import os
import unittest

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from tools.run_mfx_native_htf_incremental_commit import (
    summarize_incremental_receipts,
)
from tools.run_mfx_native_htf_incremental_preview import (
    preview_incremental_native_cache, main,
)

UTC=timezone.utc
H4=("2026-11-10 20:00:00","2026-11-11 00:00:00")
D1=("2026-11-09","2026-11-10")


def record(interval: str, status: str, new: int, created: int) -> dict[str,Any]:
    return {
        "symbol":"EUR/USD","interval":interval,
        "status":status,"newly_closed_native_bars":new,
        "drive_objects_created_max":created,"broker_orders":0,
    }


def fake_store(interval: str) -> Any:
    labels=H4 if interval=="4h" else D1
    axis="UTC_INTRADAY_OPEN" if interval=="4h" else "EXCHANGE_LOCAL_SESSION_DATE"
    batch=NativeFXBatch(
        symbol="EUR/USD",interval=interval,
        time_reference=axis,exchange_timezone="Australia/Sydney",
        incomplete_excluded=0,
        closed_bars=tuple(NativeFXBar(
            symbol="EUR/USD",interval=interval,
            native_open_label=label,time_reference=axis,
            exchange_timezone="Australia/Sydney",
            exchange_timezone_origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT",
            open="1.1000",high="1.1050",low="1.0990",close="1.1020",
        ) for label in labels),
    )
    sealed=plan_native_sealed(batch,previous=None)
    assert sealed is not None

    class Archive:
        data: dict[str,dict[str,Any]] = {}
        def __init__(self) -> None:
            self.data = {
                "chunk":{sealed.chunk_name:copy.deepcopy(sealed.chunk)},
                "manifest":{sealed.manifest_name:copy.deepcopy(sealed.manifest)},
            }
        def list_names(self,bucket: str) -> tuple[str,...]:
            return tuple(sorted(self.data[bucket]))
        def read(self,bucket: str,name: str) -> dict[str,Any]:
            return copy.deepcopy(self.data[bucket][name])
    return Archive()


class P060Tests(unittest.TestCase):
    def test_01_stale_source_request_must_not_claim_commit(self) -> None:
        r=summarize_incremental_receipts([
            record("4h","NO_NEW_CLOSED_NATIVE_BAR",0,0)])
        self.assertEqual(r["status"],"NATIVE_INCREMENTAL_PROVIDER_STALE_NO_NEW_BAR")
        self.assertEqual(r["total_newly_closed_native_bars"],0)
        self.assertEqual(r["intervals_provider_stale_no_new_bar"],["4h"])
        self.assertEqual(r["intervals_with_new_native_bars"],[])

    def test_02_committed_receipt_reports_real_new_bars(self) -> None:
        r=summarize_incremental_receipts([
            record("4h","NATIVE_BATCH_COMMITTED",1,2)])
        self.assertEqual(r["status"],"NATIVE_INCREMENTAL_NEW_BARS_COMMITTED")
        self.assertEqual(r["total_newly_closed_native_bars"],1)
        self.assertEqual(r["intervals_with_new_native_bars"],["4h"])

    def test_03_one_stale_one_new_does_not_conflate(self) -> None:
        r=summarize_incremental_receipts([
            record("4h","NO_NEW_CLOSED_NATIVE_BAR",0,0),
            record("1day","NATIVE_BATCH_COMMITTED",2,2)])
        self.assertEqual(r["total_newly_closed_native_bars"],2)
        self.assertEqual(r["intervals_provider_stale_no_new_bar"],["4h"])
        self.assertEqual(r["intervals_with_new_native_bars"],["1day"])

    def test_04_recovered_orphan_receipt_still_real_write(self) -> None:
        r=summarize_incremental_receipts([
            record("4h","RECOVERED_ORPHAN_AND_COMMITTED",1,1)])
        self.assertEqual(r["total_newly_closed_native_bars"],1)

    def test_05_false_stale_claim_with_writes_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"STALE_RECEIPT_HAS_WRITES"):
            summarize_incremental_receipts([
                record("4h","NO_NEW_CLOSED_NATIVE_BAR",1,2)])

    def test_06_false_commit_claim_without_new_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"COMMIT_RECEIPT_NO_NEW_BARS"):
            summarize_incremental_receipts([
                record("4h","NATIVE_BATCH_COMMITTED",0,2)])

    def test_07_duplicate_intervals_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"INVALID_COMMIT_RECEIPT"):
            summarize_incremental_receipts([
                record("4h","NO_NEW_CLOSED_NATIVE_BAR",0,0),
                record("4h","NO_NEW_CLOSED_NATIVE_BAR",0,0)])

    def test_08_unknown_receipt_status_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"INVALID_COMMIT_RECEIPT"):
            summarize_incremental_receipts([record("4h","APPROVED_TRADE",1,2)])

    def test_09_empty_receipts_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"RECEIPTS_REQUIRED"):
            summarize_incremental_receipts([])

    def test_10_preview_one_due_one_skipped_no_mutation(self) -> None:
        stores={"4h":fake_store("4h"),"1day":fake_store("1day")}
        old=copy.deepcopy({k:v.data for k,v in stores.items()})
        r=preview_incremental_native_cache(
            stores,now_utc=datetime(2026,11,11,9,5,tzinfo=UTC))
        self.assertEqual(r["total_price_requests_if_approved"],1)
        self.assertEqual(r["real_provider_price_requests"],0)
        self.assertEqual(r["real_provider_usage_requests"],0)
        self.assertEqual(r["drive_writes"],0)
        self.assertEqual(r["intervals"][0]["interval"],"4h")
        self.assertEqual(r["intervals"][0]["requested_outputsize_if_approved"],24)
        self.assertEqual(r["intervals"][1]["provider_price_requests_if_approved"],0)
        self.assertEqual({k:v.data for k,v in stores.items()},old)

    def test_11_preview_both_due_2_would_be_requests_0_actual(self) -> None:
        r=preview_incremental_native_cache(
            {"4h":fake_store("4h"),"1day":fake_store("1day")},
            now_utc=datetime(2026,11,12,5,15,tzinfo=UTC))
        self.assertEqual(r["total_price_requests_if_approved"],2)
        self.assertEqual(r["real_provider_price_requests"],0)
        self.assertFalse(r["automatic_native_writer_enabled"])

    def test_12_preview_both_current_zero_would_be_requests(self) -> None:
        r=preview_incremental_native_cache(
            {"4h":fake_store("4h"),"1day":fake_store("1day")},
            now_utc=datetime(2026,11,11,5,15,tzinfo=UTC))
        self.assertEqual(r["total_price_requests_if_approved"],0)
        self.assertEqual(r["intervals"][0]["decision"],
                         "NO_NEW_CLOSED_SLOT_NO_VENDOR_CALL")

    def test_13_preview_missing_interval_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"REQUIRES_H4_D1"):
            preview_incremental_native_cache(
                {"4h":fake_store("4h")},
                now_utc=datetime(2026,11,11,5,15,tzinfo=UTC))

    def test_14_preview_corrupt_chunk_sha_fails_closed(self) -> None:
        stores={"4h":fake_store("4h"),"1day":fake_store("1day")}
        one=next(iter(stores["4h"].data["chunk"]))
        stores["4h"].data["chunk"][one]["bars"][0]["close"]="1.1049"
        with self.assertRaises(ValueError):
            preview_incremental_native_cache(
                stores,now_utc=datetime(2026,11,11,5,15,tzinfo=UTC))

    def test_15_preview_orphan_requires_review(self) -> None:
        stores={"4h":fake_store("4h"),"1day":fake_store("1day")}
        stores["4h"].data["chunk"]["MFX_TD_EURUSD_H4_NATIVE_V1_chunk_orphan.json"]={}
        with self.assertRaisesRegex(ValueError,"UNCOMMITTED_NATIVE_CHUNK"):
            preview_incremental_native_cache(
                stores,now_utc=datetime(2026,11,11,5,15,tzinfo=UTC))

    def test_16_preview_requires_existing_3_gates_before_oauth(self) -> None:
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"false"}),patch(
            "tools.run_mfx_native_htf_incremental_preview._drive_auth_info"
        ) as oauth:
            out=StringIO()
            with redirect_stdout(out):
                main()
        oauth.assert_not_called()
        self.assertIn("DISABLED_EXISTING_THREE_GATES",out.getvalue())

    def test_17_preview_main_only_uses_drive_and_no_vendor(self) -> None:
        stores=[fake_store("4h"),fake_store("1day")]
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true"}),patch(
            "tools.run_mfx_native_htf_incremental_preview._drive_auth_info",
            return_value={"type":"test"}),patch(
            "tools.run_mfx_native_htf_incremental_preview._require_oauth_cache_folders"
        ),patch(
            "tools.run_mfx_native_htf_incremental_preview._session",
            return_value="fake_session"),patch(
            "tools.run_mfx_native_htf_incremental_preview.PrivateNativeDriveStore",
            side_effect=stores),patch(
            "tools.run_mfx_native_htf_incremental_preview.datetime"
        ) as clock:
            clock.now.return_value=datetime(2026,11,11,5,15,tzinfo=UTC)
            out=StringIO()
            with redirect_stdout(out):
                main()
        self.assertIn("MFX_A04_P60_NATIVE_INCREMENTAL_READONLY_PREVIEW_PASS",
                      out.getvalue())
        self.assertIn('"real_provider_price_requests": 0',out.getvalue())
        self.assertNotIn("1.1000",out.getvalue())

    def test_18_preview_workflow_is_manual_readonly_no_secret_vendor(self) -> None:
        y=Path(".github/workflows/mfx-native-htf-incremental-preview.yml").read_text()
        self.assertIn("workflow_dispatch:",y)
        self.assertNotIn("schedule:",y)
        self.assertIn("mfx-twelvedata-private-cache",y)
        self.assertIn("contents: read",y)
        self.assertIn("run_mfx_native_htf_incremental_preview",y)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY",y)
        self.assertNotIn("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED",y)
        self.assertNotIn("run_mfx_native_htf_incremental_commit",y)


if __name__=="__main__":
    unittest.main()
