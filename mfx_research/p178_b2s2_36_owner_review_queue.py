"""P0.178: 36 exact B2/S2 original-source owner decisions + private evidence gaps.

The real SHA-audited six-frame source can compute *research precursors* but
cannot approve original Forex quantitative formulas. This is an immutable,
privately detailed owner-review queue, not a live signal or policy approval.
No provider, Drive, broker, workflow or external I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from mfx_research.b2_s2_source_computation_crosswalk import (
    SourceComputationCrosswalk, RESEARCH_CATEGORIES,
)
from mfx_research.p177_real_source_b2s2_readiness import PrivateB2S2Readiness
from mfx_research.source_parameter_review import REQUIREMENTS, DOCUMENT_ID

VERSION = "MFX_P178_B2S2_36_OWNER_SOURCE_DECISION_QUEUE_V1"
RULES = ("B2", "S2")

# These links describe *research-source input* dependencies, not
# source-owner thresholds or prerequisites sufficient for a real trade.
TECHNICAL_LINKS: dict[str, tuple[str, ...]] = {
    "causal_d1_h4_trend": (
        "D1_TWO_RIGHT_CONFIRMED_HIGH_LOWS_UNQUALIFIED",
        "H4_TWO_CONFIRMED_HIGHS_AND_LOWS_MISSING",
    ),
    "confirmed_pivot_left_bars": (
        "D1_TWO_RIGHT_CONFIRMED_HIGH_LOWS_UNQUALIFIED",
        "H4_TWO_CONFIRMED_HIGHS_AND_LOWS_MISSING",
    ),
    "confirmed_pivot_right_bars": (
        "D1_TWO_RIGHT_CONFIRMED_HIGH_LOWS_UNQUALIFIED",
        "H4_TWO_CONFIRMED_HIGHS_AND_LOWS_MISSING",
    ),
    "structural_hl_lh_invalidation": (
        "D1_TWO_RIGHT_CONFIRMED_HIGH_LOWS_UNQUALIFIED",
        "H4_TWO_CONFIRMED_HIGHS_AND_LOWS_MISSING",
    ),
    "h1_zone_origin_identity": ("H1_DRAFT_TR_PERIOD_NOT_CLOSED",),
    "h1_zone_lookback": ("H1_DRAFT_TR_PERIOD_NOT_CLOSED",),
    "h1_true_range_atr_period": ("H1_DRAFT_TR_PERIOD_NOT_CLOSED",),
    "h1_near_zone_atr_multiple": ("H1_DRAFT_TR_PERIOD_NOT_CLOSED",),
    "h1_zone_width_atr_multiple": ("H1_DRAFT_TR_PERIOD_NOT_CLOSED",),
    "m15_early_reversal_structure": (
        "M15_PRETRIGGER_CONFIRMED_LEVEL_MISSING",
    ),
    "known_micro_break_confirm_rule": (
        "M15_PRETRIGGER_CONFIRMED_LEVEL_MISSING",
        "M15_CLOSED_MICROBREAK_NOT_OBSERVED",
    ),
    "anti_chase_max_atr_multiple": (
        "H1_DRAFT_TR_PERIOD_NOT_CLOSED",
    ),
}

EXTERNAL_ONLY = frozenset((
    "bid_ask_spread_and_cost_gate",
    "session_dst_rollover_news_gate",
    "structural_sl_tp_net_r_gate",
    "event_expiry_and_idempotence",
    "licensed_source_first_known_revision",
    "historical_walkforward_oos_qualification",
))

PRIVATE_GAP = "PRIVATE_MID_TECHNICAL_PRECURSOR_INCOMPLETE"
PRIVATE_ONLY = "PRIVATE_MID_SIM_PRECURSOR_ONLY"
EXTERNAL = "INDEPENDENT_OWNER_PROVIDER_OR_OOS_EVIDENCE_REQUIRED"


@dataclass(frozen=True, slots=True)
class OriginalSourceDecision:
    rule_id: str
    requirement_id: str
    phase: str
    original_source_paragraph_index: int
    source_numeric_status: str
    private_input_status: str
    research_evidence_category: str
    technical_precondition_gaps: tuple[str, ...] = field(repr=False)
    authenticated_owner_numeric_evidence: bool = False
    original_forex_numeric_rule_approved: bool = False
    is_executable_signal: bool = False


@dataclass(frozen=True, slots=True)
class OriginalSourceDecisionQueue:
    version: str
    source_locked_doc_id: str
    source_register_git_blob: str
    source_dossier_git_blob: str
    asof_utc: str
    source_mode: str
    rows: tuple[OriginalSourceDecision, ...] = field(repr=False)
    source_numeric_approvals: int = 0
    remaining_owner_decisions: int = 36
    public_action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    owner_evidence_authenticated: bool = False
    real_bidask_qualified: bool = False
    provider_first_known_qualified: bool = False
    real_oos_qualified: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_reads_added: int = 0
    drive_writes: int = 0
    broker_orders: int = 0

    def as_safe_summary(self) -> dict[str, object]:
        """Never publish private per-requirement market-derived gate states."""
        return {
            "schema": self.version,
            "status": "SOURCE_OWNER_36_NUMERIC_DECISIONS_PENDING_NO_SIGNAL",
            "source_locked_doc_id": self.source_locked_doc_id,
            "requirements_per_rule": 18,
            "remaining_owner_decisions": self.remaining_owner_decisions,
            "original_source_numeric_approvals": self.source_numeric_approvals,
            "by_rule": [{
                "rule_id": rid,
                "source_numeric_decisions_pending": 18,
                "source_requirement_phases": {
                    phase: sum(x.rule_id == rid and x.phase == phase
                               for x in self.rows)
                    for phase in ("R0", "R_C", "R_E", "R_F",
                                  "INVALIDATION", "QA")
                },
            } for rid in RULES],
            "source_numeric_owner_evidence_approved": False,
            "market_data_rights_verified": False,
            "publisher_first_known_verified": False,
            "real_bidask_net_rr_approved": False,
            "historical_oos_approved": False,
            "action": "NO_SIGNAL",
            "stage": "UNVERIFIED",
            "may_trade": False,
            "provider_requests": 0,
            "drive_reads_added": 0,
            "drive_writes": 0,
            "broker_orders": 0,
        }


def compile_source_owner_36_review_queue(
    crosswalk: SourceComputationCrosswalk,
    readiness: PrivateB2S2Readiness,
    *, same_private_source_sha256: str,
) -> OriginalSourceDecisionQueue:
    """Cross-check exact SOURCE_LOCKED paragraphs against the live P177 gaps.

    This is not a signature, owner review decision, or OOS approval; every
    source numeric approval remains unconditionally pending.
    """
    if (type(crosswalk) is not SourceComputationCrosswalk
            or type(readiness) is not PrivateB2S2Readiness):
        raise TypeError("P178_TYPED_PINNED_SOURCE_REVIEW_REQUIRED")
    if (type(same_private_source_sha256) is not str
            or len(same_private_source_sha256) != 64
            or readiness.private_input_digest_sha256
               != same_private_source_sha256
            or readiness.asof_utc != crosswalk.asof_utc
            or readiness.public_action != "NO_SIGNAL"
            or readiness.stage != "UNVERIFIED"
            or readiness.numeric_policy_approved
            or readiness.original_forex_numeric_1to1
            or readiness.d1_calendar_qualified
            or readiness.publisher_first_known_verified
            or readiness.source_data_license_verified
            or readiness.bidask_net_rr_qualified
            or readiness.real_oos_qualified
            or readiness.may_publish_buy_sell or readiness.may_trade
            or readiness.market_price_requests or readiness.drive_gets_added
            or readiness.drive_writes or readiness.broker_orders
            or crosswalk.source_locked_doc_id != DOCUMENT_ID
            or crosswalk.original_source_numeric_decisions_pending != 36
            or crosswalk.original_b2s2_numeric_approvals != 0
            or crosswalk.independently_authenticated_source_owner_formula
            or crosswalk.authorized_real_bidask_net_rr
            or crosswalk.original_forex_parity_proven
            or crosswalk.historical_oos_qualified
            or crosswalk.live_signal_release_approved
            or crosswalk.action != "NO_SIGNAL"
            or crosswalk.stage != "UNVERIFIED"
            or crosswalk.may_trade or crosswalk.provider_calls
            or crosswalk.drive_market_cache_writes
            or crosswalk.broker_orders):
        raise ValueError("P178_FALSE_SOURCE_OR_LIVE_AUTHORITY_DENIED")
    if (len(REQUIREMENTS) != 18
            or set(TECHNICAL_LINKS)|EXTERNAL_ONLY
                != {name for name,_,_,_ in REQUIREMENTS}
            or set(TECHNICAL_LINKS)&EXTERNAL_ONLY
            or len(crosswalk.rows) != 36
            or len(readiness.gates) != 2
            or tuple(g.rule_id for g in readiness.gates) != RULES
            or any(g.readiness != "RESEARCH_GAPS_NO_SIGNAL"
                   or g.can_publish_buy_sell or g.can_trade
                   for g in readiness.gates)):
        raise ValueError("P178_SOURCE_36_REQUIREMENT_COVERAGE_DRIFT")

    expected = tuple(
        (rid, name, phase, b if rid == "B2" else s)
        for rid in RULES for name, phase, b, s in REQUIREMENTS
    )
    rows: list[OriginalSourceDecision] = []
    for row, (rid,name,phase,paragraph) in zip(crosswalk.rows,expected):
        if (row.rule_id,row.source_requirement_id,row.phase,
                row.original_source_paragraph_index) != (
                rid,name,phase,paragraph):
            raise ValueError("P178_WRONG_SOURCE_DOC_PARAGRAPH_OR_RULE")
        if (row.evidence_basis != RESEARCH_CATEGORIES[name]
                or row.owner_numeric_decision != "AWAITING_SOURCE_OWNER"
                or row.original_source_numeric_rule_approved
                or row.independently_authenticated_owner_evidence
                or row.publisher_first_known_qualified
                or row.vendor_account_data_rights_verified
                or row.eligible_for_verified_buy_sell):
            raise ValueError("P178_FORGED_SOURCE_APPROVAL_OR_EVIDENCE")
        if type(row.observed_research_state) is not str:
            raise ValueError("P178_MISSING_PRIVATE_RESEARCH_CATEGORY")
        gate = readiness.gates[0 if rid == "B2" else 1]
        gaps = tuple(
            dep for dep in TECHNICAL_LINKS.get(name,())
            if dep in gate.missing_preconditions
        )
        state = (EXTERNAL if name in EXTERNAL_ONLY else
                 PRIVATE_GAP if gaps else PRIVATE_ONLY)
        rows.append(OriginalSourceDecision(
            rule_id=rid,requirement_id=name,phase=phase,
            original_source_paragraph_index=paragraph,
            source_numeric_status="ORIGINAL_SOURCE_OWNER_DECISION_PENDING",
            private_input_status=state,
            research_evidence_category=row.evidence_basis,
            technical_precondition_gaps=gaps,
        ))
    if len(rows) != 36:
        raise ValueError("P178_INCOMPLETE_36_SOURCE_ROWS")
    return OriginalSourceDecisionQueue(
        version=VERSION,source_locked_doc_id=crosswalk.source_locked_doc_id,
        source_register_git_blob=crosswalk.source_register_blob,
        source_dossier_git_blob=crosswalk.source_dossier_blob,
        asof_utc=crosswalk.asof_utc,
        source_mode=readiness.source_technical_mode,
        rows=tuple(rows),
    )
