"""P046-B3-B: staged synthetic-only two-update payload (NEVER market data).

The content explicitly carries SYNTHETIC_NOT_TWELVE_DATA identity and cannot
pass real MFX native MID/provider cache schema. No price API calls, brokers,
signals, or original Forex source dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from mfx_cache.td_m5_codec import digest

VERSION = "MFX_A04_P46_B3B_GDRIVE_SYNTHETIC_ONLY_V1"
SYNTHETIC_SOURCE = "SYNTHETIC_FIXTURE_NO_VENDOR_OR_MARKET_DATA"


class SyntheticPort(Protocol):
    def load(self) -> dict[str, Any] | None: ...
    def write(
        self, *, expected: dict[str, Any] | None,
        replacement: dict[str, Any],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class StagingReceipt:
    status: str
    first_sha256: str
    second_sha256: str
    file_creates_expected: int
    same_file_in_place_updates_expected: int
    observed_first_readback: bool
    observed_second_readback: bool
    actual_provider_requests: int = 0
    broker_orders: int = 0
    source_numeric_signals_approved: bool = False


def _utc(now: datetime) -> None:
    if (type(now) is not datetime or now.tzinfo is None
            or now.utcoffset() != timedelta(0)):
        raise ValueError("P046_B3B_STAGING_UTC_REQUIRED")


def validate_synthetic(
    payload: object, *, now_utc: datetime,
) -> dict[str, Any]:
    _utc(now_utc)
    if type(payload) is not dict or set(payload) != {
        "schema", "data_kind", "provider", "symbol", "side", "interval",
        "timezone", "fixture_created_utc", "run_id",
        "generation", "previous_sha256", "synthetic_values",
        "approval_to_trade", "broker_orders",
    }:
        raise ValueError("P046_B3B_INVALID_SYNTHETIC_SHAPE")
    m = payload
    if (m["schema"] != VERSION
            or m["data_kind"] != SYNTHETIC_SOURCE
            or m["provider"] != "NONE_SYNTHETIC"
            or m["symbol"] != "NONE_SYNTHETIC"
            or m["side"] != "SYNTHETIC"
            or m["interval"] != "SYNTHETIC"
            or m["timezone"] != "UTC"
            or m["approval_to_trade"] is not False
            or type(m["broker_orders"]) is not int
            or m["broker_orders"] != 0):
        raise ValueError("P046_B3B_FIXTURE_CANNOT_IMPERSONATE_PRICE")
    if (type(m["generation"]) is not int
            or m["generation"] not in (1, 2)
            or type(m["run_id"]) is not str
            or not m["run_id"].isdigit()
            or not 1 <= len(m["run_id"]) <= 18):
        raise ValueError("P046_B3B_INVALID_FIXTURE_GENERATION")
    if ((m["generation"] == 1 and m["previous_sha256"] is not None)
            or (m["generation"] == 2 and
                (type(m["previous_sha256"]) is not str
                 or len(m["previous_sha256"]) != 64))):
        raise ValueError("P046_B3B_BAD_FIXTURE_PARENT_SHA")
    try:
        created = datetime.fromisoformat(m["fixture_created_utc"])
    except (ValueError, TypeError) as exc:
        raise ValueError("P046_B3B_BAD_FIXTURE_TIME") from exc
    _utc(created)
    if created > now_utc:
        raise ValueError("P046_B3B_FUTURE_FIXTURE")
    if (type(m["synthetic_values"]) is not list
            or len(m["synthetic_values"]) != 3
            or any(type(x) is not int for x in m["synthetic_values"])):
        raise ValueError("P046_B3B_SYNTHETIC_INTEGERS_ONLY")
    return m


def _sample(run_id: str, now_utc: datetime, *, generation: int,
            predecessor: dict[str, Any] | None) -> dict[str, Any]:
    if (not run_id.isdigit() or not 1 <= len(run_id) <= 18
            or generation not in (1, 2)
            or (generation == 1) != (predecessor is None)):
        raise ValueError("P046_B3B_INVALID_SYNTHETIC_RUN")
    return {
        "schema": VERSION,
        "data_kind": SYNTHETIC_SOURCE,
        "provider": "NONE_SYNTHETIC",
        "symbol": "NONE_SYNTHETIC",
        "side": "SYNTHETIC",
        "interval": "SYNTHETIC",
        "timezone": "UTC",
        "fixture_created_utc": now_utc.isoformat(),
        "run_id": run_id,
        "generation": generation,
        "previous_sha256": digest(predecessor) if predecessor else None,
        "synthetic_values": (
            [100, 200, 300] if generation == 1 else [100, 201, 301]
        ),
        "approval_to_trade": False,
        "broker_orders": 0,
    }


def execute_two_synthetic_writes(
    port: SyntheticPort, *, now_utc: datetime,
    run_id: str,
) -> StagingReceipt:
    """Crash/retry safe same-run two-write synthetic-only test.

    A repeated GitHub workflow attempt may share the same run ID; it
    verifies an existing first write or an already committed second write,
    without adding a new Drive file or replacing a foreign fixture.
    """
    _utc(now_utc)
    if not run_id.isdigit() or not 1 <= len(run_id) <= 18:
        raise ValueError("P046_B3B_INVALID_RUN_ID")
    existing = port.load()
    if existing is not None:
        validate_synthetic(existing,now_utc=now_utc)
        if existing["run_id"]!=run_id:
            raise ValueError("P046_B3B_STAGING_RUN_ID_CONFLICT")
        original_time = datetime.fromisoformat(existing["fixture_created_utc"])
        first = _sample(
            run_id,original_time,generation=1,predecessor=None,
        )
        second = _sample(
            run_id,original_time,generation=2,predecessor=first,
        )
        if existing == second:
            return StagingReceipt(
                "SYNTHETIC_REPLAY_ALREADY_COMPLETED",
                digest(first),digest(second),0,0,True,True,
            )
        if existing != first:
            raise ValueError("P046_B3B_SYNTHETIC_PREDECESSOR_TAMPER")
        created = 0
        status = "SYNTHETIC_RESUMED_AFTER_FIRST_WRITE"
    else:
        first = _sample(run_id,now_utc,generation=1,predecessor=None)
        second = _sample(run_id,now_utc,generation=2,predecessor=first)
        port.write(expected=None,replacement=first)
        if port.load()!=first:
            raise ValueError("P046_B3B_FIRST_SYNTHETIC_READBACK_FAILED")
        created = 1
        status = "SYNTHETIC_TWO_WRITES_VERIFIED"
    validate_synthetic(second,now_utc=now_utc)
    if port.load()!=first:
        raise ValueError("P046_B3B_STAGING_CHANGED_BETWEEN_UPDATES")
    port.write(expected=first,replacement=second)
    if port.load()!=second:
        raise ValueError("P046_B3B_SECOND_SYNTHETIC_READBACK_FAILED")
    return StagingReceipt(
        status=status,
        first_sha256=digest(first),
        second_sha256=digest(second),
        file_creates_expected=created,
        same_file_in_place_updates_expected=1,
        observed_first_readback=True,
        observed_second_readback=True,
    )
