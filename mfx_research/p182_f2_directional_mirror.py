"""P0.182 F2 B2/S2 exact directional MIRROR design contract, SYNTHETIC ONLY.

This is a small, independently testable phase-algebra witness, not a detector
or licensed market reader. The caller claims synthetic structure flags.
It neither calibrates Forex's 36 missing source rules nor publishes BUY/SELL.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from re import fullmatch

VERSION = "MFX_P182_F2_DIRECTIONAL_MIRROR_DRAFT_V1"
ORIGINAL_APPROVED_NUMERIC_RULES = 0
ORIGINAL_PENDING_NUMERIC_RULES = 36


class F2Phase(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    NO_SETUP = "NO_SETUP"
    WATCH = "R_C_WATCH"
    EARLY = "R_E_EARLY"
    CONFIRMED_DESIGN_ONLY = "R_F_CONFIRMED_DESIGN_ONLY"
    INVALIDATED = "INVALIDATED"


# Only directional facts invert. A successful zone RE-ENTRY criterion is
# identical in both directions, rather than using incompatible prose labels.
PAIR: dict[str, dict[str, str]] = {
    "B2": {
        "opposite": "S2", "trend": "HH_HL", "zone": "SUPPORT",
        "pivot": "HL", "bos": "BOS_UP", "entry_side": "ASK",
        "exit_side": "BID",
    },
    "S2": {
        "opposite": "B2", "trend": "LH_LL", "zone": "RESISTANCE",
        "pivot": "LH", "bos": "BOS_DOWN", "entry_side": "BID",
        "exit_side": "ASK",
    },
}
MIRROR_FIELDS: dict[str, dict[str, str]] = {
    "regime": {"HH_HL": "LH_LL", "LH_LL": "HH_HL"},
    "zone_side": {"SUPPORT": "RESISTANCE", "RESISTANCE": "SUPPORT"},
    "pivot": {"HL": "LH", "LH": "HL", "NONE": "NONE"},
    "internal_bos": {
        "BOS_UP": "BOS_DOWN", "BOS_DOWN": "BOS_UP", "NONE": "NONE",
    },
}


def _price(x: Decimal, field_name: str) -> None:
    if type(x) is not Decimal or not x.is_finite() or x <= 0:
        raise ValueError("P182_POSITIVE_FINITE_SYNTHETIC_PRICE:" + field_name)


def _utc(value: datetime, field_name: str) -> None:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() is None
            or value.utcoffset().total_seconds() != 0):
        raise ValueError("P182_EXPLICIT_UTC_REQUIRED:" + field_name)


@dataclass(frozen=True, slots=True)
class F2DesignEvidence:
    """One synthetic closed M15 candidate with a previously known micro-level.

    CLOSED M15 source and H1 close are caller CLAIMS, not provider attestation.
    'zone_reentry' is a common, uncalibrated mirrored zone reaction claim.
    The zero-approval contract refuses to promote these claims to signals.
    """

    rule_id: str
    event_id: str
    asof_utc: datetime
    m15_start_utc: datetime
    m15_closed_utc: datetime
    m15_first_known_utc: datetime
    micro_first_known_utc: datetime
    regime: str
    zone_side: str
    pivot: str
    internal_bos: str
    zone_reentry: bool
    source_complete: bool
    micro_level: Decimal
    trigger_close: Decimal
    invalidation_level: Decimal
    h1_close: Decimal
    mirror_anchor: Decimal

    def __post_init__(self) -> None:
        if self.rule_id not in PAIR:
            raise ValueError("P182_ONLY_F2_B2_OR_S2")
        if type(self.event_id) is not str or fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}", self.event_id) is None:
            raise ValueError("P182_BOUNDED_SYNTHETIC_EVENT_ID_REQUIRED")
        for field_name in (
            "asof_utc", "m15_start_utc", "m15_closed_utc",
            "m15_first_known_utc", "micro_first_known_utc",
        ):
            _utc(getattr(self, field_name), field_name)
        if not (self.micro_first_known_utc <= self.m15_start_utc
                < self.m15_closed_utc <= self.m15_first_known_utc
                <= self.asof_utc):
            raise ValueError("P182_CLOSED_FIRST_KNOWN_CAUSALITY_REQUIRED")
        for f in ("zone_reentry", "source_complete"):
            if type(getattr(self, f)) is not bool:
                raise ValueError("P182_TYPED_BOOLEAN_REQUIRED:" + f)
        for field_name in (
            "micro_level", "trigger_close", "invalidation_level",
            "h1_close", "mirror_anchor",
        ):
            _price(getattr(self, field_name), field_name)
        for name, mapping in MIRROR_FIELDS.items():
            if getattr(self, name) not in mapping:
                raise ValueError("P182_BAD_DIRECTIONAL_EVIDENCE:" + name)


@dataclass(frozen=True, slots=True)
class F2DesignPreview:
    version: str
    rule_id: str
    phase: F2Phase
    event_id: str
    hypothetical_entry_side: str
    hypothetical_exit_side: str
    no_double_counted_confirmation: bool = True
    source_numeric_approvals: int = ORIGINAL_APPROVED_NUMERIC_RULES
    remaining_owner_decisions: int = ORIGINAL_PENDING_NUMERIC_RULES
    original_forex_numerical_parity_verified: bool = False
    publisher_first_known_verified: bool = False
    provider_market_rights_verified: bool = False
    real_bidask_cost_verified: bool = False
    historical_oos_verified: bool = False
    may_publish_buy_sell: bool = False
    may_execute_broker_order: bool = False
    public_action: str = "NO_SIGNAL"


def evaluate_f2_design(e: F2DesignEvidence) -> F2DesignPreview:
    """Exact directional phase PREVIEW; never a live detector/alert."""
    if type(e) is not F2DesignEvidence:
        raise TypeError("P182_TYPED_SYNTHETIC_EVIDENCE_REQUIRED")
    config = PAIR[e.rule_id]
    if not e.source_complete:
        phase = F2Phase.UNVERIFIED
    elif e.regime != config["trend"] or e.zone_side != config["zone"]:
        phase = F2Phase.NO_SETUP
    else:
        long_side = e.rule_id == "B2"
        invalid = (e.h1_close < e.invalidation_level if long_side
                   else e.h1_close > e.invalidation_level)
        early = (
            e.pivot == config["pivot"]
            or e.zone_reentry
            or e.internal_bos == config["bos"]
        )
        confirmed = (
            early and (
                e.trigger_close > e.micro_level if long_side
                else e.trigger_close < e.micro_level
            )
        )
        # One event can be confirmed OR early; it cannot emit both phases.
        if invalid:
            phase = F2Phase.INVALIDATED
        elif confirmed:
            phase = F2Phase.CONFIRMED_DESIGN_ONLY
        elif early:
            phase = F2Phase.EARLY
        else:
            phase = F2Phase.WATCH
    return F2DesignPreview(
        version=VERSION, rule_id=e.rule_id, phase=phase,
        event_id=e.event_id,
        hypothetical_entry_side=config["entry_side"],
        hypothetical_exit_side=config["exit_side"],
    )


def reflect_f2_design(e: F2DesignEvidence) -> F2DesignEvidence:
    """Reversible price reflection about a supplied SYNTHETIC positive anchor.

    Reflection twice is identity and preserves all time/event/source claims.
    This algebra is not a market simulation of real BID/ASK spread or fills.
    """
    if type(e) is not F2DesignEvidence:
        raise TypeError("P182_TYPED_SYNTHETIC_EVIDENCE_REQUIRED")
    anchor = e.mirror_anchor
    reflected_prices = {
        field_name: 2 * anchor - getattr(e, field_name)
        for field_name in (
            "micro_level", "trigger_close", "invalidation_level", "h1_close",
        )
    }
    for field_name, val in reflected_prices.items():
        _price(val, field_name)
    return F2DesignEvidence(
        rule_id=PAIR[e.rule_id]["opposite"],
        event_id=e.event_id,
        asof_utc=e.asof_utc,
        m15_start_utc=e.m15_start_utc,
        m15_closed_utc=e.m15_closed_utc,
        m15_first_known_utc=e.m15_first_known_utc,
        micro_first_known_utc=e.micro_first_known_utc,
        regime=MIRROR_FIELDS["regime"][e.regime],
        zone_side=MIRROR_FIELDS["zone_side"][e.zone_side],
        pivot=MIRROR_FIELDS["pivot"][e.pivot],
        internal_bos=MIRROR_FIELDS["internal_bos"][e.internal_bos],
        zone_reentry=e.zone_reentry,
        source_complete=e.source_complete,
        mirror_anchor=anchor,
        **reflected_prices,
    )
