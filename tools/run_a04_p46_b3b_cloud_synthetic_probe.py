"""P046-B3-B: manually authorized REAL Drive / SYNTHETIC data test.

No Twelve Data key, HTTP quote requests, FX symbols/prices or brokers.
Uses the existing private MFX-owned STAGING folder (verified metadata),
one run-specific JSON file, two writes to SAME Google file ID, readback
after each write, and retry of a partially completed same GitHub run.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os

from mfx_cache.v3_synthetic_drive_stage import (
    execute_two_synthetic_writes, validate_synthetic,
)
from tools.mfx_drive_single_slot import CloudJsonSlot
from tools.run_a04_p45_cloud_twelve_data_cache import (
    _require_env, _session,
)

MFX_STAGING_FOLDER = "1zJaO68XXyCApn5hBEKUqTOj7SU33d2dD"


def main() -> None:
    if os.environ.get("MFX_B3B_SYNTHETIC_DRIVE_STAGING_ACCEPTED") != "true":
        print("MFX_A04_P46_B3B_REAL_DRIVE_SYNTHETIC_STAGING_DISABLED")
        return
    run_id=_require_env("GITHUB_RUN_ID")
    if not run_id.isdigit() or not 1 <= len(run_id) <= 18:
        raise ValueError("P046_B3B_INVALID_GITHUB_RUN_ID")
    try:
        auth=json.loads(_require_env("MFX_GDRIVE_SERVICE_ACCOUNT_JSON"))
    except (ValueError, TypeError) as exc:
        raise ValueError("P046_B3B_INVALID_CLOUD_DRIVE_JSON") from exc
    if (type(auth) is not dict or auth.get("type")!="service_account"
            or type(auth.get("client_email")) is not str):
        raise ValueError("P046_B3B_DRIVE_SERVICE_ACCOUNT_REQUIRED")
    name="MFX_SYNTHETIC_B3B_DRIVE_REPLAY_RUN_"+run_id+".json"
    store=CloudJsonSlot(
        _session(auth),folder_id=MFX_STAGING_FOLDER,file_name=name,
        validator=lambda v,now: validate_synthetic(v,now_utc=now),
    )
    receipt=execute_two_synthetic_writes(
        store,now_utc=datetime.now(timezone.utc),run_id=run_id,
    )
    file_id=store.file_id
    if file_id is None or not file_id:
        raise ValueError("P046_B3B_NO_DRIVE_ID_AFTER_TWO_WRITES")
    # IMPORTANT: This is an actual verified Drive ID only if the workflow
    # ran successfully, not an artifact of offline Python CI.
    print("MFX_A04_P46_B3B_CLOUD_DRIVE_SYNTHETIC_TWO_WRITE_READBACK_PASS")
    print(json.dumps({
        "status":receipt.status,
        "file_id":file_id,
        "folder_id":MFX_STAGING_FOLDER,
        "first_sha256":receipt.first_sha256,
        "second_sha256":receipt.second_sha256,
        "one_new_file_expected":receipt.file_creates_expected,
        "same_file_overwrite_expected":
            receipt.same_file_in_place_updates_expected,
        "first_readback":receipt.observed_first_readback,
        "second_readback":receipt.observed_second_readback,
        "provider":"NONE_SYNTHETIC",
        "twelve_data_api_calls":0,
        "original_cache_chunks_deleted":0,
        "broker_orders":0,
        "nonmarket_synthetic_probe_only":True,
    },sort_keys=True))


if __name__=="__main__":
    main()
