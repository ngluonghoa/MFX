"""P046-B3-B mandatory hosted no-network Cloud-index and staging demo."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from typing import Any

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_batch_commit import _make_plan
from mfx_cache.v3_sealed_index import reconcile_sealed_index
from mfx_cache.v3_synthetic_drive_stage import execute_two_synthetic_writes


class Source:
    def __init__(self)->None:
        self.data:dict[str,dict[str,dict[str,Any]]]={
            "chunk":{},"manifest":{},
        }
    def list_names(self,bucket:str)->tuple[str,...]:
        return tuple(sorted(self.data[bucket]))
    def read(self,bucket:str,name:str)->dict[str,Any]:
        return deepcopy(self.data[bucket][name])
    def put_if_absent(self,bucket:str,name:str,body:dict[str,Any])->None:
        if name in self.data[bucket] and self.data[bucket][name]!=body:
            raise ValueError("P046_B3B_SOURCE_IMMUTABLE_DENIED")
        self.data[bucket][name]=deepcopy(body)


class Slot:
    def __init__(self)->None:
        self.value:dict[str,Any]|None=None
        self.creates=0
        self.updates=0
    def load(self)->dict[str,Any]|None:
        return deepcopy(self.value)
    def write(self,*,expected:dict[str,Any]|None,
              replacement:dict[str,Any])->None:
        if self.value!=expected:
            raise ValueError("P046_B3B_FAKE_DRIVE_STALE_WRITER")
        if self.value is None:
            self.creates+=1
        else:
            self.updates+=1
        self.value=deepcopy(replacement)


def main()->None:
    utc=timezone.utc
    start=datetime(2026,11,10,12,tzinfo=utc)
    now=datetime(2026,11,10,16,10,tzinfo=utc)
    source=Source()
    prev:dict[str,Any]|None=None
    for n in range(2):
        h=start+timedelta(hours=n)
        bars=tuple(ClosedM5Bar(
            start_utc=(h+timedelta(minutes=5*i)).isoformat(),
            open="1.10000",high="1.20000",low="1.00000",
            close="1.15000",
        ) for i in range(12))
        plan=_make_plan(prev,hour_utc=h.isoformat(),
                        bars=bars,now_utc=now)
        source.put_if_absent("chunk",plan.chunk_name,plan.chunk)
        source.put_if_absent("manifest",plan.manifest_name,plan.manifest)
        prev=plan.manifest
    ptr=Slot()
    first=reconcile_sealed_index(source,ptr,now_utc=now)
    again=reconcile_sealed_index(source,ptr,now_utc=now)
    synthetic=Slot()
    staged=execute_two_synthetic_writes(
        synthetic,now_utc=now,run_id="42826000001",
    )
    replay=execute_two_synthetic_writes(
        synthetic,now_utc=now,run_id="42826000001",
    )
    if (first.status!="BOOTSTRAP_INDEX_COMMITTED"
            or again.status!="UNCHANGED_B1_SEALED_INDEX"
            or staged.file_creates_expected!=1
            or staged.same_file_in_place_updates_expected!=1
            or replay.status!="SYNTHETIC_REPLAY_ALREADY_COMPLETED"
            or (ptr.creates,ptr.updates)!=(1,0)
            or (synthetic.creates,synthetic.updates)!=(1,1)):
        raise RuntimeError("P046_B3B_FAKE_CLOUD_INDEX_OR_REPLAY_FAILED")
    print("MFX_A04_P46_B3B_NO_NETWORK_SEALED_INDEX_AND_SYNTHETIC_PASS")
    print("MFX_A04_P46_B3B_RECEIPT "+json.dumps({
        "mode":"SYNTHETIC_ONLY_NO_REAL_PROVIDER",
        "b1_source_hourly_manifests_verified":2,
        "latest_sealed_hour_utc":first.source_hour_utc,
        "full_chain_bootstrap_scans":first.full_history_scans,
        "index_files_created":ptr.creates,
        "index_files_updated":ptr.updates,
        "synthetic_test_files_created":synthetic.creates,
        "same_file_in_place_updates":synthetic.updates,
        "staging_replay":replay.status,
        "real_google_drive_file_id":None,
        "github_service_account_staging_executed":False,
        "actual_vendor_requests":0,
        "original_source_deletions":0,
        "broker_orders":0,
        "market_signals_authorized":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
