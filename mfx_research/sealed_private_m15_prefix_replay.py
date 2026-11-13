"""P0.159: sequential AS-OF technical M15 research on sealed closed buffers.

Unlike a latest-only micro-break study, replay independently evaluates each
available closed M15 prefix. Prior pivots must have been confirmed by closed
right-hand candles BEFORE that prefix's latest M15 OPEN.

All values remain repr-hidden private MID technical research. Historical
publisher first-known, source revision truth, original Forex B2/S2 numeric
approval, real OOS, BID/ASK economics and rights remain UNVERIFIED.
No extra Drive GET/write, provider request, workflow or broker operation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from mfx_research.sealed_multibar_private_features import (
    PrivateMultiBarReceipt, _ts, WIDTHS,
)
from mfx_research.sealed_private_pivot_sensitivity import (
    POLICY_WINDOWS, PrivatePivotSensitivityReceipt,
)
from mfx_research.sealed_private_m15_microbreak import (
    PrivateMicroBreakReceipt, _one_profile,
    compute_private_sealed_m15_microbreak,
)
from mfx_research.six_tf_readonly_context import SixTimeframeResearchReceipt

VERSION = "MFX_V1_P159_SHA_SEALED_PRIVATE_M15_PREFIX_CAUSAL_REPLAY_V1"


@dataclass(frozen=True, slots=True, repr=False)
class PrivateM15PrefixObservation:
    profile_left_bars: int
    profile_right_bars: int
    prefix_closed_count: int
    latest_m15_open_utc: str
    latest_m15_close_utc: str
    research_state: str
    private_experimental_cross: str
    private_prior_pivot_level: Decimal | None
    private_latest_mid_close: Decimal | None
    publisher_first_known_proven: bool = False
    owner_original_numeric_rule_approved: bool = False
    historical_oos_validated: bool = False
    actionable_buy_sell: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class PrivateM15PrefixReplay:
    version: str
    asof_utc: str
    source_private_multibar_digest_sha256: str
    frames_missing_or_stale: tuple[str, ...]
    replayed_closed_m15_inputs: int
    studied_windows: tuple[tuple[int, int], ...]
    private_observations: tuple[PrivateM15PrefixObservation, ...] = field(
        repr=False,
    )
    source_price_side: str = "MID"
    replay_type: str = "CURRENT_ARCHIVE_PREFIX_RESEARCH_NOT_HISTORICAL_FIRST_KNOWN"
    original_b2s2_source_owner_numeric_approved: bool = False
    source_data_rights_attested: bool = False
    native_d1_revision_hold_cleared: bool = False
    source_publisher_first_known_attested: bool = False
    broker_bidask_risk_model_approved: bool = False
    true_historical_oos_accepted: bool = False
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    may_publish_prices_or_signals: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_gets_added: int = 0
    drive_writes: int = 0
    broker_orders: int = 0


def replay_private_m15_closed_prefixes(
    multi: PrivateMultiBarReceipt,
    technical: SixTimeframeResearchReceipt,
    pivots: PrivatePivotSensitivityReceipt,
    latest: PrivateMicroBreakReceipt,
) -> PrivateM15PrefixReplay:
    """Replay each M15 as-of prefix, re-checking existing sealed input first.

    Evidence about historical candle CLOSE does NOT establish provider
    first-known. Do not mistake synthetic prefix replay for OOS performance.
    """
    if (type(multi) is not PrivateMultiBarReceipt
            or type(technical) is not SixTimeframeResearchReceipt
            or type(pivots) is not PrivatePivotSensitivityReceipt
            or type(latest) is not PrivateMicroBreakReceipt):
        raise TypeError("P159_EXACT_TYPED_PRIVATE_SHA_RECEIPTS_REQUIRED")
    # This calls the P0.156 source price/SHA/UTC verifier via P0.158,
    # and recomputes the latest private receipt rather than trusting caller.
    if latest != compute_private_sealed_m15_microbreak(
            multi, technical, pivots):
        raise ValueError("P159_PRIVATE_LATEST_RECEIPT_OR_SOURCE_TAMPER")
    if (latest.action != "NO_SIGNAL" or latest.stage != "UNVERIFIED"
            or latest.may_publish_prices_or_signals or latest.may_trade
            or latest.original_b2_s2_approved
            or latest.independently_licensed_provider_data
            or latest.publisher_first_known_verified
            or latest.source_d1_session_or_revision_qualified
            or latest.real_bidask_sl_tp_net_rr_approved
            or latest.historical_oos_accepted
            or latest.provider_requests or latest.drive_gets_added
            or latest.drive_writes or latest.broker_orders):
        raise ValueError("P159_LATEST_SOURCE_AUTHORITY_DRIFT")
    asof = datetime.fromisoformat(multi.asof_utc)
    histories = dict(multi.private_closed_histories)
    m15 = histories.get("M15")
    if (("M15" in multi.frames_missing_or_stale) != (m15 is None)
            or tuple((x.left_bars, x.right_bars)
                     for x in latest.profiles) != POLICY_WINDOWS):
        raise ValueError("P159_M15_SOURCE_FRESHNESS_OR_POLICY_DRIFT")
    observations: list[PrivateM15PrefixObservation] = []
    if m15 is not None:
        for position, (left, right) in enumerate(POLICY_WINDOWS):
            final = latest.profiles[position]
            eligible_start = left + right + 3
            for count in range(eligible_start, len(m15) + 1):
                prefix = m15[:count]
                state = _one_profile(prefix, pivots, left, right)
                # Explicitly compare last prefix against existing latest
                # result to catch divergences in the replay algorithm.
                if count == len(m15) and state != final:
                    raise ValueError("P159_PREFIX_VS_LATEST_MICROBREAK_DRIFT")
                now = _ts(prefix[-1].label, "M15")
                closed = now + timedelta(minutes=WIDTHS["M15"])
                if closed > asof:
                    raise ValueError("P159_FUTURE_M15_PREFIX_CANDLE_DENIED")
                observations.append(PrivateM15PrefixObservation(
                    profile_left_bars=left,
                    profile_right_bars=right,
                    prefix_closed_count=count,
                    latest_m15_open_utc=now.isoformat(),
                    latest_m15_close_utc=closed.isoformat(),
                    research_state=state.status,
                    private_experimental_cross=state.experimental_cross,
                    private_prior_pivot_level=state.referenced_mid_pivot,
                    private_latest_mid_close=state.latest_closed_mid_price,
                ))
    return PrivateM15PrefixReplay(
        version=VERSION, asof_utc=multi.asof_utc,
        source_private_multibar_digest_sha256=
            multi.private_input_digest_sha256,
        frames_missing_or_stale=multi.frames_missing_or_stale,
        replayed_closed_m15_inputs=0 if m15 is None else len(m15),
        studied_windows=POLICY_WINDOWS,
        private_observations=tuple(observations),
    )
