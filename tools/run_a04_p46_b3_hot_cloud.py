"""P046-B3 Cloud-only single-object HOT overlay; STAGED and explicitly gated.

One existing Google Drive JSON file is *updated* rather than creating
a new raw chunk/Manifest for every M5 poll. B1 sealed hourly and B2 WARM
remain canonical/auditable; HOT is an untrusted research-only overlay.

Google Drive does not provide the multi-file transactional CAS contract
required for authoritative trading provenance. No broker or live signals.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any

from mfx_cache.td_m5_codec import canonical, digest, parse_closed_utc_m5
from mfx_cache.v3_hot_overlay import (
    HOT_NAME, HotStore, commit_hot, freshness, validate_hot,
)
from tools.run_a04_p45_cloud_twelve_data_cache import (
    MANIFEST_FOLDER, _drive_create, _drive_get, _session, _settings,
    _vendor_m5, _vendor_usage,
)


class DriveHotStore(HotStore):
    """Fixed one-file per-symbol mutable HOT overlay.

    Read/check/readback and GitHub concurrency guard cooperate; this is
    not an atomic Drive if-match/CAS and does not defeat external writers.
    """
    def __init__(self, session: Any) -> None:
        self.session = session
        self._file_id: str | None = None

    def _find_one(self) -> str | None:
        response = self.session.get(
            "https://www.googleapis.com/drive/v3/files",
            params={
                "q": (f"'{MANIFEST_FOLDER}' in parents and "
                      f"name = '{HOT_NAME}' and trashed = false"),
                "pageSize": 100,
                "fields": "nextPageToken,files(id,name,mimeType,parents)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },timeout=45,
        )
        response.raise_for_status()
        data = response.json()
        if (type(data) is not dict
                or not isinstance(data.get("files"),list)
                or data.get("nextPageToken") is not None):
            raise ValueError("P046_B3_HOT_LIST_NOT_COMPLETE")
        matches = data["files"]
        if len(matches)>1:
            raise ValueError("P046_B3_MULTIPLE_HOT_FILE_FORK")
        if not matches:
            self._file_id=None
            return None
        item = matches[0]
        if (type(item) is not dict
                or type(item.get("id")) is not str
                or item.get("name") != HOT_NAME
                or item.get("mimeType") != "application/json"
                or MANIFEST_FOLDER not in item.get("parents",[])):
            raise ValueError("P046_B3_INVALID_HOT_DRIVE_METADATA")
        self._file_id=item["id"]
        return self._file_id

    def load(self)->dict[str,Any]|None:
        ident=self._find_one()
        if ident is None:
            return None
        state=_drive_get(self.session,ident)
        return validate_hot(state,now_utc=datetime.now(timezone.utc))

    def write(self,*,expected:dict[str,Any]|None,
              replacement:dict[str,Any])->None:
        now=datetime.now(timezone.utc)
        validate_hot(replacement,now_utc=now)
        currently=self.load()
        if currently!=expected:
            raise ValueError("P046_B3_HOT_CHANGED_BEFORE_WRITE_NO_CAS")
        if currently is None:
            _drive_create(self.session,MANIFEST_FOLDER,HOT_NAME,replacement)
        else:
            ident=self._file_id
            if ident is None:
                raise ValueError("P046_B3_HOT_EXISTING_ID_MISSING")
            response=self.session.patch(
                "https://www.googleapis.com/upload/drive/v3/files/"+ident,
                params={"uploadType":"media",
                        "supportsAllDrives":"true",
                        "fields":"id,name,mimeType,md5Checksum,version"},
                headers={"Content-Type":"application/json; charset=UTF-8"},
                data=canonical(replacement),timeout=60,
            )
            response.raise_for_status()
        readback=self.load()
        if readback!=replacement:
            raise ValueError("P046_B3_HOT_POSTWRITE_READBACK_FAILED")
        if currently is not None and (
                readback["generation"]!=currently["generation"]+1
                or readback["previous_hot_sha256"]!=digest(currently)):
            raise ValueError("P046_B3_HOT_REPLACEMENT_CHAIN_FAILED")


def main()->None:
    if not all(os.environ.get(k)=="true" for k in (
        "MFX_REAL_CACHE_ENABLED",
        "MFX_V3_HOT_CACHE_ACCEPTED",
        "MFX_TD_ACCOUNT_CACHE_RIGHTS_CONFIRMED",
    )):
        print("MFX_A04_P46_B3_HOT_DISABLED_TRIPLE_GATE")
        return
    api_key,sa,limit_cap=_settings()
    now=datetime.now(timezone.utc)
    store=DriveHotStore(_session(sa))
    current=store.load()
    slot=now.replace(minute=(now.minute//5)*5,
                     second=0,microsecond=0).isoformat()
    if current is not None and current["last_poll_slot_utc"]==slot:
        print("MFX_A04_P46_B3_HOT_ALREADY_CHECKED_THIS_SLOT_NO_API")
        return
    used,limit=_vendor_usage(api_key)
    if used>=min(limit_cap,limit-10):
        print("MFX_A04_P46_B3_HOT_VENDOR_QUOTA_HEADROOM_NO_PRICE_REQUEST")
        return
    payload=_vendor_m5(api_key,bootstrap=False)
    observed=parse_closed_utc_m5(payload,now_utc=now)
    if not observed:
        print("MFX_A04_P46_B3_HOT_NO_CLOSED_VENDOR_M5")
        return
    r=commit_hot(store,observed,now_utc=now)
    latest=store.load()
    quality=(
        freshness(latest,now_utc=datetime.now(timezone.utc)).status
        if latest is not None else "NO_HOT_OVERLAY"
    )
    print(json.dumps({
        "status":r.status, "new_closed_m5":r.new_closed_m5,
        "hot_freshness_status":quality,
        "hot_file_created_at_most_once_per_symbol":True,
        "per_poll_new_immutable_chunk_files":0,
        "sealed_hourly_b1_remains_primary_history":True,
        "real_quote_side":"MID_NOT_EXECUTABLE_BIDASK",
        "source_numeric_signals_approved":0,
        "broker_orders":0,
        "drive_multiwriter_atomic_cas_proven":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
