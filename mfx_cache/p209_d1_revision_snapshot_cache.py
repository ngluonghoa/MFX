"""P209: owner-authorized private revised D1 snapshot cache, never canonical."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from mfx_cache.native_d1_epoch_20261118 import FreshEpochState
from mfx_cache.native_fx_htf import NativeFXBatch
from mfx_cache.p207_p192_d1_disjoint_research_fork import PrivateD1ResearchFork
from mfx_cache.p208_p192_revision_vintage_dryrun import (
    PrivateRevisedD1VintageProposal, verify_disjoint_p192_revision_vintage,
)
from mfx_cache.td_m5_codec import digest
from tools.mfx_native_htf_drive_seal import PrivateNativeDriveStore, MAX_NATIVE_FILES
from tools.run_a04_p45_cloud_twelve_data_cache import CHUNK_FOLDER

SCHEMA = "MFX_P209_REVISED_D1_PRIVATE_SNAPSHOT_V1"
PREFIX = "MFX_P209_EURUSD_D1_20261118_QUARANTINE_V1_chunk_"


class PrivateP209D1Store(PrivateNativeDriveStore):
    """One immutable, self-describing record; no orphan manifest pair."""

    def __init__(self, session: Any) -> None:
        super().__init__(session, symbol="EUR/USD", interval="1day")

    def _bucket(self, bucket: str) -> tuple[str, str]:
        if bucket != "chunk":
            raise ValueError("P209_SNAPSHOT_ONLY")
        return CHUNK_FOLDER, PREFIX


def _utc(value: Any) -> datetime:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P209_EXACT_UTC_OBSERVATION_REQUIRED")
    return value


def _record(core: dict[str, Any], observed: str) -> dict[str, Any]:
    identity = digest(core)
    record = {
        **core, "identity_sha256": identity,
        "first_runner_observed_utc": observed,
    }
    return {**record, "record_sha256": digest(record)}


def _verify_existing(
    value: Any, core: dict[str, Any], now: datetime,
) -> None:
    if type(value) is not dict:
        raise ValueError("P209_RECORD_SCHEMA_INVALID")
    observed = value.get("first_runner_observed_utc")
    if type(observed) is not str:
        raise ValueError("P209_OBSERVATION_CLOCK_INVALID")
    stamp = _utc(datetime.fromisoformat(observed))
    if stamp.isoformat() != observed or stamp > now:
        raise ValueError("P209_OBSERVATION_CLOCK_INVALID")
    if value != _record(core, observed):
        raise ValueError("P209_RECORD_CONTENT_OR_SHA_DRIFT")


def cache_revised_d1_snapshot(
    store: Any, *, proposal: PrivateRevisedD1VintageProposal,
    fork: PrivateD1ResearchFork, state: FreshEpochState,
    refetched: NativeFXBatch, validated_review: dict[str, Any],
    now_utc: datetime,
) -> dict[str, Any]:
    """Revalidate exact P208/P207 input, then seal private raw source only.

    Content identity deliberately excludes the polling clock; repeated
    identical closed rows reuse the original observation. Changes produce
    separate records. Runner observation is NOT publisher first-known.
    No canonical admission, source licence claim or signal permission.
    """
    now = _utc(now_utc)
    verify_disjoint_p192_revision_vintage(
        proposal, fork=fork, state=state, refetched=refetched,
        validated_review=validated_review, now_utc=now,
    )
    rows = [asdict(row) for row in fork.private_source_bars]
    core: dict[str, Any] = {
        "schema": SCHEMA,
        "state": "PRIVATE_QUARANTINE_NOT_CANONICAL",
        "original_manifest_sha256": fork.original_manifest_sha256,
        "original_bar_sha256": fork.original_18nov_bar_sha256,
        "revised_bar_sha256": fork.revised_18nov_bar_sha256,
        "rows": rows,
        "row_sha256": [row.sha256() for row in fork.private_source_bars],
        "owner_cache_collection_authorized": True,
        "vendor_retention_rights_verified": False,
        "publisher_first_known_verified": False,
        "owner_canonical_revision_approved": False,
        "source_admission": False,
        "may_overwrite_canonical": False,
        "may_publish_buy_sell": False,
        "may_trade": False,
        "broker_orders": 0,
    }
    name = PREFIX + digest(core) + ".json"
    names = store.list_names("chunk")
    if (type(names) is not tuple or len(names) > MAX_NATIVE_FILES
            or any(type(item) is not str or not item.startswith(PREFIX)
                   for item in names)
            or len(names) != len(set(names))):
        raise ValueError("P209_SNAPSHOT_LISTING_INVALID")
    created = 0
    if name not in names:
        if len(names) >= MAX_NATIVE_FILES:
            raise ValueError("P209_SNAPSHOT_CAPACITY_REACHED")
        record = _record(core, now.isoformat())
        store.put_if_absent("chunk", name, record)
        created = 1
    observed = store.read("chunk", name)
    _verify_existing(observed, core, now)
    if store.list_names("chunk").count(name) != 1:
        raise ValueError("P209_SNAPSHOT_NOT_SINGLETON")
    if store.read("chunk", name) != observed:
        raise ValueError("P209_SNAPSHOT_READBACK_DRIFT")
    return {
        "schema": SCHEMA,
        "status": "PRIVATE_REVISED_D1_SHA_READBACK_PASS",
        "private_closed_rows": len(rows),
        "new_snapshot_objects": created,
        "owner_cache_collection_authorized": True,
        "vendor_retention_rights_verified": False,
        "publisher_first_known_verified": False,
        "original_p192_sha_preserved": True,
        "canonical_d1_writes": 0,
        "source_admission": False,
        "may_publish_buy_sell": False,
        "provider_requests_added": 0,
        "broker_orders": 0,
        "action": "NO_SIGNAL",
    }
