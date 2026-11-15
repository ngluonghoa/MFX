"""P0.177 — private B2/S2 Option B v2 readiness on SHA-audited MID bars.

Compute *missing preconditions*, not approved numerical Forex trading rules.
Reuses source-verified P0.155/156/158 research; can never emit BUY/SELL,
entry levels, quotes, monetary performance or broker actions. No I/O except
reading the already frozen local MFX v2 candidate config.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json

from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    MfxConfirmedB2S2V2Policy, _p160_still_pinned,
    read_mfx_confirmed_b2s2_v2,
)
from mfx_research.mfx_b2s2_independent_policy_draft import (
    read_independent_mfx_policy_draft,
)
from mfx_research.sealed_multibar_private_features import PrivateMultiBarReceipt
from mfx_research.sealed_private_pivot_sensitivity import (
    POLICY_WINDOWS, PrivatePivotSensitivityReceipt,
    scan_private_sealed_pivot_sensitivity,
)
from mfx_research.sealed_private_m15_microbreak import (
    PrivateMicroBreakReceipt, compute_private_sealed_m15_microbreak,
)
from mfx_research.six_tf_readonly_context import SixTimeframeResearchReceipt

VERSION = "MFX_P177_OPTION_B_V2_REAL_SOURCE_PRIVATE_READINESS_V1"
WINDOW = (1, 1)
EXPECTED_RULES = ("B2", "S2")


@dataclass(frozen=True, slots=True)
class PrivateB2S2Gate:
    rule_id: str
    readiness: str
    missing_preconditions: tuple[str, ...]
    h4_confirmed_high_pivots: int
    h4_confirmed_low_pivots: int
    m15_prior_right_closed_level_available: bool
    h1_closed_bars_available: int
    d1_observed_native_rows: int
    # Even if microbreak computes a direction, it is PRIVATE and unapproved.
    experimental_cross: str = field(repr=False, compare=False)
    can_publish_buy_sell: bool = False
    can_trade: bool = False


@dataclass(frozen=True, slots=True)
class PrivateB2S2Readiness:
    version: str
    asof_utc: str
    private_input_digest_sha256: str
    policy_fingerprint_sha256: str
    source_technical_mode: str
    gates: tuple[PrivateB2S2Gate, ...] = field(repr=False)
    public_action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    numeric_policy_approved: bool = False
    original_forex_numeric_1to1: bool = False
    d1_calendar_qualified: bool = False
    publisher_first_known_verified: bool = False
    source_data_license_verified: bool = False
    bidask_net_rr_qualified: bool = False
    real_oos_qualified: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    market_price_requests: int = 0
    drive_gets_added: int = 0
    drive_writes: int = 0
    broker_orders: int = 0

    def as_safe_summary(self) -> dict[str, object]:
        """No prices, pivots, raw directional events, OHLC or source IDs."""
        return {
            "version": self.version,
            "status": "PRIVATE_REQUIREMENT_GAPS_NOT_LIVE_SIGNAL",
            "policy_fingerprint_sha256": self.policy_fingerprint_sha256,
            "source_technical_mode": self.source_technical_mode,
            "b2_s2": [
                {"rule_id": x.rule_id, "readiness": x.readiness,
                 "missing_preconditions": list(x.missing_preconditions),
                 "h4_confirmed_high_pivots": x.h4_confirmed_high_pivots,
                 "h4_confirmed_low_pivots": x.h4_confirmed_low_pivots,
                 "d1_observed_native_rows": x.d1_observed_native_rows,
                 "h1_closed_bars_available": x.h1_closed_bars_available}
                for x in self.gates
            ],
            "action": "NO_SIGNAL", "stage": "UNVERIFIED",
            "approved_numeric_rules": False,
            "provider_requests": 0,"drive_writes": 0,"broker_orders": 0,
        }


def compute_private_option_b2s2_requirements(
    multi: PrivateMultiBarReceipt,
    technical: SixTimeframeResearchReceipt,
    pivots: PrivatePivotSensitivityReceipt,
    microbreak: PrivateMicroBreakReceipt,
    *, active_d1_source_epoch: str,
) -> PrivateB2S2Readiness:
    """Recalculate prior source receipts before ANY private readiness claim."""
    if (type(multi) is not PrivateMultiBarReceipt
            or type(technical) is not SixTimeframeResearchReceipt
            or type(pivots) is not PrivatePivotSensitivityReceipt
            or type(microbreak) is not PrivateMicroBreakReceipt):
        raise TypeError("P177_SEALED_TYPED_SOURCE_REQUIRED")
    if active_d1_source_epoch not in (
        "P171_D1_FRESH_20261111", "LEGACY_D1_V1",
    ):
        raise ValueError("P177_EXACT_SOURCE_EPOCH_REQUIRED")
    if (pivots != scan_private_sealed_pivot_sensitivity(multi,technical)
            or microbreak != compute_private_sealed_m15_microbreak(
                multi,technical,pivots)):
        raise ValueError("P177_PRIVATE_SOURCE_PIVOT_OR_CROSS_DRIFT")
    if (multi.source_price_side != "MID"
            or pivots.source_price_side != "MID"
            or microbreak.source_price_side != "MID"
            or pivots.asof_utc != multi.asof_utc
            or microbreak.asof_utc != multi.asof_utc
            or technical.asof_utc != multi.asof_utc
            or microbreak.original_b2_s2_approved
            or microbreak.independently_licensed_provider_data
            or microbreak.publisher_first_known_verified
            or microbreak.source_d1_session_or_revision_qualified
            or microbreak.real_bidask_sl_tp_net_rr_approved
            or microbreak.historical_oos_accepted
            or microbreak.may_publish_prices_or_signals
            or microbreak.may_trade
            or microbreak.provider_requests or microbreak.drive_gets_added
            or microbreak.drive_writes or microbreak.broker_orders):
        raise ValueError("P177_PRIVATE_MID_RESEARCH_ONLY_AUTHORITY")
    _p160_still_pinned()
    policy = read_mfx_confirmed_b2s2_v2()
    numerical = read_independent_mfx_policy_draft()
    if (type(policy) is not MfxConfirmedB2S2V2Policy
            or (policy.htf_left,policy.htf_right) != WINDOW
            or (policy.micro_left,policy.micro_right) != WINDOW
            or policy.numeric_rules_approved
            or policy.market_rights_verified or policy.publisher_first_known_verified
            or policy.native_d1_revision_hold_cleared
            or policy.real_oos_qualified or policy.live_signals_allowed
            or policy.broker_orders_allowed
            or numerical.specific_numeric_policy_approved
            or numerical.may_trade or numerical.may_publish_buy_sell
            or type(numerical.h1_tr_mean_period) is not int
            or numerical.h1_tr_mean_period < 2):
        raise ValueError("P177_UNAPPROVED_POLICY_CANNOT_BE_PROMOTED")

    studies={(s.frame,s.left_bars,s.right_bars):s for s in pivots.studied}
    if (len(studies) != len(pivots.studied)
            or tuple((p.left_bars,p.right_bars)
                     for p in microbreak.profiles) != POLICY_WINDOWS):
        raise ValueError("P177_DUPLICATE_OR_DRIFTED_PIVOT_PROFILE")
    h4=studies.get(("H4",*WINDOW))
    d1=studies.get(("D1",*WINDOW))
    if h4 is None or d1 is None:
        # An incomplete source is a missing-data diagnostic, never success.
        # A present source must be D1 explicitly calendar-unqualified.
        if d1 is not None and d1.status != "D1_SOURCE_SESSION_CALENDAR_UNVERIFIED":
            raise ValueError("P177_D1_SESSION_AUTHORITY_DRIFT")
    elif d1.status != "D1_SOURCE_SESSION_CALENDAR_UNVERIFIED" or d1.pivots:
        raise ValueError("P177_D1_SESSION_AUTHORITY_DRIFT")
    frames={f.frame:f for f in multi.frames}
    if len(frames) != len(multi.frames):
        raise ValueError("P177_DUPLICATE_MULTI_FRAME")
    h1=frames.get("H1")
    d1frame=frames.get("D1")
    h1_n=h1.observed_closed_candles if h1 is not None else 0
    d1_n=d1frame.observed_closed_candles if d1frame is not None else 0
    highs=0 if h4 is None else sum(x.kind=="HIGH" for x in h4.pivots)
    lows=0 if h4 is None else sum(x.kind=="LOW" for x in h4.pivots)
    if h4 is not None and (h4.status not in (
        "INSUFFICIENT_CONTIGUOUS_CLOSED_BARS",
        "PRIVATE_RESEARCH_RIGHT_BARS_CLOSED_NO_FIRST_KNOWN_PROOF",
    )):
        raise ValueError("P177_H4_PIVOT_PROFILE_NOT_QUALIFIED")
    profile=microbreak.profiles[0]
    if ((profile.left_bars,profile.right_bars)!=WINDOW
            or profile.experimental_cross not in (
                "EXPERIMENTAL_UP_CROSS","EXPERIMENTAL_DOWN_CROSS",
                "NO_RESEARCH_EVENT",
            )):
        raise ValueError("P177_MICROBREAK_WINDOW_OR_STATUS_DRIFT")

    gates=[]
    for rule, direction in (("B2","EXPERIMENTAL_UP_CROSS"),
                            ("S2","EXPERIMENTAL_DOWN_CROSS")):
        missing=[]
        if d1 is None or d1_n<5:
            missing.append("D1_NOT_ENOUGH_OBSERVED_CLOSED_ROWS")
        # No session-calendar authority or publisher first-known is silently
        # promoted by having a longer D1 source after P0.176.
        missing.append("D1_NATIVE_SESSION_CALENDAR_AND_FIRST_KNOWN_UNVERIFIED")
        missing.append("D1_TWO_RIGHT_CONFIRMED_HIGH_LOWS_UNQUALIFIED")
        if highs<2 or lows<2:
            missing.append("H4_TWO_CONFIRMED_HIGHS_AND_LOWS_MISSING")
        if h1_n <= numerical.h1_tr_mean_period:
            missing.append("H1_DRAFT_TR_PERIOD_NOT_CLOSED")
        prior=(profile.prior_right_closed_high_available
               if rule=="B2" else profile.prior_right_closed_low_available)
        if not prior:
            missing.append("M15_PRETRIGGER_CONFIRMED_LEVEL_MISSING")
        if profile.experimental_cross!=direction:
            missing.append("M15_CLOSED_MICROBREAK_NOT_OBSERVED")
        missing+=(
            "MFX_OPTION_B_V2_NUMERIC_OWNER_REVIEW_PENDING",
            "LICENSED_SOURCE_FIRST_KNOWN_RIGHTS_UNVERIFIED",
            "REAL_BIDASK_SL_TP_NET_RR_UNVERIFIED",
            "TRUE_HISTORICAL_OOS_PENDING",
        )
        gates.append(PrivateB2S2Gate(
            rule_id=rule, readiness="RESEARCH_GAPS_NO_SIGNAL",
            missing_preconditions=tuple(missing),
            h4_confirmed_high_pivots=highs,h4_confirmed_low_pivots=lows,
            m15_prior_right_closed_level_available=prior,
            h1_closed_bars_available=h1_n,d1_observed_native_rows=d1_n,
            experimental_cross=profile.experimental_cross,
        ))
    return PrivateB2S2Readiness(
        version=VERSION,asof_utc=multi.asof_utc,
        private_input_digest_sha256=multi.private_input_digest_sha256,
        policy_fingerprint_sha256=policy.fingerprint_sha256,
        source_technical_mode=active_d1_source_epoch,
        gates=tuple(gates),
    )
