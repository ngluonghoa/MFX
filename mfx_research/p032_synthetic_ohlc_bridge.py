"""P0.32: independently computed SIM OHLC B2/S2 research -> 22-zone router.

This does NOT infer 22 entry zones, source-approved numerical predicates,
real market alerts, fills or true tradable signal quality. The only computed
patterns are preexisting UNAPPROVED P0.18/P0.19 synthetic B2/S2 pilots.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json

from forex_trading.market_data import BarSide, MarketBar
from forex_trading.model import SignalStage

from mfx_research.causal_multitf_context import (
    DerivedResearchReceipt, SyntheticDerivationParameters,
    SyntheticMultiTfBars, derive_and_evaluate_b2_s2,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.pullback_pilot import UnapprovedResearchParameters
from mfx_research.p031_sim_22_zone_router import (
    ResearchZoneReport, SimZoneLabelClaim, route_sim_22_zone_labels,
)

VERSION = "MFX_A04_P32_CAUSAL_SIM_OHLC_TO_22_ZONE_RESEARCH_V1"
SUPPORTED_PILOTS = ("B2", "S2")


@dataclass(frozen=True, slots=True)
class ComputedSIMOHLCResearch:
    """Causal synthetic price-pattern computation; not an actionable signal."""

    version: str
    pilot_rule_id: str
    experimental_numeric_action: CandidateAction
    research_reason: str
    research_phase: SignalStage
    origin_event_id: str
    research_input_sha256: str
    context_derived_from: tuple[str, ...]
    actual_ohlc_computation: DerivedResearchReceipt
    classified_output: ResearchZoneReport
    first_known_utc: datetime
    decision_utc: datetime
    source_price_side: BarSide = BarSide.MID
    pattern_source_numeric_approved: bool = False
    actual_market_data_verified: bool = False
    verified_position: bool = False
    may_send_buy_sell_or_exit_alert: bool = False
    actual_buy_sell_signals: int = 0
    real_provider_calls: int = 0
    real_drive_market_cache_writes: int = 0
    broker_orders: int = 0
    release_ready: bool = False

    @property
    def action(self) -> str:
        """External action remains NO_SIGNAL regardless of SIM pattern."""
        return "NO_SIGNAL"


def _canonical_input_digest(bars: SyntheticMultiTfBars) -> str:
    """A reproducible SIM-fixture fingerprint, NOT original vendor attestation."""
    series: tuple[tuple[str, tuple[MarketBar, ...]], ...] = (
        ("D1", bars.daily),
        ("H4", bars.four_hour),
        ("H1", bars.hourly),
        ("M15_SEED", bars.micro_seed_m15),
        ("M15_TRIGGER", bars.trigger_m15),
    )
    record: list[dict[str, object]] = []
    for name, seq in series:
        for bar in seq:
            record.append({
                "series": name,
                "instrument": bar.key.instrument_version,
                "timeframe": bar.key.timeframe.value,
                "start_utc": bar.key.bar_start_utc.isoformat(),
                "end_utc": bar.key.bar_end_utc.isoformat(),
                "calendar": bar.key.calendar_version,
                "aggregation": bar.key.aggregation_version,
                "side": bar.key.side.value,
                "provider": bar.observation.provider_id,
                "stream": bar.observation.stream_id,
                "revision": bar.revision_number,
                "known_utc": bar.first_known_utc.isoformat(),
                "retrieved_utc": bar.observation.retrieved_at_utc.isoformat(),
                "source_raw_sha256_claim": bar.observation.raw_sha256,
                "ohlc": [str(bar.open), str(bar.high),
                         str(bar.low), str(bar.close)],
            })
    return sha256(json.dumps(
        record, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _origin_id(bars: SyntheticMultiTfBars) -> str:
    """Same trigger identity gives one source opportunity, independent of rule.

    A later quote revision cannot silently edit this event: P019 rejects
    revisions >1, and the research evidence digest records fixture bytes.
    This is a local deterministic ID, NOT distributed ledger/idempotency proof.
    """
    prior, latest = bars.trigger_m15
    identity = (
        latest.key.instrument_version,
        latest.key.calendar_version,
        latest.observation.provider_id,
        latest.observation.stream_id,
        prior.key.bar_start_utc.isoformat(),
        latest.key.bar_end_utc.isoformat(),
    )
    raw = json.dumps(identity, ensure_ascii=True, separators=(",", ":"))
    return "SIM:P032-" + sha256(raw.encode("utf-8")).hexdigest()[:32]


def compute_and_route_sim_b2_s2(
    rule_id: str,
    bars: SyntheticMultiTfBars,
    derivation: SyntheticDerivationParameters,
    unapproved_parameters: UnapprovedResearchParameters,
    decision_utc: datetime,
) -> ComputedSIMOHLCResearch:
    """Actually derive synthetic B2/S2 experimental pattern from closed OHLC.

    Do NOT provide a zone claim or origin ID: those are created ONLY after
    source-side causal validation. NO_SIGNAL price result => empty 22-zone
    routing receipt, not a fabricated candidate.
    """
    if type(rule_id) is not str or rule_id not in SUPPORTED_PILOTS:
        raise ValueError("P032_ONLY_B2_S2_COMPUTED_SIM_PILOTS")
    if (not isinstance(bars, SyntheticMultiTfBars)
            or not isinstance(derivation, SyntheticDerivationParameters)
            or not isinstance(unapproved_parameters, UnapprovedResearchParameters)):
        raise TypeError("P032_TYPED_SIM_OHLC_AND_PARAMETER_INPUT_REQUIRED")
    if (not isinstance(decision_utc, datetime)
            or decision_utc.tzinfo is None
            or decision_utc.utcoffset() != timedelta(0)):
        raise ValueError("P032_EXACT_UTC_DECISION_REQUIRED")

    # The original P019 already validates all D1/H4/H1/M15 series as SIM,
    # CLOSED/COMPLETE/VERIFIED, MID, no revisions, no gaps, and as-of causality.
    # It also calculates trend proxies, H1 ATR/zone, micro pivot and triggers
    # from the OHLC, without trusting caller-supplied context metadata.
    origin = _origin_id(bars)
    computed = derive_and_evaluate_b2_s2(
        rule_id, bars, derivation, unapproved_parameters,
        decision_utc, origin_event_id=origin,
    )
    pattern = computed.signal
    if (pattern.stage is not SignalStage.UNVERIFIED
            or pattern.original_forex_numerical_parity
            or pattern.source_verified_for_market
            or pattern.may_send_confirmed_signal
            or pattern.can_trade
            or computed.structural_calibration_approved
            or computed.original_forex_source_signal_parity
            or computed.source_verified_for_market
            or computed.may_send_confirmed_signal
            or computed.can_trade):
        raise ValueError("P032_UNAPPROVED_NUMERICAL_SIGNAL_PROMOTION_DENIED")
    expected = CandidateAction.BUY if rule_id == "B2" else CandidateAction.SELL
    if pattern.action not in (expected, CandidateAction.NO_SIGNAL):
        raise ValueError("P032_WRONG_DIRECTION_FROM_UNAPPROVED_SIM_PILOT")
    latest = bars.trigger_m15[-1]
    if (latest.key.side is not BarSide.MID
            or pattern.instrument_version != latest.key.instrument_version
            or pattern.origin_event_id != origin
            or pattern.first_known_utc != latest.first_known_utc):
        raise ValueError("P032_SOURCE_ORIGIN_OR_MID_IDENTITY_DRIFT")

    claims: tuple[SimZoneLabelClaim, ...] = ()
    if pattern.action is expected:
        claims = (SimZoneLabelClaim(
            instrument_version=latest.key.instrument_version,
            calendar_version=latest.key.calendar_version,
            origin_event_id=origin,
            provider_id=latest.observation.provider_id,
            stream_id=latest.observation.stream_id,
            label=rule_id,  # from computed + verified P019/P018, not user claim
            closed_candle_end_utc=latest.key.bar_end_utc,
            first_known_utc=latest.first_known_utc,
            retrieved_at_utc=latest.observation.retrieved_at_utc,
        ),)
    routed = route_sim_22_zone_labels(claims, decision_utc)
    if (len(routed.classified) != len(claims)
            or len(routed.events) != len(claims)
            or routed.numeric_entry_predicates_approved != 0
            or routed.confirmed_buy_sell_signals != 0
            or routed.may_send_live_alerts
            or routed.may_trade
            or routed.may_auto_exit):
        raise ValueError("P032_ROUTER_MUST_REMAIN_NO_SIGNAL_AND_UNVERIFIED")
    if claims:
        row, event = routed.classified[0], routed.events[0]
        if (row.label != rule_id or row.action != "NO_SIGNAL"
                or row.stage != "UNVERIFIED"
                or row.origin_event_id != origin
                or event.action != "NO_SIGNAL"
                or event.research_opportunity_id != row.research_opportunity_id
                or event.conflict):
            raise ValueError("P032_RESEARCH_EVENT_PROVENANCE_MISMATCH")

    return ComputedSIMOHLCResearch(
        version=VERSION,
        pilot_rule_id=rule_id,
        experimental_numeric_action=pattern.action,
        research_reason=pattern.reason,
        research_phase=pattern.stage,
        origin_event_id=origin,
        research_input_sha256=_canonical_input_digest(bars),
        context_derived_from=("D1", "H4", "H1", "M15"),
        actual_ohlc_computation=computed,
        classified_output=routed,
        first_known_utc=pattern.first_known_utc,
        decision_utc=decision_utc,
    )
