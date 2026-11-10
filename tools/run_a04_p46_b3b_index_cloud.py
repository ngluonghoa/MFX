"""P046-B3-B manual Cloud B1 latest sealed index reconciliation.

GitHub service-account only, never invokes Twelve Data. B1 originals
remain immutable. A fixed mutable index is a bounded lookup hint, NOT a
signed B1 history witness or atomic Google Drive compare-and-swap.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os

from mfx_cache.v3_sealed_index import (
    INDEX_NAME, reconcile_sealed_index, validate_index,
)
from tools.mfx_drive_single_slot import CloudJsonSlot
from tools.run_a04_p45_cloud_twelve_data_cache import (
    MANIFEST_FOLDER, _require_env, _session,
)
from tools.run_a04_p46_cloud_batch_cache import PrivateDriveBatchStore


def main() -> None:
    if not all(os.environ.get(flag)=="true" for flag in (
        "MFX_REAL_CACHE_ENABLED",
        "MFX_V2_BATCH_CACHE_ACCEPTED",
        "MFX_B3B_SEALED_INDEX_ACCEPTED",
    )):
        print("MFX_A04_P46_B3B_SEALED_INDEX_DISABLED_TRIPLE_GATE")
        return
    try:
        credentials=json.loads(_require_env("MFX_GDRIVE_SERVICE_ACCOUNT_JSON"))
    except (ValueError, TypeError) as exc:
        raise ValueError("P046_B3B_INVALID_PRIVATE_DRIVE_JSON") from exc
    if (type(credentials) is not dict
            or credentials.get("type")!="service_account"
            or type(credentials.get("client_email")) is not str):
        raise ValueError("P046_B3B_PRIVATE_DRIVE_SERVICE_ACCOUNT_REQUIRED")
    session=_session(credentials)
    source=PrivateDriveBatchStore(session)
    pointer=CloudJsonSlot(
        session,folder_id=MANIFEST_FOLDER,file_name=INDEX_NAME,
        validator=lambda x,now: validate_index(x,now_utc=now),
    )
    receipt=reconcile_sealed_index(
        source,pointer,now_utc=datetime.now(timezone.utc),
    )
    print(json.dumps({
        "status":receipt.status,
        "b1_sealed_hour_utc":receipt.source_hour_utc,
        "index_generation":receipt.generation,
        "source_manifest_reads":receipt.verified_manifest_reads,
        "source_chunk_reads":receipt.verified_chunk_reads,
        "full_history_bootstrap_scans":receipt.full_history_scans,
        "new_index_files_expected":receipt.new_index_file_expected,
        "inplace_index_updates_expected":receipt.index_updates_expected,
        "provider_requests":receipt.actual_provider_requests,
        "raw_source_objects_deleted":receipt.original_source_objects_deleted,
        "broker_orders":receipt.broker_orders,
        "index_is_mutable_not_independent_CAS":True,
        "live_market_buy_sell_authorized":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
