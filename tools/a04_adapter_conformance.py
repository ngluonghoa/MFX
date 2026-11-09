"""A04/P0.2 — inert typed port contracts. Never execute or load plugins.

All inputs and outputs are *declared schema identities* only. No provider,
strategy, indicator, TP calculation, broker, cache, trade or file operation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from json import dumps

from .a04_plugin_contracts import PluginKind, PluginManifest, PluginRegistry


class PortSchema(str, Enum):
    PROVIDER_QUERY_V1 = "PROVIDER_QUERY_V1"
    PROVIDER_READONLY_UNVERIFIED_V1 = "PROVIDER_READONLY_UNVERIFIED_V1"
    FEATURES_UNVERIFIED_V1 = "FEATURES_UNVERIFIED_V1"
    CANDIDATES_UNVERIFIED_V1 = "CANDIDATES_UNVERIFIED_V1"
    TP_PROPOSAL_UNVERIFIED_V1 = "TP_PROPOSAL_UNVERIFIED_V1"


PORT_SIGNATURE: dict[PluginKind, tuple[PortSchema, PortSchema]] = {
    PluginKind.PROVIDER: (
        PortSchema.PROVIDER_QUERY_V1, PortSchema.PROVIDER_READONLY_UNVERIFIED_V1,
    ),
    PluginKind.INDICATOR: (
        PortSchema.PROVIDER_READONLY_UNVERIFIED_V1,
        PortSchema.FEATURES_UNVERIFIED_V1,
    ),
    PluginKind.DETECTOR: (
        PortSchema.FEATURES_UNVERIFIED_V1,
        PortSchema.CANDIDATES_UNVERIFIED_V1,
    ),
    PluginKind.TP_POLICY: (
        PortSchema.CANDIDATES_UNVERIFIED_V1,
        PortSchema.TP_PROPOSAL_UNVERIFIED_V1,
    ),
}


@dataclass(frozen=True, slots=True)
class AdapterPort:
    """An ABI/schema *claim*, not a bound Python callable or implementation."""

    manifest: PluginManifest
    input_schema: PortSchema
    output_schema: PortSchema
    may_invoke: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, PluginManifest):
            raise TypeError("A04P2_TYPED_MANIFEST_REQUIRED")
        if (not isinstance(self.input_schema, PortSchema)
                or not isinstance(self.output_schema, PortSchema)):
            raise TypeError("A04P2_TYPED_PORT_SCHEMAS_REQUIRED")
        if (self.input_schema, self.output_schema) != PORT_SIGNATURE[self.manifest.kind]:
            raise ValueError("A04P2_PORT_SCHEMA_KIND_MISMATCH")
        if self.may_invoke is not False:
            raise ValueError("A04P2_NO_RUNTIME_INVOCATION")


@dataclass(frozen=True, slots=True)
class AdapterGraphReceipt:
    declared_schema_compatible: bool
    graph_sha256: str
    port_count: int
    kinds: tuple[str, ...]
    reason: str
    implementation_sha_verified: bool = False
    any_plugin_executed: bool = False
    may_ingest_real_data: bool = False
    may_deploy_or_trade: bool = False


def validate_declared_adapter_graph(
    registry: PluginRegistry, ports: tuple[AdapterPort, ...],
) -> AdapterGraphReceipt:
    """Validate all four ABI v1 role boundaries; no plugin object is touched."""
    if not isinstance(registry, PluginRegistry):
        raise TypeError("A04P2_TYPED_REGISTRY_REQUIRED")
    if not isinstance(ports, tuple) or any(
            not isinstance(p, AdapterPort) for p in ports):
        raise TypeError("A04P2_IMMUTABLE_TYPED_PORTS_REQUIRED")
    by_id = {x.plugin_id: x for x in registry.manifests}
    provided = {p.manifest.plugin_id: p for p in ports}
    if len(provided) != len(ports):
        raise ValueError("A04P2_DUPLICATE_PORT_ID")
    if set(provided) != set(by_id):
        raise ValueError("A04P2_REGISTRY_PORT_SET_MISMATCH")
    for key, port in provided.items():
        if port.manifest != by_id[key]:
            raise ValueError("A04P2_MANIFEST_IDENTITY_DRIFT")
        if port.manifest.abi_major != 1:
            raise ValueError("A04P2_ABI_MAJOR_UNSUPPORTED")
    kinds = tuple(sorted(x.kind.value for x in registry.manifests))
    if kinds != tuple(sorted(kind.value for kind in PluginKind)):
        raise ValueError("A04P2_EXPECT_EXACT_FOUR_DECLARATIONS")
    # Every consumer must name exactly the one upstream kind and schema.
    upstream = {
        PluginKind.PROVIDER: None,
        PluginKind.INDICATOR: PluginKind.PROVIDER,
        PluginKind.DETECTOR: PluginKind.INDICATOR,
        PluginKind.TP_POLICY: PluginKind.DETECTOR,
    }
    for manifest in registry.manifests:
        prerequisite = upstream[manifest.kind]
        dependencies = manifest.dependency_ids
        if prerequisite is None:
            if dependencies:
                raise ValueError("A04P2_PROVIDER_MUST_BE_ROOT")
        else:
            if len(dependencies) != 1:
                raise ValueError("A04P2_EXACT_UPSTREAM_DEPENDENCY_REQUIRED")
            parent = provided[dependencies[0]]
            if parent.manifest.kind is not prerequisite:
                raise ValueError("A04P2_UPSTREAM_PLUGIN_KIND_MISMATCH")
            if parent.output_schema is not provided[manifest.plugin_id].input_schema:
                raise ValueError("A04P2_UPSTREAM_OUTPUT_INPUT_SCHEMA_DRIFT")
    payload = (
        "MFX_A04_P02_INERT_PORT_GRAPH_V1",
        registry.identity_sha256,
        tuple(sorted((
            p.manifest.plugin_id, p.manifest.identity_sha256,
            p.input_schema.value, p.output_schema.value,
        ) for p in ports)),
    )
    digest = sha256(dumps(payload, separators=(",", ":")).encode("ascii")).hexdigest()
    return AdapterGraphReceipt(
        True, digest, len(ports), kinds, "A04P2_DECLARATIONS_ONLY_NO_RUNTIME",
    )


def synthetic_reference_graph() -> tuple[PluginRegistry, tuple[AdapterPort, ...]]:
    """Four purely synthetic, deterministic CI fixture declarations."""
    provider = PluginManifest(
        "synthetic.provider", PluginKind.PROVIDER, 1, "0.1.0", "a" * 64,
    )
    indicator = PluginManifest(
        "synthetic.indicator", PluginKind.INDICATOR, 1, "0.1.0", "b" * 64,
        (provider.plugin_id,),
    )
    detector = PluginManifest(
        "synthetic.detector", PluginKind.DETECTOR, 1, "0.1.0", "c" * 64,
        (indicator.plugin_id,),
    )
    tp = PluginManifest(
        "synthetic.tp_policy", PluginKind.TP_POLICY, 1, "0.1.0", "d" * 64,
        (detector.plugin_id,),
    )
    manifests = (tp, detector, provider, indicator)
    return (
        PluginRegistry(manifests),
        tuple(AdapterPort(m, *PORT_SIGNATURE[m.kind]) for m in manifests),
    )
