"""A04/P0.3: inert schema migration, ABI and reversible declaration review.

This is metadata-only offline review; no runtime plugin loading, executable
adapter, schema transformer, Git rollback, market data or trading permission.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from re import fullmatch
from typing import Any

from .a04_adapter_conformance import (
    PortSchema, synthetic_reference_graph, validate_declared_adapter_graph,
)

HEX64 = r"[a-f0-9]{64}"
FIELD = r"[a-z][a-z0-9_]{2,63}"
SCHEMA_LABEL = "MFX_A04_P03_INERT_DECLARED_SCHEMAS_V1"


def _digest(payload: object) -> str:
    return sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _sha(value: object) -> bool:
    return isinstance(value, str) and fullmatch(HEX64, value) is not None


@dataclass(frozen=True, slots=True)
class SchemaClaim:
    """Declared field shape and semantic digest claim; not verified code."""

    schema: PortSchema
    major: int
    minor: int
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    semantic_sha256_claim: str
    may_transform: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.schema, PortSchema):
            raise TypeError("A04P3_TYPED_SCHEMA_REQUIRED")
        if (type(self.major) is not int or self.major < 1
                or type(self.minor) is not int or self.minor < 0):
            raise ValueError("A04P3_INVALID_SCHEMA_VERSION")
        if not _sha(self.semantic_sha256_claim):
            raise ValueError("A04P3_INVALID_SEMANTIC_SHA_CLAIM")
        if (not isinstance(self.required_fields, tuple)
                or not isinstance(self.optional_fields, tuple)):
            raise TypeError("A04P3_IMMUTABLE_FIELD_SHAPES_REQUIRED")
        all_fields = self.required_fields + self.optional_fields
        if (not self.required_fields
                or any(not isinstance(f, str) or
                       fullmatch(FIELD, f) is None for f in all_fields)
                or len(set(all_fields)) != len(all_fields)):
            raise ValueError("A04P3_INVALID_OR_DUPLICATE_FIELDS")
        if (self.required_fields != tuple(sorted(self.required_fields))
                or self.optional_fields != tuple(sorted(self.optional_fields))):
            raise ValueError("A04P3_FIELDS_MUST_BE_CANONICALLY_ORDERED")
        if self.may_transform is not False:
            raise ValueError("A04P3_NO_EXECUTABLE_TRANSFORM")


@dataclass(frozen=True, slots=True)
class ContractSnapshot:
    """An immutable rollback comparison target, NOT deployed Git state."""

    graph_sha256: str
    golden_sha256: str
    schemas: tuple[SchemaClaim, ...]
    project_id: str = "MFX"
    may_activate: bool = False

    def __post_init__(self) -> None:
        if self.project_id != "MFX":
            raise ValueError("A04P3_CROSS_PROJECT_SNAPSHOT")
        if not _sha(self.graph_sha256) or not _sha(self.golden_sha256):
            raise ValueError("A04P3_INVALID_GRAPH_OR_GOLDEN_SHA")
        if (not isinstance(self.schemas, tuple)
                or any(not isinstance(x, SchemaClaim) for x in self.schemas)):
            raise TypeError("A04P3_TYPED_IMMUTABLE_SCHEMAS_REQUIRED")
        names = tuple(x.schema for x in self.schemas)
        if len(self.schemas) != len(PortSchema) or set(names) != set(PortSchema):
            raise ValueError("A04P3_EXACT_FIVE_SCHEMAS_REQUIRED")
        if len(set(names)) != len(names):
            raise ValueError("A04P3_DUPLICATE_SCHEMA")
        if self.may_activate is not False:
            raise ValueError("A04P3_NO_RUNTIME_ACTIVATION")

    @property
    def identity_sha256(self) -> str:
        return _digest(snapshot_payload(self))


def snapshot_payload(snap: ContractSnapshot) -> dict[str, Any]:
    """Order-independent canonical source of identity and JSON replay."""
    return {
        "kind": SCHEMA_LABEL,
        "project_id": snap.project_id,
        "graph_sha256": snap.graph_sha256,
        "golden_sha256": snap.golden_sha256,
        "may_activate": snap.may_activate,
        "schemas": [
            {
                "schema": s.schema.value,
                "major": s.major,
                "minor": s.minor,
                "required_fields": list(s.required_fields),
                "optional_fields": list(s.optional_fields),
                "semantic_sha256_claim": s.semantic_sha256_claim,
                "may_transform": s.may_transform,
            }
            for s in sorted(snap.schemas, key=lambda x: x.schema.value)
        ],
    }


def encode_snapshot(snap: ContractSnapshot) -> bytes:
    if not isinstance(snap, ContractSnapshot):
        raise TypeError("A04P3_TYPED_SNAPSHOT_REQUIRED")
    data = json.dumps(
        snapshot_payload(snap), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")
    if not 0 < len(data) < 12000:
        raise ValueError("A04P3_SNAPSHOT_SIZE_OUT_OF_RANGE")
    return data


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("A04P3_DUPLICATE_SNAPSHOT_JSON_KEY")
        result[key] = value
    return result


def decode_snapshot(data: bytes) -> ContractSnapshot:
    """Bounded no-execution replay, rejects extra fields and duplicate keys."""
    if not isinstance(data, bytes) or not 0 < len(data) < 12000:
        raise ValueError("A04P3_INVALID_SNAPSHOT_BYTES")
    try:
        value = json.loads(
            data.decode("utf-8"), object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("A04P3_NONFINITE_JSON_NUMBER")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("A04P3_MALFORMED_SNAPSHOT_JSON") from exc
    if not isinstance(value, dict) or set(value) != {
        "kind", "project_id", "graph_sha256", "golden_sha256",
        "may_activate", "schemas",
    } or value["kind"] != SCHEMA_LABEL:
        raise ValueError("A04P3_SNAPSHOT_SHAPE_OR_KIND_DRIFT")
    records = value["schemas"]
    if not isinstance(records, list) or len(records) != 5:
        raise ValueError("A04P3_SNAPSHOT_RECORD_COUNT")
    schemas: list[SchemaClaim] = []
    for rec in records:
        if not isinstance(rec, dict) or set(rec) != {
            "schema", "major", "minor", "required_fields", "optional_fields",
            "semantic_sha256_claim", "may_transform",
        }:
            raise ValueError("A04P3_SCHEMA_RECORD_SHAPE_DRIFT")
        if not isinstance(rec["required_fields"], list) or not isinstance(
                rec["optional_fields"], list):
            raise ValueError("A04P3_SCHEMA_FIELD_ARRAY_REQUIRED")
        schemas.append(SchemaClaim(
            PortSchema(rec["schema"]), rec["major"], rec["minor"],
            tuple(rec["required_fields"]), tuple(rec["optional_fields"]),
            rec["semantic_sha256_claim"], rec["may_transform"],
        ))
    result = ContractSnapshot(
        value["graph_sha256"], value["golden_sha256"], tuple(schemas),
        value["project_id"], value["may_activate"],
    )
    if encode_snapshot(result) != data:
        raise ValueError("A04P3_NONCANONICAL_SNAPSHOT_REPLAY")
    return result


@dataclass(frozen=True, slots=True)
class TransitionDecision:
    declaration_reviewable: bool
    exact_noop: bool
    reason: str
    before_sha256: str
    after_sha256: str
    plugin_code_executed: bool = False
    schema_transform_executed: bool = False
    may_activate: bool = False
    may_trade: bool = False


def assess_transition(
    before: ContractSnapshot, after: ContractSnapshot,
) -> TransitionDecision:
    """Allow exactly unchanged or structural-review-only additive optional minor.

    This never makes a proposal executable, approved, or semantically proven.
    """
    if not isinstance(before, ContractSnapshot) or not isinstance(
            after, ContractSnapshot):
        raise TypeError("A04P3_TYPED_SNAPSHOTS_REQUIRED")
    def decision(ok: bool, noop: bool, reason: str) -> TransitionDecision:
        return TransitionDecision(
            ok, noop, reason, before.identity_sha256, after.identity_sha256,
        )

    if before.graph_sha256 != after.graph_sha256:
        return decision(False, False, "A04P3_PLUGIN_GRAPH_OR_ABI_DRIFT")
    if before.golden_sha256 != after.golden_sha256:
        return decision(False, False, "A04P3_FROZEN_GOLDEN_BASELINE_DRIFT")
    base = {s.schema: s for s in before.schemas}
    proposal = {s.schema: s for s in after.schemas}
    changed = False
    for key in sorted(base, key=lambda s: s.value):
        old, new = base[key], proposal[key]
        if old.major != new.major:
            return decision(False, False, "A04P3_SCHEMA_MAJOR_DRIFT")
        if old.semantic_sha256_claim != new.semantic_sha256_claim:
            return decision(False, False, "A04P3_SEMANTIC_CLAIM_DRIFT")
        if new.minor < old.minor:
            return decision(False, False, "A04P3_SCHEMA_MINOR_ANTI_ROLLBACK")
        if new.required_fields != old.required_fields:
            return decision(False, False, "A04P3_REQUIRED_FIELDS_CHANGED")
        if not set(old.optional_fields).issubset(new.optional_fields):
            return decision(False, False, "A04P3_OPTIONAL_FIELD_REMOVED")
        if new.minor == old.minor:
            if new.optional_fields != old.optional_fields:
                return decision(False, False, "A04P3_UNVERSIONED_FIELD_DRIFT")
        else:
            if (new.minor != old.minor + 1
                    or len(new.optional_fields) == len(old.optional_fields)):
                return decision(False, False, "A04P3_NON_ADDITIVE_MINOR")
            changed = True
    return decision(
        True, not changed,
        "A04P3_EXACT_DECLARATION_NOOP" if not changed
        else "A04P3_ADDITIVE_SHAPE_REVIEW_ONLY_NOT_APPROVED",
    )


@dataclass(frozen=True, slots=True)
class RollbackPreflight:
    declaration_rollback_reproducible: bool
    reason: str
    initial_sha256: str
    candidate_sha256: str
    restored_sha256: str
    git_rollback_performed: bool = False
    runtime_reverted: bool = False
    may_activate: bool = False
    may_trade: bool = False


def review_declarative_rollback(
    initial: ContractSnapshot, candidate: ContractSnapshot,
    restored: ContractSnapshot,
) -> RollbackPreflight:
    """Verify byte-equivalent declaration restoration; NO Git write or deploy."""
    if (not isinstance(initial, ContractSnapshot)
            or not isinstance(candidate, ContractSnapshot)
            or not isinstance(restored, ContractSnapshot)):
        raise TypeError("A04P3_TYPED_ROLLBACK_SNAPSHOTS_REQUIRED")
    upgrade = assess_transition(initial, candidate)
    exact = (
        upgrade.declaration_reviewable and not upgrade.exact_noop
        and encode_snapshot(initial) == encode_snapshot(restored)
    )
    return RollbackPreflight(
        exact,
        "A04P3_DECLARATIVE_RESTORE_MATCH_ONLY_NO_GIT_ACTION"
        if exact else "A04P3_DECLARATIVE_RESTORE_BLOCKED",
        initial.identity_sha256, candidate.identity_sha256,
        restored.identity_sha256,
    )


def synthetic_baseline_contracts(
    frozen_graph_sha256: str, frozen_golden_sha256: str,
) -> ContractSnapshot:
    """Five explicitly synthetic ABI v1 fields, NOT actual runtime schemas."""
    registry, ports = synthetic_reference_graph()
    measured = validate_declared_adapter_graph(registry, ports)
    if measured.graph_sha256 != frozen_graph_sha256:
        raise ValueError("A04P3_FROZEN_DECLARED_GRAPH_MISMATCH")
    if not _sha(frozen_golden_sha256):
        raise ValueError("A04P3_FROZEN_GOLDEN_SHA_REQUIRED")
    fields: tuple[tuple[PortSchema, tuple[str, ...], tuple[str, ...]], ...] = (
        (PortSchema.PROVIDER_QUERY_V1,
         ("decision_utc", "instrument_version", "price_basis",
          "rights_policy_ref", "timeframe"), ("review_label",)),
        (PortSchema.PROVIDER_READONLY_UNVERIFIED_V1,
         ("first_known_utc", "price_basis", "quality", "source_revision"),
         ("source_note",)),
        (PortSchema.FEATURES_UNVERIFIED_V1,
         ("asof_utc", "feature_set_id", "quality"), ()),
        (PortSchema.CANDIDATES_UNVERIFIED_V1,
         ("asof_utc", "source_quality", "zone_label"), ()),
        (PortSchema.TP_PROPOSAL_UNVERIFIED_V1,
         ("decision_utc", "reference_only", "risk_schema"), ()),
    )
    return ContractSnapshot(
        frozen_graph_sha256, frozen_golden_sha256,
        tuple(SchemaClaim(
            schema, 1, 0, required, optional,
            sha256(("MFX_SYNTHETIC_SEMANTIC_CLAIM:" + schema.value).encode()).hexdigest(),
        ) for schema, required, optional in fields),
    )


def replace_schema(
    snap: ContractSnapshot, changed: SchemaClaim,
) -> ContractSnapshot:
    if not isinstance(snap, ContractSnapshot) or not isinstance(
            changed, SchemaClaim):
        raise TypeError("A04P3_TYPED_SCHEMA_REPLACEMENT_REQUIRED")
    if changed.schema not in {s.schema for s in snap.schemas}:
        raise ValueError("A04P3_UNKNOWN_SCHEMA_REPLACEMENT")
    return replace(
        snap, schemas=tuple(
            changed if s.schema is changed.schema else s for s in snap.schemas
        ),
    )
