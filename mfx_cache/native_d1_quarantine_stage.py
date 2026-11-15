"""P0.169: append-only isolated D1 refetch *observations*, never canonical D1.

Reuses the existing authorized GitHub hourly source fetch/OAuth Drive folders.
Does NOT attest publisher first-known, source correctness, real data rights,
trades, or any permissions for SIGNAL. Original native and M5 archives
are not readable/writable through the quarantine-only object prefix.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import check_native_manifest
from mfx_cache.native_htf_revision_candidate import (
    draft_d1_revision_candidate, validate_revision_candidate,
)
from mfx_cache.td_m5_codec import digest
from tools.mfx_native_htf_drive_seal import PrivateNativeDriveStore
from tools.run_a04_p45_cloud_twelve_data_cache import CHUNK_FOLDER

SCHEMA = "MFX_P169_QUARANTINED_D1_SOURCE_OBSERVATION_V1"
PREFIX = "MFX_P169_EURUSD_D1_QUARANTINE_V1_chunk_"
SOURCE = ("EUR/USD", "1day", "Australia/Sydney")
MAX_OBSERVATIONS = 256

RECORD_KEYS = frozenset({
    "schema", "state", "observed_at_runner_utc",
    "observation_time_quality", "original_manifest_sha256",
    "original_incident_label", "source_batch_sha256",
    "source_batch", "candidate_receipt", "observation_identity_sha256",
    "source_licence_approved", "publisher_first_known_verified",
    "owner_canonical_revision_approved", "may_overwrite_canonical",
    "may_publish_buy_sell", "may_trade", "broker_orders",
    "record_sha256",
})


class PrivateD1QuarantineStore(PrivateNativeDriveStore):
    """Single-purpose namespace within existing private CHUNK folder.

    The native H4/D1 and M5 name prefixes never match PREFIX; inherited
    Drive list/read/put-if-absent enforces name scope and content readback.
    No new workflow, Drive OAuth grant, or separate source request.
    """

    def __init__(self, session: Any) -> None:
        super().__init__(session, symbol="EUR/USD", interval="1day")

    def _bucket(self, bucket: str) -> tuple[str, str]:
        if bucket != "chunk":
            raise ValueError("P169_QUARANTINE_CHUNK_ONLY")
        return CHUNK_FOLDER, PREFIX


def _source_payload(batch: NativeFXBatch) -> dict[str, Any]:
    if (type(batch) is not NativeFXBatch
            or (batch.symbol, batch.interval, batch.exchange_timezone)
            != SOURCE
            or batch.time_reference != "EXCHANGE_LOCAL_SESSION_DATE"
            or batch.source != "TWELVE_DATA_COMPOSITE_MID"
            or batch.is_provider_native is not True
            or batch.vendor_calls_made_by_parser != 0
            or batch.google_drive_writes != 0
            or batch.confirmed_buy_sell_signals != 0
            or batch.broker_orders != 0):
        raise ValueError("P169_NATIVE_D1_SCOPE_OR_AUTHORITY_DENIED")
    body = asdict(batch)
    body["closed_bars"] = [asdict(x) for x in batch.closed_bars]
    return body


def _utc(value: Any) -> datetime:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P169_EXACT_UTC_RUNNER_OBSERVATION_REQUIRED")
    return value


def _filename_identity(
    original_sha: str, batch_sha: str, candidate_bar_sha: str,
) -> str:
    return digest({
        "schema": SCHEMA,
        "original_manifest_sha256": original_sha,
        "source_batch_sha256": batch_sha,
        "candidate_bar_sha256": candidate_bar_sha,
    })


def build_d1_quarantine_observation(
    *, previous: dict[str, Any],
    sha_verified_recent: tuple[NativeFXBar, ...],
    refetched: NativeFXBatch, observed_at_utc: datetime,
) -> dict[str, Any]:
    """Construct content-addressed raw version without canonical approval."""
    _utc(observed_at_utc)
    candidate = draft_d1_revision_candidate(
        original_manifest=previous,
        sha_verified_recent=sha_verified_recent,
        refetched_batch=refetched,
        observed_at_utc=observed_at_utc,
    )
    raw = _source_payload(refetched)
    old_sha = digest(previous)
    batch_sha = digest(raw)
    identity = _filename_identity(
        old_sha, batch_sha, candidate["candidate_bar_sha256"])
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "state": "D1_QUARANTINED_UNADJUDICATED_NOT_CANONICAL",
        "observed_at_runner_utc": observed_at_utc.isoformat(),
        "observation_time_quality":
            "RUNNER_FETCH_TIME_NOT_INDEPENDENT_PUBLISHER_FIRST_KNOWN",
        "original_manifest_sha256": old_sha,
        "original_incident_label": "2026-11-11",
        "source_batch_sha256": batch_sha,
        "source_batch": raw,
        "candidate_receipt": candidate,
        "observation_identity_sha256": identity,
        "source_licence_approved": False,
        "publisher_first_known_verified": False,
        "owner_canonical_revision_approved": False,
        "may_overwrite_canonical": False,
        "may_publish_buy_sell": False,
        "may_trade": False,
        "broker_orders": 0,
    }
    body["record_sha256"] = digest(body)
    return validate_d1_quarantine_observation(body)


def validate_d1_quarantine_observation(value: Any) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != RECORD_KEYS:
        raise ValueError("P169_QUARANTINE_EXACT_RECORD_SCHEMA")
    if (value["schema"] != SCHEMA
            or value["state"] != "D1_QUARANTINED_UNADJUDICATED_NOT_CANONICAL"
            or value["observation_time_quality"] !=
                "RUNNER_FETCH_TIME_NOT_INDEPENDENT_PUBLISHER_FIRST_KNOWN"
            or value["original_incident_label"] != "2026-11-11"
            or any(value[k] is not False for k in (
                "source_licence_approved", "publisher_first_known_verified",
                "owner_canonical_revision_approved",
                "may_overwrite_canonical", "may_publish_buy_sell", "may_trade"))
            or type(value["broker_orders"]) is not int
            or value["broker_orders"] != 0):
        raise ValueError("P169_QUARANTINED_NOT_APPROVED")
    observed = value["observed_at_runner_utc"]
    if type(observed) is not str:
        raise ValueError("P169_EXACT_RUNNER_TIMESTAMP_REQUIRED")
    try:
        stamp = _utc(datetime.fromisoformat(observed))
    except ValueError as exc:
        raise ValueError("P169_EXACT_RUNNER_TIMESTAMP_REQUIRED") from exc
    if stamp.isoformat() != observed:
        raise ValueError("P169_EXACT_RUNNER_TIMESTAMP_REQUIRED")
    candidate = value["candidate_receipt"]
    validate_revision_candidate(candidate)
    if (candidate["original_manifest_sha256"]
            != value["original_manifest_sha256"]
            or candidate["native_open_label"] != "2026-11-11"
            or candidate["source_observation_time_utc"] != observed):
        raise ValueError("P169_CANDIDATE_MANIFEST_OR_CLOCK_DRIFT")
    raw = value["source_batch"]
    if type(raw) is not dict or type(raw.get("closed_bars")) is not list:
        raise ValueError("P169_QUARANTINE_SOURCE_BATCH_SHAPE")
    try:
        reconstructed = NativeFXBatch(**{
            **raw,
            "closed_bars": tuple(NativeFXBar(**r)
                                 for r in raw["closed_bars"]),
        })
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("P169_QUARANTINE_SOURCE_BATCH_INVALID") from exc
    if (_source_payload(reconstructed) != raw
            or digest(raw) != value["source_batch_sha256"]):
        raise ValueError("P169_QUARANTINE_SOURCE_PAYLOAD_SHA_DRIFT")
    by_label = {r.native_open_label:r for r in reconstructed.closed_bars}
    if (len(by_label) != len(reconstructed.closed_bars)
            or "2026-11-11" not in by_label
            or by_label["2026-11-11"].sha256()
                != candidate["candidate_bar_sha256"]):
        raise ValueError("P169_QUARANTINE_CANDIDATE_SOURCE_BAR_DRIFT")
    if (value["observation_identity_sha256"] != _filename_identity(
            value["original_manifest_sha256"],
            value["source_batch_sha256"], candidate["candidate_bar_sha256"])):
        raise ValueError("P169_QUARANTINE_IDENTITY_MISMATCH")
    if (digest({k:v for k,v in value.items() if k!="record_sha256"})
            != value["record_sha256"]):
        raise ValueError("P169_QUARANTINE_RECORD_SHA_MISMATCH")
    return value


def stage_d1_quarantine_snapshot(
    store: Any, *, previous: dict[str, Any],
    sha_verified_recent: tuple[NativeFXBar, ...],
    refetched: NativeFXBatch, observed_at_utc: datetime,
) -> dict[str, Any]:
    """At-most-one immutable raw snapshot per SHA-identical provider batch.

    The sidecar can NEVER be read by original native H4/D1 or M5 audits.
    Existing identical record reuses FIRST runner observation timestamp.
    """
    record = build_d1_quarantine_observation(
        previous=previous, sha_verified_recent=sha_verified_recent,
        refetched=refetched, observed_at_utc=observed_at_utc,
    )
    if (not callable(getattr(store,"list_names",None))
            or not callable(getattr(store,"read",None))
            or not callable(getattr(store,"put_if_absent",None))):
        raise ValueError("P169_APPEND_ONLY_QUARANTINE_STORE_REQUIRED")
    name = PREFIX + record["observation_identity_sha256"] + ".json"
    names = store.list_names("chunk")
    if type(names) is not tuple or any(
            type(x) is not str or not x.startswith(PREFIX)
            for x in names):
        raise ValueError("P169_QUARANTINE_INVALID_LISTING")
    if name in names:
        previous_record = validate_d1_quarantine_observation(
            store.read("chunk",name))
        if (previous_record["observation_identity_sha256"]
                != record["observation_identity_sha256"]
                or previous_record["source_batch"] != record["source_batch"]
                or previous_record["original_manifest_sha256"]
                    != record["original_manifest_sha256"]
                or previous_record["observed_at_runner_utc"]
                    > observed_at_utc.isoformat()):
            raise ValueError("P169_QUARANTINE_COLLISION_OR_CLOCK_ROLLBACK")
        return {
            "status": "D1_QUARANTINE_IDENTICAL_SOURCE_ALREADY_SEALED",
            "observations_created": 0,
            "closed_bars_custodied": len(refetched.closed_bars),
            "first_runner_observation_utc":
                previous_record["observed_at_runner_utc"],
            "d1_canonical_writes": 0,
            "may_publish_buy_sell": False,
        }
    if len(names) >= MAX_OBSERVATIONS:
        raise ValueError("P169_QUARANTINE_CAPACITY_REQUIRES_SAFE_EXPANSION")
    store.put_if_absent("chunk",name,record)
    if store.read("chunk",name) != record:
        raise ValueError("P169_QUARANTINE_WRITE_READBACK_MISMATCH")
    names_after = store.list_names("chunk")
    if names_after.count(name) != 1:
        raise ValueError("P169_QUARANTINE_POSTWRITE_NOT_SINGLETON")
    validate_d1_quarantine_observation(store.read("chunk",name))
    return {
        "status": "D1_QUARANTINE_NEW_SHA_SOURCE_SEALED",
        "observations_created": 1,
        "closed_bars_custodied": len(refetched.closed_bars),
        "first_runner_observation_utc": record["observed_at_runner_utc"],
        "d1_canonical_writes": 0,
        "may_publish_buy_sell": False,
    }
