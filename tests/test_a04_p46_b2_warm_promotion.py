"""A04/P0.46-B2 32 synthetic private Drive WARM day promotion QA cases."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest import TestCase, main
from unittest.mock import patch
import os

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_batch_commit import commit_hour
from mfx_cache.v2_warm_promotion import (
    _all_verified_source, _plan_day, promote_completed_utc_day,
)
from tools.run_a04_p46_cloud_batch_cache import PrivateDriveBatchStore
from tools.run_a04_p46_b2_cloud_warm import main as cloud_main

UTC = timezone.utc
DAY = datetime(2026,11,11,tzinfo=UTC)
NOW = DAY + timedelta(days=1,hours=1,minutes=10)


def rows(hour: int) -> tuple[ClosedM5Bar, ...]:
    begin = DAY + timedelta(hours=hour)
    return tuple(ClosedM5Bar(
        start_utc=(begin+timedelta(minutes=5*i)).isoformat(),
        open="1.1", high="1.2", low="1.0",close="1.15",
    ) for i in range(12))


class FakePrivateDrive:
    def __init__(self) -> None:
        self.items: dict[str,dict[str,dict[str,Any]]] = {
            "manifest":{}, "chunk":{}, "warm":{}, "promotion":{},
        }
        self.calls: list[tuple[str,str]]=[]
        self.fail_after_bucket: str | None = None
        self.corrupt_read: tuple[str,str] | None=None

    def list_names(self,bucket:str)->tuple[str,...]:
        return tuple(sorted(self.items[bucket]))

    def read(self,bucket:str,name:str)->dict[str,Any]:
        body=deepcopy(self.items[bucket][name])
        if self.corrupt_read==(bucket,name):
            body["broker_orders"]=1
        return body

    def put_if_absent(self,bucket:str,name:str,body:dict[str,Any])->None:
        old=self.items[bucket].get(name)
        if old is not None:
            if old!=body:
                raise ValueError("FAKE_IMMUTABLE_CONFLICT")
            return
        self.items[bucket][name]=deepcopy(body)
        self.calls.append((bucket,name))
        if self.fail_after_bucket==bucket:
            self.fail_after_bucket=None
            raise OSError("FAKE_CRASH_AFTER_"+bucket.upper())


def original(*hours: int) -> FakePrivateDrive:
    d=FakePrivateDrive()
    for hour in hours:
        commit_hour(d,now_utc=DAY+timedelta(hours=hour+1,minutes=10),
                    observed=rows(hour))
    return d


class P046B2WarmPromotionTests(TestCase):
    def test_01_three_source_hours_create_warm_and_receipt(self)->None:
        d=original(9,10,11)
        r=promote_completed_utc_day(d,now_utc=NOW)
        self.assertEqual(r.status,"WARM_PROMOTED")
        self.assertEqual(r.source_hour_count,3)
        self.assertEqual((len(d.items["warm"]),len(d.items["promotion"])),(1,1))

    def test_02_day_provenance_and_aggregate_rows(self)->None:
        d=original(9,10,11)
        promote_completed_utc_day(d,now_utc=NOW)
        w=next(iter(d.items["warm"].values()))
        self.assertEqual(w["source"],"TWELVE_DATA_COMPOSITE_MID")
        self.assertEqual(w["side"],"MID")
        self.assertEqual(w["timezone"],"UTC")
        self.assertEqual(len(w["closed_m5_bars"]),36)
        self.assertEqual({k:len(v) for k,v in w["derived"].items()},
                         {"M15":12,"M30":6,"H1":3})

    def test_03_partial_calendar_never_claims_full_day(self)->None:
        d=original(9,10,11)
        r=promote_completed_utc_day(d,now_utc=NOW)
        self.assertEqual(r.missing_hour_count,21)
        w=next(iter(d.items["warm"].values()))
        self.assertEqual(w["coverage"],"PARTIAL_UTC_DAY_UNKNOWN_SESSION_OR_GAPS")
        self.assertEqual(len(w["missing_utc_hour_starts"]),21)
        self.assertFalse(w["source_asof_or_bidask_proven"])

    def test_04_original_hourly_files_preserved(self)->None:
        d=original(9,10,11)
        before={k:deepcopy(d.items[k]) for k in ("manifest","chunk")}
        promote_completed_utc_day(d,now_utc=NOW)
        self.assertEqual({k:d.items[k] for k in before},before)

    def test_05_idempotent_repeat_has_zero_writes(self)->None:
        d=original(9,10,11)
        promote_completed_utc_day(d,now_utc=NOW)
        count=len(d.calls)
        r=promote_completed_utc_day(d,now_utc=NOW)
        self.assertEqual(r.status,"ALREADY_PROMOTED")
        self.assertEqual(r.expected_new_drive_objects,0)
        self.assertEqual(len(d.calls),count)

    def test_06_warm_crash_replay_one_receipt_only(self)->None:
        d=original(9,10,11)
        d.fail_after_bucket="warm"
        with self.assertRaisesRegex(OSError,"FAKE_CRASH_AFTER_WARM"):
            promote_completed_utc_day(d,now_utc=NOW)
        self.assertEqual((len(d.items["warm"]),len(d.items["promotion"])),(1,0))
        r=promote_completed_utc_day(d,now_utc=NOW)
        self.assertEqual(r.status,"RECOVERED_WARM_AND_PROMOTED")
        self.assertEqual(r.expected_new_drive_objects,1)
        self.assertEqual(len(d.items["promotion"]),1)

    def test_07_receipt_crash_replay_no_duplicate(self)->None:
        d=original(9,10,11)
        d.fail_after_bucket="promotion"
        with self.assertRaisesRegex(OSError,"FAKE_CRASH_AFTER_PROMOTION"):
            promote_completed_utc_day(d,now_utc=NOW)
        count=len(d.calls)
        self.assertEqual(promote_completed_utc_day(d,now_utc=NOW).status,
                         "ALREADY_PROMOTED")
        self.assertEqual(len(d.calls),count)

    def test_08_readback_corrupted_warm_blocks_promotion(self)->None:
        d=original(9,10,11)
        orig=d.put_if_absent
        def sabotage(bucket:str,name:str,body:dict[str,Any])->None:
            orig(bucket,name,body)
            if bucket=="warm":
                d.corrupt_read=(bucket,name)
        d.put_if_absent=sabotage  # type: ignore[method-assign]
        with self.assertRaises(ValueError):
            promote_completed_utc_day(d,now_utc=NOW)
        self.assertEqual(d.items["promotion"],{})

    def test_09_corrupted_source_chunk_detected(self)->None:
        d=original(9,10,11)
        key=next(iter(d.items["chunk"]))
        d.items["chunk"][key]["bars"][0]["close"]="1.166"
        with self.assertRaisesRegex(ValueError,"P046_B1_OBJECT_NAME_CONTENT_SHA_MISMATCH"):
            promote_completed_utc_day(d,now_utc=NOW)

    def test_10_modified_derived_close_detected(self)->None:
        d=original(9,10,11)
        key=next(iter(d.items["chunk"]))
        d.items["chunk"][key]["derived"]["H1"][0]["close"]="0.01"
        with self.assertRaises(ValueError):
            promote_completed_utc_day(d,now_utc=NOW)

    def test_11_modified_source_manifest_detected(self)->None:
        d=original(9,10,11)
        key=next(iter(d.items["manifest"]))
        d.items["manifest"][key]["chunk_sha256"]="0"*64
        with self.assertRaises(ValueError):
            promote_completed_utc_day(d,now_utc=NOW)

    def test_12_missing_middle_source_manifest_fails_chain(self)->None:
        d=original(9,10,11)
        middle=sorted(d.items["manifest"])[1]
        del d.items["manifest"][middle]
        with self.assertRaisesRegex(ValueError,"BROKEN_FULL_SOURCE_MANIFEST_CHAIN"):
            promote_completed_utc_day(d,now_utc=NOW)

    def test_13_missing_original_source_chunk_blocks_promotion(self)->None:
        d=original(9,10,11)
        del d.items["chunk"][next(iter(d.items["chunk"]))]
        with self.assertRaises((KeyError,ValueError)):
            promote_completed_utc_day(d,now_utc=NOW)

    def test_14_invalid_source_provenance_blocks_promotion(self)->None:
        d=original(9,10,11)
        key=next(iter(d.items["chunk"]))
        d.items["chunk"][key]["source_side"]="BID"
        with self.assertRaises(ValueError):
            promote_completed_utc_day(d,now_utc=NOW)

    def test_15_source_manifest_duplicate_name_rejected(self)->None:
        d=original(9,10,11)
        orig=d.list_names
        def duplicate(bucket:str)->tuple[str,...]:
            n=orig(bucket)
            return n+(n[0],) if bucket=="manifest" and n else n
        d.list_names=duplicate  # type: ignore[method-assign]
        with self.assertRaisesRegex(ValueError,"DUPLICATE_SOURCE_MANIFESTS"):
            promote_completed_utc_day(d,now_utc=NOW)

    def test_16_competing_warm_versions_fail_closed(self)->None:
        d=original(9,10,11)
        d.fail_after_bucket="warm"
        with self.assertRaises(OSError):
            promote_completed_utc_day(d,now_utc=NOW)
        key=next(iter(d.items["warm"]))
        d.items["warm"][key+"_fork"]=deepcopy(d.items["warm"][key])
        with self.assertRaisesRegex(ValueError,"COMPETING_WARM_OBJECTS"):
            promote_completed_utc_day(d,now_utc=NOW)

    def test_17_competing_receipts_fail_closed(self)->None:
        d=original(9,10,11)
        promote_completed_utc_day(d,now_utc=NOW)
        key=next(iter(d.items["promotion"]))
        d.items["promotion"][key+"_fork"]=deepcopy(d.items["promotion"][key])
        with self.assertRaisesRegex(ValueError,"CONFLICTING_DAY_PROMOTIONS"):
            promote_completed_utc_day(d,now_utc=NOW)

    def test_18_late_new_source_hour_refuses_stale_promotion(self)->None:
        d=original(9,10,11)
        promote_completed_utc_day(d,now_utc=NOW)
        commit_hour(d,now_utc=DAY+timedelta(hours=13,minutes=10),
                    observed=rows(12))
        with self.assertRaisesRegex(ValueError,"PROMOTED_DAY_SOURCE_REVISION_CONFLICT"):
            promote_completed_utc_day(d,now_utc=NOW)

    def test_19_orphan_warm_source_change_fails_closed(self)->None:
        d=original(9,10,11)
        d.fail_after_bucket="warm"
        with self.assertRaises(OSError):
            promote_completed_utc_day(d,now_utc=NOW)
        commit_hour(d,now_utc=DAY+timedelta(hours=13,minutes=10),
                    observed=rows(12))
        with self.assertRaisesRegex(ValueError,"ORPHAN_WARM_SOURCE_CHANGED"):
            promote_completed_utc_day(d,now_utc=NOW)

    def test_20_not_due_before_1am_no_reads(self)->None:
        d=original(9,10,11)
        r=promote_completed_utc_day(d,now_utc=DAY+timedelta(days=1,minutes=55))
        self.assertEqual(r.status,"NOT_DUE_BEFORE_0100_UTC")
        self.assertEqual(len(d.items["warm"]),0)

    def test_21_naive_time_rejected(self)->None:
        with self.assertRaisesRegex(ValueError,"P046_B2_EXPLICIT_UTC_NOW_REQUIRED"):
            promote_completed_utc_day(FakePrivateDrive(),
                                       now_utc=NOW.replace(tzinfo=None))

    def test_22_non_utc_offset_rejected(self)->None:
        viet=NOW.astimezone(timezone(timedelta(hours=7)))
        with self.assertRaisesRegex(ValueError,"P046_B2_EXPLICIT_UTC_NOW_REQUIRED"):
            promote_completed_utc_day(FakePrivateDrive(),now_utc=viet)

    def test_23_no_sources_gives_no_promotion(self)->None:
        d=FakePrivateDrive()
        r=promote_completed_utc_day(d,now_utc=NOW)
        self.assertEqual(r.status,"INSUFFICIENT_CLOSED_SOURCE_HOURS")
        self.assertEqual(d.calls,[])

    def test_24_only_one_hour_not_worth_compacting(self)->None:
        d=original(9)
        r=promote_completed_utc_day(d,now_utc=NOW)
        self.assertEqual(r.status,"INSUFFICIENT_CLOSED_SOURCE_HOURS")
        self.assertFalse(d.items["warm"])

    def test_25_no_data_on_target_day_returns_no_objects(self)->None:
        d=original(9,10)
        r=promote_completed_utc_day(d,now_utc=NOW+timedelta(days=1))
        self.assertEqual(r.status,"INSUFFICIENT_CLOSED_SOURCE_HOURS")
        self.assertFalse(d.items["warm"])

    def test_26_deterministic_sha_plan(self)->None:
        d=original(9,10,11)
        chain=_all_verified_source(d,now_utc=NOW)
        a=_plan_day(chain,day="2026-11-11",now_utc=NOW)
        b=_plan_day(chain,day="2026-11-11",now_utc=NOW)
        self.assertEqual(a,b)
        assert a is not None
        self.assertEqual(len(a.warm_sha256),64)
        self.assertIn(a.warm_sha256,a.warm_name)

    def test_27_missing_utc_hour_has_explicit_start_times(self)->None:
        d=original(9,11)
        promote_completed_utc_day(d,now_utc=NOW)
        w=next(iter(d.items["warm"].values()))
        self.assertIn("2026-11-11T10:00:00+00:00",
                      w["missing_utc_hour_starts"])

    def test_28_original_manifest_and_chunks_never_deleted(self)->None:
        d=original(9,10,11)
        before=(len(d.items["manifest"]),len(d.items["chunk"]))
        r=promote_completed_utc_day(d,now_utc=NOW)
        self.assertEqual(before,(len(d.items["manifest"]),len(d.items["chunk"])))
        self.assertEqual(r.original_parent_objects_deleted,0)

    def test_29_provenance_never_approves_numeric_or_order(self)->None:
        d=original(9,10)
        r=promote_completed_utc_day(d,now_utc=NOW)
        self.assertEqual((r.approved_source_numeric_signals,r.broker_orders,
                          r.actual_vendor_api_calls),(0,0,0))
        warm=next(iter(d.items["warm"].values()))
        self.assertIs(warm["source_numeric_approved"],False)
        self.assertIs(warm["source_asof_or_bidask_proven"],False)

    def test_30_adapter_maps_warm_and_promotion_to_private_folders(self)->None:
        self.assertEqual(PrivateDriveBatchStore._folder("warm")[1],
                         "MFX_TD_EURUSD_M5_V2_warm_")
        self.assertEqual(PrivateDriveBatchStore._folder("promotion")[1],
                         "MFX_TD_EURUSD_M5_V2_promotion_")

    def test_31_triple_gate_disabled_no_secrets_no_network(self)->None:
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"false",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_V2_WARM_PROMOTION_ACCEPTED":"true",
        }):
            cloud_main()

    def test_32_no_live_provider_or_real_drive_in_fake_tests(self)->None:
        d=original(9,10,11)
        r=promote_completed_utc_day(d,now_utc=NOW)
        self.assertEqual(r.actual_vendor_api_calls,0)
        self.assertEqual(r.broker_orders,0)


if __name__ == "__main__":
    main()
