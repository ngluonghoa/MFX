"""P0.31: cloud/offline MFX 22-label claim presentation, NOT a detector.

Input is *asserted* SIM closed-bar metadata. Classification never establishes
that any original Forex predicate, numeric signal or market price event fired.
Uses SHA-sealed P0.30 MFX-only roles; frozen Forex P0.17 remains untouched.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
from re import fullmatch

from forex_trading.catalog import ZONES, validate_catalog
from mfx_research.p030_approved_nonentry_design import (
    MfxDesignZone, read_22_zone_design_manifest,
)

VERSION = "MFX_A04_P31_22_ZONE_SIM_RESEARCH_PRESENTATION_V1"
MAX_CLAIMS = 256
_HINT_BY_ROLE: dict[str, str] = {
    "ENTRY_LONG_CANDIDATE": "UNVERIFIED_BUY_RESEARCH_CANDIDATE",
    "ENTRY_SHORT_CANDIDATE": "UNVERIFIED_SELL_RESEARCH_CANDIDATE",
    "WATCH_ONLY": "UNVERIFIED_WATCH_ONLY",
    "EXIT_LONG_WARNING_ONLY": "UNVERIFIED_EXIT_LONG_PROTECTION_ONLY",
    "EXIT_SHORT_WARNING_ONLY": "UNVERIFIED_EXIT_SHORT_PROTECTION_ONLY",
}


def _sim_identifier(value: str, field: str) -> None:
    if (not isinstance(value, str)
            or not fullmatch(r"SIM:[A-Za-z0-9_.:-]{1,124}", value)):
        raise ValueError("P031_SIM_PROVENANCE_REQUIRED:" + field)


def _utc(value: datetime, field: str) -> None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P031_EXACT_UTC_DATETIME_REQUIRED:" + field)


@dataclass(frozen=True, slots=True)
class SimZoneLabelClaim:
    """A claimed zone label on a CLOSED SIM candle, NOT a signal detection."""

    instrument_version: str
    calendar_version: str
    origin_event_id: str
    provider_id: str
    stream_id: str
    label: str
    closed_candle_end_utc: datetime
    first_known_utc: datetime
    retrieved_at_utc: datetime

    def __post_init__(self) -> None:
        for key in ("instrument_version", "calendar_version",
                    "origin_event_id", "provider_id", "stream_id"):
            _sim_identifier(getattr(self, key), key)
        if (not isinstance(self.label, str)
                or not fullmatch(r"[A-Za-z0-9_-]{1,32}", self.label)):
            raise ValueError("P031_INVALID_ZONE_LABEL")
        for key in ("closed_candle_end_utc", "first_known_utc",
                    "retrieved_at_utc"):
            _utc(getattr(self, key), key)
        if not (self.closed_candle_end_utc <= self.first_known_utc
                <= self.retrieved_at_utc):
            raise ValueError("P031_CLOSED_FIRST_KNOWN_RETRIEVED_ORDER")


@dataclass(frozen=True, slots=True)
class ResearchZoneRow:
    label: str
    role: str
    research_hint: str
    instrument_version: str
    calendar_version: str
    origin_event_id: str
    research_opportunity_id: str
    first_known_utc: datetime
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    actual_source_signal_confirmed: bool = False
    position_verified: bool = False
    may_publish: bool = False
    may_open_new_position: bool = False
    may_auto_exit: bool = False


@dataclass(frozen=True, slots=True)
class ResearchEventGroup:
    research_opportunity_id: str
    instrument_version: str
    calendar_version: str
    origin_event_id: str
    source_provider_id: str
    source_stream_id: str
    matched_labels: tuple[str, ...]
    entry_long_labels: tuple[str, ...]
    entry_short_labels: tuple[str, ...]
    watch_only_labels: tuple[str, ...]
    exit_long_labels: tuple[str, ...]
    exit_short_labels: tuple[str, ...]
    display_outcome: str
    first_known_utc: datetime
    conflict: bool = False
    action: str = "NO_SIGNAL"
    may_publish_alert: bool = False
    actual_numeric_signal_count: int = 0


@dataclass(frozen=True, slots=True)
class ResearchZoneReport:
    version: str
    classified: tuple[ResearchZoneRow, ...]
    events: tuple[ResearchEventGroup, ...]
    source_catalog_labels: int = 18
    mfx_design_labels: int = 22
    mfx_entry_long_design_candidates: int = 8
    mfx_entry_short_design_candidates: int = 8
    mfx_watch_only_labels: int = 2
    mfx_exit_warning_labels: int = 4
    original_b2_s2_source_numeric_obligations_pending: int = 36
    numeric_entry_predicates_approved: int = 0
    confirmed_buy_sell_signals: int = 0
    confirmed_exit_warnings: int = 0
    live_provider_calls: int = 0
    real_drive_quote_cache_writes: int = 0
    broker_orders: int = 0
    may_send_live_alerts: bool = False
    may_auto_exit: bool = False
    may_trade: bool = False
    release_ready: bool = False


def _event_identity(claim: SimZoneLabelClaim) -> tuple[str, str, str]:
    return (claim.instrument_version, claim.calendar_version,
            claim.origin_event_id)


def _opportunity_id(key: tuple[str, str, str]) -> str:
    raw = json.dumps(key, separators=(",", ":"), ensure_ascii=True)
    return sha256(raw.encode("utf-8")).hexdigest()


def _outcome(longs: tuple[str, ...], shorts: tuple[str, ...]) -> str:
    if longs and shorts:
        return "CONFLICT_NO_SIGNAL"
    if longs:
        return "UNVERIFIED_BUY_RESEARCH_GROUP_ONLY"
    if shorts:
        return "UNVERIFIED_SELL_RESEARCH_GROUP_ONLY"
    return "WATCH_OR_PROTECTION_RESEARCH_ONLY"


def route_sim_22_zone_labels(
    claims: tuple[SimZoneLabelClaim, ...],
    decision_utc: datetime,
) -> ResearchZoneReport:
    """Deterministic 22-zone research classification, always NO_SIGNAL.

    Same event across BUY/SELL/WATCH/EXIT is a single research opportunity.
    Neither numeric validation nor open-position verification occurs here.
    """
    _utc(decision_utc, "decision_utc")
    if not isinstance(claims, tuple) or len(claims) > MAX_CLAIMS:
        raise ValueError("P031_BOUNDED_IMMUTABLE_CLAIMS_REQUIRED")
    validate_catalog(ZONES)
    manifest = read_22_zone_design_manifest()
    if (len(manifest.zones) != 22 or len(manifest.original_labels) != 18
            or len(manifest.entry_long_labels) != 8
            or len(manifest.entry_short_labels) != 8
            or len(manifest.watch_labels) != 2
            or (len(manifest.exit_long_warning_labels)
                + len(manifest.exit_short_warning_labels)) != 4
            or manifest.numerical_rules_approved != 0
            or manifest.b2_s2_source_obligations_pending != 36):
        raise ValueError("P031_FROZEN_DESIGN_AND_UNAPPROVED_NUMERIC_GATE")

    labels: dict[str, MfxDesignZone] = {z.label: z for z in manifest.zones}
    if len(labels) != 22 or set(z.purpose for z in labels.values()) != set(
            _HINT_BY_ROLE):
        raise ValueError("P031_ROLE_REGISTRY_DRIFT")

    seen: set[tuple[str, str, str, str]] = set()
    events: dict[tuple[str, str, str], list[SimZoneLabelClaim]] = {}
    provider_stream: dict[tuple[str, str, str], tuple[str, str]] = {}
    for claim in claims:
        if not isinstance(claim, SimZoneLabelClaim):
            raise TypeError("P031_TYPED_SIM_ZONE_CLAIM_REQUIRED")
        if claim.label not in labels:
            raise ValueError("P031_UNAPPROVED_OR_FORGED_ZONE:" + claim.label)
        if claim.retrieved_at_utc > decision_utc:
            raise ValueError("P031_FUTURE_KNOWN_OR_RETRIEVED_CLAIM")
        key = _event_identity(claim)
        duplicate = (*key, claim.label)
        if duplicate in seen:
            raise ValueError("P031_DUPLICATE_RULE_IN_RESEARCH_OPPORTUNITY")
        seen.add(duplicate)
        source = (claim.provider_id, claim.stream_id)
        if key in provider_stream and provider_stream[key] != source:
            raise ValueError("P031_MIXED_PROVIDER_OR_STREAM_FOR_ONE_EVENT")
        provider_stream[key] = source
        events.setdefault(key, []).append(claim)

    classified: list[ResearchZoneRow] = []
    grouped: list[ResearchEventGroup] = []
    for key in sorted(events):
        members = sorted(events[key], key=lambda c: c.label)
        group_labels: dict[str, list[str]] = {
            purpose: [] for purpose in _HINT_BY_ROLE
        }
        opp = _opportunity_id(key)
        for claim in members:
            meta = labels[claim.label]
            group_labels[meta.purpose].append(claim.label)
            classified.append(ResearchZoneRow(
                label=claim.label,
                role=meta.purpose,
                research_hint=_HINT_BY_ROLE[meta.purpose],
                instrument_version=claim.instrument_version,
                calendar_version=claim.calendar_version,
                origin_event_id=claim.origin_event_id,
                research_opportunity_id=opp,
                first_known_utc=claim.first_known_utc,
            ))
        longs = tuple(group_labels["ENTRY_LONG_CANDIDATE"])
        shorts = tuple(group_labels["ENTRY_SHORT_CANDIDATE"])
        watches = tuple(group_labels["WATCH_ONLY"])
        long_exits = tuple(group_labels["EXIT_LONG_WARNING_ONLY"])
        short_exits = tuple(group_labels["EXIT_SHORT_WARNING_ONLY"])
        grouped.append(ResearchEventGroup(
            research_opportunity_id=opp,
            instrument_version=key[0],
            calendar_version=key[1],
            origin_event_id=key[2],
            source_provider_id=provider_stream[key][0],
            source_stream_id=provider_stream[key][1],
            matched_labels=tuple(c.label for c in members),
            entry_long_labels=longs,
            entry_short_labels=shorts,
            watch_only_labels=watches,
            exit_long_labels=long_exits,
            exit_short_labels=short_exits,
            display_outcome=_outcome(longs, shorts),
            first_known_utc=min(c.first_known_utc for c in members),
            conflict=bool(longs and shorts),
        ))
    return ResearchZoneReport(
        version=VERSION, classified=tuple(classified), events=tuple(grouped),
    )
