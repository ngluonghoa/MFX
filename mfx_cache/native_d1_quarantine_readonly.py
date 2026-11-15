"""P0.170: same-OAuth read-only SHA audit of P0.169 D1 quarantine observations.

This NEVER selects a canonical D1 revision, overwrites prices or permits a
signal. Source first-known and vendor contractual rights remain unverified.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any

from mfx_cache.native_d1_quarantine_stage import (
    MAX_OBSERVATIONS, PREFIX, validate_d1_quarantine_observation,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")


def audit_d1_quarantine_readonly(
    store: Any, *, canonical_d1_manifest_sha256: str, now_utc: datetime,
) -> dict[str, Any]:
    """Verify each isolated Drive object, name/hash, source and old D1 parent.

    The canonical D1 source MUST have passed its own independent full SHA
    archive audit before this function is invoked. A missing source object
    is a visible failure, never a false report of successful D1 custody.
    """
    if (type(canonical_d1_manifest_sha256) is not str
            or _SHA.fullmatch(canonical_d1_manifest_sha256) is None):
        raise ValueError("P170_CANONICAL_D1_SHA_REQUIRED")
    if (type(now_utc) is not datetime or now_utc.tzinfo is None
            or now_utc.utcoffset() != timedelta(0)):
        raise ValueError("P170_UTC_AUDIT_CLOCK_REQUIRED")
    if (not callable(getattr(store, "list_names", None))
            or not callable(getattr(store, "read", None))):
        raise ValueError("P170_READ_ONLY_SOURCE_STORE_REQUIRED")

    names = store.list_names("chunk")
    if (type(names) is not tuple
            or not all(type(name) is str and name.startswith(PREFIX)
                       for name in names)
            or len(names) != len(set(names))):
        raise ValueError("P170_QUARANTINE_LISTING_NOT_UNIQUE_OR_SCOPED")
    if not names:
        raise ValueError("P170_D1_QUARANTINE_SOURCE_NOT_FOUND")
    if len(names) > MAX_OBSERVATIONS:
        raise ValueError("P170_QUARANTINE_READER_CAPACITY_EXCEEDED")

    earliest: datetime | None = None
    latest: datetime | None = None
    total_bars = 0
    identities: set[str] = set()
    for name in names:
        record = validate_d1_quarantine_observation(
            store.read("chunk", name))
        identity = record["observation_identity_sha256"]
        if name != f"{PREFIX}{identity}.json" or identity in identities:
            raise ValueError("P170_QUARANTINE_FILENAME_OR_IDENTITY_COLLISION")
        identities.add(identity)
        if record["original_manifest_sha256"] != canonical_d1_manifest_sha256:
            raise ValueError("P170_QUARANTINE_OLD_CANONICAL_SHA_CHANGED")
        observed = datetime.fromisoformat(record["observed_at_runner_utc"])
        if observed > now_utc:
            raise ValueError("P170_FUTURE_OBSERVATION_CLOCK")
        earliest = observed if earliest is None else min(earliest, observed)
        latest = observed if latest is None else max(latest, observed)
        total_bars += len(record["source_batch"]["closed_bars"])

    if earliest is None or latest is None:
        raise ValueError("P170_QUARANTINE_EMPTY_AFTER_VALIDATION")
    return {
        "status": "D1_QUARANTINE_RAW_OBSERVATIONS_SHA_READONLY_PASS",
        "source": "TWELVE_DATA_COMPOSITE_MID",
        "symbol": "EUR/USD",
        "interval": "1day",
        "incident_local_label": "2026-11-11",
        "observation_objects_verified": len(names),
        "raw_closed_rows_across_observations": total_bars,
        "earliest_runner_observed_utc": earliest.isoformat(),
        "latest_runner_observed_utc": latest.isoformat(),
        "canonical_old_d1_parent_sha_matched": True,
        "publisher_first_known_verified": False,
        "vendor_storage_rights_verified": False,
        "d1_canonical_revision_authorized": False,
        "d1_canonical_writes": 0,
        "drive_writes": 0,
        "provider_price_requests": 0,
        "may_publish_buy_sell": False,
        "broker_orders": 0,
    }
