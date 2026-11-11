"""P0.66 hermetic full-M5-chain versus native-H4 read-only parity QA.

Only synthetic immutable fake Drive dictionaries; no live I/O or credentials.
"""
from __future__ import annotations

import copy
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from typing import Any
import unittest

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_cache.v2_batch_commit import _make_plan, _name
from tools.run_mfx_m5_h4_live_parity_audit import (
    MAX_M5_ARCHIVE_HOURS, _m5_archive, _native_h4_archive,
    audit_live_m5_h4_parity, main,
)

UTC = timezone.utc
START = datetime(2026,11,1,0,tzinfo=UTC)
NOW = datetime(2026,11,11,18,tzinfo=UTC)
OHLC = {"open":"1.10000","high":"1.10100",
        "low":"1.09900","close":"1.10050"}


class ReadOnlyStore:
    """No put_if_absent interface: auditor cannot write through this store."""
    def __init__(self) -> None:
        self.records: dict[str,dict[str,dict[str,Any]]] = {
            "chunk":{},"manifest":{}}
    def list_names(self,bucket:str) -> tuple[str,...]:
        return tuple(sorted(self.records[bucket]))
    def read(self,bucket:str,name:str) -> dict[str,Any]:
        return copy.deepcopy(self.records[bucket][name])


def m5_hour(hour: datetime) -> tuple[ClosedM5Bar,...]:
    return tuple(ClosedM5Bar(
        start_utc=(hour + timedelta(minutes=5*i)).isoformat(),
        **OHLC,
    ) for i in range(12))


def seed_m5(store:ReadOnlyStore, hours:range | tuple[int,...]) -> None:
    previous = None
    for i in hours:
        hour=START+timedelta(hours=i)
        proposal = _make_plan(previous,hour_utc=hour.isoformat(),
                              bars=m5_hour(hour),now_utc=NOW)
        store.records["chunk"][proposal.chunk_name]=copy.deepcopy(proposal.chunk)
        store.records["manifest"][proposal.manifest_name]=copy.deepcopy(proposal.manifest)
        previous=proposal.manifest


def native_batch(labels: tuple[str,...], *,
                 high: str="1.10100") -> NativeFXBatch:
    return NativeFXBatch(
        symbol="EUR/USD", interval="4h", exchange_timezone="Australia/Sydney",
        time_reference="UTC_INTRADAY_OPEN",incomplete_excluded=0,
        closed_bars=tuple(NativeFXBar(
            symbol="EUR/USD",interval="4h",native_open_label=label,
            time_reference="UTC_INTRADAY_OPEN",
            exchange_timezone="Australia/Sydney",
            exchange_timezone_origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT",
            open=OHLC["open"],high=high,
            low=OHLC["low"],close=OHLC["close"],
        ) for label in labels),
    )


def seed_native(store: ReadOnlyStore, windows:int, *,
                high: str="1.10100") -> None:
    labels = tuple((START+timedelta(hours=4*i)).strftime("%Y-%m-%d %H:%M:%S")
                   for i in range(windows))
    if not labels:
        return
    # The production native archive caps one source batch at 120 bars.
    previous=None
    for p in range(0,len(labels),120):
        batch=native_batch(labels[p:p+120],high=high)
        plan=plan_native_sealed(batch,previous=previous)
        if plan is None:
            raise AssertionError("missing synthetic native plan")
        store.records["chunk"][plan.chunk_name]=copy.deepcopy(plan.chunk)
        store.records["manifest"][plan.manifest_name]=copy.deepcopy(plan.manifest)
        previous=plan.manifest


def fixtures(hours:int=8, *, native_windows:int|None=None) -> tuple[ReadOnlyStore,ReadOnlyStore]:
    m5,native=ReadOnlyStore(),ReadOnlyStore()
    seed_m5(m5,range(hours))
    seed_native(native,hours//4 if native_windows is None else native_windows)
    return m5,native


class M5H4LiveReadOnlyParityTests(unittest.TestCase):
    def test_01_eight_hour_two_native_match_sha_lineages(self) -> None:
        m,n=fixtures()
        old_m,old_n=copy.deepcopy(m.records),copy.deepcopy(n.records)
        receipt=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertEqual(receipt["h4_compared_match"],2)
        self.assertEqual(receipt["h4_compared_mismatch"],0)
        self.assertEqual(receipt["m5_closed_bars"],96)
        self.assertEqual(receipt["m5_manifest_chunk_pairs_full_sha_verified"],8)
        self.assertEqual(receipt["h4_native_manifest_chunk_pairs_full_sha_verified"],1)
        self.assertTrue(receipt["m5_full_bounded_chain_verified"])
        self.assertTrue(receipt["h4_native_full_bounded_chain_verified"])
        self.assertEqual(receipt["status"],"OBSERVATION_WINDOW_NOT_YET_QUALIFIED")
        self.assertFalse(receipt["may_replace_native_h4"])
        self.assertEqual((receipt["provider_api_calls"],receipt["drive_writes"],
                          receipt["broker_orders"]),(0,0,0))
        self.assertEqual((m.records,n.records),(old_m,old_n))

    def test_02_mismatch_is_not_hidden_or_rounded_away(self) -> None:
        m,n=fixtures()
        n=ReadOnlyStore()
        seed_native(n,2,high="1.10101")
        result=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertEqual(result["h4_compared_mismatch"],2)
        self.assertEqual(result["h4_mismatch_sample_fields_only"][0]["fields"],["high"])
        self.assertEqual(result["status"],"SOURCE_PARITY_REVIEW_REQUIRED")
        self.assertFalse(result["h4_parity_observation_threshold_met"])

    def test_03_native_missing_reference_is_reported(self) -> None:
        m,n=fixtures(native_windows=1)
        result=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertEqual(result["h4_native_missing"],1)
        self.assertEqual(result["h4_compared_match"],1)
        self.assertEqual(result["status"],"SOURCE_PARITY_REVIEW_REQUIRED")

    def test_04_one_missing_m5_hour_never_fabricates_full_h4(self) -> None:
        m,n=ReadOnlyStore(),ReadOnlyStore()
        seed_m5(m,(0,1,2,4,5,6,7))
        seed_native(n,2)
        r=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertEqual(r["m5_h4_complete_windows"],1)
        self.assertEqual(r["m5_h4_incomplete_windows"],1)
        self.assertFalse(r["h4_parity_observation_threshold_met"])

    def test_05_tampered_early_m5_chunk_fails_whole_chain(self) -> None:
        m,n=fixtures()
        name=sorted(m.records["chunk"])[0]
        m.records["chunk"][name]["bars"][0]["close"]="1.10060"
        with self.assertRaises(ValueError):
            audit_live_m5_h4_parity(m,n,now_utc=NOW)

    def test_06_m5_missing_chunk_fails_closed(self) -> None:
        m,n=fixtures()
        del m.records["chunk"][sorted(m.records["chunk"])[0]]
        with self.assertRaisesRegex(ValueError,"ORPHAN_OR_MISSING_CHUNK"):
            audit_live_m5_h4_parity(m,n,now_utc=NOW)

    def test_07_m5_extra_orphan_fails_closed(self) -> None:
        m,n=fixtures()
        m.records["chunk"]["MFX_TD_EURUSD_M5_V2_chunk_orphan.json"]={}
        with self.assertRaisesRegex(ValueError,"ORPHAN_OR_MISSING_CHUNK"):
            audit_live_m5_h4_parity(m,n,now_utc=NOW)

    def test_08_old_manifest_corruption_not_just_tail_is_checked(self) -> None:
        m,n=fixtures()
        name=sorted(m.records["manifest"])[0]
        m.records["manifest"][name]["total_batches"]=999
        with self.assertRaises(ValueError):
            audit_live_m5_h4_parity(m,n,now_utc=NOW)

    def test_09_native_h4_sha_tamper_fails_closed(self) -> None:
        m,n=fixtures()
        name=sorted(n.records["chunk"])[0]
        n.records["chunk"][name]["bars"][0]["high"]="1.2"
        with self.assertRaises(ValueError):
            audit_live_m5_h4_parity(m,n,now_utc=NOW)

    def test_10_old_m5_derivation_drift_even_if_resigned_is_rejected(self) -> None:
        m=ReadOnlyStore()
        seed_m5(m,range(1))
        original_chunk_name=next(iter(m.records["chunk"]))
        original_manifest_name=next(iter(m.records["manifest"]))
        chunk=m.records["chunk"].pop(original_chunk_name)
        manifest=m.records["manifest"].pop(original_manifest_name)
        chunk["derived"]["H1"][0]["high"]="1.5"
        digest_chunk=digest(chunk)
        new_chunk_name=_name("chunk",manifest["hour_utc"],digest_chunk)
        manifest["chunk_sha256"]=digest_chunk
        manifest["chunk_name"]=new_chunk_name
        new_manifest_name=_name("manifest",manifest["hour_utc"],digest(manifest))
        m.records["chunk"][new_chunk_name]=chunk
        m.records["manifest"][new_manifest_name]=manifest
        with self.assertRaisesRegex(ValueError,"DERIVED_LINEAGE_DRIFT"):
            _m5_archive(m,now_utc=NOW)

    def test_11_192_hours_meet_observation_but_not_cutover_authority(self) -> None:
        m,n=fixtures(hours=192)
        r=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertEqual(r["h4_compared_match"],48)
        self.assertTrue(r["h4_parity_observation_threshold_met"])
        self.assertEqual(
            r["status"],"SOURCE_PARITY_WINDOW_MET_OWNER_CUTOVER_STILL_DENIED")
        self.assertTrue(r["h4_span_at_least_7_days"])
        self.assertFalse(r["may_reduce_native_h4_requests"])
        self.assertFalse(r["may_replace_native_h4"])

    def test_12_missing_native_entire_archive_no_false_proof(self) -> None:
        m=ReadOnlyStore()
        seed_m5(m,range(8))
        with self.assertRaises(ValueError):
            audit_live_m5_h4_parity(m,ReadOnlyStore(),now_utc=NOW)

    def test_13_utc_asof_fail_closed(self) -> None:
        m,n=fixtures()
        with self.assertRaisesRegex(ValueError,"EXACT_UTC"):
            audit_live_m5_h4_parity(m,n,
                now_utc=datetime(2026,11,11,18))

    def test_14_hard_bounded_m5_history(self) -> None:
        m=ReadOnlyStore()
        for i in range(MAX_M5_ARCHIVE_HOURS+1):
            m.records["manifest"][f"MFX_TD_EURUSD_M5_V2_manifest_{i:04d}"]={}
            m.records["chunk"][f"MFX_TD_EURUSD_M5_V2_chunk_{i:04d}"]={}
        with self.assertRaisesRegex(ValueError,"TOO_LARGE"):
            _m5_archive(m,now_utc=NOW)

    def test_15_root_without_earlier_history_no_assumed_backfill(self) -> None:
        m,n=fixtures()
        r=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertLess(r["m5_h4_complete_windows"],30)
        self.assertFalse(r["h4_parity_observation_threshold_met"])

    def test_16_native_orphan_refusal(self) -> None:
        m,n=fixtures()
        n.records["chunk"]["MFX_TD_EURUSD_H4_NATIVE_V1_chunk_orphan.json"]={}
        with self.assertRaises(ValueError):
            _native_h4_archive(n)

    def test_17_disabled_variables_never_touch_credentials(self) -> None:
        import os
        with patch.dict(os.environ,{"MFX_REAL_CACHE_ENABLED":"false",
                                   "MFX_V2_BATCH_CACHE_ACCEPTED":"false",
                                   "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"false"}):
            with patch(
                "tools.run_mfx_m5_h4_live_parity_audit._drive_auth_info",
                side_effect=AssertionError("credentials touched")
            ):
                out=StringIO()
                with redirect_stdout(out):
                    main()
        self.assertIn("DISABLED_EXISTING_GATES",out.getvalue())

    def test_18_no_ohlc_prices_in_live_receipt(self) -> None:
        m,n=fixtures()
        r=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        from json import dumps
        s=dumps(r)
        for value in ("1.10000","1.10100","1.09900","1.10050"):
            self.assertNotIn(value,s)
        self.assertFalse(r["raw_ohlc_logged"])
        self.assertFalse(r["source_numeric_signals_approved"])

    def test_19_workflow_no_provider_key_and_daily_plus_push_trigger(self) -> None:
        yml=Path(__file__).resolve().parents[1].joinpath(
            ".github/workflows/mfx-m5-h4-parity-readonly.yml").read_text()
        self.assertIn('cron: "55 0 * * *"',yml)
        self.assertIn("workflow_dispatch:",yml)
        self.assertIn("branches: [main]",yml)
        self.assertIn("group: mfx-twelvedata-private-cache",yml)
        self.assertIn("cancel-in-progress: false",yml)
        self.assertIn("MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED",yml)
        self.assertIn("run_mfx_m5_h4_live_parity_audit",yml)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY",yml)
        self.assertNotIn("drive/v3/files/create",yml)
        self.assertNotIn("secrets.MFX_GDRIVE_SERVICE_ACCOUNT_JSON",yml)

    def test_20_native_h4_origin_is_real_and_source_is_mid(self) -> None:
        m,n=fixtures()
        records,receipt=_native_h4_archive(n)
        self.assertTrue(all(b.is_provider_native for b in records))
        self.assertEqual({x.price_side for x in records},{"MID"})
        self.assertTrue(receipt["h4_native_full_bounded_chain_verified"])


if __name__ == "__main__":
    unittest.main()
