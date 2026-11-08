"""P2.1-B: in-memory synthetic Drive cache store only.

This is not Google Drive IO, market-data authorization, source custody,
encryption, cross-process atomicity, broker execution or production persistence.
All snapshots and manifest generations exist solely inside this Python process.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
from re import fullmatch

from .cache_core import CandleSnapshot
from .cache_storage_review import (
    SyntheticGenerationManifest, make_synthetic_generation,
    validate_synthetic_generation_chain,
)
from .quotes import ensure_utc


class SyntheticCacheAction(str, Enum):
    BOOTSTRAP = "BOOTSTRAP"
    DELTA_COMMITTED = "DELTA_COMMITTED"
    REUSE_UNCHANGED = "REUSE_UNCHANGED"


@dataclass(frozen=True, slots=True)
class SyntheticChunk:
    """Chunk and snapshot content exist ONLY inside this in-memory test process."""
    name: str
    snapshot: CandleSnapshot
    partition_fingerprint: str
    snapshot_fingerprint: str


class SyntheticDriveCacheStaging:
    """Deterministic metadata+in-memory chunks, *not* Google Drive IO.

    The root folder ID is a configuration pointer only. Each partition has an
    independent active generation and append-only history; publishing a new
    generation never overwrites another pair. No metadata-only pointer can
    establish a trusted anti-rollback witness or a distributed lock.
    """

    def __init__(self, root_folder_id: str):
        if not isinstance(root_folder_id, str) or not fullmatch(
            r"[A-Za-z0-9_-]{10,128}", root_folder_id
        ):
            raise ValueError("INVALID_DRIVE_FOLDER_REFERENCE")
        self.root_folder_id = root_folder_id
        self._chunks: dict[str, SyntheticChunk] = {}
        self._histories: dict[str, list[SyntheticGenerationManifest]] = {}
        self._active_names: dict[str, str] = {}
        self._active_digests: dict[str, str] = {}
        self.read_partition_ids: list[str] = []
        self.write_partition_ids: list[str] = []

    @property
    def partition_count(self) -> int:
        return len(self._active_names)

    @property
    def simulated_chunk_count(self) -> int:
        return len(self._chunks)

    def manifest_history(self, fingerprint: str) -> tuple[SyntheticGenerationManifest, ...]:
        return tuple(self._histories.get(fingerprint, ()))

    def load(self, partition_fingerprint: str) -> CandleSnapshot | None:
        if not isinstance(partition_fingerprint, str) or not fullmatch(
            r"[a-f0-9]{64}", partition_fingerprint
        ):
            raise ValueError("INVALID_PARTITION_FINGERPRINT")
        self.read_partition_ids.append(partition_fingerprint)
        name = self._active_names.get(partition_fingerprint)
        if name is None:
            return None
        history = self._histories.get(partition_fingerprint, ())
        if not history or self._active_digests.get(partition_fingerprint) != history[-1].manifest_sha256:
            raise ValueError("SIMULATED_ACTIVE_POINTER_OR_HISTORY_CORRUPT")
        for i, manifest in enumerate(history):
            validate_synthetic_generation_chain(
                manifest, history[i - 1] if i else None
            )
        chunk = self._chunks.get(name)
        if chunk is None or (
            chunk.partition_fingerprint != partition_fingerprint
            or chunk.snapshot_fingerprint != history[-1].cache_fingerprint
            or chunk.snapshot.fingerprint != chunk.snapshot_fingerprint
            or chunk.name != name
        ):
            raise ValueError("SIMULATED_CHUNK_MISSING_OR_CORRUPT")
        return chunk.snapshot

    def stage_and_commit(
        self, snapshot: CandleSnapshot, now_utc: datetime,
        *, expected_active_sha256: str | None,
        inject_crash_before_publish: bool = False,
    ) -> bool:
        """Simulated append-only chunk + manifest, then pointer publication.

        expected_active_sha256 is an in-memory optimistic-concurrency check,
        NOT a Drive API CAS guarantee. An orphan staged chunk is not active.
        """
        if not isinstance(snapshot, CandleSnapshot):
            raise TypeError("Typed CandleSnapshot required")
        ensure_utc(now_utc, "now_utc")
        if type(inject_crash_before_publish) is not bool:
            raise TypeError("inject_crash_before_publish must be bool")
        part = snapshot.partition.fingerprint
        current = self._active_digests.get(part)
        if current != expected_active_sha256:
            raise ValueError("SIMULATED_STALE_GENERATION_CONFLICT")
        prev = self._histories[part][-1] if current else None
        if prev is not None and prev.cache_fingerprint == snapshot.fingerprint:
            return False  # no new price data; retain validated immutable chunk

        name = "partitions/" + part + "/chunks/" + sha256(
            (part + ":" + snapshot.fingerprint).encode("ascii")
        ).hexdigest() + ".synthetic"
        chunk = SyntheticChunk(name, snapshot, part, snapshot.fingerprint)
        previous_at_name = self._chunks.get(name)
        if previous_at_name is not None and previous_at_name != chunk:
            # Same name+digest must not change content.
            if (previous_at_name.snapshot.fingerprint != snapshot.fingerprint
                or previous_at_name.partition_fingerprint != part):
                raise ValueError("SYNTHETIC_CONTENT_ADDRESS_COLLISION")
        else:
            self._chunks[name] = chunk
        new = make_synthetic_generation(snapshot, now_utc, prev)
        if inject_crash_before_publish:
            # Orphan chunk exists but neither manifest nor pointer changed.
            raise RuntimeError("SIMULATED_CRASH_BEFORE_PUBLISH")
        # Single-process metadata state update; not actual distributed atomicity.
        self._histories.setdefault(part, []).append(new)
        self._active_names[part] = name
        self._active_digests[part] = new.manifest_sha256
        self.write_partition_ids.append(part)
        return True

    def simulate_corrupt_active_chunk_for_test(self, fingerprint: str) -> None:
        """Negative-path fixture only: deliberately delete referenced chunk."""
        name = self._active_names.get(fingerprint)
        if name is None:
            raise ValueError("NO_ACTIVE_CHUNK_TO_CORRUPT")
        self._chunks.pop(name, None)
