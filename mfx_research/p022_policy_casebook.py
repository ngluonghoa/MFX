"""A04/P0.22: strictly offline, unapproved B2/S2 policy proposal + truth table.

This module is intentionally OUTSIDE frozen forex_trading domain and wheel.
It may neither promote a fabricated BUY/SELL to a verified Forex signal nor
use licensed market data or write a Google Drive price cache.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from forex_trading.market_data import BarCoverage, BarLifecycle, BarSide, Timeframe
from mfx_research.confirmed_swings import (
    derive_swing_b2_s2_research, detect_confirmed_swings,
)
from mfx_research.source_parameter_review import (
    DOCUMENT_ID, REQUIREMENTS, SCHEMA as P21_SCHEMA, VERSION as P21_VERSION,
    read_review_register,
)
from tools.run_a04_p19_causal_context_demo import case_from_closed_bars
from tools.run_a04_p20_confirmed_swing_demo import case_confirmed

SCHEMA = "MFX_A04_P22_SIM_POLICY_AND_CASEBOOK_V1"
VERSION = "SIM:P022-B2-S2-REVIEW-001"
CASEBOOK = Path("docs/MFX_A04_P22_SIM_POLICY_CASEBOOK.json")
P21_REGISTER = Path("docs/MFX_A04_P21_SOURCE_PARAMETER_REGISTER.json")
# The order, rule, variant and outcome are code-pinned, not user-configured.
# None of these is a real historical sample or Forex source-approved numeric rule.
EXPECTED_CASES: tuple[tuple[str, str, str, str, str], ...] = (
    ("B2_BASELINE_BUY", "B2", "BASELINE", "BUY",
     "P018_SYNTHETIC_PARAMETRIC_PATTERN_UNVERIFIED"),
    ("S2_BASELINE_SELL", "S2", "BASELINE", "SELL",
     "P018_SYNTHETIC_PARAMETRIC_PATTERN_UNVERIFIED"),
    ("B2_INSUFFICIENT_D1", "B2", "SHORT_D1", "NO_SIGNAL",
     "P018_TREND_NOT_SUPPORTED"),
    ("S2_INSUFFICIENT_H4", "S2", "SHORT_H4", "NO_SIGNAL",
     "P018_TREND_NOT_SUPPORTED"),
    ("B2_EARLY_RIGHT_BAR", "B2", "UNCONFIRMED_RIGHT", "DENIED",
     "FUTURE_PRICE_BAR"),
    ("S2_FUTURE_KNOWN_RIGHT", "S2", "FUTURE_RETRIEVAL", "DENIED",
     "FUTURE_KNOWN"),
    ("B2_REAL_PROVIDER_FORGERY", "B2", "FORGED_PROVIDER", "DENIED",
     "REJECT_REAL_MARKET_SOURCE"),
    ("S2_FAKE_LICENSE", "S2", "FORGED_LICENSE", "DENIED",
     "REJECT_REAL_MARKET_SOURCE"),
    ("B2_OPEN_CANDLE", "B2", "OPEN_CANDLE", "DENIED",
     "OPEN_PROVISIONAL_BAR"),
    ("S2_PARTIAL_CANDLE", "S2", "PARTIAL_CANDLE", "DENIED",
     "INCOMPLETE_COVERAGE"),
    ("B2_MIXED_BID_SIDE", "B2", "MIXED_SIDE", "DENIED",
     "CROSS_TIMEFRAME_OR_SIDE"),
    ("S2_OTHER_INSTRUMENT", "S2", "OTHER_INSTRUMENT", "DENIED",
     "CROSS_TIMEFRAME_IDENTITY"),
    ("B2_FAKE_APPROVAL_VERSION", "B2", "FORGED_POLICY_VERSION", "DENIED",
     "SIM_ONLY_UNAPPROVED"),
    ("S2_BOOLEAN_PIVOT_WINDOW", "S2", "BOOLEAN_PIVOT", "DENIED",
     "INVALID_EXPLICIT"),
)


def _object(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("P022_EXACT_SCHEMA:" + label)
    return value


def _equal(value: object, expected: object, label: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ValueError("P022_UNAPPROVED_OR_TAMPERED:" + label)


def _distinct(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("P022_DUPLICATE_KEY:" + key)
        out[key] = value
    return out


def verify_casebook(data: object) -> dict[str, int | bool | str]:
    """Enforce source lineage, 36 pending items, test-only examples and denial."""
    root = _object(data, {
        "schema", "version", "source", "proposal_status",
        "proposal_parameters", "tests", "independent_qualifications",
        "permissions",
    }, "root")
    _equal(root["schema"], SCHEMA, "schema")
    _equal(root["version"], VERSION, "version")
    _equal(root["proposal_status"],
           "UNAPPROVED_DESIGN_FOR_OWNER_REVIEW_ONLY", "proposal_status")
    source = _object(root["source"], {
        "document_id", "baseline", "register_schema", "register_version",
        "source_numerical_approved", "approved_entry_detectors",
        "pending_approval_obligations",
    }, "source")
    for key, expected in (
        ("document_id", DOCUMENT_ID),
        ("baseline", "SOURCE_LOCKED_03_DETECTOR_AUDIT"),
        ("register_schema", P21_SCHEMA),
        ("register_version", P21_VERSION),
        ("source_numerical_approved", False),
        ("approved_entry_detectors", 0),
        ("pending_approval_obligations", 36),
    ):
        _equal(source[key], expected, "source." + key)

    # The P0.21 register is independently validated by read_casebook().
    # Every SIM example is equal to the frozen P0.21 research example, so
    # adding a plausible new decimal does not silently create a numeric rule.
    proposals = root["proposal_parameters"]
    if not isinstance(proposals, list) or len(proposals) != 2:
        raise ValueError("P022_EXACT_TWO_PROPOSALS")
    sim_count = 0
    for index, rule in enumerate(proposals):
        item = _object(rule, {
            "rule_id", "direction", "source_status",
            "numeric_policy_status", "requirements",
        }, "proposal")
        rid = ("B2", "S2")[index]
        for key, expected in (
            ("rule_id", rid), ("direction", ("LONG", "SHORT")[index]),
            ("source_status", "SOURCE_NUMERIC_SPEC_PENDING"),
            ("numeric_policy_status", "SIM_RESEARCH_PROPOSAL_NOT_APPROVED"),
        ):
            _equal(item[key], expected, rid + "." + key)
        fields = item["requirements"]
        if not isinstance(fields, list) or len(fields) != 18:
            raise ValueError("P022_EXACT_EIGHTEEN_FIELDS_PER_RULE")
        for pos, raw in enumerate(fields):
            row = _object(raw, {
                "id", "phase", "source_paragraph_index", "proposed_sim_value",
                "approved_numeric_value", "calibration_evidence_required",
                "independent_review_evidence",
            }, "field")
            name, phase, bidx, sidx = REQUIREMENTS[pos]
            for key, expected_field_value in (
                ("id", name), ("phase", phase),
                ("source_paragraph_index", bidx if index == 0 else sidx),
                ("approved_numeric_value", None),
                ("independent_review_evidence", None),
            ):
                _equal(row[key], expected_field_value, rid + "." + name + "." + key)
            sim = row["proposed_sim_value"]
            if sim is not None:
                if (not isinstance(sim, str) or not sim.startswith("SIM:")
                        or len(sim) > 128 or len(sim) <= 4):
                    raise ValueError("P022_NON_SIM_PARAMETER_PROPOSAL")
                sim_count += 1
            method = row["calibration_evidence_required"]
            if not isinstance(method, str) or len(method.strip()) < 20:
                raise ValueError("P022_CALIBRATION_EVIDENCE_NOT_DEFINED")
    _equal(sim_count, 14, "sim_example_count")

    tests = _object(root["tests"], {
        "basis", "cases", "external_oos_performed",
    }, "tests")
    _equal(tests["basis"],
           "FABRICATED_CLOSED_SIM_OHLC_WITH_P020_CAUSAL_CODE", "basis")
    _equal(tests["external_oos_performed"], False, "external_oos_performed")
    cases = tests["cases"]
    if not isinstance(cases, list) or len(cases) != len(EXPECTED_CASES):
        raise ValueError("P022_TRUTH_TABLE_INCOMPLETE")
    for pos, row in enumerate(cases):
        case = _object(row, {
            "case_id", "rule_id", "variant", "expected_action",
            "expected_reason_contains",
        }, "test_case")
        for key, expected in zip((
            "case_id", "rule_id", "variant", "expected_action",
            "expected_reason_contains",
        ), EXPECTED_CASES[pos]):
            _equal(case[key], expected, "case." + key)

    quals = _object(root["independent_qualifications"], {
        "vendor_license", "google_drive_market_cache_rights",
        "broker_native_bidask", "session_dst_validation",
        "tp_sl_net_r_validation", "real_walkforward_oos",
        "owner_numeric_approval",
    }, "external_qualifications")
    for key, expected in (
        ("vendor_license", "MISSING"),
        ("google_drive_market_cache_rights", "MISSING"),
        ("broker_native_bidask", "MISSING"),
        ("session_dst_validation", "MISSING"),
        ("tp_sl_net_r_validation", "MISSING"),
        ("real_walkforward_oos", "NOT_RUN"),
        ("owner_numeric_approval", "NOT_GRANTED"),
    ):
        _equal(quals[key], expected, "qualifications." + key)
    permissions = _object(root["permissions"], {
        "confirmed_buy_sell_alerts", "real_market_data",
        "drive_price_cache", "broker_order_execution", "release_ready",
    }, "permissions")
    for key, value in permissions.items():
        _equal(value, False, "permissions." + key)
    return {
        "case_count": len(cases), "unapproved_numeric_obligations": 36,
        "sim_example_count": sim_count, "source_rules_approved": 0,
        "confirmed_signals_allowed": False,
        "real_feed_calls": 0, "real_drive_market_cache_writes": 0,
        "release_ready": False, "status": "UNVERIFIED_RESEARCH_ONLY",
    }


def read_casebook(path: Path = CASEBOOK) -> tuple[dict[str, int | bool | str], str]:
    if not isinstance(path, Path):
        raise TypeError("P022_PATH_REQUIRED")
    raw = path.read_bytes()
    if not raw or len(raw) > 131072:
        raise ValueError("P022_INVALID_CASEBOOK_LENGTH")
    data: Any = json.loads(raw.decode("utf-8"), object_pairs_hook=_distinct)
    receipt = verify_casebook(data)
    # Cross-check the independently established P0.21 immutable register.
    source_receipt, _ = read_review_register(P21_REGISTER)
    if (source_receipt.pending_source_numerical_approvals != 36
            or source_receipt.source_numeric_rules_approved != 0):
        raise ValueError("P022_P21_SOURCE_REVIEW_NO_LONGER_LOCKED")
    p21: Any = json.loads(
        P21_REGISTER.read_text(encoding="utf-8"), object_pairs_hook=_distinct,
    )
    proposals = data["proposal_parameters"]
    for idx in range(2):
        for j in range(18):
            old = p21["rules"][idx]["requirements"][j]
            new = proposals[idx]["requirements"][j]
            if (old["id"] != new["id"]
                    or old["source_paragraph_index"]
                    != new["source_paragraph_index"]
                    or old["research_sim_example"] != new["proposed_sim_value"]):
                raise ValueError("P022_PROPOSAL_DIFFERS_FROM_P21_RESEARCH_EXAMPLE")
    # SHA is content integrity, not independent signature or approval.
    return receipt, sha256(raw).hexdigest()


def run_synthetic_case(rule_id: str, variant: str) -> tuple[str, str]:
    """Exercise the actual P0.20 causal pipeline or its negative safety gates."""
    data, pivot = case_confirmed(rule_id)
    _, zone, trigger = case_from_closed_bars(rule_id)
    cutoff = data.trigger_m15[-1].first_known_utc + timedelta(seconds=1)
    try:
        if variant in ("BASELINE", "SHORT_D1", "SHORT_H4", "OTHER_INSTRUMENT"):
            if variant == "SHORT_D1":
                data = replace(data, daily=data.daily[:4])
            elif variant == "SHORT_H4":
                data = replace(data, four_hour=data.four_hour[:4])
            elif variant == "OTHER_INSTRUMENT":
                first = data.daily[0]
                changed = replace(
                    first, key=replace(first.key, instrument_version="SIM:OTHER"),
                )
                data = replace(data, daily=(changed,) + data.daily[1:])
            receipt = derive_swing_b2_s2_research(
                rule_id, data, pivot, zone, trigger, cutoff,
                origin_event_id="SIM:P022-" + rule_id,
            )
            if (receipt.may_send_confirmed_signal or receipt.can_trade
                    or receipt.source_forex_1to1_numerical_parity
                    or receipt.market_provider_calls
                    or receipt.drive_raw_market_cache_writes
                    or receipt.signal.may_send_confirmed_signal
                    or receipt.signal.original_forex_numerical_parity):
                raise ValueError("P022_UNAUTHORIZED_SIGNAL_PROMOTION")
            return receipt.signal.action.value, receipt.signal.reason
        if variant == "UNCONFIRMED_RIGHT":
            detect_confirmed_swings(
                data.daily[:7], Timeframe.D1, pivot,
                data.daily[6].first_known_utc - timedelta(seconds=1),
            )
        elif variant == "FUTURE_RETRIEVAL":
            bar = data.four_hour[6]
            future = replace(
                bar, observation=replace(
                    bar.observation,
                    retrieved_at_utc=data.trigger_m15[0].key.bar_start_utc
                    + timedelta(seconds=1),
                ),
            )
            detect_confirmed_swings(
                data.four_hour[:6] + (future,) + data.four_hour[7:],
                Timeframe.H4, pivot, data.trigger_m15[0].key.bar_start_utc,
            )
        elif variant == "FORGED_PROVIDER":
            bar = data.daily[2]
            changed = replace(
                bar, observation=replace(bar.observation, provider_id="OANDA"),
            )
            detect_confirmed_swings(
                data.daily[:2] + (changed,) + data.daily[3:],
                Timeframe.D1, pivot, data.trigger_m15[0].key.bar_start_utc,
            )
        elif variant == "FORGED_LICENSE":
            bar = data.daily[3]
            changed = replace(
                bar, observation=replace(
                    bar.observation, license_scope_claim="APPROVED",
                ),
            )
            detect_confirmed_swings(
                data.daily[:3] + (changed,) + data.daily[4:],
                Timeframe.D1, pivot, data.trigger_m15[0].key.bar_start_utc,
            )
        elif variant in ("OPEN_CANDLE", "PARTIAL_CANDLE", "MIXED_SIDE"):
            bar = data.daily[3] if variant != "PARTIAL_CANDLE" else data.four_hour[6]
            if variant == "OPEN_CANDLE":
                changed = replace(bar, lifecycle=BarLifecycle.OPEN)
                series = data.daily[:3] + (changed,) + data.daily[4:]
                tf = Timeframe.D1
            elif variant == "PARTIAL_CANDLE":
                changed = replace(bar, coverage=BarCoverage.PARTIAL)
                series = data.four_hour[:6] + (changed,) + data.four_hour[7:]
                tf = Timeframe.H4
            else:
                changed = replace(bar, key=replace(bar.key, side=BarSide.BID))
                series = data.daily[:3] + (changed,) + data.daily[4:]
                tf = Timeframe.D1
            detect_confirmed_swings(
                series, tf, pivot, data.trigger_m15[0].key.bar_start_utc,
            )
        elif variant == "FORGED_POLICY_VERSION":
            replace(pivot, version="APPROVED:P022")
        elif variant == "BOOLEAN_PIVOT":
            replace(pivot, left_bars=True)
        else:
            raise ValueError("P022_UNKNOWN_VARIANT:" + variant)
    except (ValueError, TypeError) as exc:
        return "DENIED", str(exc)
    return "UNEXPECTED_ACCEPT", "P022_DENIAL_GATE_DID_NOT_REJECT"


def run_truth_table() -> dict[str, int | bool | str]:
    receipt, fingerprint = read_casebook()
    for case_id, rule, variant, expected_action, expected_reason in EXPECTED_CASES:
        action, reason = run_synthetic_case(rule, variant)
        if action != expected_action or expected_reason not in reason:
            raise ValueError(
                "P022_CASE_MISMATCH:" + case_id + ":" + action + ":" + reason,
            )
    return {
        **receipt, "casebook_sha256": fingerprint,
        "passed_cases": len(EXPECTED_CASES),
        "research_buy_cases": 1, "research_sell_cases": 1,
        "no_signal_cases": 2, "denied_cases": 10,
        "may_publish_verified_buy_sell": False,
    }
