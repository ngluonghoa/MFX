"""Private P229 two-M15 draft geometry on P219 archive-visible history.

Distinguish pretrigger level availability, continuity to setup and private
conditional geometry. No signal, D1 trend inference or execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_engine import derive_intraday
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    _p160_still_pinned, read_mfx_confirmed_b2s2_v2,
)
from mfx_research.mfx_b2s2_independent_policy_draft import read_independent_mfx_policy_draft
from mfx_research.p227_pretrigger_h1 import PrivatePretriggerH1, calculate_pretrigger_h1
from mfx_research.sealed_multibar_private_features import _Bar, _latest_contiguous
from mfx_research.sealed_private_pivot_sensitivity import _scan_one
from mfx_research.six_tf_readonly_context import GRACE

M5 = timedelta(minutes=5)
M15 = timedelta(minutes=15)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateM15Geometry:
    rule_id: str
    level: Decimal | None = field(repr=False)
    near: bool = field(repr=False)
    crossed: bool = field(repr=False)
    anti_chase: bool = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class PrivatePretriggerM15:
    cutoff_utc: datetime = field(repr=False)
    status: str
    history_to_setup_complete: bool
    sides: tuple[PrivateM15Geometry, ...] = field(default=(), repr=False)
    publisher_first_known_verified: bool = False
    numeric_policy_approved: bool = False
    d1_trend_qualified: bool = False
    action: str = "NO_SIGNAL"
    may_publish_buy_sell: bool = False
    may_trade: bool = False


def calculate_pretrigger_m15(
    raw: tuple[ClosedM5Bar, ...],
    commits: tuple[tuple[datetime, datetime], ...],
    h1: PrivatePretriggerH1,
    *, latest_m15_open: datetime, decision: datetime,
) -> PrivatePretriggerM15:
    # Recheck the exact P227 source join and cutoff, not caller-claimed levels.
    if h1 != calculate_pretrigger_h1(raw, commits, latest_m15_open=latest_m15_open,
                                     decision_utc=decision):
        raise ValueError("P229_H1_SOURCE_CONTEXT_DRIFT")
    cutoff = h1.cutoff_utc
    visible = sum(known <= cutoff and end <= cutoff for known, end in commits)
    eligible = tuple(b for b in raw[:12*visible]
                     if datetime.fromisoformat(b.start_utc)+M5 <= cutoff-GRACE)
    if not eligible:
        return PrivatePretriggerM15(cutoff, "NO_PRETRIGGER_M15_ARCHIVE", False)
    history = derive_intraday(eligible, "M15", asof_utc=cutoff).candles
    if not history:
        return PrivatePretriggerM15(cutoff, "NO_PRETRIGGER_M15_ARCHIVE", False)
    # At exact setup open the immediately preceding bar has not settled.
    # Full-hour archival often leaves even earlier bars missing. Expose
    # coverage separately: never equate an old known level with a complete
    # pretrigger micro-context.
    complete = datetime.fromisoformat(history[-1].end_utc) == cutoff-M15
    rows = tuple(_Bar(b.start_utc, b.open, b.high, b.low, b.close, b.source_sha256)
                 for b in history[-16:])
    _p160_still_pinned()
    policy = read_mfx_confirmed_b2s2_v2()
    if (policy.micro_left, policy.micro_right) != (1, 1):
        raise ValueError("P229_PINNED_DRAFT_PIVOT_WIDTH_DRIFT")
    study = _scan_one("M15", _latest_contiguous(rows, "M15"),
                      policy.micro_left, policy.micro_right)
    highs = [p.candidate_mid_price for p in study.pivots if p.kind == "HIGH"]
    lows = [p.candidate_mid_price for p in study.pivots if p.kind == "LOW"]
    if not highs and not lows:
        return PrivatePretriggerM15(cutoff, "NO_PRETRIGGER_M15_LEVEL", complete)
    if (h1.status != "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED"
            or h1.mean_tr is None or h1.support_zone is None or h1.resistance_zone is None):
        return PrivatePretriggerM15(cutoff, "PRETRIGGER_H1_CONTEXT_UNAVAILABLE", complete)
    # The trigger candles are evaluated at decision, never fed into the
    # pretrigger pivot or H1 zone. Exact two contiguous closed M15 bars.
    triggers = derive_intraday(raw[-6:], "M15", asof_utc=decision).candles
    if (len(triggers) != 2 or datetime.fromisoformat(triggers[0].start_utc) != cutoff
            or triggers[0].end_utc != triggers[1].start_utc
            or datetime.fromisoformat(triggers[1].start_utc) != latest_m15_open):
        raise ValueError("P229_EXACT_CLOSED_TRIGGER_PAIR_REQUIRED")
    first, last = triggers
    p = read_independent_mfx_policy_draft()
    tolerance, chase = h1.mean_tr*p.h1_near_multiple, h1.mean_tr*p.max_chase_multiple
    first_low, first_high, first_close, last_close = map(
        Decimal, (first.low, first.high, first.close, last.close))
    sides = []
    for rule, levels, zone in (("B2", highs, h1.support_zone),
                               ("S2", lows, h1.resistance_zone)):
        level = levels[-1] if levels else None
        near = first_low <= zone[1]+tolerance and first_high >= zone[0]-tolerance
        crossed = False
        anti = False
        if level is not None:
            if rule == "B2":
                crossed = first_close <= level < last_close
                anti = crossed and last_close-level <= chase
            else:
                crossed = first_close >= level > last_close
                anti = crossed and level-last_close <= chase
        sides.append(PrivateM15Geometry(rule, level, near, crossed, anti))
    return PrivatePretriggerM15(cutoff, "PRIVATE_M15_DRAFT_GEOMETRY_COMPUTED",
                                complete, tuple(sides))
