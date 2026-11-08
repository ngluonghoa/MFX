"""Causal BID/ASK paired-bar lineage agreement, not a fill/price execution model."""
from dataclasses import dataclass
from datetime import datetime
from re import fullmatch

from .market_data import BarSide, MarketBar, evaluate_closed_bar
from .quotes import ensure_utc


@dataclass(frozen=True, slots=True)
class BidAskSourceManifest:
    """A claimed shared data revision. Not a verified vendor/retention right."""
    provider_id: str
    dataset_version: str
    instrument_version: str
    calendar_version: str
    aggregation_version: str
    source_timezone_policy: str
    bid_stream_id: str
    ask_stream_id: str
    bid_revision_id: str
    ask_revision_id: str
    dataset_digest_claim: str
    first_known_utc: datetime

    def __post_init__(self) -> None:
        for key in ("provider_id", "dataset_version", "instrument_version",
                    "calendar_version", "aggregation_version",
                    "source_timezone_policy", "bid_stream_id", "ask_stream_id",
                    "bid_revision_id", "ask_revision_id"):
            val = getattr(self, key)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{key} required")
        if not isinstance(self.dataset_digest_claim, str) or not fullmatch(
            r"[a-f0-9]{64}", self.dataset_digest_claim
        ):
            raise ValueError("DATASET_DIGEST_CLAIM_INVALID")
        ensure_utc(self.first_known_utc, "dataset_first_known_utc")


@dataclass(frozen=True, slots=True)
class SidePairGate:
    coherent_internal_metadata: bool
    trade_permission: bool
    reason: str


def assess_bid_ask_side_pair(
    bid: MarketBar | None,
    ask: MarketBar | None,
    manifest: BidAskSourceManifest | None,
    decision_utc: datetime,
    *,
    conditional_m5_early_enabled: bool = False,
    htf_context_first_known_utc: datetime | None = None,
) -> SidePairGate:
    """Fail closed for incomplete/as-of/mismatched claims; never grant fills.

    Do not compare different-stream BID/ASK OHLC as if timestamp-aligned ticks.
    A manifest digest is a CLAIM until independently tied to genuine source bytes.
    """
    ensure_utc(decision_utc, "decision_utc")

    def blocked(reason: str) -> SidePairGate:
        return SidePairGate(False, False, reason)

    if bid is None or ask is None or manifest is None:
        return blocked("REQUIRES_BOTH_BID_ASK_AND_MANIFEST")
    if not isinstance(bid, MarketBar) or not isinstance(ask, MarketBar) or not isinstance(
        manifest, BidAskSourceManifest
    ):
        raise TypeError("typed BID/ASK bars and manifest required")
    if any(known > decision_utc for known in
           (bid.first_known_utc, ask.first_known_utc, manifest.first_known_utc)):
        return blocked("SOURCE_REVISION_FUTURE_AS_OF")
    if bid.key.side is not BarSide.BID or ask.key.side is not BarSide.ASK:
        return blocked("BID_ASK_SIDE_MISMATCH")
    if (
        bid.key.instrument_version != ask.key.instrument_version
        or bid.key.timeframe != ask.key.timeframe
        or bid.key.bar_start_utc != ask.key.bar_start_utc
        or bid.key.bar_end_utc != ask.key.bar_end_utc
        or bid.key.calendar_version != ask.key.calendar_version
        or bid.key.aggregation_version != ask.key.aggregation_version
    ):
        return blocked("BAR_IDENTITY_OR_INTERVAL_MISMATCH")
    if (bid.key.instrument_version != manifest.instrument_version
            or bid.key.calendar_version != manifest.calendar_version
            or bid.key.aggregation_version != manifest.aggregation_version):
        return blocked("MANIFEST_DATASET_IDENTITY_MISMATCH")
    if (
        bid.observation.provider_id != manifest.provider_id
        or ask.observation.provider_id != manifest.provider_id
        or bid.observation.stream_id != manifest.bid_stream_id
        or ask.observation.stream_id != manifest.ask_stream_id
        or bid.observation.revision_id != manifest.bid_revision_id
        or ask.observation.revision_id != manifest.ask_revision_id
        or bid.observation.source_timezone_policy != manifest.source_timezone_policy
        or ask.observation.source_timezone_policy != manifest.source_timezone_policy
    ):
        return blocked("PROVIDER_STREAM_REVISION_OR_ZONE_POLICY_MISMATCH")
    for side, bar in (("BID", bid), ("ASK", ask)):
        gate = evaluate_closed_bar(
            bar, decision_utc,
            conditional_m5_early_enabled=conditional_m5_early_enabled,
            htf_context_first_known_utc=htf_context_first_known_utc,
        )
        if not gate.usable_for_technical_features:
            return blocked(f"{side}_{gate.reason}")
    return SidePairGate(True, False, "PAIR_INTERNAL_METADATA_MATCH_NOT_LICENSED_OR_EXECUTABLE")
