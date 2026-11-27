"""P263: private observed-archive EMA research, not synthetic relabeling.

Only called inside the P232 SHA-audited, P227 validated archive replay.
Compute from a fixed 50-hour seed available before the setup; the first
closed M15 probe is only observed at the later archive decision.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from mfx_cache.td_m5_codec import digest
from mfx_cache.v2_engine import DerivedCandle, derive_intraday
from mfx_research.p231_private_trigger_identity import PrivateTriggerIdentity
from mfx_research.p256_ema_watch import EMAWatch, _watch_from_validated_rows
from mfx_research.six_tf_readonly_context import _expected_last_closed

HOUR = timedelta(hours=1)
M15 = timedelta(minutes=15)
SEED = 50
SENSITIVITY_SEED = 100
TOLERANCE = Decimal("0.5")  # Explicit uncalibrated private research scenario.


@dataclass(frozen=True, slots=True, repr=False)
class PrivateSeedComparison:
    long_observations: tuple[EMAWatch, ...] = field(repr=False)
    agreement: tuple[tuple[bool, bool], ...] = field(repr=False)
    context_sha256: str = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateEMAWatch:
    cutoff_utc: datetime = field(repr=False)
    status: str
    observations: tuple[EMAWatch, ...] = field(default=(), repr=False)
    seed_clock_state: str = "UNCLASSIFIED"
    comparison: PrivateSeedComparison | None = field(default=None, repr=False)
    long_seed_clock_state: str = "UNCLASSIFIED"
    probe_source_sha256: str | None = field(default=None, repr=False)
    short_context_sha256: str | None = field(default=None, repr=False)


def _observe_archive_ema(raw, commits, probe, *, cutoff, decision):
    """Internal P232 source path; no extra provider or Drive IO."""
    if (type(raw) is not tuple or type(commits) is not tuple
            or not 1 <= len(commits) <= 256 or len(raw) != 12 * len(commits)
            or type(probe) is not DerivedCandle or probe.frame != "M15"
            or datetime.fromisoformat(probe.start_utc) != cutoff
            or datetime.fromisoformat(probe.end_utc) != cutoff + M15
            or cutoff + M15 > decision):
        raise ValueError("P263_ARCHIVE_PROBE_JOIN_DRIFT")
    # P232 uses the first middle-quarter probe of its final complete hour.
    if derive_intraday(raw[-9:-6], "M15", asof_utc=decision).candles != (probe,):
        raise ValueError("P266_EXACT_PROBE_SOURCE_DRIFT")
    expected = _expected_last_closed(cutoff, 60)
    visible = {end: i for i, (known, end) in enumerate(commits)
               if known <= cutoff and end <= expected}
    targets = tuple(expected - i * HOUR for i in reversed(range(SEED)))
    state = _seed_clock_state(commits, targets, cutoff)
    long_targets = tuple(expected - i * HOUR for i in reversed(range(SENSITIVITY_SEED)))
    long_state = _seed_clock_state(commits, long_targets, cutoff)
    if state != "COMPLETE":
        return PrivateEMAWatch(cutoff, "HISTORY_UNAVAILABLE", seed_clock_state=state,
                               long_seed_clock_state=long_state,
                               probe_source_sha256=probe.source_sha256)
    indices = tuple(visible[t] for t in targets)
    if indices != tuple(range(indices[0], indices[0] + SEED)):
        raise ValueError("P263_ARCHIVE_INDEX_DRIFT")
    rows = derive_intraday(raw[indices[0]*12:(indices[-1]+1)*12], "H1",
                           asof_utc=cutoff).candles
    if tuple(datetime.fromisoformat(x.end_utc) for x in rows) != targets:
        raise ValueError("P263_SEED_GRID_DRIFT")
    short_context = _seed_context(rows, commits, indices, probe, cutoff)
    try:
        pair = tuple(_watch_from_validated_rows(rule, rows, probe, TOLERANCE)
                     for rule in ("B2", "S2"))
    except ValueError as e:
        if str(e) != "P256_ZERO_TR":
            raise
        return PrivateEMAWatch(cutoff, "ZERO_TR", seed_clock_state="COMPLETE",
                               long_seed_clock_state=long_state,
                               probe_source_sha256=probe.source_sha256,
                               short_context_sha256=short_context)
    comparison = None
    if long_state == "COMPLETE":
        long_indices = tuple(visible[t] for t in long_targets)
        if long_indices != tuple(range(long_indices[0], long_indices[0] + SENSITIVITY_SEED)):
            raise ValueError("P265_LONG_SEED_INDEX_DRIFT")
        long_rows = derive_intraday(raw[long_indices[0]*12:(long_indices[-1]+1)*12], "H1",
                                    asof_utc=cutoff).candles
        if (tuple(datetime.fromisoformat(x.end_utc) for x in long_rows) != long_targets
                or long_rows[-SEED:] != rows):
            raise ValueError("P265_LONG_SEED_SUFFIX_DRIFT")
        long_pair = tuple(_watch_from_validated_rows(rule, long_rows, probe, TOLERANCE)
                          for rule in ("B2", "S2"))
        long_context = _seed_context(long_rows, commits, long_indices, probe, cutoff)
        comparison = PrivateSeedComparison(long_pair, _agreement(pair, long_pair), long_context)
    return PrivateEMAWatch(cutoff, "OBSERVED", pair, "COMPLETE", comparison, long_state,
                           probe.source_sha256, short_context)


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


def _agreement(short, long):
    return tuple((a.near20 == b.near20, a.near50 == b.near50)
                 for a, b in zip(short, long))


def ema_seed_comparison_available(value, cutoff):
    """Only paired coverage is public; private agreement is never serialized."""
    short_available = ema_observation_available(value, cutoff)
    short_state = ema_clock_state(value, cutoff)
    if value is None:
        return False
    long_state = value.long_seed_clock_state
    if long_state not in SEED_CLOCK_STATES[:-1]:
        raise ValueError("P265_LONG_SEED_CLOCK_STATE_DRIFT")
    if long_state == "COMPLETE" and short_state != "COMPLETE":
        raise ValueError("P265_IMPOSSIBLE_LONG_SEED_COVERAGE")
    comparison = value.comparison
    available = short_available and long_state == "COMPLETE"
    if available != (comparison is not None):
        raise ValueError("P265_COMPARISON_COVERAGE_DRIFT")
    if not available:
        return False
    if (type(comparison) is not PrivateSeedComparison
            or type(comparison.long_observations) is not tuple
            or len(comparison.long_observations) != 2
            or any(type(x) is not EMAWatch or type(x.near20) is not bool
                   or type(x.near50) is not bool for x in comparison.long_observations)
            or type(comparison.agreement) is not tuple
            or any(type(x) is not tuple or len(x) != 2
                   or any(type(v) is not bool for v in x) for x in comparison.agreement)
            or comparison.agreement != _agreement(value.observations, comparison.long_observations)):
        raise ValueError("P265_COMPARISON_PAIR_DRIFT")
    return True


def _seed_context(rows, commits, indices, probe, cutoff):
    """Bind the consumed inputs, not later decision prices or outcomes."""
    return digest({"schema": "MFX_P266_PRIVATE_EMA_CONTEXT_V1",
                   "cutoff": cutoff.isoformat(), "seed": len(rows),
                   "tolerance": str(TOLERANCE), "probe": probe.source_sha256,
                   "hours": [[row.source_sha256, row.end_utc, commits[i][0].isoformat()]
                             for row, i in zip(rows, indices)]})


def _is_sha(value):
    return (type(value) is str and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def bind_private_ema_to_trigger(value, trigger, cutoff):
    """Validate same first-probe source join; never an event or approval."""
    if value is None:
        return False
    available = ema_observation_available(value, cutoff)
    if (type(trigger) is not PrivateTriggerIdentity
            or not _is_sha(value.probe_source_sha256)
            or value.probe_source_sha256 != trigger.first_probe_source_sha256):
        raise ValueError("P266_EMA_TRIGGER_SOURCE_DRIFT")
    complete = ema_clock_state(value, cutoff) == "COMPLETE"
    if (complete != _is_sha(value.short_context_sha256)
            or (not complete and value.short_context_sha256 is not None)):
        raise ValueError("P266_SHORT_SEED_CONTEXT_DRIFT")
    if ema_seed_comparison_available(value, cutoff):
        if (not _is_sha(value.comparison.context_sha256)
                or value.comparison.context_sha256 == value.short_context_sha256):
            raise ValueError("P266_LONG_SEED_CONTEXT_DRIFT")
    return available
