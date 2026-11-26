"""P230 private pretrigger boundary path diagnostics, not a signed invalidation rule.

Measure distances from frozen H1/H4 anchors for later-visible closed bars.
No buffer is selected here. A zero-boundary breach is an observation only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from mfx_cache.native_fx_htf import NativeFXBar
from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_engine import derive_intraday
from mfx_research.p227_pretrigger_h1 import PrivatePretriggerH1
from mfx_research.p228_pretrigger_native import PrivatePretriggerNative
from mfx_research.six_tf_readonly_context import _expected_last_closed, _native_utc_start


@dataclass(frozen=True, slots=True, repr=False)
class PrivateBoundaryPath:
    observed_closed_bars: int
    closed_grid_complete: bool
    minimum_signed_distance: Decimal | None = field(repr=False)
    unbuffered_boundary_breach: bool = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateSetupBoundary:
    rule_id: str
    h1: PrivateBoundaryPath | None = field(repr=False)
    h4: PrivateBoundaryPath | None = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateBoundaryReceipt:
    cutoff_utc: datetime = field(repr=False)
    sides: tuple[PrivateSetupBoundary, ...] = field(repr=False)
    buffer_selected: bool = False
    invalidation_rule_approved: bool = False
    publisher_first_known_verified: bool = False
    action: str = "NO_SIGNAL"
    may_publish_buy_sell: bool = False
    may_trade: bool = False


def _utc(value: datetime) -> None:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P230_EXACT_UTC_REQUIRED")


def inspect_boundary_path(
    *, rule: str, anchor: Decimal, prior_end: datetime, decision: datetime,
    minutes: int, path: tuple[tuple[datetime, datetime, Decimal], ...],
) -> PrivateBoundaryPath:
    """A strict comparison at the raw anchor is not a buffer decision.

    Missing slots prevent an intact conclusion. An observed breach remains
    an observation even if the intervening path is incomplete. The caller
    supplies only already SHA-audited, archive-visible closed bars.
    """
    _utc(prior_end)
    _utc(decision)
    if (rule not in ("B2", "S2") or type(anchor) is not Decimal
            or not anchor.is_finite() or anchor <= 0
            or type(minutes) is not int or minutes not in (60, 240)
            or type(path) is not tuple or len(path) > 256):
        raise ValueError("P230_EXACT_BOUNDED_BOUNDARY_INPUT_REQUIRED")
    expected = _expected_last_closed(decision, minutes)
    if prior_end > expected or prior_end != _expected_last_closed(
            prior_end + timedelta(seconds=15), minutes):
        raise ValueError("P230_PRIOR_BOUNDARY_GRID_DRIFT")
    width = timedelta(minutes=minutes)
    tip = prior_end
    complete = True
    distances: list[Decimal] = []
    for start, end, close in path:
        _utc(start)
        _utc(end)
        if (start < tip or end-start != width or end > expected
                or end != _expected_last_closed(end+timedelta(seconds=15), minutes)
                or type(close) is not Decimal or not close.is_finite() or close <= 0):
            raise ValueError("P230_CLOSED_PATH_DRIFT")
        complete = complete and start == tip
        tip = end
        distances.append(close-anchor if rule == "B2" else anchor-close)
    minimum = min(distances) if distances else None
    return PrivateBoundaryPath(len(path), complete and tip == expected,
                               minimum, minimum is not None and minimum < 0)


def inspect_private_setup_boundaries(
    raw: tuple[ClosedM5Bar, ...], h4_visible: tuple[NativeFXBar, ...],
    h1: PrivatePretriggerH1, native: PrivatePretriggerNative,
    *, decision: datetime,
) -> PrivateBoundaryReceipt:
    """Consume internal P220 receipts and already-visible raw buffers.

    Path begins after last pretrigger source close; it may include late
    arrivals whose candle closed before setup but was archived afterward.
    This is not a publisher-first-known or post-entry monitoring claim.
    """
    if (type(h1) is not PrivatePretriggerH1 or type(native) is not PrivatePretriggerNative
            or h1.cutoff_utc != native.cutoff_utc or h1.cutoff_utc >= decision
            or h1.action != "NO_SIGNAL" or native.action != "NO_SIGNAL"
            or h1.numeric_policy_approved or native.numeric_policy_approved
            or h1.publisher_first_known_verified or native.publisher_first_known_verified
            or native.d1_calendar_qualified or h1.may_trade or native.may_trade
            or h1.may_publish_buy_sell or native.may_publish_buy_sell):
        raise ValueError("P230_PRETRIGGER_AUTHORITY_DRIFT")
    _utc(decision)
    prior_h1 = _expected_last_closed(h1.cutoff_utc, 60)
    h1_path = ()
    if h1.status == "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED":
        if h1.support_zone is None or h1.resistance_zone is None:
            raise ValueError("P230_H1_ANCHOR_MISSING")
        h1_path = tuple((datetime.fromisoformat(b.start_utc),
                         datetime.fromisoformat(b.end_utc), Decimal(b.close))
                        for b in derive_intraday(raw, "H1", asof_utc=decision).candles
                        if datetime.fromisoformat(b.end_utc) > prior_h1)
    h4_path = ()
    if native.h4_status == "PRETRIGGER_H4_DRAFT_STRUCTURE_COMPUTED":
        if native.h4_prior_end is None or native.h4_low_anchor is None or native.h4_high_anchor is None:
            raise ValueError("P230_H4_ANCHOR_MISSING")
        h4_path = tuple((start, start+timedelta(hours=4), Decimal(b.close))
                        for b in h4_visible
                        for start in (_native_utc_start(b.native_open_label),)
                        if start+timedelta(hours=4) > native.h4_prior_end)
    sides = []
    for rule in ("B2", "S2"):
        h1_result = h4_result = None
        if h1.status == "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED":
            assert h1.support_zone is not None and h1.resistance_zone is not None
            anchor = h1.support_zone[0] if rule == "B2" else h1.resistance_zone[1]
            h1_result = inspect_boundary_path(rule=rule, anchor=anchor, prior_end=prior_h1,
                                              decision=decision, minutes=60, path=h1_path)
        if native.h4_status == "PRETRIGGER_H4_DRAFT_STRUCTURE_COMPUTED":
            assert native.h4_prior_end is not None
            anchor = native.h4_low_anchor if rule == "B2" else native.h4_high_anchor
            assert anchor is not None
            h4_result = inspect_boundary_path(rule=rule, anchor=anchor,
                                              prior_end=native.h4_prior_end,
                                              decision=decision, minutes=240, path=h4_path)
        sides.append(PrivateSetupBoundary(rule, h1_result, h4_result))
    return PrivateBoundaryReceipt(h1.cutoff_utc, tuple(sides))
