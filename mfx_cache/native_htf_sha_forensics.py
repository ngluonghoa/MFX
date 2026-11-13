"""Source-native SHA forensic witness, strictly within the existing audit I/O.

Only use the read-through witness after audit_native_archive() completes.
Rows are capped to the most recent 16 typed sealed candles in memory.
No new Drive request, price call, Drive write, log of OHLC or quarantine bypass.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from decimal import Decimal, InvalidOperation
from typing import Any

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import RECENT_INDEX_LIMIT, check_native_manifest
from tools.mfx_native_htf_drive_seal import NativeArchiveState
from mfx_cache.native_htf_revision_diagnostics import (
    QUARANTINE_CODES, summarize_native_revision_quarantine,
)

OHLC = ("open", "high", "low", "close")
METADATA = tuple(f.name for f in fields(NativeFXBar) if f.name not in OHLC)


class NativeAuditReadThroughWitness:
    """The audited archive's ORIGINAL list/read calls, mirrored in memory.

    The wrapper intentionally has no store write method. It MUST only be
    passed to audit_native_archive before calling verified_recent_rows().
    """

    def __init__(self, store: Any) -> None:
        if not callable(getattr(store, "list_names", None)) or not callable(
                getattr(store, "read", None)):
            raise ValueError("P059_FORENSIC_STORE_NOT_READ_ONLY_CONTRACT")
        self.__store = store
        self.__recent_rows: tuple[dict[str, Any], ...] = ()

    def list_names(self, bucket: str) -> tuple[str, ...]:
        return self.__store.list_names(bucket)

    def read(self, bucket: str, name: str) -> dict[str, Any]:
        body = self.__store.read(bucket, name)
        if (bucket == "chunk" and type(body) is dict
                and type(body.get("bars")) is list):
            # Retain exact on-Drive fields, not a normalized reconstruction.
            tail = body["bars"][-RECENT_INDEX_LIMIT:]
            self.__recent_rows = (
                self.__recent_rows + tuple(deepcopy(row) for row in tail)
            )[-RECENT_INDEX_LIMIT:]
        return body

    def verified_recent_rows(
        self, state: NativeArchiveState, *, symbol: str, interval: str,
    ) -> tuple[NativeFXBar, ...]:
        """Verify rows against last SHA-validated manifest returned by audit.

        The caller must have executed audit_native_archive(self) successfully.
        A partial/failed audit is never sufficient source attestation.
        """
        if type(state) is not NativeArchiveState:
            raise ValueError("P059_FORENSIC_FULL_SHA_AUDIT_REQUIRED")
        manifest = state.last_manifest
        if manifest is None:
            if state.manifest_count or state.chunk_count or self.__recent_rows:
                raise ValueError("P059_FORENSIC_EMPTY_ARCHIVE_INCONSISTENT")
            return ()
        check_native_manifest(manifest, symbol=symbol, interval=interval,
                              zone="Australia/Sydney")
        if not 1 <= len(self.__recent_rows) <= RECENT_INDEX_LIMIT:
            raise ValueError("P059_FORENSIC_RECENT_RAW_INDEX_MISSING")
        try:
            rows = tuple(NativeFXBar(**row) for row in self.__recent_rows)
        except (TypeError, KeyError, ValueError) as exc:
            raise ValueError("P059_FORENSIC_NATIVE_ROW_INVALID") from exc
        expected = tuple((x["label"], x["sha256"])
                         for x in manifest["recent_native_bar_index"])
        actual = tuple((row.native_open_label, row.sha256()) for row in rows)
        if (actual != expected
                or any(row.symbol != symbol or row.interval != interval
                       or row.exchange_timezone != "Australia/Sydney"
                       for row in rows)):
            raise ValueError("P059_FORENSIC_STORED_RAW_SHA_NOT_ATTESTED")
        return rows


def classify_stored_vs_refetched_native(
    *, previous: dict[str, Any],
    old_verified: tuple[NativeFXBar, ...],
    fresh: NativeFXBatch,
    quarantine_error: str,
) -> dict[str, Any]:
    """Count true numeric vs lexical/provenance drift, without raw values.

    A difference establishes stored-versus-refetched evidence only. It does
    not authorize vendor restatement policy, source entitlements or trades.
    """
    if (quarantine_error not in QUARANTINE_CODES
            or type(old_verified) is not tuple
            or any(type(row) is not NativeFXBar for row in old_verified)):
        raise ValueError("P059_FORENSIC_INPUT_SCOPE_DENIED")
    diagnostic = summarize_native_revision_quarantine(
        previous=previous, batch=fresh, error_code=quarantine_error)
    index = previous["recent_native_bar_index"]
    if tuple((row.native_open_label, row.sha256())
             for row in old_verified) != tuple(
                 (x["label"], x["sha256"]) for x in index):
        raise ValueError("P059_FORENSIC_OLD_ROWS_NOT_SHA_ATTESTED")

    returned = {row.native_open_label: row for row in fresh.closed_bars}
    categories = {
        "numeric_ohlc_changed": 0,
        "equal_numeric_text_only": 0,
        "equal_numeric_metadata_only": 0,
        "equal_numeric_text_and_metadata": 0,
    }
    changed = 0
    for old in old_verified:
        new = returned.get(old.native_open_label)
        if new is None or old.sha256() == new.sha256():
            continue
        changed += 1
        try:
            old_numeric = tuple(Decimal(getattr(old, k)) for k in OHLC)
            new_numeric = tuple(Decimal(getattr(new, k)) for k in OHLC)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("P059_FORENSIC_PRICE_COMPARISON_INVALID") from exc
        if (any(not n.is_finite() or n <= 0 for n in old_numeric + new_numeric)
                or old.symbol != new.symbol
                or old.interval != new.interval):
            raise ValueError("P059_FORENSIC_SOURCE_SCOPE_INVALID")
        numeric_changed = old_numeric != new_numeric
        text_changed = any(getattr(old, k) != getattr(new, k) for k in OHLC)
        metadata_changed = any(
            getattr(old, k) != getattr(new, k) for k in METADATA)
        if numeric_changed:
            categories["numeric_ohlc_changed"] += 1
        elif text_changed and metadata_changed:
            categories["equal_numeric_text_and_metadata"] += 1
        elif text_changed:
            categories["equal_numeric_text_only"] += 1
        elif metadata_changed:
            categories["equal_numeric_metadata_only"] += 1
        else:
            raise ValueError("P059_FORENSIC_UNEXPLAINED_SHA_MISMATCH")
    if changed != diagnostic["overlap_sha_changed_count"]:
        raise ValueError("P059_FORENSIC_SHA_MISMATCH_COUNT_DRIFT")
    if sum(categories.values()) != changed:
        raise ValueError("P059_FORENSIC_CLASS_COUNT_DRIFT")

    return {
        **diagnostic,
        "full_sha_audited_old_raw_overlap_compared": True,
        **{name + "_count": n for name, n in categories.items()},
        "stored_vs_refetched_numeric_ohlc_difference_observed": (
            categories["numeric_ohlc_changed"] > 0),
        "source_vendor_revision_cause_independently_attributed": False,
        "source_mutation_or_quarantine_override_authorized": False,
        "raw_old_or_new_price_in_output": False,
        "additional_vendor_calls": 0,
        "additional_drive_gets": 0,
    }
