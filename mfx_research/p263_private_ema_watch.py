"""P263: private observed-archive EMA research, not synthetic relabeling.

Only called inside the P232 SHA-audited, P227 validated archive replay.
Compute from a fixed 50-hour seed available before the setup; the first
closed M15 probe is only observed at the later archive decision.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from mfx_cache.v2_engine import DerivedCandle, derive_intraday
from mfx_research.p256_ema_watch import EMAWatch, _watch_from_validated_rows
from mfx_research.six_tf_readonly_context import _expected_last_closed

HOUR = timedelta(hours=1)
M15 = timedelta(minutes=15)
SEED = 50
TOLERANCE = Decimal("0.5")  # Explicit uncalibrated private research scenario.


@dataclass(frozen=True, slots=True, repr=False)
class PrivateEMAWatch:
    cutoff_utc: datetime = field(repr=False)
    status: str
    observations: tuple[EMAWatch, ...] = field(default=(), repr=False)
    seed_clock_state: str = "UNCLASSIFIED"


def _observe_archive_ema(raw, commits, probe, *, cutoff, decision):
    """Internal P232 source path; no extra provider or Drive IO."""
    if (type(raw) is not tuple or type(commits) is not tuple
            or not 1 <= len(commits) <= 256 or len(raw) != 12 * len(commits)
            or type(probe) is not DerivedCandle or probe.frame != "M15"
            or datetime.fromisoformat(probe.start_utc) != cutoff
            or datetime.fromisoformat(probe.end_utc) != cutoff + M15
            or cutoff + M15 > decision):
        raise ValueError("P263_ARCHIVE_PROBE_JOIN_DRIFT")
    expected = _expected_last_closed(cutoff, 60)
    visible = {end: i for i, (known, end) in enumerate(commits)
               if known <= cutoff and end <= expected}
    targets = tuple(expected - i * HOUR for i in reversed(range(SEED)))
    state = _seed_clock_state(commits, targets, cutoff)
    if state != "COMPLETE":
        return PrivateEMAWatch(cutoff, "HISTORY_UNAVAILABLE", seed_clock_state=state)
    indices = tuple(visible[t] for t in targets)
    if indices != tuple(range(indices[0], indices[0] + SEED)):
        raise ValueError("P263_ARCHIVE_INDEX_DRIFT")
    rows = derive_intraday(raw[indices[0]*12:(indices[-1]+1)*12], "H1",
                           asof_utc=cutoff).candles
    if tuple(datetime.fromisoformat(x.end_utc) for x in rows) != targets:
        raise ValueError("P263_SEED_GRID_DRIFT")
    try:
        pair = tuple(_watch_from_validated_rows(rule, rows, probe, TOLERANCE)
                     for rule in ("B2", "S2"))
    except ValueError as e:
        if str(e) != "P256_ZERO_TR":
            raise
        return PrivateEMAWatch(cutoff, "ZERO_TR", seed_clock_state="COMPLETE")
    return PrivateEMAWatch(cutoff, "OBSERVED", pair, "COMPLETE")


def ema_observation_available(value, cutoff):
    """Only coverage may leave the private replay; never price or direction."""
    if value is None:  # backwards compatibility for legacy fixture receipts
        return False
    if (type(value) is not PrivateEMAWatch or value.cutoff_utc != cutoff
            or type(value.observations) is not tuple
            or value.status not in ("HISTORY_UNAVAILABLE", "ZERO_TR", "OBSERVED")):
        raise ValueError("P263_EMA_RECEIPT_DRIFT")
    if value.status != "OBSERVED":
        if value.observations:
            raise ValueError("P263_UNAVAILABLE_OBSERVATION_DRIFT")
        return False
    if (len(value.observations) != 2
            or any(type(x) is not EMAWatch or type(x.near20) is not bool
                   or type(x.near50) is not bool for x in value.observations)):
        raise ValueError("P263_EMA_PAIR_DRIFT")
    return True


SEED_CLOCK_STATES = ("COMPLETE", "OUTSIDE_TAIL", "MISSING_HOUR", "LATE_HOUR",
                     "MIXED", "UNCLASSIFIED")


def _seed_clock_state(commits, targets, cutoff):
    """Classify exact required hours using metadata, not prices or outcomes."""
    known_by_end = {end: known for known, end in commits}
    if len(known_by_end) != len(commits):
        raise ValueError("P264_DUPLICATE_ARCHIVE_HOUR")
    first = min(known_by_end)
    gaps = set()
    for target in targets:
        if target not in known_by_end:
            gaps.add("OUTSIDE_TAIL" if target < first else "MISSING_HOUR")
        elif known_by_end[target] > cutoff:
            gaps.add("LATE_HOUR")
    return next(iter(gaps)) if len(gaps) == 1 else "MIXED" if gaps else "COMPLETE"


def ema_clock_state(value, cutoff):
    available = ema_observation_available(value, cutoff)
    if value is None:
        return "UNCLASSIFIED"
    state = value.seed_clock_state
    if state not in SEED_CLOCK_STATES:
        raise ValueError("P264_UNKNOWN_SEED_CLOCK_STATE")
    if state == "UNCLASSIFIED":
        raise ValueError("P264_UNCLASSIFIED_EMA_RECEIPT")
    if (state == "COMPLETE") != (available or value.status == "ZERO_TR"):
        raise ValueError("P264_SEED_CLOCK_STATUS_DRIFT")
    return state
