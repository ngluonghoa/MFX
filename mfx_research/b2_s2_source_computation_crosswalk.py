"""Signal-first P0.157: source-anchored *computation coverage*, not approvals.

Reconcile all 36 B2/S2 source-owner requirements against what the current
SHA-sealed six-TF reader actually computes. A calculated MID range, TR or
SIM pivot is NOT a source-owner formula, first-known, licensed BID/ASK, OOS
or a reason to issue BUY/SELL. No quotes/Drive/API/broker work is performed.
"""
from __future__ import annotations

from dataclasses import dataclass

from mfx_research.p034_sim_adversarial_review import (
    verify_owner_decision_dossier,
)
from mfx_research.sealed_multibar_private_features import (
    PrivateMultiBarFrame, PrivateMultiBarReceipt,
)
from mfx_research.sealed_private_pivot_sensitivity import (
    POLICY_WINDOWS, PrivatePivotFrameStudy, PrivatePivotSensitivityReceipt,
    scan_private_sealed_pivot_sensitivity,
)
from mfx_research.signal_only_six_tf_response import (
    build_signal_only_research_response,
)
from mfx_research.six_tf_sealed_archive_consumer import (
    SealedArchiveSixTFReceipt,
)
from mfx_research.source_parameter_review import REQUIREMENTS

VERSION = "MFX_V1_P157_36_SOURCE_GATED_COMPUTATION_CROSSWALK_V1"

# Names are frozen source requirements, not new trading-strategy parameter
# values. These categories describe available PRIVATE technical precursors.
RESEARCH_CATEGORIES = {
    "causal_d1_h4_trend": "D1_H4_CONTEXT_NOT_SOURCE_QUALIFIED",
    "confirmed_pivot_left_bars": "M15_PIVOT_SENSITIVITY_ONLY",
    "confirmed_pivot_right_bars": "M15_PIVOT_SENSITIVITY_ONLY",
    "structural_hl_lh_invalidation": "M15_PIVOT_SENSITIVITY_ONLY",
    "h1_zone_origin_identity": "H1_ENVELOPE_ONLY",
    "h1_zone_lookback": "H1_ENVELOPE_ONLY",
    "h1_true_range_atr_period": "H1_OBSERVED_TR_MEAN_ONLY",
    "h1_near_zone_atr_multiple": "H1_OBSERVED_TR_MEAN_ONLY",
    "h1_zone_width_atr_multiple": "H1_OBSERVED_TR_MEAN_ONLY",
    "m15_early_reversal_structure": "M15_PIVOT_SENSITIVITY_ONLY",
    "known_micro_break_confirm_rule": "M15_PIVOT_SENSITIVITY_ONLY",
    "anti_chase_max_atr_multiple": "H1_OBSERVED_TR_MEAN_ONLY",
    "bid_ask_spread_and_cost_gate": "NO_LICENSED_EXECUTABLE_BIDASK",
    "session_dst_rollover_news_gate": "NO_INDEPENDENT_BROKER_SESSION_POLICY",
    "structural_sl_tp_net_r_gate": "NO_SOURCE_APPROVED_RISK_PLAN",
    "event_expiry_and_idempotence": "NO_APPROVED_REAL_EVENT_LIFECYCLE",
    "licensed_source_first_known_revision": "NO_LICENSED_PUBLISHER_FIRST_KNOWN",
    "historical_walkforward_oos_qualification": "NO_REAL_HISTORICAL_OOS",
}


@dataclass(frozen=True, slots=True)
class SourceComputationReviewRow:
    rule_id: str
    source_requirement_id: str
    phase: str
    original_source_paragraph_index: int
    evidence_basis: str
    observed_research_state: str
    owner_numeric_decision: str = "AWAITING_SOURCE_OWNER"
    original_source_numeric_rule_approved: bool = False
    independently_authenticated_owner_evidence: bool = False
    publisher_first_known_qualified: bool = False
    vendor_account_data_rights_verified: bool = False
    eligible_for_verified_buy_sell: bool = False


@dataclass(frozen=True, slots=True)
class SourceComputationCrosswalk:
    version: str
    source_locked_doc_id: str
    source_register_blob: str
    source_dossier_blob: str
    asof_utc: str
    rows: tuple[SourceComputationReviewRow, ...]
    technical_six_frame_coverage: str
    original_b2s2_numeric_approvals: int = 0
    original_source_numeric_decisions_pending: int = 36
    other_entry_rule_families_still_pending: int = 14
    experimental_pivot_windows_only: tuple[tuple[int, int], ...] = POLICY_WINDOWS
    independently_authenticated_source_owner_formula: bool = False
    authorized_real_bidask_net_rr: bool = False
    original_forex_parity_proven: bool = False
    historical_oos_qualified: bool = False
    live_signal_release_approved: bool = False
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    may_trade: bool = False
    provider_calls: int = 0
    drive_market_cache_writes: int = 0
    broker_orders: int = 0


def _private_inputs(evidence: SealedArchiveSixTFReceipt) -> tuple[
    PrivateMultiBarReceipt, PrivatePivotSensitivityReceipt,
]:
    if type(evidence) is not SealedArchiveSixTFReceipt:
        raise TypeError("P157_TYPED_SHA_SEALED_RECEIPT_REQUIRED")
    signal = build_signal_only_research_response(evidence)
    multi, pivots = (evidence.private_multibar,
                     evidence.private_pivot_sensitivity)
    if (type(multi) is not PrivateMultiBarReceipt
            or type(pivots) is not PrivatePivotSensitivityReceipt
            or multi.asof_utc != signal.asof_utc
            or pivots.asof_utc != signal.asof_utc
            or pivots.source_private_multibar_digest_sha256 !=
                multi.private_input_digest_sha256
            or multi.action != "NO_SIGNAL" or multi.stage != "UNVERIFIED"
            or pivots.action != "NO_SIGNAL" or pivots.stage != "UNVERIFIED"
            or multi.source_price_side != "MID"
            or pivots.source_price_side != "MID"
            or multi.original_forex_numeric_source_approved
            or pivots.original_forex_numeric_pivot_policy_approved
            or multi.first_known_publisher_verified
            or pivots.real_historical_first_known_verified
            or multi.vendor_source_license_verified
            or pivots.data_license_and_redistribution_verified
            or multi.historical_asof_replay_proven
            or pivots.chronological_oos_acceptance
            or multi.may_publish_prices_or_signals or multi.may_trade
            or pivots.may_publish_price_derived_values_or_signals
            or pivots.may_trade or multi.provider_requests
            or multi.drive_market_cache_writes or multi.broker_orders
            or pivots.provider_requests or pivots.drive_cache_writes
            or pivots.broker_orders
            or signal.action != "NO_SIGNAL"
            or signal.stage != "UNVERIFIED"):
        raise ValueError("P157_PRIVATE_NUMERIC_SOURCE_OR_RIGHTS_DRIFT")
    present = signal.frames_present
    if (tuple(x.frame for x in multi.frames) != present
            or multi.frames_missing_or_stale !=
                signal.frames_missing_or_stale
            or pivots.frames_missing_or_stale !=
                signal.frames_missing_or_stale
            or len(pivots.studied) != len(POLICY_WINDOWS) * len(present)):
        raise ValueError("P157_SIX_TF_RESEARCH_COVERAGE_DRIFT")
    # Re-run private SHA/closed-source validation from the same in-memory
    # bars: a caller-replaced pivot receipt cannot gain a 'ready' status.
    if pivots != scan_private_sealed_pivot_sensitivity(
            multi, evidence.technical):
        raise ValueError("P157_PIVOT_RESULT_OR_PRIVATE_INPUT_TAMPERED")
    for i, (left, right) in enumerate(POLICY_WINDOWS):
        chunk = pivots.studied[i * len(present):(i + 1) * len(present)]
        if (tuple(row.frame for row in chunk) != present
                or any(row.left_bars != left or row.right_bars != right
                       or row.may_publish_buy_sell
                       or row.source_numeric_policy_verified
                       or row.real_data_rights_verified for row in chunk)):
            raise ValueError("P157_PIVOT_RESEARCH_PROFILES_DRIFT")
    return multi, pivots


def _research_state(
    category: str, frames: dict[str, PrivateMultiBarFrame],
    studied: dict[tuple[str, int, int], PrivatePivotFrameStudy],
) -> str:
    if category == "H1_ENVELOPE_ONLY":
        h1 = frames.get("H1")
        return (
            "PRIVATE_H1_BOUNDED_ENVELOPE_PRECURSOR_ONLY"
            if h1 is not None and h1.observed_closed_candles >= 2
            and h1.observed_low is not None and h1.observed_high is not None
            else "INSUFFICIENT_H1_CLOSED_HISTORY"
        )
    if category == "H1_OBSERVED_TR_MEAN_ONLY":
        h1 = frames.get("H1")
        return (
            "PRIVATE_SIMPLE_MEAN_TRUE_RANGE_PRECURSOR_NOT_ATR"
            if h1 is not None and h1.observed_closed_candles >= 2
            and h1.observed_mean_true_range is not None
            else "INSUFFICIENT_H1_CLOSED_HISTORY"
        )
    if category == "M15_PIVOT_SENSITIVITY_ONLY":
        m15 = studied.get(("M15", 1, 1))
        return (
            "PRIVATE_SIM_PIVOT_WINDOW_RESEARCH_NOT_ORIGINAL_RULE"
            if m15 is not None and m15.status ==
            "PRIVATE_RESEARCH_RIGHT_BARS_CLOSED_NO_FIRST_KNOWN_PROOF"
            else "INSUFFICIENT_M15_CLOSED_PIVOT_CONTEXT"
        )
    if category == "D1_H4_CONTEXT_NOT_SOURCE_QUALIFIED":
        # Native Sydney D1 session continuity is not source-qualified,
        # irrespective of the number of source-closed rows.
        return "D1_CALENDAR_AND_D1_SOURCE_REVISION_UNQUALIFIED"
    if category in (
        "NO_LICENSED_EXECUTABLE_BIDASK",
        "NO_INDEPENDENT_BROKER_SESSION_POLICY",
        "NO_SOURCE_APPROVED_RISK_PLAN",
        "NO_APPROVED_REAL_EVENT_LIFECYCLE",
        "NO_LICENSED_PUBLISHER_FIRST_KNOWN",
        "NO_REAL_HISTORICAL_OOS",
    ):
        return category
    raise ValueError("P157_UNRECOGNIZED_REVIEW_CATEGORY")


def reconcile_b2s2_source_to_computation(
    evidence: SealedArchiveSixTFReceipt,
) -> SourceComputationCrosswalk:
    """36 source-pinned review items, two sides, without any local approval.

    The fixed original DOC/P021/P034 baseline must match Git blobs in this
    cloud checkout. Technical precursors are *not* source numeric formulas,
    nor proof of account licence, publisher first-known or live signals.
    """
    multi, pivots = _private_inputs(evidence)
    source = verify_owner_decision_dossier()
    if (len(REQUIREMENTS) != 18
            or set(RESEARCH_CATEGORIES) !=
                {name for name, _, _, _ in REQUIREMENTS}
            or len(source.rows) != 36
            or source.pending_owner_decisions != 36
            or source.original_numeric_rules_approved != 0
            or source.signed_owner_evidence or source.vendor_rights_verified
            or source.may_publish_confirmed_buy_sell):
        raise ValueError("P157_PINNED_OWNER_36_SOURCE_GATE_DRIFT")
    frames = {r.frame: r for r in multi.frames}
    studied = {(r.frame, r.left_bars, r.right_bars): r
               for r in pivots.studied}
    if len(studied) != len(pivots.studied):
        raise ValueError("P157_DUPLICATE_PRIVATE_PIVOT_RESEARCH_STATE")
    rows = tuple(SourceComputationReviewRow(
        rule_id=rid, source_requirement_id=name, phase=phase,
        original_source_paragraph_index=paragraph,
        evidence_basis=RESEARCH_CATEGORIES[name],
        observed_research_state=_research_state(
            RESEARCH_CATEGORIES[name], frames, studied,
        ),
    ) for rid, name, phase, paragraph in source.rows)
    return SourceComputationCrosswalk(
        version=VERSION, source_locked_doc_id=source.source_locked_doc_id,
        source_register_blob=source.original_p021_source_blob_sha,
        source_dossier_blob=source.dossier_blob_sha,
        asof_utc=multi.asof_utc, rows=rows,
        technical_six_frame_coverage=(
            "LATEST_SIX_CLOSED_FRAMES_PRESENT_RESEARCH_ONLY"
            if multi.public_technical_context_complete
            else "INCOMPLETE_OR_STALE_SIX_FRAME_TECHNICAL_RESEARCH"
        ),
    )
