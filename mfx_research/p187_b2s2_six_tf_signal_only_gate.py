"""P0.187: one READ-ONLY six-TF sealed cache -> B2/S2 signal response seam.

Already licensed source authorizations, source-owner numerical formulas, BID/ASK
execution proof and original D1 publisher-first-known are not available.
This real *composition* computes a truthful, nonactionable NO_SIGNAL envelope.
Never turn source OHLC or a SIM candidate into numeric Forex BUY/SELL.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mfx_research.p182_f2_directional_mirror import PAIR
from mfx_research.p184_paired_f2_owner_review import (
    PairedF2OwnerReviewReceipt, compile_paired_f2_owner_proposals,
)
from mfx_research.signal_only_six_tf_response import (
    SignalOnlyResearchResponse, build_signal_only_research_response,
)
from mfx_research.six_tf_readonly_context import FRAMES
from mfx_research.six_tf_sealed_archive_consumer import (
    ReadOnlyObjectStore, SealedArchiveSixTFReceipt, SyntheticFixturePins,
    consume_sealed_archives_for_six_tf,
)

VERSION = "MFX_P187_B2_S2_SEALED_SIX_TF_SIGNAL_ONLY_GATE_V1"
SIDES = ("B2", "S2")
REASONS = (
    "ORIGINAL_36_NUMERIC_SOURCE_DECISIONS_UNAPPROVED",
    "B2_S2_MIRRORED_NUMERIC_OWNER_AUTHORITY_UNVERIFIED",
    "LICENSED_VENDOR_DATA_RETENTION_AND_QUOTE_RIGHTS_UNVERIFIED",
    "D1_PROVIDER_PUBLISHER_FIRST_KNOWN_AND_REVISION_UNVERIFIED",
    "EXECUTABLE_BIDASK_SL_TP_COST_NET_R_UNVERIFIED",
    "UNTAMPERED_CHRONOLOGICAL_OOS_NOT_QUALIFIED",
)


@dataclass(frozen=True, slots=True)
class B2S2SignalOnlyGate:
    version: str
    asof_utc: str
    source_technical_status: str
    frames_present: tuple[str, ...]
    frames_missing_or_stale: tuple[str, ...]
    source_evidence_fingerprint_sha256: str
    owner_proposal_bundle_fingerprint_sha256: str
    numeric_pairs_proposed: int
    numeric_original_approvals: int
    numeric_original_pending: int
    design_roles: tuple[tuple[str, str, str, str], ...]
    blockers: tuple[str, ...]
    source_reason_codes: tuple[str, ...]
    entry_price: None = None
    stop_loss: None = None
    take_profit: None = None
    net_risk_reward: None = None
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    provider_price_requests: int = 0
    drive_market_writes: int = 0
    broker_orders: int = 0

    def public_summary(self) -> dict[str, Any]:
        """Only status, design direction, SHA fingerprints, never source prices."""
        return {
            "version": self.version,
            "asof_utc": self.asof_utc,
            "action": self.action,
            "stage": self.stage,
            "source_technical_status": self.source_technical_status,
            "source_frames_present": list(self.frames_present),
            "source_frames_missing_or_stale": list(self.frames_missing_or_stale),
            "source_evidence_fingerprint_sha256":
                self.source_evidence_fingerprint_sha256,
            "owner_proposal_bundle_fingerprint_sha256":
                self.owner_proposal_bundle_fingerprint_sha256,
            "numeric_pairs_proposed_not_approved": self.numeric_pairs_proposed,
            "original_numeric_approvals": self.numeric_original_approvals,
            "original_numeric_pending": self.numeric_original_pending,
            "design_roles_only": [
                {"rule": rule, "research_direction": direction,
                 "hypothetical_entry_quote_side": entry,
                 "hypothetical_exit_quote_side": exit_}
                for rule, direction, entry, exit_ in self.design_roles
            ],
            "blockers": list(self.blockers),
            "source_reason_codes": list(self.source_reason_codes),
            "entry_price": None, "stop_loss": None,
            "take_profit": None, "net_risk_reward": None,
            "publisher_first_known_utc": None,
            "may_publish_buy_sell": False, "may_trade": False,
            "provider_price_requests": 0, "drive_market_writes": 0,
            "broker_orders": 0,
        }


def compose_b2s2_signal_only_gate(
    sealed: SealedArchiveSixTFReceipt, *,
    owner_proposal: PairedF2OwnerReviewReceipt,
) -> B2S2SignalOnlyGate:
    """Type/rebuild protected six-TF response and nonapproved owner decisions."""
    if (type(sealed) is not SealedArchiveSixTFReceipt
            or type(owner_proposal) is not PairedF2OwnerReviewReceipt):
        raise TypeError("P187_EXACT_TYPED_SOURCE_AND_OWNER_PROPOSAL_REQUIRED")
    source: SignalOnlyResearchResponse = build_signal_only_research_response(sealed)
    if (source.action != "NO_SIGNAL" or source.stage != "UNVERIFIED"
            or source.may_publish_buy_sell or source.may_trade
            or source.provider_requests or source.drive_cache_writes
            or source.broker_orders):
        raise ValueError("P187_SEALED_SOURCE_NO_SIGNAL_ONLY")
    if (owner_proposal.paired_rows != 18
            or not 0 <= owner_proposal.actionable_proposal_pairs <= 18
            or owner_proposal.awaiting_input_pairs != (
                18-owner_proposal.actionable_proposal_pairs)
            or owner_proposal.expanded_p035_proposal_rows != (
                2*owner_proposal.actionable_proposal_pairs)
            or owner_proposal.p035_result.proposals_count != (
                owner_proposal.expanded_p035_proposal_rows)
            or owner_proposal.p035_result.source_numeric_rules_approved != 0
            or owner_proposal.p035_result.source_owner_decisions_still_pending != 36
            or owner_proposal.original_numeric_rules_approved != 0
            or owner_proposal.original_pending_numeric_rules != 36
            or owner_proposal.mirrored_formula_authenticated
            or owner_proposal.may_publish_buy_sell or owner_proposal.may_trade
            or owner_proposal.action != "NO_SIGNAL"
            or owner_proposal.provider_calls or owner_proposal.drive_writes
            or owner_proposal.broker_orders):
        raise ValueError("P187_UNVERIFIED_PROPOSAL_CANNOT_AUTHORIZE_SIGNAL")
    if (tuple(PAIR) != SIDES or
            PAIR["B2"]["opposite"] != "S2" or
            PAIR["S2"]["opposite"] != "B2" or
            PAIR["B2"]["entry_side"] != "ASK" or
            PAIR["B2"]["exit_side"] != "BID" or
            PAIR["S2"]["entry_side"] != "BID" or
            PAIR["S2"]["exit_side"] != "ASK"):
        raise ValueError("P187_MIRROR_DIRECTION_OR_BIDASK_ROLE_DRIFT")
    blockers = (
        tuple("SOURCE_" + reason for reason in source.reason_codes)
        + REASONS
    )
    if source.frames_missing_or_stale:
        blockers += ("SIX_FRAME_CLOSED_ASOF_CONTEXT_INCOMPLETE",)
    if source.technical_status == "SIX_TF_SOURCE_QUARANTINED_NO_SIGNAL":
        blockers += ("REAL_D1_SOURCE_REVISION_STILL_QUARANTINED",)
    return B2S2SignalOnlyGate(
        version=VERSION,asof_utc=source.asof_utc,
        source_technical_status=source.technical_status,
        frames_present=source.frames_present,
        frames_missing_or_stale=source.frames_missing_or_stale,
        source_evidence_fingerprint_sha256=source.evidence_fingerprint_sha256,
        owner_proposal_bundle_fingerprint_sha256=owner_proposal.expanded_p035_digest,
        numeric_pairs_proposed=owner_proposal.actionable_proposal_pairs,
        numeric_original_approvals=0,numeric_original_pending=36,
        design_roles=(
            ("B2","LONG_DESIGN_ONLY",PAIR["B2"]["entry_side"],
             PAIR["B2"]["exit_side"]),
            ("S2","SHORT_DESIGN_ONLY",PAIR["S2"]["entry_side"],
             PAIR["S2"]["exit_side"]),
        ),
        blockers=blockers,
        source_reason_codes=source.reason_codes,
    )


def from_sealed_stores_b2s2_signal_only(
    m5_store: ReadOnlyObjectStore,
    h4_store: ReadOnlyObjectStore,
    d1_store: ReadOnlyObjectStore,
    *, asof_utc: datetime, owner_proposal_packet: dict[str, Any],
    active_d1_epoch_store: ReadOnlyObjectStore | None = None,
    fixture_pins: SyntheticFixturePins | None = None,
) -> B2S2SignalOnlyGate:
    """End-to-end READ ONLY cache -> six TF -> B2/S2 owner-gated response.

    Synthetic pins may be supplied in TESTS only, and are NEVER source
    authenticated. In real mode the original M5 audited checkpoint pins are
    mandatory. Caller injects read-only already authorized storage adapters.
    """
    if type(owner_proposal_packet) is not dict:
        raise TypeError("P187_OWNER_PROPOSAL_DICT_REQUIRED")
    # Validate the full P184 exact 18-pair source proposal schema FIRST:
    # malformed/forged owner packets fail before any storage reads.
    owner = compile_paired_f2_owner_proposals(owner_proposal_packet)
    sealed = consume_sealed_archives_for_six_tf(
        m5_store,h4_store,d1_store,asof_utc=asof_utc,
        active_d1_epoch_store=active_d1_epoch_store,
        fixture_pins=fixture_pins,
    )
    return compose_b2s2_signal_only_gate(sealed,owner_proposal=owner)
