"""P0.193: GET-only P192 owner-selected D1 source; never splice P171/V1.

Root identity is independently pinned from the real 18-Nov first writer
#44316306054 and subsequent complete Drive SHA audit #44337203165.
Historical parent V1 remains an immutable audit identity, not signal bars.
This cannot authenticate provider publication timestamp, licence, or strategy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from mfx_cache.native_d1_epoch_20261118 import (
    INCIDENT, _validate_chunk, audit_fresh_epoch,
)
from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.td_m5_codec import digest
from mfx_research.p174_active_d1_epoch_reader import (
    PINNED_ORIGINAL_D1_V1_HEAD_SHA256,
)

PINNED_P192_20261118_ROOT_SHA256 = (
    "64c00f878e2ebe1425d9895069e1405d39402e8dc73bb7eacd2ff226e51f09ad"
)
SOURCE_VERSION = "P192_D1_FRESH_20261118"
MAX_D1_RESEARCH_ROWS = 120


class GetOnlyStore(Protocol):
    def list_names(self, bucket: str) -> tuple[str, ...]: ...
    def read(self, bucket: str, name: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class P192D1ReadOnlyContext:
    epoch_manifest_sha256: str
    legacy_v1_manifest_sha256: str
    epoch_manifest_pairs_full_sha: int
    last_native_open_label: str
    latest_runner_observed_utc: str
    verified_new_d1_candles: int
    batch: NativeFXBatch = field(repr=False, compare=False)
    active_source_epoch: str = SOURCE_VERSION
    original_pre_cutoff_d1_rows_in_source: int = 0
    publisher_first_known_verified: bool = False
    provider_account_rights_verified: bool = False
    may_publish_buy_sell: bool = False
    provider_price_requests: int = 0
    drive_writes: int = 0
    broker_orders: int = 0


def _snapshot(store: GetOnlyStore) -> tuple[tuple[str, ...], tuple[str, ...]]:
    chunks = store.list_names("chunk")
    manifests = store.list_names("manifest")
    if (type(chunks) is not tuple or type(manifests) is not tuple
            or chunks != tuple(sorted(set(chunks)))
            or manifests != tuple(sorted(set(manifests)))):
        raise ValueError("P193_OWNER_D1_INVALID_LISTING_OR_DUPLICATE")
    return chunks, manifests


def read_p192_owner_d1_epoch(
    store: GetOnlyStore, *, old_v1_manifest_sha256: str, asof_utc: datetime,
) -> P192D1ReadOnlyContext:
    """Verify real root plus full SHA chain and close/as-of, READ ONLY."""
    if (type(asof_utc) is not datetime or asof_utc.tzinfo is None
            or asof_utc.utcoffset() != timedelta(0)):
        raise ValueError("P193_EXACT_UTC_ASOF_REQUIRED")
    if (not callable(getattr(store,"list_names",None))
            or not callable(getattr(store,"read",None))):
        raise ValueError("P193_GET_ONLY_SOURCE_REQUIRED")
    if old_v1_manifest_sha256 != PINNED_ORIGINAL_D1_V1_HEAD_SHA256:
        raise ValueError("P193_PINNED_ORIGINAL_ARCHIVE_SHA_REQUIRED")
    before = _snapshot(store)
    state = audit_fresh_epoch(store,origin_v1_sha=old_v1_manifest_sha256)
    if (state.last_manifest is None or state.manifests < 1
            or state.manifests != state.chunks
            or state.orphan_chunk is not None
            or len(before[0]) != state.chunks
            or len(before[1]) != state.manifests):
        raise ValueError("P193_P192_ROOT_UNSEALED_OR_MISSING")
    root = store.read("manifest",before[1][0])
    if digest(root) != PINNED_P192_20261118_ROOT_SHA256:
        raise ValueError("P193_REAL_GITHUB_AUDITED_P192_ROOT_SHA_MISMATCH")
    rows: list[NativeFXBar] = []
    last_seen: datetime | None = None
    for name in before[1]:
        manifest=store.read("manifest",name)
        if (type(manifest) is not dict
                or type(manifest.get("chunk_name")) is not str
                or manifest["chunk_name"] not in before[0]):
            raise ValueError("P193_OWNER_D1_MANIFEST_SOURCE_DRIFT")
        try:
            seen=datetime.fromisoformat(manifest["first_observed_runner_utc"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("P193_INVALID_SOURCE_OBSERVED_CLOCK") from exc
        if (seen.tzinfo is None or seen.utcoffset() != timedelta(0)
                or seen > asof_utc
                or (last_seen is not None and seen < last_seen)):
            raise ValueError("P193_SOURCE_NOT_CAUSALLY_OBSERVED_AT_ASOF")
        last_seen=seen
        chunk=store.read("chunk",manifest["chunk_name"])
        if digest(chunk)!=manifest["chunk_sha256"]:
            raise ValueError("P193_PRIVATE_CHUNK_HASH_DRIFT")
        bars=_validate_chunk(
            chunk,manifest["chunk_name"],old_v1_manifest_sha256)
        rows.extend(bars)
    labels=tuple(bar.native_open_label for bar in rows)
    eligible=(asof_utc-timedelta(minutes=2,seconds=15)).astimezone(
        ZoneInfo("Australia/Sydney")).date()-timedelta(days=1)
    if (not rows or labels[0]!=INCIDENT
            or any(label>eligible.isoformat() for label in labels)
            or labels != tuple(sorted(set(labels)))
            or any(label<INCIDENT for label in labels)
            or labels[-1]!=state.last_manifest["last_native_open_label"]
            or len(rows)!=state.last_manifest["total_closed_bars"]
            or any(bar.source_numeric_strategy_approved
                   or bar.broker_orders for bar in rows)
            or _snapshot(store)!=before
            or audit_fresh_epoch(
                store,origin_v1_sha=old_v1_manifest_sha256)!=state):
        raise ValueError("P193_NO_PRE_CUTOFF_OR_SOURCE_SNAPSHOT_DRIFT")
    return P192D1ReadOnlyContext(
        epoch_manifest_sha256=digest(state.last_manifest),
        legacy_v1_manifest_sha256=old_v1_manifest_sha256,
        epoch_manifest_pairs_full_sha=state.manifests,
        last_native_open_label=labels[-1],
        latest_runner_observed_utc=state.last_manifest["first_observed_runner_utc"],
        verified_new_d1_candles=len(rows),
        batch=NativeFXBatch(
            symbol="EUR/USD",interval="1day",
            exchange_timezone="Australia/Sydney",
            time_reference="EXCHANGE_LOCAL_SESSION_DATE",
            closed_bars=tuple(rows[-MAX_D1_RESEARCH_ROWS:]),
            incomplete_excluded=0,
        ),
    )
