"""A04/P0.59/P0.64 — gated hourly + manual native EUR/USD H4/D1 writer.

P0.64 schedules the previously manual-tested P0.59 source-native incremental
commit every UTC hour at :25, without changing its data integrity or quota
contracts. Both modes preflight both archives BEFORE provider calls; skip
intervals without newly eligible closed slots. No broker or BUY/SELL.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta, date
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
import json
import os
from typing import Any

from mfx_cache.native_fx_htf import parse_native_forex
from mfx_cache.td_m5_codec import digest
from mfx_cache.native_d1_fresh_epoch import (
    PrivateD1FreshEpochStore, audit_fresh_epoch,
    plan_fresh_epoch_fetch, plan_fresh_epoch_seal, commit_fresh_epoch,
)
from mfx_cache.native_htf_archive import plan_native_sealed, verify_native_sealed
from mfx_cache.native_htf_revision_diagnostics import (
    QUARANTINE_CODES, summarize_native_revision_quarantine,
)
from mfx_cache.native_d1_quarantine_stage import (
    PrivateD1QuarantineStore, stage_d1_quarantine_snapshot,
)
from mfx_cache.native_htf_sha_forensics import (
    NativeAuditReadThroughWitness, classify_stored_vs_refetched_native,
)
from mfx_cache.native_htf_incremental import (
    NATIVE_INTERVALS, SYMBOL, IncrementalFetchPlan, plan_native_fetch,
    validate_incremental_source,
)
from tools.mfx_native_htf_drive_seal import (
    PrivateNativeDriveStore, audit_native_archive, commit_native_batch,
    native_append_slots_remaining,
)
from tools.run_a04_p45_cloud_twelve_data_cache import _settings, _session
from tools.run_a04_p46_cloud_batch_cache import quota_headroom
from tools.run_mfx_native_htf_probe import _usage, _read_payload, TIME_SERIES_URL


def summarize_incremental_receipts(
    receipts: list[dict[str,Any]],
) -> dict[str,Any]:
    """Separate actual immutable writes from vendor-side stale responses.

    A source request and a successful SHA audit do NOT establish that a
    new candle was persisted. Reject impossible storage receipts rather
    than reporting a misleading 'COMMITTED' status.
    """
    if type(receipts) is not list or not receipts:
        raise ValueError("P060_NATIVE_RECEIPTS_REQUIRED")
    accepted = {
        "NO_NEW_CLOSED_NATIVE_BAR",
        "NATIVE_BATCH_COMMITTED",
        "RECOVERED_ORPHAN_AND_COMMITTED",
    }
    seen: set[str] = set()
    committed: list[str] = []
    vendor_stale: list[str] = []
    new_total = 0
    for r in receipts:
        if (type(r) is not dict
                or r.get("status") not in accepted
                or r.get("symbol") != SYMBOL
                or r.get("interval") not in NATIVE_INTERVALS
                or r["interval"] in seen
                or type(r.get("newly_closed_native_bars")) is not int
                or r["newly_closed_native_bars"] < 0
                or type(r.get("drive_objects_created_max")) is not int
                or not 0 <= r["drive_objects_created_max"] <= 2
                or r.get("broker_orders") != 0):
            raise ValueError("P060_NATIVE_INVALID_COMMIT_RECEIPT")
        seen.add(r["interval"])
        n = r["newly_closed_native_bars"]
        if r["status"] == "NO_NEW_CLOSED_NATIVE_BAR":
            if n != 0 or r["drive_objects_created_max"] != 0:
                raise ValueError("P060_NATIVE_STALE_RECEIPT_HAS_WRITES")
            vendor_stale.append(r["interval"])
        else:
            if n < 1 or r["drive_objects_created_max"] not in (1,2):
                raise ValueError("P060_NATIVE_COMMIT_RECEIPT_NO_NEW_BARS")
            committed.append(r["interval"])
        new_total += n
    return {
        "status": ("NATIVE_INCREMENTAL_NEW_BARS_COMMITTED" if new_total
                   else "NATIVE_INCREMENTAL_PROVIDER_STALE_NO_NEW_BAR"),
        "total_newly_closed_native_bars": new_total,
        "intervals_with_new_native_bars": committed,
        "intervals_provider_stale_no_new_bar": vendor_stale,
    }


# P0.168 is an explicit cross-TF *isolation* rule, NOT a D1 revision
# clearance. If the exact documented native D1 source discrepancy persists,
# a separately validated H4 may append while D1 remains unwritten/NO_SIGNAL.
# Unknown incidents, missing SHA custody, or unvalidated H4 always fail
# before any scoped append.
KNOWN_D1_INCIDENT_LABEL = "2026-11-11"


def _confirmed_known_d1_hold(diagnostic: Any) -> bool:
    """Requires already full-SHA-audited OLD D1 and exact refetched OHLC drift.

    SHA equality or a matching incident label alone NEVER authorizes a write.
    This only permits the other, independently full-validated H4 interval.
    """
    if type(diagnostic) is not dict:
        return False
    return (
        diagnostic.get("interval") == "1day"
        and diagnostic.get("first_changed_label") == KNOWN_D1_INCIDENT_LABEL
        and diagnostic.get("last_changed_label") == KNOWN_D1_INCIDENT_LABEL
        and diagnostic.get("quarantine_reason")
            == "P059_SOURCE_NATIVE_REVISION_QUARANTINE"
        and diagnostic.get("numeric_ohlc_changed_count") == 1
        and diagnostic.get("overlap_sha_changed_count") == 1
        and diagnostic.get("overlap_sha_unchanged_count") == 15
        and diagnostic.get("overlap_labels_missing_count") == 0
        and diagnostic.get("previous_sha_index_count") == 16
        and diagnostic.get("full_sha_audited_old_raw_overlap_compared") is True
        and diagnostic.get("stored_vs_refetched_numeric_ohlc_difference_observed")
            is True
        and diagnostic.get("source_vendor_revision_cause_independently_attributed")
            is False
        and diagnostic.get("source_mutation_or_quarantine_override_authorized")
            is False
        and diagnostic.get("drive_writes") == 0
        and diagnostic.get("additional_vendor_calls") == 0
        and diagnostic.get("additional_drive_gets") == 0
        and diagnostic.get("broker_orders") == 0
    )


def main() -> None:
    if (os.environ.get("MFX_REAL_CACHE_ENABLED") != "true"
            or os.environ.get("MFX_V2_BATCH_CACHE_ACCEPTED") != "true"
            or os.environ.get("MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED") != "true"
            or os.environ.get("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED") != "true"):
        print("MFX_A04_P59_INCREMENTAL_DISABLED_EXPLICIT_FOUR_GATE")
        return

    # GitHub injects a protected event name; never report a manual
    # acceptance marker for an unattended hourly scheduled run.
    scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    owner_rebase_d1 = os.environ.get("MFX_D1_OWNER_REBASE_20261111") == "true"
    key, auth, cap = _settings()
    now = datetime.now(timezone.utc)
    session = _session(auth)
    archives: list[tuple[str, Any, Any, Any]] = []
    sha_verified_recent: dict[str, Any] = {}
    fresh_d1_store: Any = None
    fresh_d1_state: Any = None
    fresh_d1_origin: str | None = None
    for interval in NATIVE_INTERVALS:
        store = PrivateNativeDriveStore(session,symbol=SYMBOL,interval=interval)
        # Mirror the ALREADY scheduled full native archive SHA reads in
        # bounded memory. No additional Drive request, vendor price call or
        # change to original writer's commit store/append semantics.
        if type(store) is PrivateNativeDriveStore:
            # Real, pinned GitHub OAuth Drive adapter only. Tests that
            # deliberately replace this store with scripted doubles retain
            # the exact original P0.59 auditor API/call sequence.
            witness = NativeAuditReadThroughWitness(store)
            archive = audit_native_archive(
                witness, symbol=SYMBOL, interval=interval)
            sha_verified_recent[interval] = witness.verified_recent_rows(
                archive, symbol=SYMBOL, interval=interval)
        else:
            archive = audit_native_archive(
                store, symbol=SYMBOL, interval=interval)
        if archive.uncommitted_chunk_names:
            # One orphan might be recoverable in the legacy writer, but
            # this *incremental* approval does not allow ambiguous resume.
            raise ValueError("P059_ORPHAN_REQUIRES_SEPARATE_RECOVERY")
        if interval == "1day" and owner_rebase_d1:
            # Old SHA archive stays strictly read-only. Only the separate
            # owner-requested epoch may be fed from a NEW provider request.
            if archive.last_manifest is None:
                raise ValueError("P171_ORIGINAL_D1_ARCHIVE_REQUIRED")
            fresh_d1_origin = digest(archive.last_manifest)
            fresh_d1_store = PrivateD1FreshEpochStore(session)
            fresh_d1_state = audit_fresh_epoch(
                fresh_d1_store, origin_v1_sha=fresh_d1_origin)
            req = plan_fresh_epoch_fetch(state=fresh_d1_state, now_utc=now)
            active_last = (fresh_d1_state.last_manifest["last_native_open_label"]
                           if fresh_d1_state.last_manifest else None)
            expected = (now-timedelta(minutes=2,seconds=15)).astimezone(
                ZoneInfo("Australia/Sydney")).date()-timedelta(days=1)
            plan = IncrementalFetchPlan(
                symbol=SYMBOL,interval=interval,
                status=("P171_D1_FRESH_EPOCH_REFETCH_REQUIRED" if req
                        else "NO_NEW_CLOSED_SLOT_NO_VENDOR_CALL"),
                request=req,last_native_open_label=active_last,
                latest_expected_closed_label=expected.isoformat(),
                calendar_slots_behind=(
                    (expected-date.fromisoformat(active_last)).days
                    if active_last else 0),
                overlap_bar_count=(
                    len(fresh_d1_state.last_manifest["recent_native_bar_index"])
                    if fresh_d1_state.last_manifest else 0),
                provider_requests_planned=1 if req else 0,
            )
        else:
            plan = plan_native_fetch(
                interval=interval, previous=archive.last_manifest, now_utc=now)
        archives.append((interval,store,archive,plan))
    # Audit BOTH scopes before vendor usage/price calls. Capacity is a
    # hard bounded SHA-auditor constraint, not available Drive quota.
    # Fail all due intervals before spending credits if either cannot
    # safely accept one more immutable Chunk+Manifest pair.
    for _,_,archive,plan in archives:
        if (plan.provider_requests_planned
                and native_append_slots_remaining(archive) < 1):
            raise ValueError("P063_NATIVE_CAPACITY_EXHAUSTED_NO_VENDOR_CALL")
    due = [a for a in archives if a[3].provider_requests_planned]
    if not due:
        print("MFX_A04_P59_NATIVE_NO_NEW_CLOSED_SLOTS_ZERO_VENDOR_CALLS")
        print(json.dumps({
            "status":"NO_NATIVE_CLOSED_SLOTS_DUE",
            "provider_price_requests":0,"provider_usage_requests":0,
            "drive_writes":0,"broker_orders":0,
            "automatic_native_schedule_activated":scheduled,
            "execution_mode":"hourly_schedule" if scheduled else "manual",
        },sort_keys=True))
        return

    # The usage API itself consumes credits. Conservatively reserve budget
    # for all price calls AND up to one usage call per selected interval.
    used,limit = _usage(key)
    ok,threshold = quota_headroom(used,limit,cap)
    if not ok or used+(2*len(due))+1 > threshold:
        print("MFX_A04_P59_NATIVE_QUOTA_NO_PRICE_REQUESTS")
        print(json.dumps({
            "status":"NOT_EXECUTED_INSUFFICIENT_QUOTA_HEADROOM",
            "price_requests":0,"drive_writes":0,"broker_orders":0,
            "automatic_native_schedule_activated":scheduled,
            "execution_mode":"hourly_schedule" if scheduled else "manual",
        },sort_keys=True))
        return

    prepared: list[tuple[str,Any,Any,Any]] = []
    quarantined_d1: dict[str, Any] | None = None
    quarantined_d1_source: tuple[Any,Any,Any] | None = None
    new_epoch_d1_batch: Any = None
    for idx, (interval,store,archive,plan) in enumerate(due):
        if idx:
            current,maximum = _usage(key)
            accepted,limit_now = quota_headroom(current,maximum,cap)
            if not accepted or current+2 > limit_now:
                raise ValueError("P059_QUOTA_RECHECK_FAILS_BEFORE_ANY_DRIVE_WRITE")
        assert plan.request is not None
        envelope = _read_payload(
            TIME_SERIES_URL,{**plan.request,"apikey":key})
        batch = parse_native_forex(
            envelope,symbol=SYMBOL,interval=interval,now_utc=now,
            requested_timezone="UTC" if interval=="4h" else None)
        if interval=="1day" and owner_rebase_d1:
            if fresh_d1_state is None or fresh_d1_origin is None:
                raise ValueError("P171_MISSING_REBASE_SOURCE_AUDIT")
            plan_fresh_epoch_seal(
                batch,state=fresh_d1_state,
                origin_v1_sha=fresh_d1_origin,now_utc=now)
            new_epoch_d1_batch = batch
            continue
        try:
            validate_incremental_source(
                batch, previous=archive.last_manifest, plan=plan)
        except ValueError as error:
            # Reuse the ALREADY fetched provider batch and SHA-only index
            # to explain a quarantine. No extra vendor/Drive request, no
            # price/secret logging, no trading and no override of P0.59.
            diagnostic: dict[str, Any] | None = None
            if str(error) in QUARANTINE_CODES and archive.last_manifest is not None:
                try:
                    if interval in sha_verified_recent:
                        diagnostic = classify_stored_vs_refetched_native(
                            previous=archive.last_manifest,
                            old_verified=sha_verified_recent[interval],
                            fresh=batch, quarantine_error=str(error),
                        )
                    else:
                        # Scripted/legacy store doubles never claim real
                        # previous raw source forensic custody.
                        diagnostic = summarize_native_revision_quarantine(
                            previous=archive.last_manifest, batch=batch,
                            error_code=str(error),
                        )
                except (KeyError, TypeError, ValueError):
                    print("MFX_P059_NATIVE_OVERLAP_DIAGNOSTIC_UNAVAILABLE_FAIL_CLOSED")
                else:
                    print("MFX_P059_NATIVE_OVERLAP_QUARANTINED_NO_DRIVE_WRITE")
                    if interval in sha_verified_recent:
                        print("MFX_P059_NATIVE_OVERLAP_FORENSICS_NO_DRIVE_WRITE")
                    print(json.dumps(diagnostic, sort_keys=True))
            # P0.168: only this documented, independently old-SHA-verified
            # D1 incident can isolate the OTHER native TF (H4). The normal
            # all-or-nothing source quarantine is unchanged for every other
            # failure, including forged metadata or another D1 correction.
            # Never authorize D1 writes, D1 source promotion or signal.
            if (interval == "1day"
                    and str(error) == "P059_SOURCE_NATIVE_REVISION_QUARANTINE"
                    and "1day" in sha_verified_recent
                    and _confirmed_known_d1_hold(diagnostic)
                    and (not prepared or (
                        len(prepared) == 1
                        and prepared[0][0] == "4h"
                        and plan_native_sealed(
                            prepared[0][1],
                            previous=prepared[0][3].last_manifest
                        ) is not None))):
                quarantined_d1 = diagnostic
                quarantined_d1_source = (
                    archive.last_manifest, sha_verified_recent["1day"],
                    batch,
                )
                continue
            raise
        proposal = plan_native_sealed(batch,previous=archive.last_manifest)
        if proposal is not None:
            verify_native_sealed(proposal,previous=archive.last_manifest)
        prepared.append((interval,batch,store,archive))

    # Second preflight protects against provider request delays. In the
    # isolated branch, audit BOTH native histories again before touching H4:
    # even an external D1 change must stop an unrelated H4 append.
    if owner_rebase_d1:
        to_reaudit = [(interval,store,archive)
                      for interval,store,archive,_ in archives]
    elif quarantined_d1 is not None:
        to_reaudit = [
            (interval,store,archive)
            for interval,store,archive,_ in archives
        ]
    else:
        # P0.59's original tuples are (interval,batch,store,archive).
        # Preserve the original normal path and its existing regression QA.
        to_reaudit = [
            (interval,store,archive)
            for interval,_,store,archive in prepared
        ]
    for interval,store,archive in to_reaudit:
        state = audit_native_archive(
            store,symbol=SYMBOL,interval=interval)
        if state != archive:
            raise ValueError("P059_NATIVE_ARCHIVE_CHANGED_DURING_FETCH")

    if quarantined_d1 is not None:
        # The fresh D1 response was ALREADY fetched and independently
        # compared against the full-SHA-attested original. Preserve its raw
        # bytes in a disjoint, SHA-addressed quarantine-only namespace.
        # This is a RUNNER observation, NOT a publisher first-known stamp.
        if quarantined_d1_source is None:
            raise ValueError("P169_NO_SHA_AUDITED_D1_SOURCE_TO_STAGE")
        original, old_sha_rows, fresh = quarantined_d1_source
        staging = stage_d1_quarantine_snapshot(
            PrivateD1QuarantineStore(session), previous=original,
            sha_verified_recent=old_sha_rows, refetched=fresh,
            observed_at_utc=now,
        )
        if (staging["d1_canonical_writes"] != 0
                or staging["may_publish_buy_sell"] is not False):
            raise ValueError("P169_D1_QUARANTINE_AUTHORITY_DRIFT")
        # Existing independent H4 path can still append with the ORIGINAL
        # immutable 2-object readback writer; no H4 vendor-call increase.
        h4_summary: dict[str, Any] = {
            "status": "NO_NEW_CLOSED_H4_SLOT",
            "total_newly_closed_native_bars": 0,
            "h4_drive_objects_created_max": 0,
            "h4_newly_closed_bars": 0,
        }
        if prepared:
            h4_tf,h4_batch,h4_store,_ = prepared[0]
            if h4_tf != "4h":
                raise ValueError("P168_H4_ISOLATION_SCOPE_DENIED")
            h4_receipt = asdict(commit_native_batch(h4_store,h4_batch))
            summary = summarize_incremental_receipts([h4_receipt])
            h4_summary = {
                **summary,
                "h4_drive_objects_created_max":
                    h4_receipt["drive_objects_created_max"],
                "h4_newly_closed_bars":
                    h4_receipt["newly_closed_native_bars"],
            }
        print("MFX_P169_D1_QUARANTINE_OBSERVATION_SHA_READBACK")
        print("MFX_P168_H4_ISOLATED_D1_STILL_QUARANTINED_NONZERO")
        print(json.dumps({
            **h4_summary,
            "d1_quarantine": staging,
            "source_d1_status": "P059_SOURCE_NATIVE_REVISION_QUARANTINE",
            "source_d1_incident": KNOWN_D1_INCIDENT_LABEL,
            "d1_drive_writes": 0,
            "source_numeric_signals_approved": False,
            "no_broker_execution": True,
            "h4_append_does_not_clear_d1_hold": True,
            "automatic_native_schedule_activated": scheduled,
            "execution_mode": "hourly_schedule" if scheduled else "manual",
        }, sort_keys=True))
        # KEEP THE SCHEDULED JOB RED until D1 is independently resolved:
        # separate observations never authorize canonical D1 or signals.
        raise ValueError("P059_SOURCE_NATIVE_REVISION_QUARANTINE")

    receipts = [asdict(commit_native_batch(store,batch))
                for _,batch,store,_ in prepared]
    summary = summarize_incremental_receipts(receipts)
    print("MFX_A04_P64_HOURLY_NATIVE_INCREMENTAL_SHA_READBACK_PASS"
          if scheduled
          else "MFX_A04_P59_NATIVE_INCREMENTAL_MANUAL_SHA_READBACK_PASS")
    print(json.dumps({
        **summary,
        "results":receipts,"source":"TWELVE_DATA_COMPOSITE_MID",
        "provider_price_requests":len(due),
        "provider_usage_requests":len(due),
        "requested_outputsize_by_interval":{
            interval:int(plan.request["outputsize"])
            for interval,_,_,plan in due if plan.request is not None},
        "intervals_skipped_no_new_closed_slot":[
            interval for interval,_,_,plan in archives
            if plan.provider_requests_planned == 0],
        "m5_cache_modified":False,"broker_orders":0,
        "source_numeric_signals_approved":False,
        "automatic_native_schedule_activated":scheduled,
        "execution_mode":"hourly_schedule" if scheduled else "manual",
    },sort_keys=True))


if __name__ == "__main__":
    main()
