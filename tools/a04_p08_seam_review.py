"""A04/P0.8: exact, source-pinned adapter boundary REVIEW; no adapter binding.

Only the seven A04/P0.7 pure reference helpers may be described here.
Existing functions do NOT have the ABI/PortSchema declared for future
plugins. A successful review means a documentation candidate, NOT
schema callable compatibility, an adapter, runtime behavior, or authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tools.a04_adapter_conformance import PORT_SIGNATURE, PortSchema
from tools.a04_plugin_contracts import PluginKind


class ReferenceFunction(str, Enum):
    QUOTE_INDICATIVE = "quotes.indicative_price"
    CLOSED_BAR_GATE = "market_data.evaluate_closed_bar"
    ASOF_REVISION = "market_data.select_asof_revision"
    EMA_FULL = "cache_indicators.ema_full"
    EMA_DIRTY = "cache_indicators.ema_recompute"
    CATALOG_COUNT = "catalog.catalog_counts"
    CATALOG_VALIDATE = "catalog.validate_catalog"


SOURCE_TO_ROLE: dict[ReferenceFunction, PluginKind] = {
    ReferenceFunction.QUOTE_INDICATIVE: PluginKind.PROVIDER,
    ReferenceFunction.CLOSED_BAR_GATE: PluginKind.PROVIDER,
    ReferenceFunction.ASOF_REVISION: PluginKind.PROVIDER,
    ReferenceFunction.EMA_FULL: PluginKind.INDICATOR,
    ReferenceFunction.EMA_DIRTY: PluginKind.INDICATOR,
    ReferenceFunction.CATALOG_COUNT: PluginKind.DETECTOR,
    ReferenceFunction.CATALOG_VALIDATE: PluginKind.DETECTOR,
}

# Intentional: these declarations do not implement P0.2 PortSchema
# input/output, particularly catalog taxonomy is not a signal detector.
PORTS_ARE_FUTURE_DESIGN_TARGETS_ONLY = True


@dataclass(frozen=True, slots=True)
class SourceBindingPins:
    """CI-measured source+golden identities, not vendor rights or code approval."""
    source_digests: dict[str, str]
    symbol_digests: dict[str, str]
    p06_source_graph_sha256: str
    p07_wrapper_case_sha256: str
    frozen_golden_sha256: str
    declared_port_graph_sha256: str


@dataclass(frozen=True, slots=True)
class ProposedSeam:
    """Declaration-only review; every field is an untrusted design claim."""
    reference: ReferenceFunction
    kind: PluginKind
    project_id: str
    plugin_id: str
    abi_major: int
    source_file_sha256: str
    ast_signature_sha256: str
    p07_wrapper_case_sha256: str
    target_input_schema: PortSchema
    target_output_schema: PortSchema
    target_schema_major: int = 1
    target_schema_minor: int = 0
    request_runtime_bind: bool = False
    request_real_feed: bool = False
    request_write_cache: bool = False
    request_trade: bool = False
    request_schema_fallback: bool = False
    request_release: bool = False
    licensed_data_claim: bool = False
    numeric_detector_claim: bool = False
    tp_sl_engine_claim: bool = False
    complete_1to1_runtime_claim: bool = False


@dataclass(frozen=True, slots=True)
class SeamReview:
    source_reference_documentable: bool
    reason: str
    may_construct_runtime_adapter: bool = False
    may_load_plugin: bool = False
    p02_ports_callable_compatible: bool = False
    may_fetch_real_data: bool = False
    may_write_real_cache: bool = False
    numeric_detector_verified: bool = False
    tp_sl_engine_verified: bool = False
    may_release_or_trade: bool = False


def proposal_for(reference: ReferenceFunction, pins: SourceBindingPins) -> ProposedSeam:
    if not isinstance(reference, ReferenceFunction) or not isinstance(
            pins, SourceBindingPins):
        raise TypeError("A04P8_TYPED_REFERENCE_AND_PINS_REQUIRED")
    role = SOURCE_TO_ROLE[reference]
    module, symbol = reference.value.split(".", 1)
    sha = pins.source_digests.get(module + ".py")
    sig = pins.symbol_digests.get(reference.value)
    if not isinstance(sha, str) or not isinstance(sig, str):
        raise ValueError("A04P8_FROZEN_SOURCE_SYMBOL_NOT_ATTESTED")
    input_schema, output_schema = PORT_SIGNATURE[role]
    return ProposedSeam(
        reference, role, "MFX", "synthetic." + role.value.lower(), 1,
        sha, sig, pins.p07_wrapper_case_sha256,
        input_schema, output_schema,
    )


def review_source_seam(proposal: ProposedSeam,
                       pins: SourceBindingPins) -> SeamReview:
    """Never elevate a pure source-reference wrapper into a working plugin."""
    if not isinstance(proposal, ProposedSeam) or not isinstance(
            pins, SourceBindingPins):
        raise TypeError("A04P8_TYPED_SEAM_REVIEW_REQUIRED")

    def deny(reason: str) -> SeamReview:
        return SeamReview(False, reason)

    if (proposal.project_id != "MFX"
            or not isinstance(proposal.reference, ReferenceFunction)
            or not isinstance(proposal.kind, PluginKind)):
        return deny("A04P8_WRONG_PROJECT_OR_REFERENCE")
    if (type(proposal.abi_major) is not int or proposal.abi_major != 1
            or type(proposal.target_schema_major) is not int
            or proposal.target_schema_major != 1
            or type(proposal.target_schema_minor) is not int
            or proposal.target_schema_minor != 0):
        return deny("A04P8_UNREVIEWED_ABI_OR_SCHEMA_VERSION")
    if proposal.kind is not SOURCE_TO_ROLE[proposal.reference]:
        return deny("A04P8_SOURCE_ROLE_MISMATCH")
    if proposal.plugin_id != "synthetic." + proposal.kind.value.lower():
        return deny("A04P8_UNAPPROVED_IMPLEMENTATION_ID")
    if (proposal.target_input_schema, proposal.target_output_schema) != (
            PORT_SIGNATURE[proposal.kind]):
        return deny("A04P8_DECLARED_FUTURE_PORT_MISMATCH")
    module, symbol = proposal.reference.value.split(".", 1)
    source_digest = pins.source_digests.get(module + ".py")
    declared_digest = pins.symbol_digests.get(module + "." + symbol)
    if (not isinstance(source_digest, str)
            or proposal.source_file_sha256 != source_digest
            or not isinstance(declared_digest, str)
            or proposal.ast_signature_sha256 != declared_digest):
        return deny("A04P8_FROZEN_SOURCE_OR_SIGNATURE_DRIFT")
    if (proposal.p07_wrapper_case_sha256
            != pins.p07_wrapper_case_sha256):
        return deny("A04P8_FROZEN_WRAPPER_PARITY_DRIFT")
    if any(flag is not False for flag in (
            proposal.request_runtime_bind, proposal.request_real_feed,
            proposal.request_write_cache, proposal.request_trade,
            proposal.request_schema_fallback, proposal.request_release)):
        return deny("A04P8_FORBIDDEN_RUNTIME_REQUEST")
    if any(flag is not False for flag in (
            proposal.licensed_data_claim, proposal.numeric_detector_claim,
            proposal.tp_sl_engine_claim, proposal.complete_1to1_runtime_claim)):
        return deny("A04P8_UNVERIFIED_EXTERNAL_OR_ECONOMIC_CLAIM")
    if PORTS_ARE_FUTURE_DESIGN_TARGETS_ONLY is not True:
        return deny("A04P8_PORT_AUTHORITY_POLICY_CHANGED")
    return SeamReview(
        True, "A04P8_SOURCE_REFERENCE_DOC_REVIEW_ONLY_PORT_UNIMPLEMENTED",
    )
