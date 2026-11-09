"""A04/P0.1 — inert, typed MFX plugin manifest and provider capability contracts.

CI-only reference scaffolding: this module is NOT in the installed runtime
package, dynamically loads no plugins, performs no I/O, and cannot authorize
real data, production cache, backtest, broker routing or order execution.
The original Forex Trading source and behavior remain frozen.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from json import dumps
from re import fullmatch
from typing import Protocol

from forex_trading.market_data import BarSide, Timeframe


class PluginKind(str, Enum):
    PROVIDER = "PROVIDER"
    DETECTOR = "DETECTOR"
    INDICATOR = "INDICATOR"
    TP_POLICY = "TP_POLICY"


class PriceBasis(str, Enum):
    REFERENCE_OHLC = "REFERENCE_OHLC"
    NATIVE_BID_ASK = "NATIVE_BID_ASK"


class ProbePurpose(str, Enum):
    TECHNICAL_RESEARCH = "TECHNICAL_RESEARCH"
    EXECUTION_REPLAY = "EXECUTION_REPLAY"


def _ident(value: object, label: str) -> str:
    if (not isinstance(value, str)
            or fullmatch(r"[a-zA-Z][a-zA-Z0-9_.-]{2,79}", value) is None):
        raise ValueError("A04_INVALID_NONSECRET_IDENTIFIER:" + label)
    return value


def _claim_digest(value: object) -> str:
    if not isinstance(value, str) or fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("A04_INVALID_DECLARED_SHA256")
    return value


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Untrusted metadata, not an activated module or executable ABI guarantee."""

    plugin_id: str
    kind: PluginKind
    abi_major: int
    implementation_version: str
    implementation_sha256_claim: str
    dependency_ids: tuple[str, ...] = ()
    project_id: str = "MFX"
    may_activate: bool = False

    def __post_init__(self) -> None:
        if self.project_id != "MFX":
            raise ValueError("A04_CROSS_PROJECT_PLUGIN_REJECTED")
        _ident(self.plugin_id, "plugin_id")
        if not isinstance(self.kind, PluginKind):
            raise TypeError("A04_EXPLICIT_TYPED_PLUGIN_KIND_REQUIRED")
        if type(self.abi_major) is not int or self.abi_major < 1:
            raise ValueError("A04_INVALID_ABI_MAJOR")
        if (not isinstance(self.implementation_version, str) or
                fullmatch(r"\d+\.\d+\.\d+", self.implementation_version) is None):
            raise ValueError("A04_INVALID_SEMVER_CLAIM")
        _claim_digest(self.implementation_sha256_claim)
        if (not isinstance(self.dependency_ids, tuple) or
                any(not isinstance(v, str) for v in self.dependency_ids)):
            raise TypeError("A04_IMMUTABLE_DEPENDENCY_IDS_REQUIRED")
        for item in self.dependency_ids:
            _ident(item, "dependency_id")
        if (self.plugin_id in self.dependency_ids or
                len(set(self.dependency_ids)) != len(self.dependency_ids)):
            raise ValueError("A04_SELF_OR_DUPLICATE_DEPENDENCY")
        if self.may_activate is not False:
            raise ValueError("A04_NO_RUNTIME_ACTIVATION_AUTHORITY")

    @property
    def identity_sha256(self) -> str:
        payload = (
            "MFX_A04_PLUGIN_MANIFEST_V1", self.project_id,
            self.plugin_id, self.kind.value, self.abi_major,
            self.implementation_version, self.implementation_sha256_claim,
            tuple(sorted(self.dependency_ids)),
        )
        return sha256(dumps(payload, separators=(",", ":")).encode()).hexdigest()


class PluginDescriptor(Protocol):
    """Future typed declaration only; no loading or execution method."""

    def describe_manifest(self) -> PluginManifest: ...


@dataclass(frozen=True, slots=True)
class PluginRegistry:
    """Pure immutable registry; never imports, instantiates or executes plugins."""

    manifests: tuple[PluginManifest, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.manifests, tuple)
                or any(not isinstance(x, PluginManifest) for x in self.manifests)):
            raise TypeError("A04_TYPED_IMMUTABLE_PLUGIN_MANIFESTS_REQUIRED")
        by_id = {item.plugin_id: item for item in self.manifests}
        if len(by_id) != len(self.manifests):
            raise ValueError("A04_DUPLICATE_PLUGIN_ID")
        for item in self.manifests:
            for dep in item.dependency_ids:
                if dep not in by_id:
                    raise ValueError("A04_UNKNOWN_PLUGIN_DEPENDENCY:" + dep)

        # Validate the *whole* immutable graph, not merely the requested node.
        state: dict[str, int] = {}

        def visit(plugin_id: str) -> None:
            level = state.get(plugin_id, 0)
            if level == 1:
                raise ValueError("A04_PLUGIN_DEPENDENCY_CYCLE")
            if level == 2:
                return
            state[plugin_id] = 1
            for dep in by_id[plugin_id].dependency_ids:
                visit(dep)
            state[plugin_id] = 2

        for plugin_id in sorted(by_id):
            visit(plugin_id)

    @property
    def identity_sha256(self) -> str:
        payload = tuple(sorted(
            (m.plugin_id, m.identity_sha256) for m in self.manifests
        ))
        return sha256(dumps(
            ("MFX_A04_REGISTRY_V1", payload), separators=(",", ":"),
        ).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class DeclaredPluginResolution:
    declared_abi_compatible: bool
    plugin_id: str | None
    reason: str
    may_load_code: bool = False
    may_activate: bool = False


def resolve_declared_plugin(
    registry: PluginRegistry, plugin_id: str,
    expected_kind: PluginKind, required_abi_major: int,
) -> DeclaredPluginResolution:
    """Exact typed manifest match; NEVER silently fall back to another plugin."""
    if not isinstance(registry, PluginRegistry):
        raise TypeError("A04_TYPED_REGISTRY_REQUIRED")
    _ident(plugin_id, "requested_plugin_id")
    if not isinstance(expected_kind, PluginKind):
        raise TypeError("A04_EXPLICIT_TYPED_PLUGIN_KIND_REQUIRED")
    if type(required_abi_major) is not int or required_abi_major < 1:
        raise ValueError("A04_INVALID_REQUIRED_ABI")
    matches = tuple(m for m in registry.manifests if m.plugin_id == plugin_id)
    if not matches:
        return DeclaredPluginResolution(
            False, None, "A04_PLUGIN_NOT_DECLARED_NO_FALLBACK",
        )
    entry = matches[0]
    if entry.kind is not expected_kind:
        return DeclaredPluginResolution(
            False, None, "A04_PLUGIN_KIND_MISMATCH",
        )
    if entry.abi_major != required_abi_major:
        return DeclaredPluginResolution(
            False, None, "A04_PLUGIN_ABI_MISMATCH",
        )
    return DeclaredPluginResolution(
        True, entry.plugin_id, "A04_METADATA_ONLY_NO_ACTIVATION",
    )


@dataclass(frozen=True, slots=True)
class ProviderCapability:
    """Claim of shape support; never a licensed quote or account entitlement."""

    manifest: PluginManifest
    provider_id: str
    product_ref: str
    instrument_version: str
    supported_timeframes: frozenset[Timeframe]
    basis: PriceBasis
    native_sides: frozenset[BarSide]
    calendar_version: str
    timezone_policy: str
    rights_policy_ref: str
    lineage_policy_ref: str
    may_fetch_real_data: bool = False
    may_store_real_data: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, PluginManifest) or (
                self.manifest.kind is not PluginKind.PROVIDER):
            raise TypeError("A04_TYPED_PROVIDER_MANIFEST_REQUIRED")
        for field in (
            "provider_id", "product_ref", "instrument_version",
            "calendar_version", "timezone_policy", "rights_policy_ref",
            "lineage_policy_ref",
        ):
            _ident(getattr(self, field), field)
        if (not isinstance(self.supported_timeframes, frozenset)
                or not self.supported_timeframes
                or any(not isinstance(x, Timeframe) for x in self.supported_timeframes)):
            raise TypeError("A04_TYPED_TIMEFRAME_CAPABILITY_REQUIRED")
        if (not isinstance(self.basis, PriceBasis)
                or not isinstance(self.native_sides, frozenset)
                or any(not isinstance(s, BarSide) for s in self.native_sides)):
            raise TypeError("A04_TYPED_QUOTE_BASIS_REQUIRED")
        if self.basis is PriceBasis.REFERENCE_OHLC:
            # Generic OHLC is NOT MID, BID, ASK, or a broker fill stream.
            if self.native_sides:
                raise ValueError("A04_REFERENCE_OHLC_NOT_BROKER_SIDE")
        elif self.native_sides != frozenset((BarSide.BID, BarSide.ASK)):
            raise ValueError("A04_NATIVE_PAIR_REQUIRES_BOTH_BID_AND_ASK")
        if (self.may_fetch_real_data is not False or
                self.may_store_real_data is not False):
            raise ValueError("A04_NO_REAL_IO_OR_STORAGE_AUTHORITY")


@dataclass(frozen=True, slots=True)
class ProviderProbe:
    """Structural question, not an API request, URL or data acquisition."""

    provider_id: str
    product_ref: str
    instrument_version: str
    timeframe: Timeframe
    basis: PriceBasis
    quote_side: BarSide | None
    calendar_version: str
    timezone_policy: str
    rights_policy_ref: str
    purpose: ProbePurpose = ProbePurpose.TECHNICAL_RESEARCH

    def __post_init__(self) -> None:
        for field in (
            "provider_id", "product_ref", "instrument_version",
            "calendar_version", "timezone_policy", "rights_policy_ref",
        ):
            _ident(getattr(self, field), field)
        if (not isinstance(self.timeframe, Timeframe)
                or not isinstance(self.basis, PriceBasis)
                or not isinstance(self.purpose, ProbePurpose)):
            raise TypeError("A04_TYPED_PROVIDER_PROBE_REQUIRED")
        if self.basis is PriceBasis.REFERENCE_OHLC:
            if self.quote_side is not None:
                raise ValueError("A04_REFERENCE_PROBE_MUST_HAVE_NO_BROKER_SIDE")
        elif not isinstance(self.quote_side, BarSide) or (
                self.quote_side is BarSide.MID):
            raise ValueError("A04_NATIVE_PROBE_NEEDS_BID_OR_ASK")


@dataclass(frozen=True, slots=True)
class ProviderAssessment:
    declared_structure_compatible: bool
    selected_plugin_id: str | None
    reason: str
    rights_independently_verified: bool = False
    may_fetch_real_data: bool = False
    may_cache_real_data: bool = False
    may_run_real_backtest: bool = False
    may_trade: bool = False


def assess_declared_provider(
    registry: PluginRegistry,
    capabilities: tuple[ProviderCapability, ...],
    requested_plugin_id: str,
    probe: ProviderProbe,
    *,
    required_abi_major: int = 1,
) -> ProviderAssessment:
    """Exact provider/product/side/calendar/rights claim match, no fallback.

    Never returns a real entitlement even when all structural fields match.
    Execution replay always fails closed until independent licensed BID/ASK
    and broker-equivalent fills are implemented elsewhere and reviewed.
    """
    if not isinstance(registry, PluginRegistry) or (
            not isinstance(probe, ProviderProbe)):
        raise TypeError("A04_TYPED_REGISTRY_AND_PROBE_REQUIRED")
    if (not isinstance(capabilities, tuple) or
            any(not isinstance(c, ProviderCapability) for c in capabilities)):
        raise TypeError("A04_TYPED_IMMUTABLE_PROVIDER_CAPABILITIES_REQUIRED")
    declared = resolve_declared_plugin(
        registry, requested_plugin_id, PluginKind.PROVIDER, required_abi_major,
    )
    if not declared.declared_abi_compatible:
        return ProviderAssessment(False, None, declared.reason)
    matches = tuple(
        c for c in capabilities if c.manifest.plugin_id == requested_plugin_id
    )
    if not matches:
        return ProviderAssessment(False, None, "A04_PROVIDER_CAPABILITY_MISSING")
    if len(matches) != 1:
        return ProviderAssessment(False, None, "A04_PROVIDER_CAPABILITY_AMBIGUOUS")
    cap = matches[0]
    if (cap.provider_id != probe.provider_id or
            cap.product_ref != probe.product_ref or
            cap.instrument_version != probe.instrument_version):
        return ProviderAssessment(False, None, "A04_PROVIDER_PRODUCT_OR_SYMBOL_MISMATCH")
    if probe.timeframe not in cap.supported_timeframes:
        return ProviderAssessment(False, None, "A04_UNSUPPORTED_TIMEFRAME")
    if cap.basis is not probe.basis or (
            probe.quote_side is not None and
            probe.quote_side not in cap.native_sides):
        return ProviderAssessment(False, None, "A04_QUOTE_BASIS_OR_SIDE_MISMATCH")
    if (probe.calendar_version != cap.calendar_version or
            probe.timezone_policy != cap.timezone_policy or
            probe.rights_policy_ref != cap.rights_policy_ref):
        return ProviderAssessment(False, None, "A04_CALENDAR_TIMEZONE_OR_RIGHTS_DRIFT")
    if probe.purpose is ProbePurpose.EXECUTION_REPLAY:
        return ProviderAssessment(False, None, "A04_EXECUTION_BASIS_UNVERIFIED")
    return ProviderAssessment(
        True, requested_plugin_id,
        "A04_DECLARED_SHAPE_ONLY_EXTERNAL_RIGHTS_UNVERIFIED",
    )
