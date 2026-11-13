"""MFX v1: genuinely multi-candle features from ALREADY sealed archive rows.

Called after the existing M5 SHA/parent and native H4/D1 SHA-chain audits
using the SAME decoded in-memory buffers; no extra GET, new vendor query,
historical source mutation or CI publication of derivative FX prices.

All results are private MID research. As-of closed bars are NOT proof of
historical publisher first-known/revision or source-owner numeric strategy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json

from mfx_cache.native_fx_htf import NativeFXBatch
from mfx_cache.td_m5_codec import ClosedM5Bar, PROVIDER, SYMBOL
from mfx_cache.v2_engine import derive_intraday, validate_m5
from mfx_research.six_tf_readonly_context import (
    FRAMES, ReadonlyTimeframeEvidence, SixTimeframeResearchReceipt,
    _validate_native,
)

VERSION = "MFX_V1_SEALED_CLOSED_MID_MULTIBAR_FEATURES_RESEARCH_V1"
MAX_M5_INPUT = 48
MAX_OBSERVED_PER_FRAME = 16
WIDTHS = {"M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}
UTC = timezone.utc
ZERO = Decimal(0)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateMultiBarFrame:
    frame: str
    latest_source_sha256_claim: str
    latest_source_label: str
    observed_closed_candles: int
    analysis_status: str
    continuity: str
    latest_two_close_direction: str
    latest_close_change: Decimal | None
    latest_true_range: Decimal | None
    observed_mean_true_range: Decimal | None
    observed_low: Decimal | None
    observed_high: Decimal | None
    original_numeric_entry_source_approved: bool = False
    data_rights_independently_verified: bool = False
    provider_first_known_proven: bool = False
    publishable_buy_sell: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class PrivateMultiBarReceipt:
    version: str
    asof_utc: str
    frames: tuple[PrivateMultiBarFrame, ...]
    frames_missing_or_stale: tuple[str, ...]
    private_input_digest_sha256: str
    public_technical_context_complete: bool
    # P0.156: keep exactly the already-audited contiguous candle suffixes
    # IN MEMORY so right-closed pivot research never triggers another GET.
    # Never expose these price-bearing rows to public CI logs or export.
    private_closed_histories: tuple[tuple[str, tuple[_Bar, ...]], ...] = field(
        default=(), repr=False, compare=False,
    )
    source_price_side: str = "MID"
    actual_multi_bar_technical_arithmetic: bool = True
    confirmed_pivot_or_original_trend_inferred: bool = False
    vendor_source_license_verified: bool = False
    first_known_publisher_verified: bool = False
    original_forex_numeric_source_approved: bool = False
    bidask_net_rr_available: bool = False
    historical_asof_replay_proven: bool = False
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    may_publish_prices_or_signals: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_market_cache_writes: int = 0
    broker_orders: int = 0


@dataclass(frozen=True, slots=True, repr=False)
class _Bar:
    label: str
    open: str
    high: str
    low: str
    close: str
    sha_claim: str


def _number(text: str) -> Decimal:
    if type(text) is not str or not 0 < len(text) <= 64:
        raise ValueError("V1_MULTIBAR_PRICE_STRING_REQUIRED")
    try:
        n = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("V1_MULTIBAR_PRICE_STRING_REQUIRED") from exc
    if not n.is_finite() or n <= ZERO:
        raise ValueError("V1_MULTIBAR_PRICE_POSITIVE_FINITE_REQUIRED")
    return n


def _ts(label: str, frame: str) -> datetime:
    if frame == "H4":
        try:
            ts = datetime.strptime(label, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=UTC)
        except (TypeError, ValueError) as exc:
            raise ValueError("V1_MULTIBAR_INVALID_H4_UTC_LABEL") from exc
        return ts
    try:
        ts = datetime.fromisoformat(label)
    except (TypeError, ValueError) as exc:
        raise ValueError("V1_MULTIBAR_INVALID_UTC_LABEL") from exc
    if ts.tzinfo is None or ts.utcoffset() != timedelta(0):
        raise ValueError("V1_MULTIBAR_ONLY_EXACT_UTC_INTRADAY")
    return ts


def _latest_contiguous(
    rows: tuple[_Bar, ...], frame: str,
) -> tuple[_Bar, ...]:
    """UTC grid contiguous suffix, no gap-bridging or weekend inference."""
    recent = rows[-MAX_OBSERVED_PER_FRAME:]
    if frame == "D1":
        # Sydney local session date label is NOT a fixed 24h UTC grid.
        # The provider session's missing/trading dates are NOT certified.
        return recent
    expected_step = timedelta(minutes=WIDTHS[frame])
    start = len(recent) - 1
    while start > 0:
        a, b = _ts(recent[start - 1].label, frame), _ts(
            recent[start].label, frame)
        if b - a != expected_step:
            break
        start -= 1
    return recent[start:]


def _compute_frame(
    frame: str, rows: tuple[_Bar, ...], latest: ReadonlyTimeframeEvidence,
) -> PrivateMultiBarFrame:
    if not rows or rows[-1].label != latest.source_label:
        raise ValueError("V1_MULTIBAR_LAST_CLOSED_SOURCE_LABEL_DRIFT")
    newest = rows[-1]
    if (newest.sha_claim != latest.evidence_sha256
            or (newest.open, newest.high, newest.low, newest.close)
               != (latest.open, latest.high, latest.low, latest.close)):
        raise ValueError("V1_MULTIBAR_LATEST_SOURCE_PRICE_SHA_MISMATCH")
    selected = _latest_contiguous(rows, frame)
    if not selected or selected[-1] != newest:
        raise ValueError("V1_MULTIBAR_NO_LATEST_CLOSED_SUFFIX")
    validated: list[tuple[Decimal, Decimal, Decimal, Decimal]] = []
    for b in selected:
        o, h, lo, c = (_number(x) for x in (
            b.open, b.high, b.low, b.close))
        if not lo <= min(o, c) <= max(o, c) <= h:
            raise ValueError("V1_MULTIBAR_INVALID_CLOSED_OHLC")
        validated.append((o, h, lo, c))

    status = ("MULTIBAR_RESEARCH_CALCULATED_NOT_APPROVED"
              if len(validated) >= 2 else "INSUFFICIENT_CLOSED_HISTORY")
    continuity = ("D1_LOCAL_SESSION_GAPS_UNVERIFIED" if frame == "D1"
                  else "EXACT_CONTIGUOUS_UTC_GRID_ONLY")
    if len(validated) < 2:
        delta = last_tr = mean_tr = low = high = None
        direction = "NO_TWO_CLOSED_CANDLES"
    else:
        delta = validated[-1][3] - validated[-2][3]
        direction = ("CLOSE_INCREASED" if delta > ZERO
                     else "CLOSE_DECREASED" if delta < ZERO
                     else "CLOSE_UNCHANGED")
        tr_values = [
            max(cur[1] - cur[2], abs(cur[1] - prev[3]),
                abs(cur[2] - prev[3]))
            for prev, cur in zip(validated, validated[1:])
        ]
        last_tr = tr_values[-1]
        mean_tr = sum(tr_values, ZERO) / Decimal(len(tr_values))
        low = min(x[2] for x in validated)
        high = max(x[1] for x in validated)
    return PrivateMultiBarFrame(
        frame=frame, latest_source_sha256_claim=latest.evidence_sha256,
        latest_source_label=latest.source_label,
        observed_closed_candles=len(validated), analysis_status=status,
        continuity=continuity, latest_two_close_direction=direction,
        latest_close_change=delta, latest_true_range=last_tr,
        observed_mean_true_range=mean_tr, observed_low=low,
        observed_high=high,
    )


def calculate_private_multibar_from_sealed_rows(
    m5_bars: tuple[ClosedM5Bar, ...],
    h4: NativeFXBatch,
    d1: NativeFXBatch,
    technical: SixTimeframeResearchReceipt,
    *, asof_utc: datetime,
) -> PrivateMultiBarReceipt:
    """Use buffers that the original sealed archive consumer JUST validated.

    Independent validation still checks types, closed price/UTC, native source
    roles and alignment to the exact latest six-frame technical receipt.
    Cannot infer historical custody merely from a current sealed archive.
    """
    if (type(technical) is not SixTimeframeResearchReceipt
            or type(asof_utc) is not datetime
            or asof_utc.tzinfo is None
            or asof_utc.utcoffset() != timedelta(0)
            or technical.instrument != SYMBOL
            or technical.source_provider != PROVIDER
            or technical.action != "NO_SIGNAL"
            or technical.stage != "UNVERIFIED"
            or technical.asof_utc != asof_utc.isoformat()
            or technical.may_publish_verified_buy_sell
            or technical.may_trade
            or technical.forex_1to1_numerical_parity_verified
            or technical.source_feed_subscription_verified):
        raise ValueError("V1_MULTIBAR_TYPED_NO_AUTHORITY_UTC_INPUT_REQUIRED")
    if (type(m5_bars) is not tuple or not m5_bars):
        raise ValueError("V1_MULTIBAR_BOUNDED_M5_REQUIRED")
    m5 = tuple(m5_bars[-MAX_M5_INPUT:])
    validate_m5(m5, asof_utc=asof_utc)
    h4_bars = _validate_native(h4, "4h", asof=asof_utc)
    d1_bars = _validate_native(d1, "1day", asof=asof_utc)
    data: dict[str, tuple[_Bar, ...]] = {
        "M5": tuple(_Bar(
            x.start_utc, x.open, x.high, x.low, x.close, x.digest(),
        ) for x in m5),
        "H4": tuple(_Bar(
            x.native_open_label, x.open, x.high, x.low, x.close, x.sha256(),
        ) for x in h4_bars),
        "D1": tuple(_Bar(
            x.native_open_label, x.open, x.high, x.low, x.close, x.sha256(),
        ) for x in d1_bars),
    }
    for frame in ("M15", "M30", "H1"):
        report = derive_intraday(m5, frame, asof_utc=asof_utc)
        if report.provider_calls or report.broker_orders:
            raise ValueError("V1_MULTIBAR_DERIVATION_SIDE_EFFECT_DRIFT")
        data[frame] = tuple(_Bar(
            x.start_utc, x.open, x.high, x.low, x.close, x.source_sha256,
        ) for x in report.candles)

    ordered = tuple(e.frame for e in technical.frames)
    missing = tuple(f for f in FRAMES if f not in ordered)
    if (ordered != tuple(f for f in FRAMES if f in ordered)
            or len(ordered) != len(set(ordered))
            or missing != technical.missing_or_stale_frames
            or technical.total_frames != len(ordered)
            or technical.research_technical_context_complete !=
                (len(ordered) == len(FRAMES))):
        raise ValueError("V1_MULTIBAR_SIX_TF_TECHNICAL_COVERAGE_DRIFT")
    frames: list[PrivateMultiBarFrame] = []
    private_input: list[dict[str, object]] = []
    private_histories: list[tuple[str, tuple[_Bar, ...]]] = []
    for e in technical.frames:
        if type(e) is not ReadonlyTimeframeEvidence:
            raise TypeError("V1_MULTIBAR_TYPED_FRAME_REQUIRED")
        rows = data[e.frame]
        feature = _compute_frame(e.frame, rows, e)
        frames.append(feature)
        private_histories.append((e.frame, _latest_contiguous(rows, e.frame)))
        # Fingerprint includes ALL private source numbers, not just the
        # caller-provided public SHA metadata. Do not publish this digest.
        private_input.append({
            "frame": e.frame,
            "observations": [
                (x.label, x.open, x.high, x.low, x.close, x.sha_claim)
                for x in _latest_contiguous(rows, e.frame)
            ],
        })
    fingerprint = sha256(json.dumps({
        "version": VERSION, "asof": technical.asof_utc,
        "source_m5_sha_claim": technical.input_m5_sha256,
        "frames": private_input,
    }, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return PrivateMultiBarReceipt(
        version=VERSION, asof_utc=asof_utc.isoformat(),
        frames=tuple(frames), frames_missing_or_stale=missing,
        private_input_digest_sha256=fingerprint,
        public_technical_context_complete=len(frames) == len(FRAMES),
        private_closed_histories=tuple(private_histories),
    )
