"""MFX v1: OHLC-first analysis decision, BID/ASK is an optional licensed API tier.

This is a READ-ONLY presentation classifier of the already sealed, immutable
six-frame MID research response, not a vendor client nor source approval.
MT4/MT5 terminals are NEVER a required dependency for the signal-only scope.
"""
from __future__ import annotations

from dataclasses import dataclass

from mfx_cache.td_m5_codec import PROVIDER, SYMBOL
from mfx_research.signal_only_six_tf_response import SignalOnlyResearchResponse
from mfx_research.six_tf_readonly_context import FRAMES

VERSION = "MFX_V1_OHLC_FIRST_OPTIONAL_API_BIDASK_POLICY_V1"
_SOURCE_BLOCKERS = (
    "ORIGINAL_SOURCE_NUMERIC_RULES_UNAPPROVED",
    "ACCOUNT_SPECIFIC_DATA_RIGHTS_UNVERIFIED",
    "PUBLISHER_FIRST_KNOWN_UNVERIFIED",
    "BID_ASK_SPREAD_COST_SL_TP_NET_RR_UNVERIFIED",
    "CAUSAL_OOS_AND_RELEASE_NOT_ACCEPTED",
)


@dataclass(frozen=True, slots=True)
class OhlcFirstModeDecision:
    schema_version: str
    instrument: str
    source_quote_side: str
    technical_status: str
    frames_missing_or_stale: tuple[str, ...]
    analysis_lane: str = "CLOSED_OHLC_RESEARCH_ONLY"
    market_quote_mode: str = "MID_TECHNICAL_REFERENCE_ONLY"
    ohlc_research_implementation_may_proceed_offline: bool = True
    sealed_six_frame_context_complete: bool = False
    requires_bidask_for_closed_ohlc_pattern_research: bool = False
    requires_bidask_for_executable_net_rr: bool = True
    requires_mt4_or_mt5_terminal: bool = False
    future_bidask_route: str = "OPTIONAL_LICENSED_READ_ONLY_API"
    future_broker_connection_required: bool = False
    source_data_account_rights_verified: bool = False
    bidask_quote_observed_and_licensed: bool = False
    original_numeric_rules_approved: bool = False
    net_rr_status: str = "NOT_AVAILABLE_FROM_MID_OHLC"
    live_bidask_broker_fill_accuracy_proven: bool = False
    publishable_buy_sell: bool = False
    release_ready: bool = False
    broker_order_integration: bool = False
    provider_requests: int = 0
    drive_price_cache_writes: int = 0
    broker_orders: int = 0


def classify_ohlc_first_mode(
    sealed_view: SignalOnlyResearchResponse,
) -> OhlcFirstModeDecision:
    """Describe the CURRENT MID capability and the future independent API gate.

    The quote-side mode is intentionally NOT selectable by caller booleans:
    source-owner permissions, independent vendor rights and real BID/ASK
    cannot be granted by passing a Python argument.
    """
    if type(sealed_view) is not SignalOnlyResearchResponse:
        raise TypeError("MFX_OHLC_FIRST_TYPED_SIGNAL_ONLY_RECEIPT_REQUIRED")
    if (sealed_view.instrument != SYMBOL
            or sealed_view.source_provider != PROVIDER
            or sealed_view.quote_side != "MID"
            or sealed_view.action != "NO_SIGNAL"
            or sealed_view.stage != "UNVERIFIED"
            or sealed_view.verified_original_numeric_rules
            or sealed_view.account_data_rights_verified
            or sealed_view.bidask_execution_costs_verified
            or sealed_view.historical_oos_verified
            or sealed_view.may_publish_buy_sell or sealed_view.may_trade
            or sealed_view.provider_requests != 0
            or sealed_view.drive_cache_writes != 0
            or sealed_view.broker_orders != 0):
        raise ValueError("MFX_OHLC_FIRST_FORGED_RIGHTS_OR_QUOTE_SIDE")
    present = sealed_view.frames_present
    missing = sealed_view.frames_missing_or_stale
    if (type(present) is not tuple or type(missing) is not tuple
            or present != tuple(x for x in FRAMES if x in present)
            or missing != tuple(x for x in FRAMES if x not in present)
            or type(sealed_view.reason_codes) is not tuple
            or any(x not in sealed_view.reason_codes for x in _SOURCE_BLOCKERS)):
        raise ValueError("MFX_OHLC_FIRST_FRAME_OR_SOURCE_REASON_DRIFT")
    complete = len(present) == len(FRAMES)
    expected_status = ("SIX_TF_COMPLETE_RESEARCH_ONLY" if complete
                       else "SIX_TF_INCOMPLETE_RESEARCH_ONLY")
    if sealed_view.technical_status != expected_status:
        raise ValueError("MFX_OHLC_FIRST_TECHNICAL_STATUS_DRIFT")
    return OhlcFirstModeDecision(
        schema_version=VERSION,
        instrument=SYMBOL,
        source_quote_side="MID",
        technical_status=expected_status,
        frames_missing_or_stale=missing,
        sealed_six_frame_context_complete=complete,
    )
