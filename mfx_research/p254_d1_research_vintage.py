"""P254: one versioned private D1 research selection rule.

Inputs MUST already be SHA-audited P220 archives. This is an observed
archive availability proxy, not publisher first-known or source admission.
Never stitch vintages or choose by OHLC, length, freshness or outcome.
"""
from datetime import datetime, timedelta

from tools.audit_mfx_p209_d1_private_cache import PrivateSnapshot

VERSION = "MFX_P254_LATEST_ARCHIVE_VISIBLE_WHOLE_D1_RESEARCH_VINTAGE_V1"
MAX_SNAPSHOTS = 256


def _utc(value):
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P254_EXACT_UTC_CLOCK_REQUIRED")


def select_private_d1_research_vintage(
    history: tuple[tuple[datetime, PrivateSnapshot], ...],
    *, cutoff: datetime,
) -> PrivateSnapshot | None:
    """Return newest observed *whole* visible snapshot, even if short/stale.

    Archive creation must be at or before cutoff; late backfills cannot
    enter earlier decisions. Unique runner observation timestamps required.
    No canonical D1, external IO, vendor first-known or price approval.
    """
    _utc(cutoff)
    if type(history) is not tuple or len(history) > MAX_SNAPSHOTS:
        raise ValueError("P254_BOUNDED_VERIFIED_HISTORY_REQUIRED")
    selected = None
    seen = set()
    for pair in history:
        if type(pair) is not tuple or len(pair) != 2:
            raise ValueError("P254_EXACT_ARCHIVE_PAIR_REQUIRED")
        created, snap = pair
        _utc(created)
        if (type(snap) is not PrivateSnapshot
                or type(snap.rows) is not tuple or not snap.rows):
            raise ValueError("P254_TYPED_NONEMPTY_D1_SNAPSHOT_REQUIRED")
        _utc(snap.observed)
        if snap.observed > created or snap.observed in seen:
            raise ValueError("P254_AMBIGUOUS_OR_IMPOSSIBLE_ARCHIVE_CLOCK")
        seen.add(snap.observed)
        if created <= cutoff and (selected is None or snap.observed > selected.observed):
            selected = snap
    return selected
