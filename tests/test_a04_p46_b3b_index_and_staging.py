"""A04/P0.46-B3-B: sealed SHA index and SYNTHETIC-only Drive staging QA."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import os
from typing import Any
import unittest
from unittest.mock import patch

from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_cache.v2_batch_commit import _make_plan
from mfx_cache.v3_hot_overlay import plan_hot
from mfx_cache.v3_sealed_index import (
    INDEX_NAME, _new_index, _read_index_source, _source, _hour,
    check_hot_against_sealed_index, reconcile_sealed_index,
    validate_index,
)
from mfx_cache.v3_synthetic_drive_stage import (
    SYNTHETIC_SOURCE, execute_two_synthetic_writes, validate_synthetic,
)
from tools.mfx_drive_single_slot import CloudJsonSlot
from tools.run_a04_p46_b3b_cloud_synthetic_probe import main as cloud_stage_main
from tools.run_a04_p46_b3b_index_cloud import main as cloud_index_main

UTC=timezone.utc
START=datetime(2026,11,10,12,tzinfo=UTC)
NOW=START+timedelta(hours=4,minutes=10)
RUN="42826000001"


def hour_rows(hour: int)->tuple[ClosedM5Bar,...]:
    s=START+timedelta(hours=hour)
    return tuple(ClosedM5Bar(
        start_utc=(s+timedelta(minutes=5*i)).isoformat(),
        open="1.10000",high="1.20000",low="1.00000",close="1.15000",
    ) for i in range(12))


class FakeB1:
    def __init__(self)->None:
        self.obj:dict[str,dict[str,dict[str,Any]]]={
            "manifest":{},"chunk":{},
        }
        self.list_calls=0
        self.read_counts={"manifest":0,"chunk":0}

    def list_names(self,bucket:str)->tuple[str,...]:
        self.list_calls+=1
        return tuple(sorted(self.obj[bucket]))

    def read(self,bucket:str,name:str)->dict[str,Any]:
        self.read_counts[bucket]+=1
        return deepcopy(self.obj[bucket][name])

    def put_if_absent(self,bucket:str,name:str,body:dict[str,Any])->None:
        if name in self.obj[bucket] and self.obj[bucket][name]!=body:
            raise ValueError("B3B_FAKE_CANNOT_REPLACE_IMMUTABLE_B1")
        self.obj[bucket][name]=deepcopy(body)

    def append(self,hour:int)->None:
        names=sorted(self.obj["manifest"])
        prev=self.obj["manifest"][names[-1]] if names else None
        source_hour=(START+timedelta(hours=hour)).isoformat()
        plan=_make_plan(
            prev,hour_utc=source_hour,bars=hour_rows(hour),
            now_utc=NOW+timedelta(hours=max(0,hour)),
        )
        self.put_if_absent("chunk",plan.chunk_name,plan.chunk)
        self.put_if_absent("manifest",plan.manifest_name,plan.manifest)


class FakeIndex:
    def __init__(self)->None:
        self.state:dict[str,Any]|None=None
        self.creates=0
        self.updates=0
        self.reads=0
        self.crash_after_write=False
        self.corrupt_readback=False
        self.race_after_first_read=False

    def load(self)->dict[str,Any]|None:
        self.reads+=1
        if self.race_after_first_read and self.reads==2 and self.state:
            self.state["broker_orders"]=1
        value=deepcopy(self.state)
        if self.corrupt_readback and self.creates+self.updates and value:
            value["symbol"]="USD/JPY"
        return value

    def write(self,*,expected:dict[str,Any]|None,
              replacement:dict[str,Any])->None:
        if self.state!=expected:
            raise ValueError("B3B_FAKE_POINTER_CHANGED")
        if self.state is None:
            self.creates+=1
        else:
            self.updates+=1
        self.state=deepcopy(replacement)
        if self.crash_after_write:
            self.crash_after_write=False
            raise OSError("B3B_FAKE_CRASH_AFTER_WRITING_POINTER")


class FakeSynthetic:
    def __init__(self)->None:
        self.value:dict[str,Any]|None=None
        self.creates=0
        self.updates=0
        self.fail_after_first=False
        self.fail_after_second=False
        self.corrupt=False

    def load(self)->dict[str,Any]|None:
        v=deepcopy(self.value)
        if self.corrupt and v is not None:
            v["provider"]="TWELVE_DATA_COMPOSITE_MID"
        return v

    def write(self,*,expected:dict[str,Any]|None,
              replacement:dict[str,Any])->None:
        if self.value!=expected:
            raise ValueError("B3B_FAKE_SYNTHETIC_STALE_WRITER")
        if self.value is None:
            self.creates+=1
        else:
            self.updates+=1
        self.value=deepcopy(replacement)
        if self.fail_after_first and self.creates==1 and self.updates==0:
            self.fail_after_first=False
            raise OSError("B3B_FAKE_AFTER_FIRST_SYNTHETIC_WRITE")
        if self.fail_after_second and self.updates==1:
            self.fail_after_second=False
            raise OSError("B3B_FAKE_AFTER_SECOND_SYNTHETIC_WRITE")


def source2()->FakeB1:
    source=FakeB1()
    source.append(0)
    source.append(1)
    return source


def index2()->tuple[FakeB1,FakeIndex,dict[str,Any]]:
    source=source2()
    ptr=FakeIndex()
    r=reconcile_sealed_index(source,ptr,now_utc=NOW)
    assert r.status=="BOOTSTRAP_INDEX_COMMITTED"
    assert ptr.state is not None
    return source,ptr,deepcopy(ptr.state)


def anchored_hot()->dict[str,Any]:
    start=START+timedelta(hours=1,minutes=30)
    observed=tuple(ClosedM5Bar(
        start_utc=(start+timedelta(minutes=5*i)).isoformat(),
        open="1.10000",high="1.20000",low="1.00000",close="1.15000",
    ) for i in range(16))
    r=plan_hot(None,observed,now_utc=NOW)
    assert r.new_state is not None
    return r.new_state


class P046B3BTests(unittest.TestCase):
    def test_01_full_two_hour_bootstrap_writes_one_index(self)->None:
        src,port,idx=index2()
        self.assertEqual((port.creates,port.updates),(1,0))
        self.assertEqual(idx["source_total_batches"],2)
        self.assertEqual(idx["generation"],1)
        self.assertEqual(idx["index_mode"],"ROOT_FULL_B1_CHAIN_READ")

    def test_02_bootstrap_counts_true_full_scan(self)->None:
        src=source2()
        port=FakeIndex()
        receipt=reconcile_sealed_index(src,port,now_utc=NOW)
        self.assertEqual(receipt.full_history_scans,1)
        self.assertEqual(receipt.broker_orders,0)
        self.assertEqual(receipt.actual_provider_requests,0)

    def test_03_same_B1_hour_is_noop(self)->None:
        src,port,_=index2()
        n=src.list_calls
        r=reconcile_sealed_index(src,port,now_utc=NOW)
        self.assertEqual(r.status,"UNCHANGED_B1_SEALED_INDEX")
        self.assertEqual((port.creates,port.updates),(1,0))
        self.assertEqual(src.list_calls-n,1)

    def test_04_next_B1_hour_advances_without_full_rescan(self)->None:
        src,port,_=index2()
        src.append(2)
        r=reconcile_sealed_index(src,port,now_utc=NOW)
        self.assertEqual(r.status,"NEXT_B1_SEALED_INDEX_COMMITTED")
        self.assertEqual(r.generation,2)
        self.assertEqual(r.full_history_scans,0)
        self.assertEqual((port.creates,port.updates),(1,1))

    def test_05_next_index_has_previous_content_sha(self)->None:
        src,port,prev=index2()
        src.append(2)
        reconcile_sealed_index(src,port,now_utc=NOW)
        assert port.state is not None
        self.assertEqual(port.state["previous_index_sha256"],digest(prev))

    def test_06_b1_hot_guard_reads_two_objects_no_archive_list(self)->None:
        src,_,idx=index2()
        before=src.list_calls
        g=check_hot_against_sealed_index(src,idx,anchored_hot(),
                                         now_utc=NOW)
        self.assertEqual(g.status,"B1_IMMUTABLE_OVERLAP_VERIFIED_RESEARCH_ONLY")
        self.assertEqual(g.overlap_bars,6)
        self.assertEqual(src.list_calls,before)
        self.assertFalse(g.authoritative_signal_allowed)

    def test_07_hot_tamper_matching_self_sha_still_conflicts_B1(self)->None:
        src,_,idx=index2()
        hot=anchored_hot()
        rec=hot["recent_bars"][0]
        rec["close"]="1.17000"
        from mfx_cache.td_m5_codec import digest as sha
        rec["bar_sha256"]=sha({k:rec[k] for k in (
            "start_utc","open","high","low","close",
        )})
        hot["recent_index_sha256"]=sha(hot["recent_bars"])
        with self.assertRaisesRegex(ValueError,"HOT_B1_IMMUTABLE_SOURCE_MISMATCH"):
            check_hot_against_sealed_index(src,idx,hot,now_utc=NOW)

    def test_08_wrong_B1_manifest_payload_denied(self)->None:
        src,_,idx=index2()
        src.obj["manifest"][idx["manifest_name"]]["broker_orders"]=1
        with self.assertRaises(ValueError):
            check_hot_against_sealed_index(src,idx,anchored_hot(),
                                           now_utc=NOW)

    def test_09_missing_B1_chunk_rejected(self)->None:
        src,_,idx=index2()
        del src.obj["chunk"][idx["chunk_name"]]
        with self.assertRaisesRegex(ValueError,"MISSING_SEALED_SOURCE"):
            check_hot_against_sealed_index(src,idx,anchored_hot(),
                                           now_utc=NOW)

    def test_10_mismatched_index_B1_sha_rejected(self)->None:
        src,_,idx=index2()
        idx["manifest_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"INDEX_REFERENCE_MISMATCH"):
            check_hot_against_sealed_index(src,idx,anchored_hot(),
                                           now_utc=NOW)

    def test_11_missing_previous_B1_history_denies_bootstrap(self)->None:
        src=source2()
        del src.obj["manifest"][sorted(src.obj["manifest"])[0]]
        with self.assertRaisesRegex(ValueError,"BOOTSTRAP_B1_CHAIN_BROKEN"):
            reconcile_sealed_index(src,FakeIndex(),now_utc=NOW)

    def test_12_same_hour_B1_fork_denies_bootstrap(self)->None:
        src=source2()
        name=sorted(src.obj["manifest"])[-1]
        src.obj["manifest"][name+"_fork"]=deepcopy(src.obj["manifest"][name])
        with self.assertRaises(ValueError):
            reconcile_sealed_index(src,FakeIndex(),now_utc=NOW)

    def test_13_two_unindexed_hours_fail_closed(self)->None:
        src,port,_=index2()
        src.append(2)
        src.append(3)
        with self.assertRaisesRegex(ValueError,"MULTIPLE_UNINDEXED"):
            reconcile_sealed_index(src,port,now_utc=NOW)

    def test_14_missing_indexed_manifest_in_list(self)->None:
        src,port,idx=index2()
        del src.obj["manifest"][idx["manifest_name"]]
        with self.assertRaises(ValueError):
            reconcile_sealed_index(src,port,now_utc=NOW)

    def test_15_pointer_readback_tamper_blocks_acceptance(self)->None:
        src=source2()
        port=FakeIndex()
        port.corrupt_readback=True
        with self.assertRaisesRegex(ValueError,"POINTER_READBACK_MISMATCH"):
            reconcile_sealed_index(src,port,now_utc=NOW)

    def test_16_pointer_crash_after_write_replay_no_duplicate(self)->None:
        src=source2()
        port=FakeIndex()
        port.crash_after_write=True
        with self.assertRaises(OSError):
            reconcile_sealed_index(src,port,now_utc=NOW)
        r=reconcile_sealed_index(src,port,now_utc=NOW)
        self.assertEqual(r.status,"UNCHANGED_B1_SEALED_INDEX")
        self.assertEqual((port.creates,port.updates),(1,0))

    def test_17_unknown_index_field_denied(self)->None:
        _,_,idx=index2()
        idx["unapproved_release"]=True
        with self.assertRaisesRegex(ValueError,"EXACT_INDEX_SCHEMA_REQUIRED"):
            validate_index(idx,now_utc=NOW)

    def test_18_source_index_broker_elevation_denied(self)->None:
        _,_,idx=index2()
        idx["broker_orders"]=1
        with self.assertRaisesRegex(ValueError,"SOURCE_PROVENANCE_NOT_APPROVAL"):
            validate_index(idx,now_utc=NOW)

    def test_19_index_bad_clock_denied(self)->None:
        _,_,idx=index2()
        idx["index_updated_utc"]=(NOW+timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError,"IMPOSSIBLE_INDEX_CLOCK"):
            validate_index(idx,now_utc=NOW)

    def test_20_index_bad_parent_sha_denied(self)->None:
        _,_,idx=index2()
        idx["source_parent_manifest_sha256"]="bad"
        with self.assertRaisesRegex(ValueError,"INVALID_B1_HASH"):
            validate_index(idx,now_utc=NOW)

    def test_21_generation_1_with_parent_invalid(self)->None:
        _,_,idx=index2()
        idx["previous_index_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"INDEX_PREDECESSOR_INVALID"):
            validate_index(idx,now_utc=NOW)

    def test_22_index_invalid_utc_hour_denied(self)->None:
        _,_,idx=index2()
        idx["source_hour_utc"]="2026-11-10T13:15:00+00:00"
        with self.assertRaisesRegex(ValueError,"NOT_HOUR_ALIGNED"):
            validate_index(idx,now_utc=NOW)

    def test_23_index_incomplete_B1_candle_hour_denied(self)->None:
        src,_,idx=index2()
        source=src.obj["chunk"][idx["chunk_name"]]
        source["bars"][1]["start_utc"]="2026-11-10T13:06:00+00:00"
        with self.assertRaises(ValueError):
            check_hot_against_sealed_index(src,idx,anchored_hot(),
                                           now_utc=NOW)

    def test_24_hot_no_overlap_research_unanchored(self)->None:
        src,_,idx=index2()
        later=NOW+timedelta(hours=6)
        bars=tuple(ClosedM5Bar(
            start_utc=(later-timedelta(hours=1)+timedelta(minutes=5*i)).isoformat(),
            open="1.10000",high="1.20000",low="1.00000",close="1.15000",
        ) for i in range(10))
        x=plan_hot(None,bars,now_utc=later)
        assert x.new_state is not None
        result=check_hot_against_sealed_index(src,idx,x.new_state,
                                              now_utc=later)
        self.assertEqual(result.status,"UNANCHORED_NO_OVERLAPPING_SOURCE_M5")
        self.assertFalse(result.canonical_source_matches)

    def test_25_no_index_and_no_b1_is_noop(self)->None:
        receipt=reconcile_sealed_index(FakeB1(),FakeIndex(),now_utc=NOW)
        self.assertEqual(receipt.status,"NO_SEALED_B1_HOUR")

    def test_26_not_utc_time_rejected(self)->None:
        with self.assertRaisesRegex(ValueError,"EXACT_UTC_REQUIRED"):
            reconcile_sealed_index(FakeB1(),FakeIndex(),
                                   now_utc=NOW.replace(tzinfo=None))

    def test_27_synthetic_two_writes_same_fixture(self)->None:
        p=FakeSynthetic()
        r=execute_two_synthetic_writes(p,now_utc=NOW,run_id=RUN)
        self.assertEqual(r.status,"SYNTHETIC_TWO_WRITES_VERIFIED")
        self.assertEqual((p.creates,p.updates),(1,1))
        self.assertNotEqual(r.first_sha256,r.second_sha256)

    def test_28_synthetic_never_source_provider(self)->None:
        p=FakeSynthetic()
        execute_two_synthetic_writes(p,now_utc=NOW,run_id=RUN)
        assert p.value is not None
        self.assertEqual(p.value["data_kind"],SYNTHETIC_SOURCE)
        self.assertEqual(p.value["provider"],"NONE_SYNTHETIC")
        self.assertEqual(p.value["symbol"],"NONE_SYNTHETIC")
        self.assertIs(p.value["approval_to_trade"],False)

    def test_29_synthetic_replay_already_complete_no_write(self)->None:
        p=FakeSynthetic()
        execute_two_synthetic_writes(p,now_utc=NOW,run_id=RUN)
        r=execute_two_synthetic_writes(
            p,now_utc=NOW+timedelta(minutes=5),run_id=RUN,
        )
        self.assertEqual(r.status,"SYNTHETIC_REPLAY_ALREADY_COMPLETED")
        self.assertEqual((p.creates,p.updates),(1,1))

    def test_30_synthetic_crash_after_first_recovers(self)->None:
        p=FakeSynthetic()
        p.fail_after_first=True
        with self.assertRaisesRegex(OSError,"AFTER_FIRST"):
            execute_two_synthetic_writes(p,now_utc=NOW,run_id=RUN)
        r=execute_two_synthetic_writes(
            p,now_utc=NOW+timedelta(minutes=5),run_id=RUN,
        )
        self.assertEqual(r.status,"SYNTHETIC_RESUMED_AFTER_FIRST_WRITE")
        self.assertEqual((p.creates,p.updates),(1,1))

    def test_31_synthetic_crash_after_second_recovers(self)->None:
        p=FakeSynthetic()
        p.fail_after_second=True
        with self.assertRaisesRegex(OSError,"AFTER_SECOND"):
            execute_two_synthetic_writes(p,now_utc=NOW,run_id=RUN)
        r=execute_two_synthetic_writes(
            p,now_utc=NOW+timedelta(minutes=5),run_id=RUN,
        )
        self.assertEqual(r.status,"SYNTHETIC_REPLAY_ALREADY_COMPLETED")
        self.assertEqual((p.creates,p.updates),(1,1))

    def test_32_synthetic_wrong_run_id_conflict(self)->None:
        p=FakeSynthetic()
        execute_two_synthetic_writes(p,now_utc=NOW,run_id=RUN)
        with self.assertRaisesRegex(ValueError,"STAGING_RUN_ID_CONFLICT"):
            execute_two_synthetic_writes(p,now_utc=NOW,run_id="42")

    def test_33_synthetic_as_price_provider_tamper_rejected(self)->None:
        p=FakeSynthetic()
        execute_two_synthetic_writes(p,now_utc=NOW,run_id=RUN)
        assert p.value is not None
        p.value["provider"]="TWELVE_DATA_COMPOSITE_MID"
        with self.assertRaisesRegex(ValueError,"FIXTURE_CANNOT_IMPERSONATE_PRICE"):
            execute_two_synthetic_writes(p,now_utc=NOW,run_id=RUN)

    def test_34_synthetic_broker_elevation_rejected(self)->None:
        p=FakeSynthetic()
        execute_two_synthetic_writes(p,now_utc=NOW,run_id=RUN)
        assert p.value is not None
        p.value["broker_orders"]=1
        with self.assertRaises(ValueError):
            validate_synthetic(p.value,now_utc=NOW)

    def test_35_synthetic_incomplete_parent_sha_rejected(self)->None:
        p=FakeSynthetic()
        execute_two_synthetic_writes(p,now_utc=NOW,run_id=RUN)
        assert p.value is not None
        p.value["previous_sha256"]="abc"
        with self.assertRaisesRegex(ValueError,"BAD_FIXTURE_PARENT_SHA"):
            validate_synthetic(p.value,now_utc=NOW)

    def test_36_invalid_synthetic_run_non_digits_rejected(self)->None:
        with self.assertRaisesRegex(ValueError,"INVALID_RUN_ID"):
            execute_two_synthetic_writes(
                FakeSynthetic(),now_utc=NOW,run_id="--a",
            )

    def test_37_synthetic_cannot_use_real_forex_price_bars(self)->None:
        p=FakeSynthetic()
        execute_two_synthetic_writes(p,now_utc=NOW,run_id=RUN)
        assert p.value is not None
        p.value["synthetic_values"]=["1.1","1.2","1.3"]
        with self.assertRaisesRegex(ValueError,"SYNTHETIC_INTEGERS_ONLY"):
            validate_synthetic(p.value,now_utc=NOW)

    def test_38_index_manual_activation_no_credentials(self)->None:
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"false",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"false",
            "MFX_B3B_SEALED_INDEX_ACCEPTED":"false",
        }):
            cloud_index_main()

    def test_39_drive_staging_gate_no_credentials(self)->None:
        with patch.dict(os.environ,{
            "MFX_B3B_SYNTHETIC_DRIVE_STAGING_ACCEPTED":"false",
        }):
            cloud_stage_main()

    def test_40_manual_staging_workflow_no_vendor_key(self)->None:
        from pathlib import Path
        txt=Path(".github/workflows/mfx-b3b-synthetic-drive-proof.yml").read_text()
        self.assertIn("workflow_dispatch:",txt)
        self.assertIn("MFX_B3B_SYNTHETIC_DRIVE_STAGING_ACCEPTED",txt)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY",txt)
        self.assertNotIn("cron:",txt)
        self.assertNotIn("MFX_REAL_CACHE_ENABLED",txt)

    def test_41_manual_index_workflow_no_vendor_key(self)->None:
        from pathlib import Path
        txt=Path(".github/workflows/mfx-b3b-sealed-index.yml").read_text()
        self.assertIn("workflow_dispatch:",txt)
        self.assertIn("MFX_B3B_SEALED_INDEX_ACCEPTED",txt)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY",txt)
        self.assertNotIn("cron:",txt)

    def test_42_private_slot_bad_filename_rejected(self)->None:
        with self.assertRaisesRegex(ValueError,"INVALID_SCOPED_JSON_SLOT"):
            CloudJsonSlot(object(),folder_id="f",file_name="../outside.json",
                          validator=lambda v,now: {})

    def test_43_hot_index_always_not_order_authorization(self)->None:
        src,_,idx=index2()
        r=check_hot_against_sealed_index(src,idx,anchored_hot(),
                                         now_utc=NOW)
        self.assertFalse(r.broker_orders_allowed)
        self.assertFalse(r.authoritative_signal_allowed)
        self.assertEqual(r.overlap_bars,6)

    def test_44_source_manifest_older_index_not_claimed_latest(self)->None:
        src,port,idx=index2()
        src.append(2)
        # Without explicit hourly reconciliation, the pointer may be stale:
        # two direct immutable reads prove consistency, NOT latestness.
        r=check_hot_against_sealed_index(src,idx,anchored_hot(),
                                         now_utc=NOW)
        self.assertEqual(r.status,"B1_IMMUTABLE_OVERLAP_VERIFIED_RESEARCH_ONLY")
        self.assertEqual(port.updates,0)

    def test_45_multiple_b1_gap_hours_not_mistaken_for_market_session(self)->None:
        src=FakeB1()
        src.append(0)
        src.append(2)
        port=FakeIndex()
        reconcile_sealed_index(src,port,now_utc=NOW)
        assert port.state is not None
        self.assertEqual(port.state["source_continuity_status"],
                         "MISSING_PRIOR_HOURS_UNVERIFIED")

    def test_46_synthetic_staging_folder_is_mfx_own_staging(self)->None:
        from tools.run_a04_p46_b3b_cloud_synthetic_probe import (
            MFX_STAGING_FOLDER,
        )
        self.assertEqual(
            MFX_STAGING_FOLDER,"1zJaO68XXyCApn5hBEKUqTOj7SU33d2dD",
        )

    def test_47_source_immutable_ids_use_exact_SHA(self)->None:
        src,_,idx=index2()
        self.assertIn(idx["manifest_sha256"],idx["manifest_name"])
        self.assertIn(idx["chunk_sha256"],idx["chunk_name"])
        self.assertIn("EURUSD_M5_V3",INDEX_NAME)

    def test_48_no_live_API_credits_or_file_deletions(self)->None:
        src,_,_=index2()
        p=FakeIndex()
        r=reconcile_sealed_index(src,p,now_utc=NOW)
        self.assertEqual(r.actual_provider_requests,0)
        self.assertEqual(r.original_source_objects_deleted,0)
        self.assertFalse(r.source_numeric_signals_approved)
