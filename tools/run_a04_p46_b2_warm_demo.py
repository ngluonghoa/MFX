"""P046-B2 CI receipt: fake private Drive WARM promotion (no network)."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from typing import Any

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_batch_commit import PrivateObjectStore, commit_hour
from mfx_cache.v2_warm_promotion import promote_completed_utc_day


class MemoryDrive(PrivateObjectStore):
    def __init__(self)->None:
        self.data: dict[str,dict[str,dict[str,Any]]]={
            "chunk":{},"manifest":{},"warm":{},"promotion":{},
        }

    def list_names(self,bucket:str)->tuple[str,...]:
        return tuple(sorted(self.data[bucket]))

    def read(self,bucket:str,name:str)->dict[str,Any]:
        return deepcopy(self.data[bucket][name])

    def put_if_absent(self,bucket:str,name:str,body:dict[str,Any])->None:
        if name in self.data[bucket] and self.data[bucket][name]!=body:
            raise ValueError("P046_B2_FAKE_DRIVE_IMMUTABLE_CONFLICT")
        self.data[bucket][name]=deepcopy(body)


def main()->None:
    start=datetime(2026,11,11,9,tzinfo=timezone.utc)
    store=MemoryDrive()
    for hour in (0,1,2):
        h=start+timedelta(hours=hour)
        rows=tuple(ClosedM5Bar(
            start_utc=(h+timedelta(minutes=5*i)).isoformat(),
            open="1.10",high="1.20",low="1.00",close="1.15",
        ) for i in range(12))
        outcome=commit_hour(
            store,now_utc=h+timedelta(hours=1,minutes=10),observed=rows,
        )
        if outcome.status!="BATCH_COMMITTED":
            raise RuntimeError("P046_B2_FAKE_ORIGINAL_HOUR_COMMIT_FAILED")
    now=datetime(2026,11,12,1,10,tzinfo=timezone.utc)
    first=promote_completed_utc_day(store,now_utc=now)
    duplicate=promote_completed_utc_day(store,now_utc=now)
    if (first.status!="WARM_PROMOTED"
            or duplicate.status!="ALREADY_PROMOTED"
            or (len(store.data["chunk"]),len(store.data["manifest"]))!=(3,3)
            or (len(store.data["warm"]),len(store.data["promotion"]))!=(1,1)
            or first.original_parent_objects_deleted):
        raise RuntimeError("P046_B2_FAKE_WARM_PROMOTION_CONTRACT_FAILED")
    print("MFX_A04_P46_B2_FAKE_DRIVE_WARM_DAY_PROMOTION_PASS")
    print("MFX_A04_P46_B2_RECEIPT "+json.dumps({
        "dataset":"SYNTHETIC_CLOSED_MID_UTC_NO_VENDOR",
        "historical_hourly_sources_preserved":3,
        "packed_warm_utc_day":first.day_utc,
        "observed_hours":first.source_hour_count,
        "missing_hours_unverified":first.missing_hour_count,
        "warm_objects_added":first.expected_new_drive_objects,
        "idempotent_reuse":duplicate.status,
        "source_chunk_deletions":first.original_parent_objects_deleted,
        "provider_calls":first.actual_vendor_api_calls,
        "real_google_drive_writes":0,
        "source_numeric_signals":0,"broker_orders":0,
        "multi_object_atomic_CAS_proven":False,
        "real_twelve_data_cache_live":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
