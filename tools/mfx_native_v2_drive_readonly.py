"""A04/P0.77 -- V2 native H4/D1 Drive GET-only archive adapter (NOT LIVE).

Only a caller-injected GET session can be used. No credentials, CLI,
workflow, Google Drive writes, Twelve Data calls, broker or trading. All
data and tips remain untrusted without an independent external witness.
The active V1 native archive is untouched and still capped at 256.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any

from mfx_cache.td_m5_codec import canonical, digest
from tools.mfx_native_htf_drive_seal import NativeArchiveState
from tools.mfx_native_shard_v2_design import (
    DESIGN_ONLY, NativeV2ShardProposal,
)
from tools.mfx_native_v2_shard_chain import (
    MAX_PAIRS_PER_SHARD, MAX_RESEARCH_SHARDS, V2ReadOnlyAudit,
    V2SealedPair, _context, audit_v2_chain,
)
from tools.run_a04_p45_cloud_twelve_data_cache import (
    CHUNK_FOLDER, MANIFEST_FOLDER, _drive_get,
)

URL = "https://www.googleapis.com/drive/v3/files"
MAX_PAGES = 10
MAX_OBJECT_BYTES = 262144
PAGE_SIZE = 1000
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,160}$")
BASENAME = re.compile(
    r"^MFX_TD_EURUSD_(?:H4|D1)_NATIVE_V2_SHARD[0-9]{6}$"
)


@dataclass(frozen=True, slots=True)
class _DriveObject:
    shard: int
    position: int
    name: str
    file_id: str


@dataclass(frozen=True, slots=True)
class V2DriveReadOnlyReceipt:
    status: str
    symbol: str
    interval: str
    full_supplied_chain_sha_verified: bool
    pair_count: int
    shard_count: int
    last_native_open_label: str
    tip_manifest_sha256: str
    scan_snapshot_unchanged: bool
    independent_external_tail_witness_verified: bool = False
    live_v2_activation_authorized: bool = False
    drive_writes: int = 0
    provider_requests: int = 0
    broker_orders: int = 0


class V2NativeDriveReadOnlyStore:
    """Enumerate/read ONLY exact EUR/USD native V2 shard objects.

    Existing OAuth CHUNK/MANIFEST folder IDs are inherited, but no auth
    is created or scope widened. Google Drive server-side name contains
    is only a discovery filter; local checks enforce exact names, IDs,
    mime, parent, file size, one-to-one index and 10-page bounded scan.
    """

    def __init__(
        self, session: Any, proposal: NativeV2ShardProposal, *,
        shard_capacity: int = MAX_PAIRS_PER_SHARD,
    ) -> None:
        if (type(proposal) is not NativeV2ShardProposal
                or proposal.status != DESIGN_ONLY
                or proposal.symbol != "EUR/USD"
                or proposal.interval not in ("4h", "1day")
                or type(shard_capacity) is not int
                or not 1 <= shard_capacity <= MAX_PAIRS_PER_SHARD):
            raise ValueError("P077_READONLY_SCOPE_OR_CAPACITY_DENIED")
        expected = (
            "MFX_TD_EURUSD_H4_NATIVE_V2_SHARD000001"
            if proposal.interval == "4h" else
            "MFX_TD_EURUSD_D1_NATIVE_V2_SHARD000001"
        )
        if proposal.proposed_v2_scope != expected:
            raise ValueError("P077_READONLY_V2_SCOPE_MISMATCH")
        prefix = expected[:-6]
        if not BASENAME.fullmatch(prefix + "000001"):
            raise ValueError("P077_READONLY_PREFIX_INVALID")
        if not callable(getattr(session, "get", None)):
            raise ValueError("P077_GET_SESSION_REQUIRED")
        self._session = session
        self._proposal = proposal
        self._prefix = prefix
        self._capacity = shard_capacity

    def _folder(self, kind: str) -> str:
        if kind == "chunk":
            return CHUNK_FOLDER
        if kind == "manifest":
            return MANIFEST_FOLDER
        raise ValueError("P077_ONLY_CHUNK_AND_MANIFEST_READS")

    def _pattern(self, kind: str) -> re.Pattern[str]:
        prefix = re.escape(self._prefix)
        stamp = (
            r"[0-9]{8}T[0-9]{4}UTC"
            if self._proposal.interval == "4h" else
            r"[0-9]{8}LOCAL"
        )
        return re.compile(
            rf"^{prefix}(?P<shard>[0-9]{{6}})_{kind}_"
            rf"(?P<position>[0-9]{{4}})_{stamp}_[0-9a-f]{{64}}\.json$"
        )

    def scan(self, kind: str) -> tuple[_DriveObject, ...]:
        folder = self._folder(kind)
        pattern = self._pattern(kind)
        prefix = self._prefix
        seen_names: set[str] = set()
        seen_ids: set[str] = set()
        seen_indices: set[tuple[int, int]] = set()
        records: list[_DriveObject] = []
        token: str | None = None
        seen_tokens: set[str] = set()
        for _ in range(MAX_PAGES):
            params: dict[str, Any] = {
                "q": (
                    f"'{folder}' in parents and name contains "
                    f"'{prefix}' and trashed = false"
                ),
                "pageSize": PAGE_SIZE,
                "fields": (
                    "nextPageToken,files(id,name,mimeType,parents,size)"
                ),
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if token is not None:
                params["pageToken"] = token
            response = self._session.get(
                URL, params=params, timeout=45,
            )
            response.raise_for_status()
            body = response.json()
            if (type(body) is not dict
                    or type(body.get("files")) is not list):
                raise ValueError("P077_BAD_DRIVE_LIST_ENVELOPE")
            for item in body["files"]:
                if (type(item) is not dict
                        or type(item.get("name")) is not str
                        or type(item.get("id")) is not str):
                    raise ValueError("P077_BAD_DRIVE_LIST_ITEM")
                name = item["name"]
                if not name.startswith(prefix):
                    # Ignore unrelated V1 / M5 discovery hits. Google
                    # "contains" is NOT our security namespace boundary.
                    continue
                match = pattern.fullmatch(name)
                if not match:
                    raise ValueError("P077_V2_OBJECT_NAME_MALFORMED")
                shard = int(match["shard"])
                position = int(match["position"])
                index = (shard, position)
                file_id = item["id"]
                if (not 1 <= shard <= MAX_RESEARCH_SHARDS
                        or not 1 <= position <= self._capacity):
                    raise ValueError("P077_V2_SHARD_OR_PAIR_OUT_OF_BOUND")
                if (not ID_PATTERN.fullmatch(file_id)
                        or item.get("mimeType") != "application/json"
                        or item.get("parents") != [folder]
                        or type(item.get("size")) is not str
                        or not item["size"].isdigit()
                        or not 1 <= int(item["size"]) <= MAX_OBJECT_BYTES):
                    raise ValueError("P077_OBJECT_METADATA_UNSAFE")
                if (name in seen_names or file_id in seen_ids
                        or index in seen_indices):
                    raise ValueError("P077_DUPLICATE_NAME_ID_OR_INDEX")
                seen_names.add(name)
                seen_ids.add(file_id)
                seen_indices.add(index)
                records.append(_DriveObject(shard,position,name,file_id))
                if len(records) > self._capacity * MAX_RESEARCH_SHARDS:
                    raise ValueError("P077_OBJECT_COUNT_EXCEEDS_BOUND")
            next_token = body.get("nextPageToken")
            if next_token is None:
                return tuple(sorted(
                    records, key=lambda x:(x.shard,x.position)
                ))
            if (type(next_token) is not str or not next_token
                    or next_token == token
                    or next_token in seen_tokens):
                raise ValueError("P077_REPEATED_OR_INVALID_PAGE_TOKEN")
            seen_tokens.add(next_token)
            token = next_token
        raise ValueError("P077_PAGE_SCAN_LIMIT_EXCEEDED")

    def _load(self, record: _DriveObject) -> dict[str, Any]:
        value = _drive_get(self._session, record.file_id)
        if (type(value) is not dict
                or len(canonical(value)) > MAX_OBJECT_BYTES):
            raise ValueError("P077_OBJECT_CONTENT_NOT_BOUNDED_JSON")
        return value


def audit_v2_native_drive_readonly(
    session: Any, proposal: NativeV2ShardProposal,
    legacy: NativeArchiveState, *,
    expected_v1_manifest_sha256: str,
    expected_v2_tip_sha256: str,
    now_utc: datetime,
    shard_capacity: int = MAX_PAIRS_PER_SHARD,
) -> V2DriveReadOnlyReceipt:
    """Single untrusted GET-only scan with postscan identity verification.

    This routine is NOT wired to a real Cloud workflow. A live V1 archive
    with <256 sealed pairs fails its preflight BEFORE any Drive request.
    A caller-provided V1 state/tip is not an external trusted witness.
    """
    _context(
        proposal,legacy,expected_v1_manifest_sha256=
        expected_v1_manifest_sha256,now_utc=now_utc,
        shard_capacity=shard_capacity,
    )
    store = V2NativeDriveReadOnlyStore(
        session,proposal,shard_capacity=shard_capacity,
    )
    manifests = store.scan("manifest")
    chunks = store.scan("chunk")
    indices_m = tuple((r.shard,r.position) for r in manifests)
    indices_c = tuple((r.shard,r.position) for r in chunks)
    if indices_m != indices_c:
        raise ValueError("P077_MISSING_OR_ORPHAN_V2_PAIR")
    if len(set(r.file_id for r in (*manifests,*chunks))) != 2*len(manifests):
        raise ValueError("P077_REUSED_ID_ACROSS_BUCKETS")
    if len(manifests) > MAX_PAIRS_PER_SHARD * MAX_RESEARCH_SHARDS:
        raise ValueError("P077_TOTAL_NATIVE_V2_CAPACITY_EXCEEDED")
    pairs: list[V2SealedPair] = []
    for chunk,manifest in zip(chunks,manifests):
        c = store._load(chunk)
        m = store._load(manifest)
        pairs.append(V2SealedPair(
            chunk_name=chunk.name,chunk_sha256=digest(c),chunk=c,
            manifest_name=manifest.name,manifest_sha256=digest(m),manifest=m,
        ))
    # Index + ID stability catch a changed enumeration during the audit.
    # This is cooperative read consistency, NOT an atomic Drive snapshot.
    if (store.scan("manifest") != manifests
            or store.scan("chunk") != chunks):
        raise ValueError("P077_READONLY_LIST_CHANGED_DURING_AUDIT")
    receipt: V2ReadOnlyAudit = audit_v2_chain(
        proposal,legacy,
        expected_v1_manifest_sha256=expected_v1_manifest_sha256,
        pairs=tuple(pairs),
        expected_v2_tip_sha256=expected_v2_tip_sha256,
        now_utc=now_utc,shard_capacity=shard_capacity,
    )
    return V2DriveReadOnlyReceipt(
        status="V2_GET_ONLY_SHA_CHECK_NO_REAL_TRUST_OR_ACTIVATION",
        symbol=proposal.symbol,interval=proposal.interval,
        full_supplied_chain_sha_verified=(
            receipt.complete_supplied_chain_sha_verified
        ),
        pair_count=receipt.pair_count,shard_count=receipt.shard_count,
        last_native_open_label=receipt.last_native_open_label,
        tip_manifest_sha256=receipt.latest_manifest_sha256,
        scan_snapshot_unchanged=True,
    )
