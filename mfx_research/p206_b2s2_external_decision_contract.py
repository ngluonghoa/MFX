"""P0.206: seven unresolved B2/S2 mirrored source-owner decision contracts.

Completes the *review questions* alongside P188's eleven experimental pairs,
not the numerical strategy. No vendor, Drive, broker, clock or source I/O.
Symbolic bounds deliberately contain no approved parameter values.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from mfx_research.p188_b2s2_numeric_owner_review_candidates import (
    EXTERNAL_UNRESOLVED, POLICY_STATUS, UNRESOLVED_STATUS,
    compile_p188_review_draft,
)
from mfx_research.source_parameter_review import REQUIREMENTS

VERSION = "MFX_P206_REMAINING_SEVEN_B2S2_OWNER_EXTERNAL_DECISIONS_V1"
STATE = "CONDITIONAL_DESIGN_ONLY_NOT_AN_OWNER_PROPOSAL_OR_APPROVAL"
BLOCKED = "NO_SIGNAL"
REQUIRES = (
    "NUMERIC_SOURCE_OWNER_SIGNOFF",
    "ACCOUNT_VENDOR_LICENSED_DATA_USE_AND_RETENTION",
    "SOURCE_FIRST_KNOWN_AND_REVISION_AUTHORITY",
    "REAL_BIDASK_COST_AND_OOS_EVIDENCE",
)
# Each tuple: source requirement ID, B2 LONG conditional design,
# S2 SHORT conditional design, owner/external values still missing,
# independent non-numeric evidence required. None are defaults.
_CONTRACTS: tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "structural_hl_lh_invalidation",
        "B2: cancel candidate if a CLOSED bar violates a pre-known higher-low support minus an owner-defined buffer; no lookahead.",
        "S2: cancel candidate if a CLOSED bar violates a pre-known lower-high resistance plus an owner-defined buffer; no lookahead.",
        ("pivot_invalidation_rule_version", "structure_buffer_price_or_atr"),
        ("closed_timestamped_support_resistance", "reviewed_source_invalidation_policy"),
    ),
    (
        "bid_ask_spread_and_cost_gate",
        "B2: use time-matched executable ASK entry and BID exit; block unless spread, commissions, slippage and owner-defined cost ceiling are verified.",
        "S2: use time-matched executable BID entry and ASK exit; block unless spread, commissions, slippage and owner-defined cost ceiling are verified.",
        ("max_spread", "fee_schedule", "slippage_model", "max_total_cost"),
        ("licensed_historical_bidask", "quote_first_known", "account_cost_terms"),
    ),
    (
        "session_dst_rollover_news_gate",
        "B2: require an owner-approved tradable session calendar; reject unverified DST, rollover, blackout or news windows before LONG entry.",
        "S2: require an owner-approved tradable session calendar; reject unverified DST, rollover, blackout or news windows before SHORT entry.",
        ("session_policy", "rollover_blackout", "news_blackout"),
        ("authenticated_session_calendar", "known_at_news_feed", "timezone_dst_version"),
    ),
    (
        "structural_sl_tp_net_r_gate",
        "B2: SL below pre-known LONG support, TP at pre-known opposing resistance, ASK entry/BID exit; require positive after-cost risk and owner-defined net R threshold.",
        "S2: SL above pre-known SHORT resistance, TP at pre-known opposing support, BID entry/ASK exit; require positive after-cost risk and owner-defined net R threshold.",
        ("sl_buffer", "tp_selection_policy", "minimum_net_r", "fill_uncertainty_policy"),
        ("right_confirmed_structure", "licensed_bidask", "fees_spread_slippage", "same_bar_path_policy"),
    ),
    (
        "event_expiry_and_idempotence",
        "B2: hash a stable source-version, LONG rule-version, origin and CLOSED M15 trigger; expire after owner-defined closed M15 count or invalidation, dedupe replays.",
        "S2: hash a stable source-version, SHORT rule-version, origin and CLOSED M15 trigger; expire after owner-defined closed M15 count or invalidation, dedupe replays.",
        ("expiry_closed_m15_bars", "origin_policy", "event_revision_policy"),
        ("event_first_known_history", "source_version_hash", "duplicate_replay_negative_fixtures"),
    ),
    (
        "licensed_source_first_known_revision",
        "B2: reject LONG when source account rights, original SHA, publisher first-known at decision or owner-admitted D1 revision are not independently established.",
        "S2: reject SHORT when source account rights, original SHA, publisher first-known at decision or owner-admitted D1 revision are not independently established.",
        ("admissible_source_version", "revision_resolution_policy", "retention_ttl"),
        ("provider_account_license", "immutable_original_and_revision_roots", "publisher_first_known_witness"),
    ),
    (
        "historical_walkforward_oos_qualification",
        "B2: chronological LONG walk-forward with untouched OOS, embargo, source-asof and BIDASK net-cost scoring; require separately owner-qualified statistical bounds.",
        "S2: chronological SHORT walk-forward with untouched OOS, embargo, source-asof and BIDASK net-cost scoring; require separately owner-qualified statistical bounds.",
        ("oos_min_samples", "embargo", "walkforward_splits", "max_drawdown", "net_expectancy_floor"),
        ("timestamped_licensed_bidask_history", "pre_registered_oos_evidence", "independent_replay_and_owner_signoff"),
    ),
)


@dataclass(frozen=True, slots=True)
class ExternalDecision:
    requirement_id: str
    phase: str
    b2_source_paragraph_index: int
    s2_source_paragraph_index: int
    b2_conditional_design: str
    s2_conditional_design: str
    owner_values_missing: tuple[str, ...]
    independent_evidence_missing: tuple[str, ...]
    state: str = STATE
    owner_approved: bool = False
    original_forex_numeric_parity: bool = False
    may_publish_buy_sell: bool = False


@dataclass(frozen=True, slots=True)
class P206ReviewReceipt:
    version: str
    complete_source_review_questions: int
    existing_experimental_paired_drafts: int
    remaining_conditional_paired_questions: int
    external: tuple[ExternalDecision, ...]
    review_digest_sha256: str
    original_source_numeric_approvals: int = 0
    original_source_numeric_pending: int = 36
    owner_authentication_verified: bool = False
    account_license_verified: bool = False
    publisher_first_known_verified: bool = False
    bidask_net_r_verified: bool = False
    historical_oos_verified: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    action: str = BLOCKED
    provider_calls: int = 0
    drive_writes: int = 0
    broker_orders: int = 0

    def public_summary(self) -> dict[str, object]:
        return {
            "schema": self.version,
            "review_question_pairs": self.complete_source_review_questions,
            "pre_existing_mfx_experiment_pairs": self.existing_experimental_paired_drafts,
            "seven_new_conditional_questions_not_numeric_proposals": self.remaining_conditional_paired_questions,
            "missing_external_requirement_ids": [x.requirement_id for x in self.external],
            "unapproved_original_source_numeric_decisions": self.original_source_numeric_pending,
            "approved_original_source_numeric_decisions": self.original_source_numeric_approvals,
            "may_publish_buy_sell": False,
            "action": BLOCKED, "broker_orders": 0, "drive_writes": 0,
        }


def compile_p206_remaining_decisions(
    *,
    expected_contracts: tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...]], ...] = _CONTRACTS,
) -> P206ReviewReceipt:
    """Pin exact paired qualitative contracts; reject modified authorizations."""
    if type(expected_contracts) is not tuple or expected_contracts != _CONTRACTS:
        raise ValueError("P206_SOURCE_GATES_NOT_OWNER_AUTHORIZED_TO_CHANGE")
    baseline = compile_p188_review_draft()
    if len(baseline.rows) != len(REQUIREMENTS):
        raise ValueError("P206_SOURCE_18_PAIR_COUNT_CHANGED")
    if (baseline.experimental_pairs_for_review != 11
            or baseline.unresolved_source_pairs != 7
            or baseline.original_owner_numeric_approvals != 0
            or baseline.pending_original_numeric_decisions != 36
            or baseline.owner_authenticated or baseline.may_publish_buy_sell
            or baseline.may_trade or baseline.action != BLOCKED):
        raise ValueError("P206_P188_SOURCE_REVIEW_AUTHORITY_DRIFT")
    by_id = {row[0]: row for row in _CONTRACTS}
    if (len(by_id) != 7 or set(by_id) != set(EXTERNAL_UNRESOLVED)
            or len(REQUIRES) != 4):
        raise ValueError("P206_EXACT_EXTERNAL_SOURCE_GATES_REQUIRED")
    questions = []
    seen: set[str] = set()
    for (rid, phase, b2idx, s2idx), source_row in zip(REQUIREMENTS, baseline.rows):
        if (rid, phase, b2idx, s2idx) != (
                source_row.requirement_id, source_row.phase,
                source_row.b2_source_paragraph_index,
                source_row.s2_source_paragraph_index):
            raise ValueError("P206_SOURCE_PARAGRAPH_OR_PHASE_DRIFT")
        if rid in seen:
            raise ValueError("P206_DUPLICATE_SOURCE_REQUIREMENT")
        seen.add(rid)
        if rid in by_id:
            _, long, short, owner_missing, evidence_missing = by_id[rid]
            if (source_row.status != UNRESOLVED_STATUS
                    or any(x is not None for x in (
                        source_row.b2_formula, source_row.s2_formula,
                        source_row.units, source_row.causal_asof_notes))):
                raise ValueError("P206_EXTERNAL_SOURCE_NUMERIC_INVENTED")
            if (not isinstance(long, str) or not isinstance(short, str)
                    or not long.startswith("B2:") or not short.startswith("S2:")
                    or len(long) > 450 or len(short) > 450
                    or not owner_missing or not evidence_missing
                    or len(set(owner_missing)) != len(owner_missing)
                    or len(set(evidence_missing)) != len(evidence_missing)):
                raise ValueError("P206_INCOMPLETE_PAIRED_EXTERNAL_GATE")
            questions.append(ExternalDecision(
                rid, phase, b2idx, s2idx, long, short,
                owner_missing, evidence_missing,
            ))
        elif source_row.status != POLICY_STATUS or rid not in (
                row.requirement_id for row in baseline.rows
                if row.b2_formula is not None and row.s2_formula is not None):
            raise ValueError("P206_MISSING_P188_EXPERIMENTAL_SOURCE_REVIEW")
    if len(questions) != 7 or len(seen) != 18:
        raise ValueError("P206_SOURCE_18_PAIR_COVERAGE_FAILED")
    projection = [
        (q.requirement_id, q.phase, q.b2_source_paragraph_index,
         q.s2_source_paragraph_index, q.b2_conditional_design,
         q.s2_conditional_design, q.owner_values_missing,
         q.independent_evidence_missing) for q in questions
    ]
    digest = sha256(json.dumps(
        {"version": VERSION, "evidence_pending": projection},
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")).hexdigest()
    return P206ReviewReceipt(VERSION, 18, 11, 7, tuple(questions), digest)
