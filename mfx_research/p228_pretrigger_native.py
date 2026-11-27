"""P228: native H4 and revised D1 vintage visible at the P227 setup cutoff.

Only current SHA-audited archive metadata is used, never provider first-known.
No synthetic relabeling of real prices, D1 calendar inference or signal authority.
"""
from __future__ import annotations

from mfx_research.p254_d1_research_vintage import select_private_d1_research_vintage

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.td_m5_codec import digest
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    _p160_still_pinned, read_mfx_confirmed_b2s2_v2,
)
from mfx_research.sealed_multibar_private_features import _Bar, _latest_contiguous
from mfx_research.sealed_private_pivot_sensitivity import _scan_one
from mfx_research.shared_pivot_trend import trend_from_pivot_prices
from mfx_research.six_tf_readonly_context import (
    GRACE, MAX_H4_AGE, MAX_D1_SESSION_DATE_AGE, _native_utc_start, _validate_native,
)
from tools.audit_mfx_p209_d1_private_cache import PrivateSnapshot

H4 = timedelta(hours=4)
MAX_ARCHIVE_PAIRS = 256


@dataclass(frozen=True, slots=True, repr=False)
class PrivatePretriggerNative:
    h4_status: str
    d1_status: str
    cutoff_utc: datetime = field(repr=False)
    h4_trend: str = field(default="UNKNOWN", repr=False)
    d1_rows: tuple[NativeFXBar, ...] = field(default=(), repr=False)
    h4_prior_end: datetime | None = field(default=None, repr=False)
    h4_low_anchor: Decimal | None = field(default=None, repr=False)
    h4_high_anchor: Decimal | None = field(default=None, repr=False)
    d1_calendar_qualified: bool = False
    publisher_first_known_verified: bool = False
    numeric_policy_approved: bool = False
    action: str = "NO_SIGNAL"
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    h4_context_sha256: str | None = field(default=None, repr=False)
    d1_context_sha256: str | None = field(default=None, repr=False)


def _utc(clock: datetime) -> None:
    if (type(clock) is not datetime or clock.tzinfo is None
            or clock.utcoffset() != timedelta(0)):
        raise ValueError("P228_EXACT_UTC_CLOCK_REQUIRED")


def _batch(interval: str, bars: tuple[NativeFXBar, ...]) -> NativeFXBatch:
    return NativeFXBatch(
        symbol="EUR/USD", interval=interval, exchange_timezone="Australia/Sydney",
        time_reference="UTC_INTRADAY_OPEN" if interval == "4h" else "EXCHANGE_LOCAL_SESSION_DATE",
        closed_bars=bars, incomplete_excluded=0,
    )


def calculate_pretrigger_native(
    h4: tuple[tuple[datetime, tuple[NativeFXBar, ...]], ...],
    d1: tuple[tuple[datetime, PrivateSnapshot], ...],
    *, cutoff: datetime, decision: datetime,
) -> PrivatePretriggerNative:
    """Consume histories already verified by P220; recheck clocks and scope."""
    _utc(cutoff)
    _utc(decision)
    if (cutoff >= decision or cutoff.minute % 15 or cutoff.second or cutoff.microsecond
            or type(h4) is not tuple or type(d1) is not tuple
            or len(h4) > MAX_ARCHIVE_PAIRS or len(d1) > MAX_ARCHIVE_PAIRS):
        raise ValueError("P228_BOUNDED_SETUP_HISTORY_REQUIRED")
    visible_h4: list[NativeFXBar] = []
    previous_clock: datetime | None = None
    previous_label = ""
    for known, bars in h4:
        _utc(known)
        if (known > decision or (previous_clock is not None and known < previous_clock)
                or type(bars) is not tuple or not bars):
            raise ValueError("P228_H4_ARCHIVE_CLOCK_DRIFT")
        _validate_native(_batch("4h", bars), "4h", asof=decision)
        if (bars[0].native_open_label <= previous_label
                or _native_utc_start(bars[-1].native_open_label) + H4 > known):
            raise ValueError("P228_H4_ARCHIVE_ORDER_DRIFT")
        if known <= cutoff:
            visible_h4.extend(b for b in bars
                              if _native_utc_start(b.native_open_label) + H4 <= cutoff - GRACE)
        previous_clock, previous_label = known, bars[-1].native_open_label

    seen: set[datetime] = set()
    for created, snap in d1:
        _utc(created)
        if type(snap) is not PrivateSnapshot:
            raise ValueError("P228_TYPED_D1_VINTAGE_REQUIRED")
        _utc(snap.observed)
        if (created > decision or snap.observed > created or snap.observed in seen
                or not snap.rows):
            raise ValueError("P228_D1_ARCHIVE_CLOCK_DRIFT")
        _validate_native(_batch("1day", snap.rows), "1day", asof=snap.observed)
        seen.add(snap.observed)
    selected = select_private_d1_research_vintage(d1, cutoff=cutoff)
    daily = selected.rows if selected else ()
    d1_status = "NO_PRETRIGGER_D1_VINTAGE"
    if daily:
        today = cutoff.astimezone(ZoneInfo("Australia/Sydney")).date()
        age = (today-date.fromisoformat(daily[-1].native_open_label)).days
        if not 1 <= age <= MAX_D1_SESSION_DATE_AGE:
            d1_status = "PRETRIGGER_D1_STALE"
        elif len(daily) < 5:
            d1_status = "PRETRIGGER_D1_HISTORY_INSUFFICIENT"
        else:
            d1_status = "PRETRIGGER_D1_VINTAGE_PRESENT_CALENDAR_UNQUALIFIED"

    d1_context = None
    if d1_status == "PRETRIGGER_D1_VINTAGE_PRESENT_CALENDAR_UNQUALIFIED":
        assert selected is not None
        d1_context = digest({"schema": "P237_D1_PRIVATE_VINTAGE_V1",
                             "cutoff": cutoff.isoformat(), "snapshot": selected.identity,
                             "observed": selected.observed.isoformat(),
                             "source": [b.sha256() for b in daily]})
    h4_status, trend = "NO_PRETRIGGER_H4_ARCHIVE", "UNKNOWN"
    anchor_end = low_anchor = high_anchor = h4_context = None
    if visible_h4:
        end = _native_utc_start(visible_h4[-1].native_open_label) + H4
        if cutoff-end > MAX_H4_AGE:
            h4_status = "PRETRIGGER_H4_STALE"
        else:
            _p160_still_pinned()
            policy = read_mfx_confirmed_b2s2_v2()
            if (policy.htf_left, policy.htf_right) != (1, 1):
                raise ValueError("P228_PINNED_DRAFT_PIVOT_WIDTH_DRIFT")
            rows = tuple(_Bar(b.native_open_label, b.open, b.high, b.low, b.close, b.sha256())
                         for b in visible_h4[-16:])
            contiguous = _latest_contiguous(rows, "H4")
            study = _scan_one("H4", contiguous, policy.htf_left, policy.htf_right)
            highs = [p.candidate_mid_price for p in study.pivots if p.kind == "HIGH"]
            lows = [p.candidate_mid_price for p in study.pivots if p.kind == "LOW"]
            if len(highs) < 2 or len(lows) < 2:
                h4_status = "PRETRIGGER_H4_PIVOTS_INSUFFICIENT"
            else:
                h4_status = "PRETRIGGER_H4_DRAFT_STRUCTURE_COMPUTED"
                anchor_end, low_anchor, high_anchor = end, lows[-1], highs[-1]
                h4_context = digest({"schema": "P237_H4_DRAFT_INPUT_V1",
                                     "cutoff": cutoff.isoformat(),
                                     "policy": policy.fingerprint_sha256,
                                     "source": [b.sha_claim for b in contiguous]})
                trend = trend_from_pivot_prices(highs, lows)
    return PrivatePretriggerNative(h4_status, d1_status, cutoff, trend, daily,
                                   anchor_end, low_anchor, high_anchor,
                                   h4_context_sha256=h4_context, d1_context_sha256=d1_context)
