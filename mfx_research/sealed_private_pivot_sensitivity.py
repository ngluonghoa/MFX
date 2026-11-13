"""MFX v1 P0.156 — *private* right-closed pivot sensitivity on sealed MID bars.

This is a real computation on archived, previously SHA-audited multi-candle
inputs. Both explicit SIM research windows (1L/1R, 2L/2R) are NOT approved
numeric Forex rules. Unlike the existing synthetic-only P0.20 MarketBar
pivot engine, no live vendor source is converted to a fake SIM MarketBar,
and no unverified publisher-first-known timestamp is asserted.

No broker, vendor, Drive read/write, public price or actionable BUY/SELL.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json

from mfx_research.sealed_multibar_private_features import (
    VERSION as MULTIBAR_VERSION, PrivateMultiBarReceipt, _Bar, _number,
    _latest_contiguous, _ts, WIDTHS,
)
from mfx_research.six_tf_readonly_context import (
    FRAMES, ReadonlyTimeframeEvidence, SixTimeframeResearchReceipt,
)

VERSION = "MFX_V1_PRIVATE_SEALED_CONFIRMED_PIVOT_SENSITIVITY_V1"
POLICY_WINDOWS = ((1, 1), (2, 2))
MID = "MID"


@dataclass(frozen=True, slots=True, repr=False)
class PrivatePivotPoint:
    frame: str
    kind: str
    candidate_source_open_label: str
    right_confirmation_source_open_label: str
    candidate_mid_price: Decimal
    # This is CANDLE CLOSE TIME ONLY, *NOT* first-known source attestation.
    right_candle_closed_utc: str
    left_bars_research_only: int
    right_bars_research_only: int
    independently_proven_first_known: bool = False
    source_owner_numeric_rule_approved: bool = False
    may_publish_buy_sell: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class PrivatePivotFrameStudy:
    frame: str
    observations: int
    left_bars: int
    right_bars: int
    status: str
    pivots: tuple[PrivatePivotPoint, ...]
    source_price_side: str = MID
    real_data_rights_verified: bool = False
    source_numeric_policy_verified: bool = False
    may_publish_buy_sell: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class PrivatePivotSensitivityReceipt:
    version: str
    asof_utc: str
    source_private_multibar_digest_sha256: str
    studied: tuple[PrivatePivotFrameStudy, ...]
    frames_missing_or_stale: tuple[str, ...]
    policy_authority: str = "TWO_SIM_RESEARCH_WINDOWS_NOT_FOREX_1TO1_RULES"
    source_price_side: str = MID
    data_license_and_redistribution_verified: bool = False
    real_historical_first_known_verified: bool = False
    chronological_oos_acceptance: bool = False
    original_forex_numeric_pivot_policy_approved: bool = False
    real_d1_session_continuity_qualified: bool = False
    net_bidask_rr_available: bool = False
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    may_publish_price_derived_values_or_signals: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_cache_writes: int = 0
    broker_orders: int = 0


def _recheck_private_source(
    data: PrivateMultiBarReceipt, technical: SixTimeframeResearchReceipt,
) -> tuple[tuple[str, tuple[_Bar, ...]], ...]:
    if (type(data) is not PrivateMultiBarReceipt
            or type(technical) is not SixTimeframeResearchReceipt
            or data.version != MULTIBAR_VERSION
            or data.asof_utc != technical.asof_utc
            or data.source_price_side != MID
            or data.action != "NO_SIGNAL" or data.stage != "UNVERIFIED"
            or data.vendor_source_license_verified
            or data.first_known_publisher_verified
            or data.original_forex_numeric_source_approved
            or data.historical_asof_replay_proven
            or data.may_publish_prices_or_signals or data.may_trade
            or data.provider_requests or data.drive_market_cache_writes
            or data.broker_orders or technical.action != "NO_SIGNAL"
            or technical.stage != "UNVERIFIED"
            or technical.may_trade or technical.may_publish_verified_buy_sell
            or technical.forex_1to1_numerical_parity_verified):
        raise ValueError("V1_PRIVATE_PIVOT_RESEARCH_ONLY_TYPED_INPUT_REQUIRED")
    histories = data.private_closed_histories
    present = tuple(x.frame for x in technical.frames)
    missing = tuple(f for f in FRAMES if f not in present)
    if (type(histories) is not tuple
            or len(histories) != len(present)
            or len(data.frames) != len(present)
            or tuple(n for n, _ in histories) != present
            or tuple(f.frame for f in data.frames) != present
            or present != tuple(f for f in FRAMES if f in present)
            or data.frames_missing_or_stale != missing
            or technical.missing_or_stale_frames != missing
            or data.public_technical_context_complete !=
                (len(present) == len(FRAMES))):
        raise ValueError("V1_PRIVATE_PIVOT_FRAME_OR_HISTORY_DRIFT")
    try:
        asof = datetime.fromisoformat(data.asof_utc)
    except (TypeError, ValueError) as exc:
        raise ValueError("V1_PRIVATE_PIVOT_INVALID_UTC_ASOF") from exc
    if asof.tzinfo is None or asof.utcoffset() != timedelta(0):
        raise ValueError("V1_PRIVATE_PIVOT_INVALID_UTC_ASOF")
    fingerprint_frames: list[dict[str, object]] = []
    for (frame, rows), meta, technical_frame in zip(
            histories, data.frames, technical.frames):
        if (type(technical_frame) is not ReadonlyTimeframeEvidence
                or type(rows) is not tuple
                or not 1 <= len(rows) <= 16
                or any(type(r) is not _Bar for r in rows)
                or rows != _latest_contiguous(rows, frame)):
            raise ValueError("V1_PRIVATE_PIVOT_UNTRUSTED_HISTORY_SEQUENCE")
        newest = rows[-1]
        if (meta.latest_source_sha256_claim != technical_frame.evidence_sha256
                or newest.sha_claim != technical_frame.evidence_sha256
                or newest.label != technical_frame.source_label
                or meta.latest_source_label != newest.label
                or (newest.open,newest.high,newest.low,newest.close) !=
                    (technical_frame.open,technical_frame.high,
                     technical_frame.low,technical_frame.close)
                or meta.observed_closed_candles != len(rows)):
            raise ValueError("V1_PRIVATE_PIVOT_SOURCE_CANDLE_SHA_MISMATCH")
        for row in rows:
            o,h,l,c = (_number(v) for v in
                       (row.open,row.high,row.low,row.close))
            if not l <= min(o,c) <= max(o,c) <= h:
                raise ValueError("V1_PRIVATE_PIVOT_INVALID_CLOSED_OHLC")
            if frame != "D1":
                if (_ts(row.label,frame)+timedelta(
                        minutes=WIDTHS[frame]) > asof):
                    raise ValueError("V1_PRIVATE_PIVOT_FUTURE_OR_OPEN_ROW")
        fingerprint_frames.append({
            "frame": frame,
            "observations": [
                (x.label,x.open,x.high,x.low,x.close,x.sha_claim)
                for x in rows
            ],
        })
    reconstructed = sha256(json.dumps({
        "version": MULTIBAR_VERSION, "asof": data.asof_utc,
        "source_m5_sha_claim": technical.input_m5_sha256,
        "frames": fingerprint_frames,
    }, sort_keys=True,ensure_ascii=True,separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    if reconstructed != data.private_input_digest_sha256:
        raise ValueError("V1_PRIVATE_PIVOT_PRIVATE_INPUT_SHA_MISMATCH")
    return histories


def _scan_one(
    frame: str, rows: tuple[_Bar, ...], left: int, right: int,
) -> PrivatePivotFrameStudy:
    if frame == "D1":
        # Session date != independently authenticated trading-day calendar.
        # Do not use an unverified trading gap as one "right" candle.
        return PrivatePivotFrameStudy(
            frame=frame, observations=len(rows),left_bars=left,
            right_bars=right,status="D1_SOURCE_SESSION_CALENDAR_UNVERIFIED",
            pivots=(),
        )
    if len(rows) < left + right + 1:
        return PrivatePivotFrameStudy(
            frame=frame,observations=len(rows),left_bars=left,
            right_bars=right,status="INSUFFICIENT_CONTIGUOUS_CLOSED_BARS",
            pivots=(),
        )
    candles = tuple(
        (_number(x.high),_number(x.low)) for x in rows
    )
    pivots: list[PrivatePivotPoint] = []
    for i in range(left,len(candles)-right):
        hi,lo = candles[i]
        neighbors = candles[i-left:i]+candles[i+1:i+right+1]
        high = all(hi > h for h,_ in neighbors)
        low = all(lo < low_ for _,low_ in neighbors)
        # Strict extrema, no ties; a candle making BOTH extremes is
        # ambiguous for structural direction and MUST be discarded.
        if high == low:
            continue
        right_end = _ts(rows[i+right].label,frame)+timedelta(
            minutes=WIDTHS[frame])
        pivots.append(PrivatePivotPoint(
            frame=frame,kind=("HIGH" if high else "LOW"),
            candidate_source_open_label=rows[i].label,
            right_confirmation_source_open_label=rows[i+right].label,
            candidate_mid_price=hi if high else lo,
            right_candle_closed_utc=right_end.isoformat(),
            left_bars_research_only=left,
            right_bars_research_only=right,
        ))
    return PrivatePivotFrameStudy(
        frame=frame,observations=len(rows),left_bars=left,right_bars=right,
        status="PRIVATE_RESEARCH_RIGHT_BARS_CLOSED_NO_FIRST_KNOWN_PROOF",
        pivots=tuple(pivots),
    )


def scan_private_sealed_pivot_sensitivity(
    data: PrivateMultiBarReceipt, technical: SixTimeframeResearchReceipt,
) -> PrivatePivotSensitivityReceipt:
    """Compare 1/1 and 2/2 experimental pivots, no selected source threshold.

    A RIGHT candle can confirm a candidate only after its CLOSED timestamp;
    no source first-known, account entitlement or as-of OOS is inferred.
    """
    histories=_recheck_private_source(data,technical)
    studies=tuple(
        _scan_one(frame,rows,left,right)
        for left,right in POLICY_WINDOWS
        for frame,rows in histories
    )
    return PrivatePivotSensitivityReceipt(
        version=VERSION,asof_utc=data.asof_utc,
        source_private_multibar_digest_sha256=
            data.private_input_digest_sha256,
        studied=studies,frames_missing_or_stale=data.frames_missing_or_stale,
    )
