"""P0.34 — adversarial SIM replay stress + exact 36-item owner decision gate.

The stress harness is deterministic, fixture-limited and Cloud CI-only.
No sample constitutes a source-signed Forex parameter, vendor price,
historical out-of-sample result, trading alert, or broker instruction.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Decimal
from hashlib import sha1
import json
from pathlib import Path
from typing import Any, Callable

from forex_trading.market_data import BarCoverage, BarLifecycle
from mfx_research.p033_asof_sim_replay import (
    ResearchReplayReport, SyntheticReplayWindow,
    run_asof_sim_ohlc_replay, verify_sim_replay_chain,
)
from mfx_research.source_parameter_review import (
    read_review_register, REQUIREMENTS,
)

VERSION = "MFX_A04_P34_ADVERSARIAL_SIM_STRESS_AND_36_OWNER_DOSSIER_V1"
P021 = Path("docs/MFX_A04_P21_SOURCE_PARAMETER_REGISTER.json")
P021_BLOB_SHA = "ef88e20271ad93c34d9d09c0cc6148f67d321929"
DOSSIER = Path("docs/MFX_A04_P34_SOURCE_OWNER_DECISION_DOSSIER.json")
DOSSIER_BLOB_SHA = "9b2625080705078e17572963795b41ca496481a4"
SCENARIOS = (
    "FUTURE_APPEND_PREFIX",
    "NO_PATTERN_LAST",
    "MUTATE_LATER_H1_VALID",
    "DUPLICATE_ORIGIN_IDENTICAL",
    "DUPLICATE_ORIGIN_REVISED",
    "CLOCK_REORDER",
    "FUTURE_GLOBAL_ASOF",
    "OPEN_LAST_M15",
    "PARTIAL_LAST_M15",
    "FUTURE_KNOWN_H4",
    "FUTURE_RETRIEVED_H1",
    "REAL_PROVIDER_H1",
    "REVISED_HISTORY_D1",
    "CALENDAR_MISMATCH_H1",
    "STREAM_MISMATCH_H1",
    "TAMPER_CHAIN_PAYLOAD",
)


def _blob_sha(raw: bytes) -> str:
    return sha1(
        b"blob " + str(len(raw)).encode("ascii") + bytes([0]) + raw
    ).hexdigest()


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("P034_DUPLICATE_DOSSIER_JSON_KEY")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class OwnerDecisionGate:
    rows: tuple[tuple[str, str, str, int], ...]
    original_p021_source_blob_sha: str
    dossier_blob_sha: str
    source_locked_doc_id: str
    pending_owner_decisions: int = 36
    original_numeric_rules_approved: int = 0
    sim_examples_not_approved: int = 14
    signed_owner_evidence: bool = False
    vendor_rights_verified: bool = False
    may_publish_confirmed_buy_sell: bool = False
    may_release: bool = False


def verify_owner_decision_dossier() -> OwnerDecisionGate:
    """Check 36 original pending IDs/paragraph anchors; cannot approve them."""
    src_raw = P021.read_bytes()
    dossier_raw = DOSSIER.read_bytes()
    if (_blob_sha(src_raw) != P021_BLOB_SHA
            or _blob_sha(dossier_raw) != DOSSIER_BLOB_SHA):
        raise ValueError("P034_PINNED_SOURCE_OR_DOSSIER_BLOB_DRIFT")
    original_receipt, _ = read_review_register(P021)
    if (original_receipt.pending_source_numerical_approvals != 36
            or original_receipt.simulated_research_examples != 14
            or original_receipt.source_numeric_rules_approved != 0
            or original_receipt.authenticated_approval_evidence
            or original_receipt.may_send_confirmed_buy_sell_signal):
        raise ValueError("P034_ORIGINAL_NUMERIC_APPROVAL_GATES_CHANGED")
    source: Any = json.loads(src_raw.decode("utf-8"),
                             object_pairs_hook=_strict_pairs)
    data: Any = json.loads(dossier_raw.decode("utf-8"),
                           object_pairs_hook=_strict_pairs)
    if not isinstance(data, dict) or set(data) != {
        "schema", "version", "approval_authority", "source", "counters",
        "owner_evidence_contract", "requirements", "action_gates",
        "related_issues",
    }:
        raise ValueError("P034_DOSSIER_EXACT_TOP_LEVEL_SCHEMA_REQUIRED")
    if (data["schema"] != "MFX_A04_P34_SOURCE_OWNER_DECISION_DOSSIER_V1"
            or data["version"] != "MFX:P034-EXTERNAL_OWNER_EVIDENCE_INTAKE_ONLY"
            or data["approval_authority"] != "NONE_FOR_NUMERIC_SOURCE_RULES"):
        raise ValueError("P034_DOSSIER_COULD_BE_MISTAKEN_FOR_APPROVAL")
    p = data["source"]
    if (p["original_forex_repository"] != "ngluonghoa/forex-trading-1-0"
            or p["frozen_original_forex_commit"]
            != "7e1c1c012b1b189be5ad7b9d07756eac012a8309"
            or p["immutable_p021_register_path"] != str(P021)
            or p["immutable_p021_register_git_blob_sha"] != P021_BLOB_SHA
            or p["source_doc_id"] != original_receipt.source_doc_id
            or p["source_register_version"] != original_receipt.register_version):
        raise ValueError("P034_SOURCE_PARAGRAPH_LINEAGE_DRIFT")
    c = data["counters"]
    for key, expected in (
        ("original_forex_labels", 18),
        ("mfx_approved_design_labels", 22),
        ("source_approved_numeric_entry_predicates", 0),
        ("rule_ids", ["B2", "S2"]),
        ("requirements_per_rule", 18),
        ("pending_source_owner_decisions", 36),
        ("approved_source_owner_decisions", 0),
        ("original_sim_example_values_not_approvals", 14),
        ("real_data_rights_confirmed", False),
    ):
        if type(c[key]) is not type(expected) or c[key] != expected:
            raise ValueError("P034_PENDING_COUNTER_NOT_SOURCE_MATCHED:" + key)
    evidence = data["owner_evidence_contract"]
    if (evidence["owner_decision_options"] !=
            ["APPROVE_WITH_SEPARATELY_VERIFIED_EVIDENCE",
             "REJECT", "DEFER"]
            or evidence["source_owner_signature_or_equivalent_verification"]
            != "NOT_SUPPLIED"
            or not evidence["no_per_row_approval_can_be_derived_from_this_dossier"]
            or evidence["informational_signal_only_no_broker_scope"]
            != "HARD_REQUIREMENT"):
        raise ValueError("P034_OWNER_SIGNOFF_CANNOT_BE_SELF_GRANTED")
    for key in (
        "owner_signed_formula_units_and_version",
        "authoritative_source_doc_supersession_link",
        "causal_quote_side_close_first_known_revision_proof",
        "independent_positive_negative_boundary_fixtures",
        "backward_compatibility_and_mfx_parity_review",
        "licensed_bid_ask_cost_sl_tp_net_r_oos_plan",
    ):
        if evidence[key] != "NOT_SUPPLIED":
            raise ValueError("P034_UNVERIFIED_EXTERNAL_OWNER_EVIDENCE:" + key)
    if data["action_gates"] != {
        "may_mark_original_numeric_rules_approved": False,
        "may_publish_confirmed_buy_sell": False,
        "may_call_real_market_provider": False,
        "may_write_real_fx_quotes_to_drive": False,
        "may_execute_broker_order": False,
        "may_release": False,
    }:
        raise ValueError("P034_TRADE_AND_RELEASE_GATES_MUST_REMAIN_FALSE")
    original_rows = source["rules"]
    expected_rows: list[dict[str, Any]] = []
    for rule in original_rows:
        for value in rule["requirements"]:
            expected_rows.append({
                "rule_id": rule["rule_id"],
                "side": rule["direction"],
                "requirement_id": value["id"],
                "phase": value["phase"],
                "source_paragraph_index": value["source_paragraph_index"],
                "inherited_source_status": value["source_numeric_status"],
                "source_approved_value": None,
                "independently_verified_evidence": None,
                "owner_decision": "AWAITING_SOURCE_OWNER",
                "technical_evidence_status": "NOT_SUBMITTED",
                "sim_research_example_present": value["research_sim_example"] is not None,
                "never_promote_sim_example": True,
            })
    if (data["requirements"] != expected_rows
            or len(expected_rows) != 36
            or len(REQUIREMENTS) != 18):
        raise ValueError("P034_DOSSIER_36_EXACT_SOURCE_ROWS_MISMATCH")
    rows = tuple(
        (r["rule_id"], r["requirement_id"],
         r["phase"], r["source_paragraph_index"])
        for r in expected_rows
    )
    return OwnerDecisionGate(
        rows=rows, original_p021_source_blob_sha=P021_BLOB_SHA,
        dossier_blob_sha=DOSSIER_BLOB_SHA,
        source_locked_doc_id=original_receipt.source_doc_id,
    )


@dataclass(frozen=True, slots=True)
class StressCaseResult:
    scenario: str
    outcome: str
    observed_error: str | None
    prior_prefix_unchanged: bool
    resulting_tip_sha256: str | None
    action: str = "NO_SIGNAL"
    may_publish: bool = False
    market_orders: int = 0


@dataclass(frozen=True, slots=True)
class AdversarialStressReport:
    version: str
    baseline_tip_sha256: str
    prefix_chain_sha256: str
    cases: tuple[StressCaseResult, ...]
    owner_decisions: OwnerDecisionGate
    expected_scenarios: int = 16
    failed_scenarios: int = 0
    original_forex_catalog_labels: int = 18
    approved_mfx_design_labels: int = 22
    independent_price_detectors: tuple[str, str] = ("B2", "S2")
    source_approved_numeric_entry_rules: int = 0
    confirmed_real_signals: int = 0
    actual_market_out_of_sample_metrics: int = 0
    real_market_data_calls: int = 0
    real_drive_quote_writes: int = 0
    alerts_published: int = 0
    broker_orders: int = 0
    release_ready: bool = False


def _edited_h1(w: SyntheticReplayWindow) -> SyntheticReplayWindow:
    old = w.bars.hourly[0]
    modified = replace(old, close=old.close + Decimal("0.00001"))
    if not (modified.low <= modified.close <= modified.high):
        raise ValueError("P034_STRESS_FIXTURE_PRICE_OUT_OF_RANGE")
    return replace(w, bars=replace(
        w.bars, hourly=(modified,) + w.bars.hourly[1:],
    ))


def _latest_m15(w: SyntheticReplayWindow, **changes: Any) -> SyntheticReplayWindow:
    a, b = w.bars.trigger_m15
    modified = replace(b, **changes)
    return replace(w, bars=replace(w.bars, trigger_m15=(a, modified)))


def _last_h4_future(w: SyntheticReplayWindow) -> SyntheticReplayWindow:
    last = w.bars.four_hour[-1]
    late = replace(
        last, first_known_utc=w.bars.trigger_m15[0].key.bar_start_utc
        + timedelta(seconds=2),
    )
    return replace(w, bars=replace(
        w.bars, four_hour=w.bars.four_hour[:-1] + (late,)))


def _last_h1_retrieved_future(w: SyntheticReplayWindow) -> SyntheticReplayWindow:
    last = w.bars.hourly[-1]
    revised_observation = replace(
        last.observation,
        retrieved_at_utc=w.bars.trigger_m15[0].key.bar_start_utc
        + timedelta(seconds=2),
    )
    return replace(w, bars=replace(
        w.bars, hourly=w.bars.hourly[:-1] +
        (replace(last, observation=revised_observation),)))


def _last_h1_vendor(w: SyntheticReplayWindow) -> SyntheticReplayWindow:
    last = w.bars.hourly[-1]
    changed = replace(last, observation=replace(
        last.observation, provider_id="OANDA",
    ))
    return replace(w, bars=replace(
        w.bars, hourly=w.bars.hourly[:-1] + (changed,)))


def _first_d1_revised(w: SyntheticReplayWindow) -> SyntheticReplayWindow:
    original = w.bars.daily[0]
    changed = replace(original, revision_number=2)
    return replace(w, bars=replace(
        w.bars, daily=(changed,) + w.bars.daily[1:],
    ))


def _last_h1_calendar(w: SyntheticReplayWindow) -> SyntheticReplayWindow:
    last = w.bars.hourly[-1]
    changed = replace(last, key=replace(
        last.key, calendar_version="SIM:ADVERSARIAL_ALT",
    ))
    return replace(w, bars=replace(
        w.bars, hourly=w.bars.hourly[:-1] + (changed,)))


def _last_h1_stream(w: SyntheticReplayWindow) -> SyntheticReplayWindow:
    last = w.bars.hourly[-1]
    changed = replace(last, observation=replace(
        last.observation, stream_id="SIM:ADVERSARIAL_ALT",
    ))
    return replace(w, bars=replace(
        w.bars, hourly=w.bars.hourly[:-1] + (changed,)))


def _expected_rejection(
    scenario: str, marker: str, operation: Callable[[], object],
) -> StressCaseResult:
    try:
        operation()
    except (ValueError, TypeError) as exc:
        if marker not in str(exc):
            raise ValueError(
                "P034_INCORRECT_REJECTION_REASON:" + scenario + ":" + str(exc)
            ) from exc
        return StressCaseResult(
            scenario=scenario, outcome="EXPECTED_REJECTION",
            observed_error=marker, prior_prefix_unchanged=True,
            resulting_tip_sha256=None,
        )
    raise ValueError("P034_INVALID_SIM_SCENARIO_WAS_ACCEPTED:" + scenario)


def _safe_accepted(
    scenario: str, report: ResearchReplayReport,
    original_first_sha: str,
) -> StressCaseResult:
    if (not verify_sim_replay_chain(report)
            or not report.entries
            or report.entries[0].chain_sha256 != original_first_sha
            or report.actual_confirmed_buy_sell_signals != 0
            or report.actual_out_of_sample_performance_metrics != 0
            or report.provider_calls != 0
            or report.real_drive_market_cache_writes != 0
            or report.broker_orders != 0
            or report.publish_alerts
            or report.may_trade
            or report.release_ready
            or any(e.action != "NO_SIGNAL" for e in report.entries)):
        raise ValueError("P034_VALID_STRESS_CASE_PROMOTED_OR_CHANGED_PREFIX")
    return StressCaseResult(
        scenario=scenario, outcome="ACCEPTED_RESEARCH_ONLY",
        observed_error=None, prior_prefix_unchanged=True,
        resulting_tip_sha256=report.chain_tip_sha256,
    )


def run_p034_adversarial_stress(
    first: SyntheticReplayWindow,
    later: SyntheticReplayWindow,
) -> AdversarialStressReport:
    """16 finite, deterministic adversarial cases, no real feeds or alerts."""
    if (not isinstance(first, SyntheticReplayWindow)
            or not isinstance(later, SyntheticReplayWindow)):
        raise TypeError("P034_TYPED_TWO_SYNTHETIC_SNAPSHOTS_REQUIRED")
    if first.rule_id != "B2" or later.rule_id != "S2":
        raise ValueError("P034_TEST_FIXTURE_REQUIRES_B2_THEN_S2")
    if first.decision_utc >= later.decision_utc:
        raise ValueError("P034_TWO_SNAPSHOT_CAUSAL_ORDER_REQUIRED")
    owner = verify_owner_decision_dossier()
    prefix = run_asof_sim_ohlc_replay((first,), first.decision_utc)
    baseline = run_asof_sim_ohlc_replay(
        (first, later), later.decision_utc,
    )
    if (baseline.entries[0] != prefix.entries[0]
            or baseline.executed_sim_snapshots != 2
            or baseline.experimental_pattern_observations != 2
            or baseline.entries[0].linked_research_labels != ("B2",)
            or baseline.entries[1].linked_research_labels != ("S2",)):
        raise ValueError("P034_EXPECTED_TWO_COMPUTED_SIM_PILOT_PATTERNS")
    prefix_sha = prefix.chain_tip_sha256
    out: list[StressCaseResult] = []
    out.append(_safe_accepted(
        "FUTURE_APPEND_PREFIX", baseline, prefix_sha,
    ))
    a, b = later.bars.trigger_m15
    no_pattern = _latest_m15(later, close=a.close)
    no_pattern_report = run_asof_sim_ohlc_replay(
        (first, no_pattern), later.decision_utc,
    )
    if (no_pattern_report.no_pattern_snapshots != 1
            or no_pattern_report.entries[1].linked_research_labels != ()
            or no_pattern_report.experimental_pattern_observations != 1):
        raise ValueError("P034_NO_PATTERN_MUST_REMOVE_FALSE_ENTRY")
    out.append(_safe_accepted(
        "NO_PATTERN_LAST", no_pattern_report, prefix_sha,
    ))
    changed = run_asof_sim_ohlc_replay(
        (first, _edited_h1(later)), later.decision_utc,
    )
    if (changed.chain_tip_sha256 == baseline.chain_tip_sha256
            or changed.entries[1].research_input_sha256 ==
            baseline.entries[1].research_input_sha256):
        raise ValueError("P034_LATER_OHLC_FINGERPRINT_DID_NOT_CHANGE")
    out.append(_safe_accepted(
        "MUTATE_LATER_H1_VALID", changed, prefix_sha,
    ))
    extra = timedelta(seconds=1)
    out.append(_expected_rejection(
        "DUPLICATE_ORIGIN_IDENTICAL", "DUPLICATE_OR_REVISED",
        lambda: run_asof_sim_ohlc_replay(
            (first, replace(first, decision_utc=first.decision_utc + extra)),
            later.decision_utc,
        ),
    ))
    out.append(_expected_rejection(
        "DUPLICATE_ORIGIN_REVISED", "DUPLICATE_OR_REVISED",
        lambda: run_asof_sim_ohlc_replay(
            (first, replace(_edited_h1(first),
                            decision_utc=first.decision_utc + extra)),
            later.decision_utc,
        ),
    ))
    out.append(_expected_rejection(
        "CLOCK_REORDER", "NONINCREASING_REPLAY",
        lambda: run_asof_sim_ohlc_replay(
            (later, first), later.decision_utc,
        ),
    ))
    out.append(_expected_rejection(
        "FUTURE_GLOBAL_ASOF", "FUTURE_REPLAY_WINDOW",
        lambda: run_asof_sim_ohlc_replay(
            (first, later), first.decision_utc,
        ),
    ))
    out.append(_expected_rejection(
        "OPEN_LAST_M15", "OPEN_PROVISIONAL",
        lambda: run_asof_sim_ohlc_replay(
            (first, _latest_m15(later, lifecycle=BarLifecycle.OPEN)),
            later.decision_utc,
        ),
    ))
    out.append(_expected_rejection(
        "PARTIAL_LAST_M15", "INCOMPLETE_COVERAGE",
        lambda: run_asof_sim_ohlc_replay(
            (first, _latest_m15(later, coverage=BarCoverage.PARTIAL)),
            later.decision_utc,
        ),
    ))
    out.append(_expected_rejection(
        "FUTURE_KNOWN_H4", "FUTURE_KNOWN",
        lambda: run_asof_sim_ohlc_replay(
            (first, _last_h4_future(later)), later.decision_utc,
        ),
    ))
    out.append(_expected_rejection(
        "FUTURE_RETRIEVED_H1", "FUTURE_KNOWN",
        lambda: run_asof_sim_ohlc_replay(
            (first, _last_h1_retrieved_future(later)),
            later.decision_utc,
        ),
    ))
    out.append(_expected_rejection(
        "REAL_PROVIDER_H1", "REJECT_REAL_MARKET_SOURCE",
        lambda: run_asof_sim_ohlc_replay(
            (first, _last_h1_vendor(later)), later.decision_utc,
        ),
    ))
    out.append(_expected_rejection(
        "REVISED_HISTORY_D1", "REJECT_REAL_MARKET_SOURCE",
        lambda: run_asof_sim_ohlc_replay(
            (first, _first_d1_revised(later)), later.decision_utc,
        ),
    ))
    out.append(_expected_rejection(
        "CALENDAR_MISMATCH_H1", "CROSS_TIMEFRAME_IDENTITY",
        lambda: run_asof_sim_ohlc_replay(
            (first, _last_h1_calendar(later)), later.decision_utc,
        ),
    ))
    out.append(_expected_rejection(
        "STREAM_MISMATCH_H1", "INTRA_TIMEFRAME_STREAM",
        lambda: run_asof_sim_ohlc_replay(
            (first, _last_h1_stream(later)), later.decision_utc,
        ),
    ))
    tampered = replace(baseline, entries=(
        baseline.entries[0],
        replace(baseline.entries[1], payload_sha256="0" * 64),
    ))
    out.append(_expected_rejection(
        "TAMPER_CHAIN_PAYLOAD", "HASH_CHAIN_TAMPER",
        lambda: verify_sim_replay_chain(tampered),
    ))
    if (tuple(item.scenario for item in out) != SCENARIOS
            or len(set(item.scenario for item in out)) != 16
            or sum(item.outcome == "ACCEPTED_RESEARCH_ONLY"
                   for item in out) != 3
            or sum(item.outcome == "EXPECTED_REJECTION"
                   for item in out) != 13):
        raise ValueError("P034_SCENARIO_COVERAGE_AND_OUTCOME_COUNT_DRIFT")
    return AdversarialStressReport(
        version=VERSION, baseline_tip_sha256=baseline.chain_tip_sha256,
        prefix_chain_sha256=prefix_sha, cases=tuple(out),
        owner_decisions=owner,
    )
