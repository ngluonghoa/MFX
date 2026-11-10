"""A04/P0.30: user-approved MFX-only 22-label DESIGN register.

Three new mirror zones are non-entry *design roles*, not signals. Original
Forex 18-zone source and prior MFX P0.28E 19-zone overlay stay immutable.
No price feed, broker, trading, live cache, alert, or actual exit behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
from typing import Any

from forex_trading.catalog import ZONES, validate_catalog
from forex_trading.model import ZonePurpose
from mfx_research.p028e_fxb9_design_overlay import read_fxb9_design_manifest

CONTRACT = Path("docs/MFX_A04_P30_22_ZONE_APPROVED_DESIGN_OVERLAY.json")
CONTRACT_SHA = "45f58ead4c30dec37120ad00f6e01222c0ff8498"
P029_AUDIT = Path("docs/MFX_A04_P29_ELEVEN_PAIR_SYMMETRY_AUDIT.json")
P029_AUDIT_SHA = "08bc1896c2007f532367750f5f1eeb6be06d1ad6"
P028E_OVERLAY = Path("docs/MFX_A04_P28E_FXB9_DESIGN_OVERLAY.json")
P028E_SHA = "bfa6f3b6f6f7832cc72d1ccecbfa106d615b1212"
SOURCE_CATALOG_SHA = "dc0cd0d7eab7f8603071401aa51723f7e4b8ef20"
SOURCE_COMMIT = "7e1c1c012b1b189be5ad7b9d07756eac012a8309"
SOURCE_TREE = "5df2058346f6dc96ed5bb02581b139fe2aa2d803"
SCHEMA = "MFX_A04_P30_22_ZONE_NONENTRY_DESIGN_OVERLAY_V1"
VERSION = "MFX_DESIGN_ONLY_22_LABELS_2026_11_10"
ADDITIONS = ("FX-S11", "FX-B10", "FX-B11")
ROLES = ("WATCH_ONLY", "EXIT_SHORT_WARNING_ONLY", "EXIT_SHORT_WARNING_ONLY")
MIRRORS = ("B7", "S3", "S8")


def _blob(data: bytes) -> str:
    return sha1(
        b"blob " + str(len(data)).encode("ascii") + bytes([0]) + data
    ).hexdigest()


def _pairs_unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in items:
        if key in seen:
            raise ValueError("P030_DUPLICATE_JSON_KEY:" + key)
        seen[key] = value
    return seen


def _keys(value: Any, expected: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("P030_EXACT_KEYS_REQUIRED:" + where)
    return value


def _eq(actual: Any, expected: Any, label: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise ValueError("P030_APPROVED_SCOPE_MISMATCH:" + label)


def _sealed_json(path: Path, expected_sha: str, max_bytes: int) -> Any:
    raw = path.read_bytes()
    if not raw or len(raw) > max_bytes:
        raise ValueError("P030_BOUNDED_SOURCE_REQUIRED:" + str(path))
    if _blob(raw) != expected_sha:
        raise ValueError("P030_SOURCE_GIT_SHA_DRIFT:" + str(path))
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_unique)


@dataclass(frozen=True, slots=True)
class MfxDesignZone:
    label: str
    purpose: str
    mirror_of: str | None = None
    requires_verified_open_short: bool = False
    can_open_new_position: bool = False


@dataclass(frozen=True, slots=True)
class Mfx22DesignReceipt:
    zones: tuple[MfxDesignZone, ...]
    original_labels: tuple[str, ...]
    previous_mfx_19_labels: tuple[str, ...]
    approved_new_labels: tuple[str, ...]
    entry_long_labels: tuple[str, ...]
    entry_short_labels: tuple[str, ...]
    watch_labels: tuple[str, ...]
    exit_long_warning_labels: tuple[str, ...]
    exit_short_warning_labels: tuple[str, ...]
    original_source_unchanged: bool = True
    numerical_rules_approved: int = 0
    b2_s2_source_obligations_pending: int = 36
    live_signals: int = 0
    live_exit_warnings: int = 0
    real_quote_calls: int = 0
    market_drive_cache_writes: int = 0
    broker_orders: int = 0
    release_ready: bool = False


@dataclass(frozen=True, slots=True)
class DesignOnlyRoute:
    label: str
    design_role: str
    position_gate_satisfied_by_claim: bool
    research_display: str
    action: str = "NO_SIGNAL"
    source_verified: bool = False
    may_publish: bool = False
    may_auto_exit: bool = False
    may_open_position: bool = False
    broker_orders: int = 0


def verify_22_zone_design_manifest(value: object) -> Mfx22DesignReceipt:
    root = _keys(value, {
        "schema", "version", "approval", "provenance",
        "new_nonentry_design_labels", "counts", "cross_zone_governance",
        "stop_gates",
    }, "root")
    _eq(root["schema"], SCHEMA, "schema")
    _eq(root["version"], VERSION, "version")
    approval = _keys(root["approval"], {
        "authority", "date", "scope", "numeric_formula_approved",
        "data_provider_rights_approved", "real_alerts_approved",
        "automated_position_exit_approved", "broker_order_execution_approved",
    }, "approval")
    for key, expected in (
        ("authority", "USER_APPROVED_THREE_NONENTRY_MFX_DESIGN_MIRRORS"),
        ("date", "2026-11-10"),
        ("scope", "MFX_ONLY_OVERLAY_NOT_FROZEN_FOREX"),
        ("numeric_formula_approved", False),
        ("data_provider_rights_approved", False),
        ("real_alerts_approved", False),
        ("automated_position_exit_approved", False),
        ("broker_order_execution_approved", False),
    ):
        _eq(approval[key], expected, "approval." + key)

    lineage = _keys(root["provenance"], {
        "original_forex_repository", "original_forex_commit",
        "original_forex_tree", "original_catalog_git_blob_sha",
        "legacy_fxb9_design_overlay_git_blob_sha",
        "p029_audit_git_blob_sha", "original_source_audit_doc_id",
        "new_label_origin", "source_locked_docs_unchanged",
    }, "provenance")
    for key, expected in (
        ("original_forex_repository", "ngluonghoa/forex-trading-1-0"),
        ("original_forex_commit", SOURCE_COMMIT),
        ("original_forex_tree", SOURCE_TREE),
        ("original_catalog_git_blob_sha", SOURCE_CATALOG_SHA),
        ("legacy_fxb9_design_overlay_git_blob_sha", P028E_SHA),
        ("p029_audit_git_blob_sha", P029_AUDIT_SHA),
        ("original_source_audit_doc_id",
         "10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA"),
        ("new_label_origin",
         "P029_THREE_PROPOSALS_EXPLICITLY_APPROVED_BY_USER_2026_11_10"),
        ("source_locked_docs_unchanged", 11),
    ):
        _eq(lineage[key], expected, "provenance." + key)

    frozen = _sealed_json(P029_AUDIT, P029_AUDIT_SHA, 65536)
    _sealed_json(P028E_OVERLAY, P028E_SHA, 32768)
    if _blob(Path("src/forex_trading/catalog.py").read_bytes()) != SOURCE_CATALOG_SHA:
        raise ValueError("P030_FROZEN_FOREX_SOURCE_CHANGED")
    previous = read_fxb9_design_manifest()
    if len(previous.original_labels) != 18 or len(previous.extended_labels) != 19:
        raise ValueError("P030_ORIGINAL_OR_PRIOR_DESIGN_DRIFT")
    validate_catalog(ZONES)

    proposed = frozen["nonentry_missing_mirrors"]
    extensions = root["new_nonentry_design_labels"]
    if not isinstance(extensions, list) or len(extensions) != 3:
        raise ValueError("P030_EXACTLY_THREE_NEW_NONENTRY_LABELS")
    if not isinstance(proposed, list) or len(proposed) != 3:
        raise ValueError("P030_P029_SOURCE_PROPOSALS_CHANGED")
    new_zones: list[MfxDesignZone] = []
    for i, value in enumerate(extensions):
        zone = _keys(value, {
            "label", "mirror_of", "family", "purpose", "direction_role",
            "scope", "scope_approved", "eligible_for_entry",
            "approved_numeric_formula", "may_warn_live",
            "may_automate_exit", "may_create_broker_order",
            "source_status", "position_requirement", "stage_names",
            "stage_hypotheses", "invalid_if", "numeric_thresholds",
        }, "new_nonentry_design_labels")
        _eq(zone["label"], ADDITIONS[i], "label")
        _eq(zone["mirror_of"], MIRRORS[i], "mirror_of")
        _eq(zone["purpose"], ROLES[i], "purpose")
        _eq(zone["family"], (
            "COUNTERTREND_SHORT_WATCH", "SHORT_PROTECTION_SWING_LOW",
            "SHORT_PROTECTION_DOWNSIDE_EXHAUSTION",
        )[i], "family")
        _eq(zone["direction_role"], (
            "WATCH_SHORT_COUNTERTREND", "EXIT_SHORT_SWING_LOW",
            "EXIT_SHORT_EXHAUSTION",
        )[i], "direction_role")
        _eq(zone["scope"], "MFX_ONLY_APPROVED_DESIGN_NOT_ORIGINAL_FOREX",
            "scope")
        _eq(zone["scope_approved"], True, "scope_approved")
        for name in (
            "eligible_for_entry", "approved_numeric_formula", "may_warn_live",
            "may_automate_exit", "may_create_broker_order",
        ):
            _eq(zone[name], False, name)
        _eq(zone["source_status"],
            "NEW_MFX_DESIGN_NO_HISTORICAL_SOURCE_NUMERIC_CALIBRATION",
            "source_status")
        _eq(zone["position_requirement"],
            ("WATCH_ONLY_NO_POSITION_REQUIRED"
             if i == 0 else "VERIFIED_OPEN_SHORT_REQUIRED"),
            "position_requirement")
        _eq(zone["stage_names"], ["R0", "R_C", "R_E", "R_F"],
            "stage_names")
        phases = _keys(zone["stage_hypotheses"],
                       {"R0", "R_C", "R_E", "R_F"}, "stage_hypotheses")
        _eq(phases, proposed[i]["phases"], "source_approved_stages_from_P029")
        if not all(isinstance(v, str) and len(v) > 40
                   for v in phases.values()):
            raise ValueError("P030_STAGE_NOT_APPROVED_DESIGN_ONLY")
        _eq(zone["numeric_thresholds"], {}, "numeric_thresholds")
        invalid = zone["invalid_if"]
        if (not isinstance(invalid, list) or len(invalid) < 4
                or not all(isinstance(x, str) and x for x in invalid)
                or len(set(invalid)) != len(invalid)):
            raise ValueError("P030_MISSING_FAIL_CLOSED_INVALIDATION")
        if i > 0 and ("NO_VERIFIED_OPEN_SHORT" not in invalid
                      or "NO_APPROVED_POSITION_EXIT_RULE" not in invalid):
            raise ValueError("P030_EXIT_SHORT_MUST_VERIFY_POSITION")
        if i == 0 and "COUNTERTREND_WATCH_PROMOTED_TO_SHORT_ENTRY" not in invalid:
            raise ValueError("P030_WATCH_CANNOT_OPEN_SHORT")
        for key, expected in (
            ("proposed", ADDITIONS[i]), ("existing", MIRRORS[i]),
            ("purpose", ROLES[i]),
        ):
            _eq(proposed[i][key], expected, "source_proposal." + key)
        new_zones.append(MfxDesignZone(
            label=ADDITIONS[i], purpose=ROLES[i], mirror_of=MIRRORS[i],
            requires_verified_open_short=(i > 0),
        ))

    counts = _keys(root["counts"], {
        "original_forex_catalog_labels", "previous_mfx_design_labels",
        "newly_approved_mfx_design_labels", "effective_mfx_design_labels",
        "entry_long_design_candidates", "entry_short_design_candidates",
        "effective_entry_candidates", "watch_only_labels",
        "exit_long_warning_labels", "exit_short_warning_labels",
        "total_watch_labels", "total_protection_labels",
        "total_nonentry_labels", "approved_entry_numeric_predicates",
        "original_b2_s2_numeric_requirements_pending",
    }, "counts")
    for key, expected in (
        ("original_forex_catalog_labels", 18),
        ("previous_mfx_design_labels", 19),
        ("newly_approved_mfx_design_labels", 3),
        ("effective_mfx_design_labels", 22),
        ("entry_long_design_candidates", 8),
        ("entry_short_design_candidates", 8),
        ("effective_entry_candidates", 16),
        ("watch_only_labels", ["B7", "FX-S11"]),
        ("exit_long_warning_labels", ["S3", "S8"]),
        ("exit_short_warning_labels", ["FX-B10", "FX-B11"]),
        ("total_watch_labels", 2),
        ("total_protection_labels", 4),
        ("total_nonentry_labels", 6),
        ("approved_entry_numeric_predicates", 0),
        ("original_b2_s2_numeric_requirements_pending", 36),
    ):
        _eq(counts[key], expected, "counts." + key)

    governance = _keys(root["cross_zone_governance"], {
        "original_18_and_prior_19_remain_immutable",
        "no_new_buy_or_sell_entry_rule",
        "no_opposite_entry_from_protection",
        "same_instrument_calendar_origin_one_research_opportunity",
        "entry_and_position_protection_are_distinct_roles",
        "no_position_exit_warning_watches_only_no_signal",
        "source_context_unknown_no_signal",
        "do_not_copy_mirror_thresholds_sl_tp_spread_swap_oos",
    }, "cross_zone_governance")
    for key, asserted in governance.items():
        _eq(asserted, True, key)

    stop = _keys(root["stop_gates"], {
        "all_research_stage", "current_action", "eligible_for_trading",
        "eligible_for_live_signal", "eligible_for_live_exit_warning",
        "live_data_provider_calls", "real_drive_market_quote_cache_writes",
        "broker_orders", "release_ready",
    }, "stop_gates")
    _eq(stop["all_research_stage"], "UNVERIFIED", "all_research_stage")
    _eq(stop["current_action"], "NO_SIGNAL", "current_action")
    for key in ("eligible_for_trading", "eligible_for_live_signal",
                "eligible_for_live_exit_warning", "release_ready"):
        _eq(stop[key], False, key)
    for key in ("live_data_provider_calls", "real_drive_market_quote_cache_writes",
                "broker_orders"):
        _eq(stop[key], 0, key)

    source_purposes = {z.label: z.purpose.value for z in ZONES}
    prior_labels = previous.extended_labels
    original = tuple(z.label for z in ZONES)
    prior_design = [
        MfxDesignZone(label=label, purpose=(
            ZonePurpose.ENTRY_LONG_CANDIDATE.value if label == "FX-B9"
            else source_purposes[label]
        ), can_open_new_position=False)
        for label in prior_labels
    ]
    combined = tuple(prior_design + new_zones)
    if (len(combined) != 22
            or len({z.label for z in combined}) != 22
            or tuple(z.label for z in combined[:19]) != prior_labels
            or tuple(z.label for z in combined if z.label in original) != original):
        raise ValueError("P030_STRICT_PRIOR_LABEL_ORDER_OR_UNIQUENESS")
    long_labels = tuple(z.label for z in combined
                        if z.purpose == ZonePurpose.ENTRY_LONG_CANDIDATE.value)
    short_labels = tuple(z.label for z in combined
                         if z.purpose == ZonePurpose.ENTRY_SHORT_CANDIDATE.value)
    watch_labels = tuple(z.label for z in combined
                         if z.purpose == ZonePurpose.WATCH_ONLY.value)
    long_exit = tuple(z.label for z in combined
                      if z.purpose == ZonePurpose.EXIT_LONG_WARNING_ONLY.value)
    short_exit = tuple(z.label for z in combined
                       if z.purpose == "EXIT_SHORT_WARNING_ONLY")
    if (len(long_labels), len(short_labels),
            watch_labels, long_exit, short_exit) != (
            8, 8, ("B7", "FX-S11"), ("S3", "S8"),
            ("FX-B10", "FX-B11")):
        raise ValueError("P030_8_8_2_4_ROLE_COUNTS_VIOLATED")
    return Mfx22DesignReceipt(
        zones=combined, original_labels=original,
        previous_mfx_19_labels=prior_labels,
        approved_new_labels=ADDITIONS,
        entry_long_labels=long_labels, entry_short_labels=short_labels,
        watch_labels=watch_labels, exit_long_warning_labels=long_exit,
        exit_short_warning_labels=short_exit,
    )


def read_22_zone_design_manifest() -> Mfx22DesignReceipt:
    value = _sealed_json(CONTRACT, CONTRACT_SHA, 32768)
    return verify_22_zone_design_manifest(value)


def nonentry_design_preview(label: str,
                            claimed_verified_open_short: bool) -> DesignOnlyRoute:
    """Never an actionable signal; caller claim is NOT real position evidence."""
    if type(label) is not str or type(claimed_verified_open_short) is not bool:
        raise TypeError("P030_TYPED_DESIGN_PREVIEW_REQUIRED")
    receipt = read_22_zone_design_manifest()
    zones = [z for z in receipt.zones if z.label == label
             and z.label in ADDITIONS]
    if len(zones) != 1:
        raise ValueError("P030_ONLY_APPROVED_NONENTRY_NEW_LABELS")
    zone = zones[0]
    claimed_gate = (not zone.requires_verified_open_short
                    or claimed_verified_open_short)
    return DesignOnlyRoute(
        label=label, design_role=zone.purpose,
        position_gate_satisfied_by_claim=claimed_gate,
        research_display=("RESEARCH_SCOPE_ONLY"
                          if claimed_gate else "NO_POSITION_WATCH_ONLY"),
    )
