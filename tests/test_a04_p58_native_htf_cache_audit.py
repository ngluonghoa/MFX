"""A04/P0.58 offline tests: full native H4/D1 SHA read-only audit and lag."""
from __future__ import annotations

import copy
from dataclasses import replace
from datetime import datetime, timezone
from io import StringIO
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from typing import Any
import json
import os
import unittest

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from tools.run_mfx_native_htf_cache_audit import audit_native_cache, main

UTC = timezone.utc
NOW = datetime(2026,11,11,5,15,tzinfo=UTC)


def native(interval: str, labels: tuple[str,...]) -> NativeFXBatch:
    axis = ("UTC_INTRADAY_OPEN" if interval=="4h"
            else "EXCHANGE_LOCAL_SESSION_DATE")
    return NativeFXBatch(
        symbol="EUR/USD", interval=interval,
        exchange_timezone="Australia/Sydney",
        time_reference=axis, incomplete_excluded=0,
        closed_bars=tuple(NativeFXBar(
            symbol="EUR/USD", interval=interval,
            native_open_label=label,
            time_reference=axis, exchange_timezone="Australia/Sydney",
            exchange_timezone_origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT",
            open="1.1000",high="1.1050",low="1.0990",close="1.1030",
        ) for label in labels),
    )


class ReadOnlyFakeStore:
    """Implements only read/list, so tests cannot silently create Drive files."""
    def __init__(self) -> None:
        self.data: dict[str,dict[str,dict[str,Any]]] = {
            "chunk":{}, "manifest":{}}
    def list_names(self, bucket: str) -> tuple[str,...]:
        return tuple(sorted(self.data[bucket]))
    def read(self, bucket: str, name: str) -> dict[str,Any]:
        return copy.deepcopy(self.data[bucket][name])
    def seed(self, batch: NativeFXBatch) -> None:
        names = sorted(self.data["manifest"])
        old = self.data["manifest"][names[-1]] if names else None
        p = plan_native_sealed(batch,previous=old)
        if p is None:
            raise AssertionError("test must add at least one new bar")
        self.data["chunk"][p.chunk_name] = copy.deepcopy(p.chunk)
        self.data["manifest"][p.manifest_name] = copy.deepcopy(p.manifest)


def h4() -> ReadOnlyFakeStore:
    store = ReadOnlyFakeStore()
    store.seed(native("4h",(
        "2026-11-10 20:00:00","2026-11-11 00:00:00")))
    return store


def d1() -> ReadOnlyFakeStore:
    store = ReadOnlyFakeStore()
    store.seed(native("1day",("2026-11-09","2026-11-10")))
    return store


class P058NativeAuditTests(unittest.TestCase):
    def test_01_h4_live_shaped_closed_slot_sha_pass(self) -> None:
        store=h4()
        old=copy.deepcopy(store.data)
        result=audit_native_cache(store,interval="4h",now_utc=NOW)
        self.assertEqual(result["status"],"LAST_EXPECTED_NATIVE_SLOT_PRESENT")
        self.assertEqual(result["lag"],0)
        self.assertEqual(result["last_native_open_label"],"2026-11-11 00:00:00")
        self.assertTrue(result["full_bounded_archive_verified"])
        self.assertEqual(result["historical_manifest_chunk_pairs_verified"],1)
        self.assertEqual(result["twelve_data_api_calls"],0)
        self.assertEqual(result["drive_writes"],0)
        self.assertEqual(store.data,old)

    def test_02_d1_exchange_local_session_date_sha_pass(self) -> None:
        r=audit_native_cache(d1(),interval="1day",now_utc=NOW)
        self.assertEqual(r["status"],"LAST_EXPECTED_NATIVE_SLOT_PRESENT")
        self.assertEqual(r["lag"],0)
        self.assertEqual(r["lag_unit"],"calendar_days_not_market_sessions")
        self.assertEqual(r["time_reference"],"EXCHANGE_LOCAL_SESSION_DATE")

    def test_03_h4_lag_is_observation_not_integrity_failure(self) -> None:
        r=audit_native_cache(
            h4(),interval="4h",
            now_utc=datetime(2026,11,12,9,30,tzinfo=UTC))
        self.assertEqual(r["status"],"LAGGING_OR_MARKET_CLOSED_REVIEW_REQUIRED")
        self.assertGreater(r["lag"],0)
        self.assertTrue(r["observed_only_not_market_session_sla"])

    def test_04_d1_weekend_or_manual_writer_lag_not_false_market_failure(self) -> None:
        r=audit_native_cache(
            d1(),interval="1day",
            now_utc=datetime(2026,11,16,9,0,tzinfo=UTC))
        self.assertEqual(r["status"],"LAGGING_OR_MARKET_CLOSED_REVIEW_REQUIRED")
        self.assertGreater(r["lag"],0)
        self.assertEqual(r["lag_unit"],"calendar_days_not_market_sessions")

    def test_05_tampered_chunk_exact_sha_rejected(self) -> None:
        s=h4()
        name=next(iter(s.data["chunk"]))
        s.data["chunk"][name]["bars"][0]["close"]="1.1040"
        with self.assertRaises(ValueError):
            audit_native_cache(s,interval="4h",now_utc=NOW)

    def test_06_tampered_manifest_sha_rejected(self) -> None:
        s=d1()
        name=next(iter(s.data["manifest"]))
        s.data["manifest"][name]["total_closed_native_bars"]=99
        with self.assertRaises(ValueError):
            audit_native_cache(s,interval="1day",now_utc=NOW)

    def test_07_missing_manifest_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError,"NOT_BOOTSTRAPPED"):
            audit_native_cache(ReadOnlyFakeStore(),interval="4h",now_utc=NOW)

    def test_08_missing_referenced_chunk_fails_closed(self) -> None:
        s=d1()
        s.data["chunk"].clear()
        with self.assertRaisesRegex(ValueError,"MISSING_REFERENCED_CHUNK"):
            audit_native_cache(s,interval="1day",now_utc=NOW)

    def test_09_single_orphan_is_quarantined_for_readonly_audit(self) -> None:
        s=h4()
        s.data["chunk"]["MFX_TD_EURUSD_H4_NATIVE_V1_chunk_uncommitted.json"]={}
        with self.assertRaisesRegex(ValueError,"UNCOMMITTED_NATIVE_CHUNK"):
            audit_native_cache(s,interval="4h",now_utc=NOW)

    def test_10_full_parent_chain_is_checked_not_just_tail(self) -> None:
        s=ReadOnlyFakeStore()
        s.seed(native("4h",("2026-11-10 16:00:00","2026-11-10 20:00:00")))
        s.seed(native("4h",("2026-11-10 20:00:00","2026-11-11 00:00:00")))
        a=audit_native_cache(s,interval="4h",now_utc=NOW)
        self.assertEqual(a["historical_manifest_chunk_pairs_verified"],2)
        first=sorted(s.data["manifest"])[0]
        s.data["manifest"][first]["batch_count"]=8
        with self.assertRaises(ValueError):
            audit_native_cache(s,interval="4h",now_utc=NOW)

    def test_11_future_or_open_h4_rejected(self) -> None:
        s=ReadOnlyFakeStore()
        s.seed(native("4h",("2026-11-11 04:00:00",)))
        with self.assertRaisesRegex(ValueError,"FUTURE_OR_UNCLOSED_NATIVE_H4"):
            audit_native_cache(s,interval="4h",now_utc=NOW)

    def test_12_h4_not_4h_utc_grid_rejected(self) -> None:
        s=ReadOnlyFakeStore()
        s.seed(native("4h",("2026-11-11 01:00:00",)))
        with self.assertRaisesRegex(ValueError,"NOT_ON_UTC_GRID"):
            audit_native_cache(s,interval="4h",now_utc=NOW)

    def test_13_future_or_same_day_d1_rejected(self) -> None:
        s=ReadOnlyFakeStore()
        s.seed(native("1day",("2026-11-11",)))
        with self.assertRaisesRegex(ValueError,"FUTURE_OR_UNCLOSED_NATIVE_D1"):
            audit_native_cache(s,interval="1day",now_utc=NOW)

    def test_14_utc_required_without_timezone(self) -> None:
        with self.assertRaisesRegex(ValueError,"REQUIRES_UTC"):
            audit_native_cache(
                h4(),interval="4h",now_utc=datetime(2026,11,11,5,15))

    def test_15_wrong_interval_refused(self) -> None:
        with self.assertRaisesRegex(ValueError,"INTERVAL_NOT_ALLOWED"):
            audit_native_cache(h4(),interval="5min",now_utc=NOW)

    def test_16_wrong_scope_manifest_not_treated_as_other_interval(self) -> None:
        with self.assertRaises(ValueError):
            audit_native_cache(h4(),interval="1day",now_utc=NOW)

    def test_17_native_archive_does_not_self_mutate(self) -> None:
        s=d1()
        data=copy.deepcopy(s.data)
        audit_native_cache(s,interval="1day",now_utc=NOW)
        audit_native_cache(s,interval="1day",now_utc=NOW)
        self.assertEqual(s.data,data)

    def test_18_d1_iana_sydney_daylight_saving_boundary(self) -> None:
        s=ReadOnlyFakeStore()
        s.seed(native("1day",("2026-04-04",)))
        result=audit_native_cache(
            s,interval="1day",
            now_utc=datetime(2026,4,5,12,0,tzinfo=UTC))
        self.assertEqual(result["lag"],0)

    def test_19_root_manifest_malformed_parent_rejected(self) -> None:
        s=h4()
        name=next(iter(s.data["manifest"]))
        s.data["manifest"][name]["parent_manifest_sha256"]="a"*64
        with self.assertRaises(ValueError):
            audit_native_cache(s,interval="4h",now_utc=NOW)

    def test_20_three_way_gate_off_never_authenticates(self) -> None:
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"false"}),patch(
            "tools.run_mfx_native_htf_cache_audit._drive_auth_info") as auth:
            output=StringIO()
            with redirect_stdout(output):
                main()
        auth.assert_not_called()
        self.assertIn("DISABLED_THREE_WAY_GATE",output.getvalue())

    def test_21_main_uses_only_readonly_stores_and_prints_no_prices(self) -> None:
        original_h4,original_d1=h4(),d1()
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true"}),patch(
            "tools.run_mfx_native_htf_cache_audit._drive_auth_info",
            return_value={"type":"test"}),patch(
            "tools.run_mfx_native_htf_cache_audit._require_oauth_cache_folders"
        ),patch(
            "tools.run_mfx_native_htf_cache_audit._session",
            return_value="fake-session"),patch(
            "tools.run_mfx_native_htf_cache_audit.PrivateNativeDriveStore",
            side_effect=[original_h4,original_d1]):
            output=StringIO()
            with redirect_stdout(output):
                main()
        receipt=output.getvalue()
        self.assertIn("MFX_A04_P58_NATIVE_H4_D1_READONLY_FULL_SHA_AUDIT_PASS",
                      receipt)
        self.assertIn('"provider_price_requests": 0',receipt)
        self.assertIn('"drive_writes": 0',receipt)
        self.assertNotIn("1.1030",receipt)
        self.assertNotIn("apikey",receipt.lower())

    def test_22_scheduled_workflow_has_no_vendor_secret_or_write_entry(self) -> None:
        y=Path(".github/workflows/mfx-native-htf-cache-audit.yml").read_text(
            encoding="utf-8")
        self.assertIn('cron: "45 * * * *"',y)
        self.assertIn("workflow_dispatch:",y)
        self.assertIn("permissions:",y)
        self.assertIn("contents: read",y)
        self.assertIn("mfx-twelvedata-private-cache",y)
        self.assertIn("run_mfx_native_htf_cache_audit",y)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY",y)
        self.assertNotIn("run_mfx_native_htf_drive_commit",y)
        self.assertNotIn("secrets.GITHUB_TOKEN",y)

    def test_23_existing_writer_remains_manual_only(self) -> None:
        y=Path(".github/workflows/mfx-native-htf-drive-commit.yml").read_text(
            encoding="utf-8")
        self.assertIn("workflow_dispatch:",y)
        self.assertNotIn("schedule:",y)
        self.assertIn("MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED",y)

    def test_24_no_orphan_d1_m5_overlap_in_separate_namespaces(self) -> None:
        a,b=h4(),d1()
        self.assertNotEqual(
            next(iter(a.data["manifest"])),
            next(iter(b.data["manifest"])))
        for tf,s in (("4h",a),("1day",b)):
            self.assertEqual(
                audit_native_cache(s,interval=tf,now_utc=NOW)["chunk_count"],
                1)


if __name__=="__main__":
    unittest.main()
