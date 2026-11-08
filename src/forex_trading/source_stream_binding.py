"""P2.2-A: read-only, SYNTHETIC-ONLY declared Forex source-stream binding.

This validates consistency of a caller-supplied typed cache snapshot against
a caller-supplied stream/product mapping claim. Matching strings are NOT an
independent vendor, broker-product, licence or timestamp attestation.
No source IO, cache mutation, persistence or trade permission is available.
"""
from dataclasses import dataclass
from datetime import datetime

from .cache_core import CandleSnapshot
from .market_data import BarSide, Timeframe
from .quotes import ensure_utc


def _label(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")


@dataclass(frozen=True, slots=True)
class SourceStreamBinding:
    """Opaque *declared* mapping; product entitlement is NOT verified here."""

    provider_id: str
    broker_product_ref: str
    instrument_version: str
    side: BarSide
    timeframe: Timeframe
    calendar_version: str
    aggregation_version: str
    source_timezone_policy: str
    rights_policy_ref: str
    schema_version: str
    stream_id: str
    endpoint: str
    license_scope_claim: str
    product_mapping_claim_ref: str

    def __post_init__(self) -> None:
        for name in (
            "provider_id", "broker_product_ref", "instrument_version",
            "calendar_version", "aggregation_version",
            "source_timezone_policy", "rights_policy_ref", "schema_version",
            "stream_id", "endpoint", "license_scope_claim",
            "product_mapping_claim_ref",
        ):
            _label(getattr(self, name), name)
        if not isinstance(self.side, BarSide) or not isinstance(
            self.timeframe, Timeframe
        ):
            raise TypeError("TYPED_SOURCE_SIDE_AND_TIMEFRAME_REQUIRED")
        # A claim reference is an opaque non-secret marker, never a token/URL.
        if any(x in self.product_mapping_claim_ref for x in ("@", "://", "\n", "\r")):
            raise ValueError("NONSECRET_PRODUCT_MAPPING_REFERENCE_REQUIRED")


@dataclass(frozen=True, slots=True)
class StreamBindingReview:
    """Read-only consistency result; NEVER an authorization to use real data."""

    declared_metadata_consistent: bool
    reason: str
    examined_bars: int
    partition_fingerprint: str | None
    mapping_independently_verified: bool = False
    vendor_entitlement_independently_verified: bool = False
    may_ingest_real_data: bool = False
    may_persist_real_data: bool = False
    may_trade: bool = False


def qualify_snapshot_binding(
    snapshot: CandleSnapshot,
    binding: SourceStreamBinding | None,
    decision_utc: datetime,
) -> StreamBindingReview:
    """Fail closed on mismatched *declared* identity, side or causal as-of.

    A consistent result is ONLY evidence that the caller's metadata is
    self-consistent. It cannot prove that stream X belongs to broker product Y,
    or that any claimed vendor access/storage right exists.
    """
    if not isinstance(snapshot, CandleSnapshot):
        raise TypeError("TYPED_CANDLE_SNAPSHOT_REQUIRED")
    ensure_utc(decision_utc, "decision_utc")
    if binding is not None and not isinstance(binding, SourceStreamBinding):
        raise TypeError("TYPED_SOURCE_STREAM_BINDING_REQUIRED")

    fingerprint = snapshot.partition.fingerprint

    def blocked(reason: str) -> StreamBindingReview:
        return StreamBindingReview(False, reason, len(snapshot.closed_bars), fingerprint)

    if binding is None:
        return blocked("SOURCE_STREAM_BINDING_MISSING")
    if snapshot.checked_at_utc > decision_utc:
        return blocked("SNAPSHOT_NOT_KNOWN_AT_DECISION")
    if not snapshot.closed_bars:
        return blocked("NO_OBSERVED_BARS_TO_QUALIFY")

    part = snapshot.partition
    expected_partition = (
        binding.provider_id, binding.broker_product_ref,
        binding.instrument_version, binding.side, binding.timeframe,
        binding.calendar_version, binding.aggregation_version,
        binding.source_timezone_policy, binding.rights_policy_ref,
        binding.schema_version,
    )
    actual_partition = (
        part.provider_id, part.broker_product_ref,
        part.instrument_version, part.side, part.timeframe,
        part.calendar_version, part.aggregation_version,
        part.source_timezone_policy, part.rights_policy_ref,
        part.schema_version,
    )
    if expected_partition != actual_partition:
        return blocked("DECLARED_PARTITION_OR_BROKER_PRODUCT_CONFLICT")

    for bar in snapshot.closed_bars:
        observation = bar.observation
        # The CandleSnapshot itself has already validated key/timeframe/side,
        # provider, closed status, coverage and source quality.
        if observation.stream_id != binding.stream_id:
            return blocked("DECLARED_STREAM_ID_CONFLICT")
        if observation.endpoint != binding.endpoint:
            return blocked("DECLARED_SOURCE_ENDPOINT_CONFLICT")
        if observation.license_scope_claim != binding.license_scope_claim:
            return blocked("DECLARED_LICENSE_SCOPE_CLAIM_CONFLICT")
        if (
            bar.first_known_utc > decision_utc
            or observation.first_known_utc > decision_utc
            or observation.retrieved_at_utc > decision_utc
        ):
            return blocked("DECLARED_EVIDENCE_NOT_KNOWN_AT_DECISION")

    return StreamBindingReview(
        True, "DECLARED_SYNTHETIC_METADATA_CONSISTENT_NOT_AUTHORIZED",
        len(snapshot.closed_bars), fingerprint,
    )
