"""P0.188: source-anchored *MFX-only* B2/S2 numeric review suggestions.

Extract 11 actual existing MFX P160/P161 experiment choices into the
18 paired P184 owner REVIEW intake. The other seven are explicitly unresolved.
No original Forex rule is changed or independently approved by this helper.
An external evidence SHA supplied to the builder is syntax-checked but
NEVER authenticated. The returned valid P184 receipt is always NO_SIGNAL.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from re import fullmatch
from typing import Any

from mfx_research.mfx_b2s2_independent_policy_draft import (
    LINEAGE as P160_LINEAGE, read_independent_mfx_policy_draft,
)
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    read_mfx_confirmed_b2s2_v2,
)
from mfx_research.p184_paired_f2_owner_review import (
    TEMPLATE, compile_paired_f2_owner_proposals,
)
from mfx_research.source_parameter_review import REQUIREMENTS

VERSION = "MFX_P188_F2_NUMERIC_TECHNICAL_OWNER_REVIEW_CANDIDATES_V1"
PROPOSEABLE = (
    "causal_d1_h4_trend",
    "confirmed_pivot_left_bars",
    "confirmed_pivot_right_bars",
    "h1_zone_origin_identity",
    "h1_zone_lookback",
    "h1_true_range_atr_period",
    "h1_near_zone_atr_multiple",
    "h1_zone_width_atr_multiple",
    "m15_early_reversal_structure",
    "known_micro_break_confirm_rule",
    "anti_chase_max_atr_multiple",
)
EXTERNAL_UNRESOLVED = (
    "structural_hl_lh_invalidation",
    "bid_ask_spread_and_cost_gate",
    "session_dst_rollover_news_gate",
    "structural_sl_tp_net_r_gate",
    "event_expiry_and_idempotence",
    "licensed_source_first_known_revision",
    "historical_walkforward_oos_qualification",
)
POLICY_STATUS = "MFX_INDEPENDENT_EXPERIMENT_NOT_ORIGINAL_FOREX_RULE"
UNRESOLVED_STATUS = "UNRESOLVED_OWNER_OR_EXTERNAL_EVIDENCE"
_COMMON_ASOF = (
    "CLOSED causal candle prefix only; candidate must be known at decision "
    "time. Actual historical publisher first-known is unverified."
)


@dataclass(frozen=True, slots=True)
class ReviewPair:
    requirement_id: str
    phase: str
    b2_source_paragraph_index: int
    s2_source_paragraph_index: int
    status: str
    b2_formula: str | None
    s2_formula: str | None
    units: str | None
    causal_asof_notes: str | None
    owner_numeric_approved: bool = False
    original_forex_1to1_numeric_parity_verified: bool = False
    may_publish_buy_sell: bool = False


@dataclass(frozen=True, slots=True)
class NumericReviewDraft:
    version: str
    p160_policy_sha256: str
    p161_policy_sha256: str
    rows: tuple[ReviewPair, ...]
    experimental_pairs_for_review: int = 11
    unresolved_source_pairs: int = 7
    original_owner_numeric_approvals: int = 0
    pending_original_numeric_decisions: int = 36
    owner_authenticated: bool = False
    real_vendor_rights_verified: bool = False
    publisher_first_known_verified: bool = False
    live_bidask_risk_verified: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    action: str = "NO_SIGNAL"
    broker_orders: int = 0

    def public_summary(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source_requirements_paired": len(self.rows),
            "mfx_experimental_pairs_for_owner_review":
                self.experimental_pairs_for_review,
            "external_or_methodology_unresolved_pairs":
                self.unresolved_source_pairs,
            "original_source_numeric_approvals": 0,
            "original_source_numeric_pending": 36,
            "external_evidence_sha_authenticated": False,
            "owner_authenticated": False,
            "may_publish_buy_sell": False, "may_trade": False,
            "action": "NO_SIGNAL", "broker_orders": 0,
            "provider_price_requests": 0, "drive_cache_writes": 0,
        }


def _formulas() -> tuple[dict[str, tuple[str, str, str, str]], str, str]:
    p160 = read_independent_mfx_policy_draft()
    p161 = read_mfx_confirmed_b2s2_v2()
    if (p160.strategy_lineage != P160_LINEAGE
            or not p160.user_option_b_development_scope_approved
            or any((p160.specific_numeric_policy_approved,
                    p160.original_forex_numerical_parity_verified,
                    p160.source_license_verified,
                    p160.native_d1_source_revision_qualified,
                    p160.historical_oos_qualified,
                    p160.may_publish_buy_sell, p160.may_trade))
            or p161.numeric_rules_approved or p161.forex_original_numeric_parity
            or p161.market_rights_verified or p161.publisher_first_known_verified
            or p161.native_d1_revision_hold_cleared
            or p161.real_oos_qualified or p161.live_signals_allowed
            or p161.broker_orders_allowed):
        raise ValueError("P188_UNAPPROVED_SOURCE_CONFIG_MUST_STAY_EXPERIMENTAL")
    a,b,c,d = p161.htf_left,p161.htf_right,p161.micro_left,p161.micro_right
    n,z = p160.h1_tr_mean_period,p160.h1_zone_lookback
    near,width,chase = map(str,(p160.h1_near_multiple,
                                p160.h1_width_multiple,
                                p160.max_chase_multiple))
    # Each candidate is an existing P160/P161 research formula. All use
    # mid OHLC and their profile-derived H1 simple-mean TR, NOT Wilder ATR.
    f = {
        "causal_d1_h4_trend": (
            f"D1 and H4 each show two HIGH and LOW pivots confirmed {a}L/{b}R; "
            "both newest confirmed highs and lows strictly higher than prior",
            f"D1 and H4 each show two HIGH and LOW pivots confirmed {a}L/{b}R; "
            "both newest confirmed highs and lows strictly lower than prior",
            "closed right-confirmed H4/D1 swing comparisons",
            "Right-confirmed bar CLOSE does not attest publisher first-known."),
        "confirmed_pivot_left_bars": (
            f"Each D1,H4 pivot needs {a} prior CLOSED left bar; M15 uses {c}",
            f"Each D1,H4 pivot needs {a} prior CLOSED left bar; M15 uses {c}",
            "bars", _COMMON_ASOF),
        "confirmed_pivot_right_bars": (
            f"Each D1,H4 pivot needs {b} CLOSED right confirmation; M15 uses {d}",
            f"Each D1,H4 pivot needs {b} CLOSED right confirmation; M15 uses {d}",
            "bars", _COMMON_ASOF),
        "h1_zone_origin_identity": (
            f"H1 SUPPORT anchor = MIN of LOW over latest {z} CLOSED H1 bars",
            f"H1 RESISTANCE anchor = MAX of HIGH over latest {z} CLOSED H1 bars",
            "MID price; H1 rolling extreme", _COMMON_ASOF),
        "h1_zone_lookback": (
            f"Use latest {z} complete CLOSED H1 bars for B2 support anchor",
            f"Use latest {z} complete CLOSED H1 bars for S2 resistance anchor",
            "H1 bars", _COMMON_ASOF),
        "h1_true_range_atr_period": (
            f"H1 scale = simple MEAN of {n} closed True Ranges, not Wilder ATR",
            f"H1 scale = simple MEAN of {n} closed True Ranges, not Wilder ATR",
            "H1 True Range count",
            _COMMON_ASOF+" Explicit ATR methodology deviation needs owner decision."),
        "h1_near_zone_atr_multiple": (
            f"Prior CLOSED M15 bar overlaps expanded H1 support range by {near} "
            "times H1 simple-mean TR",
            f"Prior CLOSED M15 bar overlaps expanded H1 resistance range by {near} "
            "times H1 simple-mean TR",
            "multiplier of H1 mean TR", _COMMON_ASOF),
        "h1_zone_width_atr_multiple": (
            f"H1 support zone = [anchor, anchor + {width} x H1 mean TR]",
            f"H1 resistance zone = [anchor - {width} x H1 mean TR, anchor]",
            "multiplier of H1 mean TR", _COMMON_ASOF),
        "m15_early_reversal_structure": (
            f"Prior CLOSED M15 bar touches H1 support area; micro HIGH is "
            f"confirmed {c}L/{d}R before trigger M15 begins",
            f"Prior CLOSED M15 bar touches H1 resistance area; micro LOW is "
            f"confirmed {c}L/{d}R before trigger M15 begins",
            "closed M15 reversal and right-confirmed micro pivot",
            _COMMON_ASOF+" No proprietary publisher timestamp inferred."),
        "known_micro_break_confirm_rule": (
            "Prior M15 close <= previously confirmed micro HIGH; latest CLOSED "
            "M15 close > that HIGH",
            "Prior M15 close >= previously confirmed micro LOW; latest CLOSED "
            "M15 close < that LOW",
            "MID price; strict close crossover", _COMMON_ASOF),
        "anti_chase_max_atr_multiple": (
            f"0 <= latest CLOSED M15 close - known micro HIGH <= {chase} "
            "x H1 simple-mean TR",
            f"0 <= known micro LOW - latest CLOSED M15 close <= {chase} "
            "x H1 simple-mean TR",
            "multiplier of H1 mean TR", _COMMON_ASOF),
    }
    return f,p160.canonical_sha256,p161.fingerprint_sha256


def compile_p188_review_draft() -> NumericReviewDraft:
    formulas,p160sha,p161sha = _formulas()
    if set(formulas) != set(PROPOSEABLE):
        raise ValueError("P188_EXACT_MFX_CANDIDATE_COVERAGE_REQUIRED")
    if set(PROPOSEABLE).intersection(EXTERNAL_UNRESOLVED):
        raise ValueError("P188_DUPLICATE_REQUIREMENT")
    rows=[]
    for name,phase,b,s in REQUIREMENTS:
        if name in formulas:
            long,short,units,notes=formulas[name]
            if (not all(type(x) is str and x and len(x)<=512 for x
                        in (long,short,units,notes))):
                raise ValueError("P188_UNSAFE_PUBLIC_REVIEW_FORMULA")
            rows.append(ReviewPair(name,phase,b,s,POLICY_STATUS,
                                   long,short,units,notes))
        elif name in EXTERNAL_UNRESOLVED:
            rows.append(ReviewPair(name,phase,b,s,UNRESOLVED_STATUS,
                                   None,None,None,None))
        else:
            raise ValueError("P188_SOURCE_REQUIREMENT_NOT_CLASSIFIED")
    if len(rows)!=18 or sum(r.b2_formula is not None for r in rows)!=11:
        raise ValueError("P188_EXACT_18_PAIRED_REVIEW_ROWS_REQUIRED")
    return NumericReviewDraft(VERSION,p160sha,p161sha,tuple(rows))


def prepare_p184_external_review(
    *, externally_supplied_evidence_sha256: str,
    selected_requirement_ids: tuple[str, ...],
) -> tuple[dict[str, Any], Any]:
    """Prepare P184/P035 *proposals* only; never approve source or data.

    The SHA MUST be supplied by a real external reviewer. This code verifies
    its string shape only; underlying evidence and signer's identity remain
    independently unverified here.
    """
    if (type(externally_supplied_evidence_sha256) is not str
            or fullmatch(r"[a-f0-9]{64}",
                         externally_supplied_evidence_sha256) is None):
        raise ValueError("P188_REAL_EXTERNAL_EVIDENCE_SHA256_INPUT_REQUIRED")
    if (type(selected_requirement_ids) is not tuple
            or not selected_requirement_ids
            or len(selected_requirement_ids)>len(PROPOSEABLE)
            or any(type(x) is not str for x in selected_requirement_ids)
            or len(set(selected_requirement_ids))!=len(selected_requirement_ids)
            or not set(selected_requirement_ids).issubset(PROPOSEABLE)):
        raise ValueError("P188_EXACT_SUBSET_OF_REVIEWABLE_REQUIREMENTS_REQUIRED")
    draft=compile_p188_review_draft()
    doc=json.loads(TEMPLATE.read_text(encoding="utf-8"))
    selected=set(selected_requirement_ids)
    for target,row in zip(doc["paired_rows"],draft.rows):
        if row.requirement_id not in selected:
            continue
        target.update({
            "review_intent":"PROPOSE_FORMULA",
            "b2_formula":row.b2_formula,
            "s2_formula":row.s2_formula,
            "units":row.units,
            "causal_asof_notes":row.causal_asof_notes,
            "evidence_sha256":externally_supplied_evidence_sha256,
            "rationale":None,
        })
    verified=compile_paired_f2_owner_proposals(doc)
    if (verified.action!="NO_SIGNAL"
            or verified.original_numeric_rules_approved!=0
            or verified.original_pending_numeric_rules!=36
            or verified.may_publish_buy_sell or verified.may_trade
            or verified.expanded_p035_proposal_rows!=2*len(selected)
            or verified.broker_orders!=0):
        raise ValueError("P188_P184_SOURCE_APPROVAL_FORGERY_DENIED")
    return deepcopy(doc),verified
