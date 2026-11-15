"""P0.174: read-only, source-isolated P0.171 active D1 -> six-frame research.

A *fresh provider* D1 epoch is explicitly owner-selected from 2026-11-11.
This bridge never substitutes original V1 D1 candles for the fresh epoch,
never relaxes the legacy source HOLD, and never publishes BUY/SELL or OHLC.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from mfx_cache.native_d1_fresh_epoch import (
    INCIDENT, _validate_chunk, audit_fresh_epoch,
)
from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.td_m5_codec import digest

MAX_RECENT_CONTEXT = 120


class GetOnlyStore(Protocol):
    def list_names(self, bucket: str) -> tuple[str, ...]: ...
    def read(self, bucket: str, name: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class FreshD1ReadOnlyContext:
    """Private OHLC never appears in repr, ordinary JSON or log receipts."""

    epoch_manifest_sha256: str
    legacy_v1_manifest_sha256: str
    epoch_manifest_pairs_full_sha: int
    last_native_open_label: str
    latest_runner_observed_utc: str
    batch: NativeFXBatch = field(repr=False, compare=False)
    active_source_epoch: str = "P171_D1_FRESH_20261111"
    provider_price_requests: int = 0
    drive_writes: int = 0
    broker_orders: int = 0
    may_publish_buy_sell: bool = False


def _snapshot(store: GetOnlyStore) -> tuple[tuple[str, ...], tuple[str, ...]]:
    chunks = store.list_names("chunk")
    manifests = store.list_names("manifest")
    if (type(chunks) is not tuple or type(manifests) is not tuple
            or any(type(name) is not str for name in chunks+manifests)):
        raise ValueError("P174_D1_READONLY_INVALID_LISTING")
    return chunks, manifests


def read_active_d1_epoch(
    store: GetOnlyStore, *, old_v1_manifest_sha256: str,
    asof_utc: datetime,
) -> FreshD1ReadOnlyContext:
    """Full SHA/parent audit, re-decode only fresh rows, repeat snapshot check.

    Caller must first independently SHA-audit the old V1 source archive and
    supply THAT verified manifest SHA, not a user-configurable fake pin.
    """
    if (type(asof_utc) is not datetime or asof_utc.tzinfo is None
            or asof_utc.utcoffset() != timedelta(0)):
        raise ValueError("P174_EXACT_UTC_SOURCE_ASOF_REQUIRED")
    if (not callable(getattr(store,"list_names",None))
            or not callable(getattr(store,"read",None))):
        raise ValueError("P174_GET_ONLY_D1_SOURCE_REQUIRED")
    initial = _snapshot(store)
    state = audit_fresh_epoch(store,origin_v1_sha=old_v1_manifest_sha256)
    if (state.last_manifest is None or state.manifests < 1
            or state.chunks != state.manifests
            or state.orphan_chunk is not None
            or len(initial[0]) != state.chunks
            or len(initial[1]) != state.manifests):
        raise ValueError("P174_ACTIVE_D1_EPOCH_UNSEEDED_OR_UNCOMMITTED")

    rows: list[NativeFXBar] = []
    previous_observation: datetime | None = None
    for name in initial[1]:
        m = store.read("manifest",name)
        if (type(m) is not dict
                or type(m.get("chunk_name")) is not str
                or m["chunk_name"] not in initial[0]):
            raise ValueError("P174_ACTIVE_D1_MANIFEST_OR_CHUNK_DRIFT")
        observed = datetime.fromisoformat(m["first_observed_runner_utc"])
        if (observed > asof_utc or (previous_observation is not None
                                    and observed < previous_observation)):
            raise ValueError("P174_EPOCH_NOT_FIRST_OBSERVED_AT_DECISION")
        previous_observation = observed
        c = store.read("chunk",m["chunk_name"])
        bars = _validate_chunk(c,m["chunk_name"],old_v1_manifest_sha256)
        if m["chunk_sha256"] != digest(c):
            raise ValueError("P174_ACTIVE_D1_RAW_CHUNK_SHA_DRIFT")
        rows.extend(bars)

    labels = tuple(bar.native_open_label for bar in rows)
    if (not rows or labels[0] != INCIDENT
            or labels != tuple(sorted(set(labels)))
            or len(rows) != state.last_manifest["total_closed_bars"]
            or labels[-1] != state.last_manifest["last_native_open_label"]
            or digest(store.read("manifest",initial[1][-1])) !=
                digest(state.last_manifest)
            or _snapshot(store) != initial
            or audit_fresh_epoch(store,origin_v1_sha=old_v1_manifest_sha256)
               != state):
        raise ValueError("P174_ACTIVE_D1_EPOCH_READONLY_SNAPSHOT_DRIFT")

    batch = NativeFXBatch(
        symbol="EUR/USD",interval="1day",
        exchange_timezone="Australia/Sydney",
        time_reference="EXCHANGE_LOCAL_SESSION_DATE",
        closed_bars=tuple(rows[-MAX_RECENT_CONTEXT:]),
        incomplete_excluded=0,
    )
    return FreshD1ReadOnlyContext(
        epoch_manifest_sha256=digest(state.last_manifest),
        legacy_v1_manifest_sha256=old_v1_manifest_sha256,
        epoch_manifest_pairs_full_sha=state.manifests,
        last_native_open_label=labels[-1],
        latest_runner_observed_utc=state.last_manifest["first_observed_runner_utc"],
        batch=batch,
    )
