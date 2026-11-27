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
    if any(t not in visible for t in targets):
        return PrivateEMAWatch(cutoff, "HISTORY_UNAVAILABLE")
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
        return PrivateEMAWatch(cutoff, "ZERO_TR")
    return PrivateEMAWatch(cutoff, "OBSERVED", pair)


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
