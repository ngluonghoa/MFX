"""L1–L5 minimal dependency closure and cache fingerprint contracts (synthetic).

L1 candles -> L2 features -> L3 structure -> L4 signals -> L5 audit/history.
Explicit per-pair, side, timeframe edges avoid unrelated-pair invalidation.
No real persistent storage, source entitlement, or trade authorization here.
"""
from dataclasses import dataclass
from enum import IntEnum
from hashlib import sha256
from json import dumps


class CacheLayer(IntEnum):
    L1_MARKET = 1
    L2_INDICATORS = 2
    L3_STRUCTURE = 3
    L4_SIGNALS = 4
    L5_REPORT = 5


@dataclass(frozen=True, slots=True)
class CacheNode:
    node_id: str
    layer: CacheLayer
    partition_fingerprint: str
    algorithm_version: str
    parameters_version: str
    parents: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in ("node_id", "partition_fingerprint",
                      "algorithm_version", "parameters_version"):
            val = getattr(self, field)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{field} required")
        if not isinstance(self.layer, CacheLayer):
            raise TypeError("Explicit L1..L5 cache layer required")
        if not isinstance(self.parents, tuple) or any(
            not isinstance(p, str) or not p for p in self.parents
        ):
            raise TypeError("Parents must be immutable IDs")
        if self.node_id in self.parents or len(set(self.parents)) != len(self.parents):
            raise ValueError("Self/duplicate dependencies rejected")


def validate_cache_dag(nodes: tuple[CacheNode, ...]) -> None:
    if not isinstance(nodes, tuple) or any(not isinstance(n, CacheNode) for n in nodes):
        raise TypeError("Immutable typed nodes required")
    by_id = {n.node_id: n for n in nodes}
    if len(by_id) != len(nodes):
        raise ValueError("DUPLICATE_NODE_ID")
    for node in nodes:
        for parent_id in node.parents:
            parent = by_id.get(parent_id)
            if parent is None:
                raise ValueError("MISSING_DEPENDENCY_NODE")
            if parent.layer >= node.layer:
                raise ValueError("INVALID_LAYER_DEPENDENCY_ORDER")
    # Strictly increasing layer number makes cycles impossible.


def dirty_dependency_closure(
    nodes: tuple[CacheNode, ...], changed: tuple[str, ...]
) -> tuple[str, ...]:
    """Only invalidate explicit descendants, not every symbol or timeframe."""
    validate_cache_dag(nodes)
    if not isinstance(changed, tuple) or any(not isinstance(v, str) for v in changed):
        raise TypeError("Changed node IDs must be immutable tuple")
    by_id = {n.node_id: n for n in nodes}
    if any(id_ not in by_id for id_ in changed):
        raise ValueError("UNKNOWN_CHANGED_NODE")
    affected = set(changed)
    # Iterate by strictly increasing layer number; dependencies only earlier.
    ordered = sorted(nodes, key=lambda n: (n.layer, n.node_id))
    for node in ordered:
        if any(p in affected for p in node.parents):
            affected.add(node.node_id)
    return tuple(n.node_id for n in ordered if n.node_id in affected)


@dataclass(frozen=True, slots=True)
class CacheArtifactFingerprint:
    node: CacheNode
    input_fingerprint: str
    dependency_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.node, CacheNode) or not isinstance(
            self.dependency_fingerprints, tuple
        ):
            raise TypeError("Typed node and immutable dependency fingerprints required")
        for field in (self.input_fingerprint, *self.dependency_fingerprints):
            if not isinstance(field, str) or not field.strip():
                raise ValueError("All input and dependency digests required")
        if len(self.dependency_fingerprints) != len(self.node.parents):
            raise ValueError("DEPENDENCY_FINGERPRINT_COUNT_MISMATCH")

    @property
    def digest(self) -> str:
        payload = (
            self.node.node_id, int(self.node.layer),
            self.node.partition_fingerprint, self.node.algorithm_version,
            self.node.parameters_version, self.input_fingerprint,
            tuple(zip(self.node.parents, self.dependency_fingerprints)),
        )
        return sha256(dumps(payload, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ReuseAssessment:
    value_reusable: bool
    audit_stage_revalidation_required: bool
    production_authorized: bool
    reason: str


def assess_artifact_reuse(
    previous: CacheArtifactFingerprint,
    candidate: CacheArtifactFingerprint,
    *,
    previous_complete: bool,
    source_unchanged_independently_verified: bool,
) -> ReuseAssessment:
    """A matching digest alone does not prove freshness, entitlement, or 8/8 QA."""
    if not isinstance(previous, CacheArtifactFingerprint) or not isinstance(
        candidate, CacheArtifactFingerprint
    ):
        raise TypeError("Expected cache fingerprint")
    if type(previous_complete) is not bool or type(
        source_unchanged_independently_verified
    ) is not bool:
        raise TypeError("Explicit quality flags required")
    valid = (
        previous.digest == candidate.digest
        and previous_complete
        and source_unchanged_independently_verified
    )
    return ReuseAssessment(
        valid, True, False,
        "SYNTHETIC_REUSE_CANDIDATE_REVERIFY_AUDIT" if valid
        else "DIRTY_STALE_OR_UNVERIFIED_DEPENDENCY",
    )
