"""P0.174: read-only, source-isolated P0.171 active D1 -> six-frame research.

A *fresh provider* D1 epoch is explicitly owner-selected from 2026-11-11.
This bridge never substitutes original V1 D1 candles for the fresh epoch,
never relaxes the legacy source HOLD, and never publishes BUY/SELL or OHLC.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from mfx_cache.native_d1_fresh_epoch import (
    INCIDENT, _validate_chunk, audit_fresh_epoch,
)
from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.td_m5_codec import digest

MAX_RECENT_CONTEXT = 120

# P0.175 independent trusted GitHub Actions witnesses, NOT fetched from Drive:
# original V1 archive: 43721636644 and 43718134019; fresh owner epoch:
# actual newly fetched writer 43721121364 and independent reader 43721636644.
# The user explicitly retained original V1 history and rooted the replacement
# EUR/USD Sydney D1 epoch at 2026-11-11. Root values MUST remain immutable.
PINNED_ORIGINAL_D1_V1_HEAD_SHA256 = (
    "346ef3e48bec1b33e489d86233b9a5fa200810ef48563367d059ee098978fcae"
)
PINNED_FRESH_D1_20261111_ROOT_SHA256 = (
    "b0c1c2400c9b20a1c6a7e2b411723da15be31940ad101d40aa8423eadddf35e0"
)


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
    if old_v1_manifest_sha256 != PINNED_ORIGINAL_D1_V1_HEAD_SHA256:
        raise ValueError("P175_ARCHIVED_V1_D1_ORIGINAL_TRUST_ANCHOR_CHANGED")
    initial = _snapshot(store)
    state = audit_fresh_epoch(store,origin_v1_sha=old_v1_manifest_sha256)
    if (state.last_manifest is None or state.manifests < 1
            or state.chunks != state.manifests
            or state.orphan_chunk is not None
            or len(initial[0]) != state.chunks
            or len(initial[1]) != state.manifests):
        raise ValueError("P174_ACTIVE_D1_EPOCH_UNSEEDED_OR_UNCOMMITTED")

    # A fully self-consistent replacement Drive history must not pass by
    # recomputing every SHA and parent pointer. Pin the REAL first manifest
    # that GitHub Actions already independently fetched and audited.
    if digest(store.read("manifest",initial[1][0])) != (
            PINNED_FRESH_D1_20261111_ROOT_SHA256):
        raise ValueError("P175_FRESH_D1_ROOT_TRUST_ANCHOR_CHANGED")

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


# P0.176: Owner asked to re-fetch *11 November*, not to throw away all
# independently SHA-verified D1 history before that incident. Preserve the
# original V1 pre-incident prefix, discard its 11 Nov disputed candle, then
# use only genuinely re-fetched P171 candles from 11 Nov onwards. This is
# an in-memory READ-ONLY research context, NOT a new canonical Drive write.
SEAM_VERSION = "MFX_P176_PREINCIDENT_D1_PREFIX_PLUS_P171_FRESH_TAIL_V1"


@dataclass(frozen=True, slots=True)
class ComposedD1ReadOnlyHistory:
    """Never log source OHLC: only SHA-addressed identities/counts."""

    schema: str
    original_v1_head_sha256: str
    active_epoch_head_sha256: str
    last_preincident_label: str
    first_fresh_label: str
    original_v1_preincident_bars_verified: int
    new_epoch_bars_verified_in_context: int
    context_bars_after_120_limit: int
    composition_sha256: str
    batch: NativeFXBatch = field(repr=False, compare=False)
    public_action: str = "NO_SIGNAL"
    source_numeric_rules_approved: bool = False
    publisher_first_known_verified: bool = False
    may_trade: bool = False
    broker_orders: int = 0
    provider_requests: int = 0
    drive_writes: int = 0


def compose_verified_preincident_d1_history(
    original: NativeFXBatch,
    fresh: FreshD1ReadOnlyContext,
    *, original_v1_head_sha256: str,
) -> ComposedD1ReadOnlyHistory:
    """Join independently SHA-audited data without reusing V1 11 Nov OHLC.

    Caller has ALREADY completed full native V1 SHA and P171 full SHA/root
    checks, including the external real GitHub witness and runner as-of.
    The old original archive must have ended ON the disputed 11 Nov date.
    No guess, missing old boundary, backwards time or arbitrary provider.
    """
    if (type(original) is not NativeFXBatch
            or type(fresh) is not FreshD1ReadOnlyContext
            or original_v1_head_sha256 != PINNED_ORIGINAL_D1_V1_HEAD_SHA256
            or fresh.legacy_v1_manifest_sha256 != original_v1_head_sha256
            or original.symbol != "EUR/USD" or original.interval != "1day"
            or original.exchange_timezone != "Australia/Sydney"
            or original.time_reference != "EXCHANGE_LOCAL_SESSION_DATE"
            or original.source != "TWELVE_DATA_COMPOSITE_MID"
            or original.is_provider_native is not True
            or original.vendor_calls_made_by_parser != 0
            or original.google_drive_writes != 0
            or original.confirmed_buy_sell_signals != 0
            or original.broker_orders != 0
            or type(original.closed_bars) is not tuple
            or len(original.closed_bars) < 2
            or fresh.active_source_epoch != "P171_D1_FRESH_20261111"
            or fresh.provider_price_requests != 0 or fresh.drive_writes != 0
            or fresh.broker_orders != 0 or fresh.may_publish_buy_sell):
        raise ValueError("P176_INDEPENDENT_SOURCE_SCOPE_OR_PIN_REQUIRED")

    old = original.closed_bars
    new = fresh.batch.closed_bars
    old_labels = tuple(bar.native_open_label for bar in old)
    new_labels = tuple(bar.native_open_label for bar in new)
    incident = date.fromisoformat(INCIDENT)
    previous_session = (incident - timedelta(days=1)).isoformat()
    if (old_labels != tuple(sorted(set(old_labels)))
            or old_labels[-1] != INCIDENT
            or new_labels != tuple(sorted(set(new_labels)))
            or not new or new_labels[-1] != fresh.last_native_open_label
            or fresh.batch.symbol != "EUR/USD"
            or fresh.batch.interval != "1day"
            or fresh.batch.exchange_timezone != "Australia/Sydney"
            or fresh.batch.time_reference != "EXCHANGE_LOCAL_SESSION_DATE"):
        raise ValueError("P176_OLD_INCIDENT_OR_FRESH_SEQUENCE_MISMATCH")

    # Exactly the old 11 Nov candle is excluded, never silently retained.
    prefix = tuple(bar for bar in old if bar.native_open_label < INCIDENT)
    if (len(prefix) != len(old)-1
            or not prefix or prefix[-1].native_open_label != previous_session
            or new_labels[0] < INCIDENT):
        raise ValueError("P176_PREINCIDENT_BOUNDARY_NOT_PROVEN")

    all_rows = prefix + new
    labels = tuple(bar.native_open_label for bar in all_rows)
    if labels != tuple(sorted(set(labels))):
        raise ValueError("P176_DUPLICATE_OR_NONMONOTONIC_CUTOVER")
    for bar in all_rows:
        if (type(bar) is not NativeFXBar
                or bar.symbol != "EUR/USD" or bar.interval != "1day"
                or bar.time_reference != "EXCHANGE_LOCAL_SESSION_DATE"
                or bar.exchange_timezone != "Australia/Sydney"
                or bar.source != "TWELVE_DATA_COMPOSITE_MID"
                or bar.price_side != "MID"
                or bar.is_provider_native is not True
                or bar.source_numeric_strategy_approved
                or bar.broker_orders != 0):
            raise ValueError("P176_UNTRUSTED_BAR_PROVENANCE")

    selected = tuple(all_rows[-MAX_RECENT_CONTEXT:])
    composite = digest({
        "schema":SEAM_VERSION,
        "old_head_sha256":original_v1_head_sha256,
        "fresh_head_sha256":fresh.epoch_manifest_sha256,
        "old_preincident_label":prefix[-1].native_open_label,
        "new_epoch_first_label":INCIDENT,
        "selected_closed_bars":[asdict(bar) for bar in selected],
    })
    return ComposedD1ReadOnlyHistory(
        schema=SEAM_VERSION,
        original_v1_head_sha256=original_v1_head_sha256,
        active_epoch_head_sha256=fresh.epoch_manifest_sha256,
        last_preincident_label=prefix[-1].native_open_label,
        first_fresh_label=INCIDENT,
        original_v1_preincident_bars_verified=len(prefix),
        new_epoch_bars_verified_in_context=len(new),
        context_bars_after_120_limit=len(selected),
        composition_sha256=composite,
        batch=NativeFXBatch(
            symbol="EUR/USD",interval="1day",
            exchange_timezone="Australia/Sydney",
            time_reference="EXCHANGE_LOCAL_SESSION_DATE",
            closed_bars=selected,incomplete_excluded=0,
        ),
    )
