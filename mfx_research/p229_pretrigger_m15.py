"""Private P229 two-M15 draft geometry on P219 archive-visible history.

Distinguish pretrigger level availability, continuity to setup and private
conditional geometry. No signal, D1 trend inference or execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_cache.v2_engine import derive_intraday
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    _p160_still_pinned, read_mfx_confirmed_b2s2_v2,
)
from mfx_research.mfx_b2s2_independent_policy_draft import read_independent_mfx_policy_draft
from mfx_research.p227_pretrigger_h1 import PrivatePretriggerH1, calculate_pretrigger_h1
from mfx_research.sealed_multibar_private_features import _Bar, _latest_contiguous
from mfx_research.sealed_private_pivot_sensitivity import _scan_one
from mfx_research.six_tf_readonly_context import GRACE
from mfx_research.shared_b2s2_geometry import b2s2_geometry

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
class PrivateEarlyObservation:
    rule_id: str
    first_zone_contact: bool = field(repr=False)
    strict_relative_extremum: bool = field(repr=False)
    strict_zone_edge_reclaim: bool = field(repr=False)


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
    early_sides: tuple[PrivateEarlyObservation, ...] = field(default=(), repr=False)
    early_event_approved: bool = False
    history_context_sha256: str | None = field(default=None, repr=False)


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
    return _calculate_archive_geometry(
        raw, commits, h1, trigger_raw=raw[-6:],
        latest_m15_open=latest_m15_open, decision=decision)


def _calculate_archive_geometry(
    raw: tuple[ClosedM5Bar, ...],
    commits: tuple[tuple[datetime, datetime], ...],
    h1: PrivatePretriggerH1,
    *, trigger_raw: tuple[ClosedM5Bar, ...],
    latest_m15_open: datetime, decision: datetime,
) -> PrivatePretriggerM15:
    """Internal geometry; caller binds the exact H1 and source trigger pair."""
    cutoff = h1.cutoff_utc
    if (cutoff != latest_m15_open-M15 or type(trigger_raw) is not tuple
            or len(trigger_raw) != 6):
        raise ValueError("P232_TRIGGER_CUTOFF_JOIN_DRIFT")
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
    contiguous = _latest_contiguous(rows, "M15")
    study = _scan_one("M15", contiguous, policy.micro_left, policy.micro_right)
    highs = [p.candidate_mid_price for p in study.pivots if p.kind == "HIGH"]
    lows = [p.candidate_mid_price for p in study.pivots if p.kind == "LOW"]
    if (h1.status != "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED"
            or h1.mean_tr is None or h1.support_zone is None or h1.resistance_zone is None):
        status = ("NO_PRETRIGGER_M15_LEVEL" if not highs and not lows
                  else "PRETRIGGER_H1_CONTEXT_UNAVAILABLE")
        return PrivatePretriggerM15(cutoff, status, complete)
    # The trigger candles are evaluated at decision, never fed into the
    # pretrigger pivot or H1 zone. Exact two contiguous closed M15 bars.
    triggers = derive_intraday(trigger_raw, "M15", asof_utc=decision).candles
    if (len(triggers) != 2 or datetime.fromisoformat(triggers[0].start_utc) != cutoff
            or triggers[0].end_utc != triggers[1].start_utc
            or datetime.fromisoformat(triggers[1].start_utc) != latest_m15_open):
        raise ValueError("P229_EXACT_CLOSED_TRIGGER_PAIR_REQUIRED")
    first, last = triggers
    p = read_independent_mfx_policy_draft()
    tolerance, chase = h1.mean_tr*p.h1_near_multiple, h1.mean_tr*p.max_chase_multiple
    first_low, first_high, first_close, last_close = map(
        Decimal, (first.low, first.high, first.close, last.close))
    last_low, last_high = Decimal(last.low), Decimal(last.high)
    sides = []
    early = []
    for rule, levels, zone in (("B2", highs, h1.support_zone),
                               ("S2", lows, h1.resistance_zone)):
        level = levels[-1] if levels else None
        near, crossed, anti = b2s2_geometry(
            rule, first_low, first_high, first_close, last_close,
            zone, level, tolerance, chase,
        )
        # P236 independent observations, not a confirmed swing or early event.
        # They require the frozen H1 zone, but not a confirmed micro level.
        relative = last_low > first_low if rule == "B2" else last_high < first_high
        reclaim = (first_close <= zone[1] < last_close if rule == "B2"
                   else first_close >= zone[0] > last_close)
        early.append(PrivateEarlyObservation(rule, near, relative, reclaim))
        sides.append(PrivateM15Geometry(rule, level, near, crossed, anti))
    if not highs and not lows:
        return PrivatePretriggerM15(cutoff, "NO_PRETRIGGER_M15_LEVEL", complete,
                                    early_sides=tuple(early))
    history_context = digest({"schema": "P237_M15_DRAFT_HISTORY_V1",
                              "cutoff": cutoff.isoformat(),
                              "policy": policy.fingerprint_sha256,
                              "source": [b.sha_claim for b in contiguous]})
    return PrivatePretriggerM15(cutoff, "PRIVATE_M15_DRAFT_GEOMETRY_COMPUTED",
                                complete, tuple(sides), early_sides=tuple(early),
                                history_context_sha256=history_context)


def early_observation_coverage(m15: PrivatePretriggerM15, h1: PrivatePretriggerH1) -> bool:
    """Redacted availability only: no observations, combinations or events exported."""
    if (type(m15) is not PrivatePretriggerM15 or type(h1) is not PrivatePretriggerH1
            or m15.cutoff_utc != h1.cutoff_utc or m15.early_event_approved
            or m15.action != "NO_SIGNAL" or m15.numeric_policy_approved
            or m15.publisher_first_known_verified or m15.d1_trend_qualified
            or m15.may_publish_buy_sell or m15.may_trade
            or type(m15.early_sides) is not tuple):
        raise ValueError("P236_EARLY_OBSERVATION_AUTHORITY_DRIFT")
    if not m15.early_sides:
        return False
    if (h1.status != "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED"
            or any(type(s) is not PrivateEarlyObservation for s in m15.early_sides)
            or tuple(s.rule_id for s in m15.early_sides) != ("B2", "S2")
            or any(type(v) is not bool for s in m15.early_sides
                   for v in (s.first_zone_contact, s.strict_relative_extremum,
                             s.strict_zone_edge_reclaim))):
        raise ValueError("P236_EARLY_OBSERVATION_PAIR_DRIFT")
    return True
