"""P232: retrospective M15 middle-pair research on sealed hourly archives.

The :15/:30 opens can have a complete settled pretrigger grid if the
previous hour was committed by :15. The pair is not available until the
current full-hour manifest commits. This is delayed research, not a live
entry, first-known attestation, or qualified historical OOS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from mfx_cache.native_fx_htf import NativeFXBar
from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_engine import derive_intraday
from mfx_research.p227_pretrigger_h1 import (
    PrivatePretriggerH1, _calculate_archive_h1_at_cutoff,
)
from mfx_research.p228_pretrigger_native import (
    PrivatePretriggerNative, calculate_pretrigger_native,
)
from mfx_research.p229_pretrigger_m15 import (
    PrivatePretriggerM15, _calculate_archive_geometry,
)
from tools.audit_mfx_p209_d1_private_cache import PrivateSnapshot

MAX_SAMPLE = 32
MAX_HOURS = 256
M15 = timedelta(minutes=15)
GRACE = timedelta(seconds=15)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateDelayedMiddlePair:
    archive_decision_utc: datetime = field(repr=False)
    trigger_end_utc: datetime = field(repr=False)
    h1: PrivatePretriggerH1 = field(repr=False)
    native: PrivatePretriggerNative = field(repr=False)
    m15: PrivatePretriggerM15 = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateDelayedMiddleReplay:
    verified_hours: int
    samples: tuple[PrivateDelayedMiddlePair, ...] = field(repr=False)

    def public_summary(self) -> dict[str, object]:
        h1 = h4 = d1 = complete = geometry = joint = 0
        for row in self.samples:
            if (row.archive_decision_utc-row.trigger_end_utc < M15+GRACE
                    or row.h1.cutoff_utc != row.trigger_end_utc-2*M15
                    or row.native.cutoff_utc != row.h1.cutoff_utc
                    or row.m15.cutoff_utc != row.h1.cutoff_utc
                    or row.h1.action != "NO_SIGNAL" or row.native.action != "NO_SIGNAL"
                    or row.m15.action != "NO_SIGNAL"
                    or any(x.numeric_policy_approved or x.publisher_first_known_verified
                           or x.may_publish_buy_sell or x.may_trade
                           for x in (row.h1, row.native, row.m15))
                    or row.native.d1_calendar_qualified or row.m15.d1_trend_qualified):
                raise ValueError("P232_RESEARCH_AUTHORITY_OR_CLOCK_DRIFT")
            h1_ok = row.h1.status == "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED"
            h4_ok = row.native.h4_status == "PRETRIGGER_H4_DRAFT_STRUCTURE_COMPUTED"
            d1_ok = row.native.d1_status == "PRETRIGGER_D1_VINTAGE_PRESENT_CALENDAR_UNQUALIFIED"
            complete_ok = row.m15.history_to_setup_complete
            geometry_ok = row.m15.status == "PRIVATE_M15_DRAFT_GEOMETRY_COMPUTED"
            h1 += int(h1_ok)
            h4 += int(h4_ok)
            d1 += int(d1_ok)
            complete += int(complete_ok)
            geometry += int(geometry_ok)
            joint += int(h1_ok and h4_ok and d1_ok and complete_ok and geometry_ok)
        if len(self.samples) != min(MAX_SAMPLE,self.verified_hours):
            raise ValueError("P232_BOUNDED_SAMPLE_ACCOUNTING_DRIFT")
        return {
            "sample_basis": "LATEST_UP_TO_32_SHA_VERIFIED_HOURS_MIDDLE_M15_PAIR",
            "verified_hours": self.verified_hours,
            "middle_pairs_replayed": len(self.samples),
            "pretrigger_h1_draft_contexts_computed": h1,
            "pretrigger_h4_draft_structures_computed": h4,
            "pretrigger_d1_fresh_vintages_with_five_rows": d1,
            "pretrigger_m15_settled_grid_complete": complete,
            "private_m15_draft_geometry_computed": geometry,
            "joint_inputs_present_d1_unqualified": joint,
            "minimum_structural_delay_minutes": 15,
            "retrospective_delayed_research_only": True,
            "publisher_first_known_verified": False,
            "d1_calendar_qualified": False,
            "historical_oos_qualified": False,
            "market_signal_eligibility_assessed": False,
            "action": "NO_SIGNAL", "may_publish_buy_sell": False,
            "may_trade": False,
        }


def replay_delayed_middle_pairs(
    raw: tuple[ClosedM5Bar, ...],
    commits: tuple[tuple[datetime, datetime], ...],
    h4: tuple[tuple[datetime, tuple[NativeFXBar, ...]], ...],
    d1: tuple[tuple[datetime, PrivateSnapshot], ...],
) -> PrivateDelayedMiddleReplay:
    """Call only with the final already SHA-audited P219 raw prefix.

    For each sampled hour, the observed decision is its actual manifest
    creation clock; even later M5 bars from that hour cannot affect the
    pretrigger context or middle trigger pair. No replay at invented clocks.
    """
    if (type(raw) is not tuple or type(commits) is not tuple
            or not 0 <= len(commits) <= MAX_HOURS or len(raw) != 12*len(commits)):
        raise ValueError("P232_EXACT_BOUNDED_PREFIX_REQUIRED")
    samples = []
    for i in range(max(0,len(commits)-MAX_SAMPLE),len(commits)):
        known, end = commits[i]
        cutoff = end-3*M15
        latest_open = end-2*M15
        trigger_end = end-M15
        prefix = raw[:12*(i+1)]
        # Full sealed hour: slots 3..8 are the two middle M15 bars.
        pair_raw = prefix[-9:-3]
        if known < end+GRACE:
            raise ValueError("P232_ARCHIVE_BEFORE_SETTLED_HOUR")
        h1 = _calculate_archive_h1_at_cutoff(
            prefix, commits[:i+1], cutoff=cutoff, decision_utc=known)
        pair = derive_intraday(pair_raw, "M15", asof_utc=known).candles
        if (len(pair) != 2 or datetime.fromisoformat(pair[0].start_utc) != cutoff
                or datetime.fromisoformat(pair[1].start_utc) != latest_open
                or datetime.fromisoformat(pair[-1].end_utc) != trigger_end
                or pair[0].end_utc != pair[1].start_utc):
            raise ValueError("P232_EXACT_MIDDLE_PAIR_REQUIRED")
        native = calculate_pretrigger_native(
            tuple((clock,bars) for clock,bars in h4 if clock<=known),
            tuple((clock,snap) for clock,snap in d1 if clock<=known),
            cutoff=cutoff, decision=known)
        m15 = _calculate_archive_geometry(
            prefix, commits[:i+1], h1, trigger_raw=pair_raw,
            latest_m15_open=latest_open, decision=known)
        samples.append(PrivateDelayedMiddlePair(known,trigger_end,h1,native,m15))
    receipt = PrivateDelayedMiddleReplay(len(commits),tuple(samples))
    receipt.public_summary()
    return receipt
