"""MFX signal-first: actual six-frame CLOSED MID OHLC candle geometry.

Pure math on typed, previously parsed and source-SHA-audited sealed cache
research objects. One latest candle per available timeframe is NOT enough
to infer trend, confirmed pivot, BUY/SELL, economic fill or 1:1 original
Forex numeric policy. Results and original prices must remain private until
vendor/derived-data redistribution rights are independently accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from mfx_cache.td_m5_codec import SYMBOL
from mfx_research.ohlc_first_optional_bidask_policy import (
    classify_ohlc_first_mode,
)
from mfx_research.signal_only_six_tf_response import (
    build_signal_only_research_response,
)
from mfx_research.six_tf_readonly_context import (
    FRAMES, ReadonlyTimeframeEvidence,
)
from mfx_research.six_tf_sealed_archive_consumer import SealedArchiveSixTFReceipt

VERSION = "MFX_V1_SIX_TF_CLOSED_MID_CANDLE_GEOMETRY_RESEARCH_V1"
ZERO = Decimal(0)
ONE = Decimal(1)
_EXPECTED_COUNTS = {
    "M5": 1, "M15": 3, "M30": 6, "H1": 12, "H4": 1, "D1": 1,
}
_EXPECTED_TIME_BASIS = {
    "M5": "UTC_NATIVE_M5_OPEN",
    "M15": "UTC_INTRADAY_WINDOW",
    "M30": "UTC_INTRADAY_WINDOW",
    "H1": "UTC_INTRADAY_WINDOW",
    "H4": "UTC_INTRADAY_OPEN",
    "D1": "EXCHANGE_LOCAL_SESSION_DATE",
}
_NATIVE_FRAMES = frozenset(("M5", "H4", "D1"))


def _price(raw: str, field: str) -> Decimal:
    if type(raw) is not str or not raw or len(raw) > 64:
        raise ValueError("V1_GEOMETRY_DECIMAL_PRICE_STRING_REQUIRED:" + field)
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("V1_GEOMETRY_DECIMAL_PRICE_STRING_REQUIRED:" + field) from exc
    if not value.is_finite() or value <= ZERO:
        raise ValueError("V1_GEOMETRY_FINITE_POSITIVE_PRICE_REQUIRED:" + field)
    return value


def _scope(frame: ReadonlyTimeframeEvidence, asof: datetime) -> None:
    if (type(frame.source_bar_count) is not int
            or frame.source_bar_count != _EXPECTED_COUNTS[frame.frame]
            or type(frame.native) is not bool
            or frame.native != (frame.frame in _NATIVE_FRAMES)
            or frame.time_basis != _EXPECTED_TIME_BASIS[frame.frame]
            or type(frame.source_label) is not str
            or not frame.source_label):
        raise ValueError("V1_GEOMETRY_FRAME_SOURCE_SCOPE_DRIFT")
    if frame.frame == "D1":
        if frame.end_utc is not None:
            raise ValueError("V1_GEOMETRY_D1_SESSION_CANNOT_CLAIM_UTC_CLOSE")
    else:
        try:
            end = datetime.fromisoformat(frame.end_utc)
        except (TypeError, ValueError) as exc:
            raise ValueError("V1_GEOMETRY_INVALID_FRAME_END_UTC") from exc
        if (end.tzinfo is None or end.utcoffset() != timedelta(0)
                or end > asof):
            raise ValueError("V1_GEOMETRY_OPEN_OR_FUTURE_FRAME_DENIED")


@dataclass(frozen=True, slots=True)
class PrivateCandleShape:
    """Only private, actual-in-memory Decimal geometry; NEVER a trade signal."""

    frame: str
    source_evidence_sha256: str
    shape: str
    price_range: Decimal
    real_body: Decimal
    upper_shadow: Decimal
    lower_shadow: Decimal
    body_fraction_of_range: Decimal | None
    close_position_in_range: Decimal | None
    source_close_time_utc: str | None
    price_side: str = "MID"
    original_strategy_numeric_approved: bool = False
    may_publish_buy_sell: bool = False


@dataclass(frozen=True, slots=True)
class PrivateSixTfCandleGeometry:
    version: str
    instrument: str
    asof_utc: str
    shapes: tuple[PrivateCandleShape, ...]
    frames_missing_or_stale: tuple[str, ...]
    source_fingerprint_sha256: str
    technical_six_frame_complete: bool
    source_price_side: str = "MID"
    resolution: str = "ONE_LATEST_CLOSED_CANDLE_PER_PRESENT_FRAME"
    indicator_trend_or_confirmed_pivot_inferred: bool = False
    external_data_license_and_derived_distribution_approved: bool = False
    real_first_known_attribution_verified: bool = False
    numeric_forex_1to1_strategy_approved: bool = False
    independent_causal_oos_proven: bool = False
    bidask_cost_net_rr_available: bool = False
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    may_publish_prices_or_derived_signals: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_price_cache_writes: int = 0
    broker_orders: int = 0


def _shape(frame: ReadonlyTimeframeEvidence) -> PrivateCandleShape:
    o = _price(frame.open, "open")
    h = _price(frame.high, "high")
    lo = _price(frame.low, "low")
    c = _price(frame.close, "close")
    if not lo <= min(o, c) <= max(o, c) <= h:
        raise ValueError("V1_GEOMETRY_INVALID_CLOSED_OHLC")
    spread = h - lo  # CANDLE HIGH-LOW RANGE, NOT BID/ASK SPREAD.
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - lo
    if (spread != body + upper + lower
            or any(x < ZERO for x in (spread, body, upper, lower))):
        raise ValueError("V1_GEOMETRY_CANDLE_DECOMPOSITION_INVALID")
    direction = ("CLOSE_ABOVE_OPEN" if c > o else
                 "CLOSE_BELOW_OPEN" if c < o else "CLOSE_EQUALS_OPEN")
    body_fraction = (body / spread if spread > ZERO else None)
    close_position = ((c - lo) / spread if spread > ZERO else None)
    if (body_fraction is not None and not ZERO <= body_fraction <= ONE
            or close_position is not None and not ZERO <= close_position <= ONE):
        raise ValueError("V1_GEOMETRY_OUT_OF_RANGE_FRACTION")
    return PrivateCandleShape(
        frame=frame.frame,
        source_evidence_sha256=frame.evidence_sha256,
        shape=direction,
        price_range=spread, real_body=body,
        upper_shadow=upper, lower_shadow=lower,
        body_fraction_of_range=body_fraction,
        close_position_in_range=close_position,
        source_close_time_utc=frame.end_utc,
    )


def compute_private_six_tf_candle_geometry(
    evidence: SealedArchiveSixTFReceipt,
) -> PrivateSixTfCandleGeometry:
    """Actually compute exact geometry for all present CLOSED six-TF frames.

    This can be called inside an existing GET-only owner-approved source audit
    but MUST NOT serialize the returned price-derived shapes to public CI.
    A sealed cached SHA isn't an independent vendor-licence/first-known proof.
    """
    if type(evidence) is not SealedArchiveSixTFReceipt:
        raise TypeError("V1_GEOMETRY_TYPED_SEALED_INPUT_REQUIRED")
    signal = build_signal_only_research_response(evidence)
    mode = classify_ohlc_first_mode(signal)
    if (mode.source_quote_side != "MID" or mode.publishable_buy_sell
            or mode.requires_mt4_or_mt5_terminal
            or not mode.ohlc_research_implementation_may_proceed_offline):
        raise ValueError("V1_GEOMETRY_NO_OHLC_ANALYSIS_AUTHORIZATION")
    asof = datetime.fromisoformat(signal.asof_utc)
    shapes: list[PrivateCandleShape] = []
    for entry in evidence.technical.frames:
        if type(entry) is not ReadonlyTimeframeEvidence or entry.frame not in FRAMES:
            raise TypeError("V1_GEOMETRY_UNEXPECTED_TYPED_FRAME")
        _scope(entry, asof)
        shapes.append(_shape(entry))
    if (tuple(x.frame for x in shapes) != signal.frames_present
            or tuple(f for f in FRAMES if f not in signal.frames_present)
               != signal.frames_missing_or_stale
            or mode.sealed_six_frame_context_complete != (len(shapes) == 6)):
        raise ValueError("V1_GEOMETRY_SIX_FRAME_COVERAGE_DRIFT")
    return PrivateSixTfCandleGeometry(
        version=VERSION,
        instrument=SYMBOL,
        asof_utc=signal.asof_utc,
        shapes=tuple(shapes),
        frames_missing_or_stale=signal.frames_missing_or_stale,
        source_fingerprint_sha256=signal.evidence_fingerprint_sha256,
        technical_six_frame_complete=mode.sealed_six_frame_context_complete,
    )
