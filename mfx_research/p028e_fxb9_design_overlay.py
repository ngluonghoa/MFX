"""A04/P0.28E: MFX-only FX-B9 design overlay, never original Forex taxonomy.

The frozen original Forex catalog must remain 18 labels and must continue to
reject FX-B9 as a source-catalog item. This separate review-only overlay
provides 8 BUY + 8 SELL design candidates with 3 watch/protection labels.

All event classifications are caller-ASSERTED SIM context, not independent
price detection. Outputs can never become market signals, data, or orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha1, sha256
import json
from pathlib import Path
from typing import Any

from forex_trading.catalog import ZONES, validate_catalog
from forex_trading.model import ZoneDefinition, ZonePurpose

MANIFEST = Path("docs/MFX_A04_P28E_FXB9_DESIGN_OVERLAY.json")
MANIFEST_BLOB_SHA = "bfa6f3b6f6f7832cc72d1ccecbfa106d615b1212"
FROZEN_CATALOG_SHA = "dc0cd0d7eab7f8603071401aa51723f7e4b8ef20"
SOURCE_COMMIT = "7e1c1c012b1b189be5ad7b9d07756eac012a8309"
FXB9_LABEL = "FX-B9"
FXB9_FAMILY = "F8_FALSE_DOWN_BREAK"
SCHEMA = "MFX_A04_P28E_FXB9_DESIGN_OVERLAY_V1"
VERSION = "MFX_EXTENSION_ONLY:FXB9_DESIGN_2026_11_10"


def _blob(content: bytes) -> str:
    return sha1(
        b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    ).hexdigest()


def _pairs_unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in items:
        if key in out:
            raise ValueError("P028E_DUPLICATE_MANIFEST_KEY:" + key)
        out[key] = value
    return out


def _keys(v: Any, names: set[str], where: str) -> dict[str, Any]:
    if not isinstance(v, dict) or set(v) != names:
        raise ValueError("P028E_EXACT_MANIFEST_KEYS:" + where)
    return v


def _eq(actual: Any, expected: Any, name: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise ValueError("P028E_DESIGN_SCOPE_NOT_APPROVED:" + name)


def _sim(value: str, field: str) -> None:
    if (not isinstance(value, str)
            or not value.startswith("SIM:")
            or not 5 <= len(value) <= 128
            or any(c.isspace() for c in value)):
        raise ValueError("P028E_SIM_ONLY_" + field)


def _utc(value: datetime, field: str) -> None:
    if (not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() != timezone.utc.utcoffset(value)):
        raise ValueError("P028E_UTC_REQUIRED_" + field)


@dataclass(frozen=True, slots=True)
class MfxDesignOverlayReceipt:
    original_labels: tuple[str, ...]
    extended_labels: tuple[str, ...]
    original_buy_candidates: int
    extended_buy_candidates: int
    short_candidates: int
    non_entry_labels: tuple[str, ...]
    numeric_entry_approvals: int = 0
    b2_s2_numeric_source_requirements_pending: int = 36
    source_verified: bool = False
    real_buy_sell_alerts: int = 0
    market_provider_calls: int = 0
    drive_price_cache_writes: int = 0
    broker_orders: int = 0
    release_ready: bool = False


def verify_fxb9_design_manifest(obj: object) -> MfxDesignOverlayReceipt:
    root = _keys(obj, {
        "schema", "version", "approval", "original_source",
        "extension", "counts", "stop_gates",
    }, "root")
    _eq(root["schema"], SCHEMA, "schema")
    _eq(root["version"], VERSION, "version")
    approval = _keys(root["approval"], {
        "authority", "date", "type", "numeric_formula_approved",
        "backtest_verified", "real_buy_sell_authorized",
        "broker_order_execution_authorized",
    }, "approval")
    for approval_name, approval_expected in (
        ("authority", "USER_APPROVED_MFX_DESIGN_ONLY"),
        ("date", "2026-11-10"),
        ("type", "NEW_MFX_EXTENSION_NOT_ORIGINAL_FOREX_1TO1"),
        ("numeric_formula_approved", False), ("backtest_verified", False),
        ("real_buy_sell_authorized", False),
        ("broker_order_execution_authorized", False),
    ):
        _eq(approval[approval_name], approval_expected, "approval." + approval_name)

    source = _keys(root["original_source"], {
        "repository", "commit", "tree_sha", "catalog_git_blob_sha",
        "source_audit_document_id", "source_audit_b3_heading_index",
        "source_audit_s6_heading_index",
        "source_audit_fxb9_prior_exclusion_index",
        "original_catalog_labels", "source_locked_docs_unchanged",
    }, "original_source")
    for source_name, source_expected in (
        ("repository", "ngluonghoa/forex-trading-1-0"),
        ("commit", SOURCE_COMMIT),
        ("tree_sha", "5df2058346f6dc96ed5bb02581b139fe2aa2d803"),
        ("catalog_git_blob_sha", FROZEN_CATALOG_SHA),
        ("source_audit_document_id",
         "10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA"),
        ("source_audit_b3_heading_index", 39),
        ("source_audit_s6_heading_index", 160),
        ("source_audit_fxb9_prior_exclusion_index", 255),
        ("original_catalog_labels", 18), ("source_locked_docs_unchanged", 11),
    ):
        _eq(source[source_name], source_expected, "original_source." + source_name)

    extension = _keys(root["extension"], {
        "label", "family", "purpose", "direction", "design_status",
        "action_eligible", "signal_stage", "current_action",
        "future_entry_quote_side_if_numerically_approved",
        "mechanism", "phase_names", "phase_descriptions",
        "overlap", "invalid_cases", "numeric_thresholds",
    }, "extension")
    for ext_name, ext_expected in (
        ("label", FXB9_LABEL), ("family", FXB9_FAMILY),
        ("purpose", ZonePurpose.ENTRY_LONG_CANDIDATE.value),
        ("direction", "LONG"),
        ("design_status", "APPROVED_DESIGN_SCOPE_FORMULA_PENDING"),
        ("action_eligible", False), ("signal_stage", "UNVERIFIED"),
        ("current_action", "NO_SIGNAL"),
        ("future_entry_quote_side_if_numerically_approved", "ASK"),
        ("mechanism", "BEAR_TRAP_FALSE_BREAKDOWN_OUTSIDE_PREDECLARED_RANGE"),
        ("phase_names", ["R0", "R_C", "R_E", "R_F"]),
        ("numeric_thresholds", {}),
    ):
        _eq(extension[ext_name], ext_expected, "extension." + ext_name)
    phases = _keys(extension["phase_descriptions"],
                   {"R0", "R_C", "R_E", "R_F"}, "phase_descriptions")
    for name in ("R0", "R_C", "R_E", "R_F"):
        value = phases[name]
        if not isinstance(value, str) or len(value) < 60 or "PENDING" not in value:
            raise ValueError("P028E_NOT_EXECUTABLE_PHASE:" + name)
    overlap = _keys(extension["overlap"], {"B3", "S6", "opportunity"},
                    "overlap")
    if (not isinstance(overlap["B3"], str)
            or "NOT FX-B9" not in overlap["B3"]
            or not isinstance(overlap["S6"], str)
            or "No symmetry assumption" not in overlap["S6"]
            or not isinstance(overlap["opportunity"], str)
            or "one research opportunity" not in overlap["opportunity"]):
        raise ValueError("P028E_MISSING_B3_S6_OVERLAP_DENIAL")
    if (not isinstance(extension["invalid_cases"], list)
            or len(extension["invalid_cases"]) != 8
            or len(set(extension["invalid_cases"])) != 8):
        raise ValueError("P028E_RESEARCH_DENIAL_CASES_REQUIRED")
    counts = _keys(root["counts"], {
        "original_catalog_labels", "extended_mfx_design_labels",
        "original_buy_entry_candidates", "extended_buy_entry_candidates",
        "sell_entry_candidates", "watch_and_protective_labels",
        "extended_entry_design_candidates",
        "approved_numerical_entry_predicates",
        "b2_s2_original_numeric_obligations_pending",
    }, "counts")
    for count_name, count_expected in (
        ("original_catalog_labels", 18),
        ("extended_mfx_design_labels", 19),
        ("original_buy_entry_candidates", 7),
        ("extended_buy_entry_candidates", 8),
        ("sell_entry_candidates", 8),
        ("watch_and_protective_labels", 3),
        ("extended_entry_design_candidates", 16),
        ("approved_numerical_entry_predicates", 0),
        ("b2_s2_original_numeric_obligations_pending", 36),
    ):
        _eq(counts[count_name], count_expected, "counts." + count_name)
    stop = _keys(root["stop_gates"], {
        "source_numeric_approval_required", "licensed_bid_ask_data_required",
        "real_drive_market_cache_rights_required",
        "chronological_oos_required", "live_market_signals_enabled",
        "real_drive_market_cache_writes", "real_provider_calls",
        "broker_orders", "release_ready",
    }, "stop")
    for stop_name, stop_expected in (
        ("source_numeric_approval_required", True),
        ("licensed_bid_ask_data_required", True),
        ("real_drive_market_cache_rights_required", True),
        ("chronological_oos_required", True),
        ("live_market_signals_enabled", False),
        ("real_drive_market_cache_writes", 0),
        ("real_provider_calls", 0),
        ("broker_orders", 0),
        ("release_ready", False),
    ):
        _eq(stop[stop_name], stop_expected, "stop_gates." + stop_name)

    validate_catalog(ZONES)
    original = tuple(z.label for z in ZONES)
    if len(original) != 18 or FXB9_LABEL in original:
        raise ValueError("P028E_ORIGINAL_18_ZONE_FREEZE")
    if _blob(Path("src/forex_trading/catalog.py").read_bytes()) != FROZEN_CATALOG_SHA:
        raise ValueError("P028E_ORIGINAL_FOREX_CATALOG_SHA_DRIFT")
    ext = ZoneDefinition(FXB9_LABEL, FXB9_FAMILY,
                         ZonePurpose.ENTRY_LONG_CANDIDATE)
    # Insert the MFX-only LONG proposal after B8 in the PRESENTATION
    # overlay; stripping FX-B9 reproduces the frozen 18 original order.
    split = next(i for i, z in enumerate(ZONES) if z.label == "S1")
    design = ZONES[:split] + (ext,) + ZONES[split:]
    if len(set(z.label for z in design)) != 19:
        raise ValueError("P028E_DUPLICATE_ORIGINAL_DESIGN_ZONE")
    longs = sum(z.purpose is ZonePurpose.ENTRY_LONG_CANDIDATE for z in design)
    shorts = sum(z.purpose is ZonePurpose.ENTRY_SHORT_CANDIDATE for z in design)
    nonentry = tuple(z.label for z in design if z.purpose not in (
        ZonePurpose.ENTRY_LONG_CANDIDATE, ZonePurpose.ENTRY_SHORT_CANDIDATE,
    ))
    if (longs, shorts, nonentry) != (8, 8, ("B7", "S3", "S8")):
        raise ValueError("P028E_8_BUY_8_SELL_3_PROTECTION_INVALID")
    # The original source validator is intentionally NOT called on the
    # extension. It explicitly rejects FX-B9, as it must for 1:1 parity.
    return MfxDesignOverlayReceipt(
        original_labels=original,
        extended_labels=tuple(z.label for z in design),
        original_buy_candidates=7,
        extended_buy_candidates=longs,
        short_candidates=shorts,
        non_entry_labels=nonentry,
    )


def read_fxb9_design_manifest() -> MfxDesignOverlayReceipt:
    raw = MANIFEST.read_bytes()
    if not raw or len(raw) > 32768:
        raise ValueError("P028E_MANIFEST_NOT_BOUNDED")
    if _blob(raw) != MANIFEST_BLOB_SHA:
        raise ValueError("P028E_MANIFEST_BLOB_CHANGED_WITHOUT_REVIEW")
    obj: Any = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_unique)
    return verify_fxb9_design_manifest(obj)


class PredeclaredRangeScope(str, Enum):
    INSIDE_OR_AT_RANGE_LOWER_BAND = "INSIDE_OR_AT_RANGE_LOWER_BAND"
    OUTSIDE_PREDECLARED_RANGE = "OUTSIDE_PREDECLARED_RANGE"
    UNKNOWN = "UNKNOWN"


class MfxSetupClassification(str, Enum):
    B3_RESEARCH_ONLY = "B3_RESEARCH_ONLY"
    FXB9_RESEARCH_ONLY = "FXB9_RESEARCH_ONLY"
    UNKNOWN = "UNKNOWN"
    NOT_FALSE_BREAK = "NOT_FALSE_BREAK"


@dataclass(frozen=True, slots=True)
class SimFalseBreakEvidence:
    """Declared SIM-only metadata: not computed from licensed OHLC bars."""

    instrument_version: str
    origin_event_id: str
    provider_id: str
    stream_id: str
    calendar_version: str
    scope: PredeclaredRangeScope
    support_first_known_utc: datetime
    candle_end_utc: datetime
    first_known_utc: datetime
    retrieved_at_utc: datetime
    decision_utc: datetime
    predeclared_support_exists: bool = False
    break_observed: bool = False
    closed_reclaim_observed: bool = False
    downside_continuation: bool = False
    closed_candle: bool = True
    revised: bool = False
    quote_side: str = "MID"
    source_numeric_approved: bool = False
    real_provider_license_claimed: bool = False

    def __post_init__(self) -> None:
        for name in ("instrument_version", "origin_event_id", "provider_id",
                     "stream_id", "calendar_version"):
            _sim(getattr(self, name), name)
        if not isinstance(self.scope, PredeclaredRangeScope):
            raise TypeError("P028E_TYPED_PREDECLARED_RANGE_SCOPE")
        for name in ("support_first_known_utc", "candle_end_utc",
                     "first_known_utc", "retrieved_at_utc", "decision_utc"):
            _utc(getattr(self, name), name)
        if not (self.support_first_known_utc <= self.candle_end_utc
                <= self.first_known_utc <= self.retrieved_at_utc
                <= self.decision_utc):
            raise ValueError("P028E_FUTURE_KNOWN_OR_UNDECLARED_SUPPORT")
        for name in ("predeclared_support_exists", "break_observed",
                     "closed_reclaim_observed", "downside_continuation",
                     "closed_candle", "revised", "source_numeric_approved",
                     "real_provider_license_claimed"):
            if type(getattr(self, name)) is not bool:
                raise TypeError("P028E_TYPED_SIM_PROVENANCE_FLAGS")
        if (self.quote_side != "MID" or not self.closed_candle
                or self.revised or self.source_numeric_approved
                or self.real_provider_license_claimed):
            raise ValueError("P028E_UNVERIFIED_OR_REAL_MARKET_EVIDENCE_DENIED")


@dataclass(frozen=True, slots=True)
class SimFalseBreakResult:
    classification: MfxSetupClassification
    primary_design_label: str | None
    research_opportunity_id: str
    current_action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    may_publish: bool = False
    source_numeric_approved: bool = False
    real_provider_calls: int = 0
    real_drive_quote_cache_writes: int = 0
    broker_orders: int = 0


def classify_false_break_research(
    evidence: SimFalseBreakEvidence,
) -> SimFalseBreakResult:
    """Choose an EXPERIMENTAL B3-vs-FX-B9 scope label, never a BUY signal."""
    if not isinstance(evidence, SimFalseBreakEvidence):
        raise TypeError("P028E_TYPED_RESEARCH_METADATA_REQUIRED")
    # Origin-based key EXCLUDES rule name and predeclared range classification
    # so a shared false-break event cannot be counted as two opportunities.
    key = sha256(json.dumps({
        "pair": evidence.instrument_version,
        "origin": evidence.origin_event_id,
        "calendar": evidence.calendar_version,
        "support_known": evidence.support_first_known_utc.isoformat(),
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if (not evidence.predeclared_support_exists
            or evidence.scope is PredeclaredRangeScope.UNKNOWN):
        return SimFalseBreakResult(MfxSetupClassification.UNKNOWN, None, key)
    if (not evidence.break_observed
            or not evidence.closed_reclaim_observed
            or evidence.downside_continuation):
        return SimFalseBreakResult(
            MfxSetupClassification.NOT_FALSE_BREAK, None, key,
        )
    if evidence.scope is PredeclaredRangeScope.INSIDE_OR_AT_RANGE_LOWER_BAND:
        return SimFalseBreakResult(
            MfxSetupClassification.B3_RESEARCH_ONLY, "B3", key,
        )
    if evidence.scope is PredeclaredRangeScope.OUTSIDE_PREDECLARED_RANGE:
        return SimFalseBreakResult(
            MfxSetupClassification.FXB9_RESEARCH_ONLY, "FX-B9", key,
        )
    raise ValueError("P028E_UNRECOGNIZED_DESIGN_SCOPE")
