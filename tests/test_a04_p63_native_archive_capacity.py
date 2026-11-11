"""A04/P0.63: native archive 256-cap preflight BEFORE price and writes.

Only pure hermetic Drive fakes, provider mocks and simulated UTC clock. No
network, broker, Google Drive write or real Twelve Data quota consumed.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any
from unittest import TestCase
from unittest.mock import patch
import copy
import os

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from tools.mfx_native_htf_drive_seal import (
    NativeArchiveState, audit_native_archive, commit_native_batch,
    native_append_slots_remaining,
)
from tools.run_mfx_native_htf_incremental_commit import main as writer_main
from tools.run_mfx_native_htf_incremental_preview import (
    preview_incremental_native_cache,
)

UTC=timezone.utc
SEAL="tools.mfx_native_htf_drive_seal"
WRITER="tools.run_mfx_native_htf_incremental_commit"


def batch(tf: str, labels: tuple[str,...]) -> NativeFXBatch:
    axis="UTC_INTRADAY_OPEN" if tf=="4h" else "EXCHANGE_LOCAL_SESSION_DATE"
    return NativeFXBatch(
        symbol="EUR/USD",interval=tf,
        exchange_timezone="Australia/Sydney",time_reference=axis,
        incomplete_excluded=0,
        closed_bars=tuple(NativeFXBar(
            symbol="EUR/USD",interval=tf,native_open_label=label,
            time_reference=axis,exchange_timezone="Australia/Sydney",
            exchange_timezone_origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT",
            open="1.1000",high="1.1040",low="1.0990",close="1.1030",
        ) for label in labels),
    )


H4=("2026-11-11 00:00:00","2026-11-11 04:00:00",
    "2026-11-11 08:00:00")
D1=("2026-11-10","2026-11-11","2026-11-12")


class DriveMemory:
    def __init__(self) -> None:
        self.data: dict[str,dict[str,dict[str,Any]]] = {
            "chunk":{},"manifest":{}}
        self.writes=0
    def list_names(self, kind: str) -> tuple[str,...]:
        return tuple(sorted(self.data[kind]))
    def read(self, kind: str, name: str) -> dict[str,Any]:
        return copy.deepcopy(self.data[kind][name])
    def put_if_absent(self, kind: str, name: str, item: dict[str,Any]) -> None:
        if name in self.data[kind]:
            if self.data[kind][name] != item:
                raise ValueError("DUPLICATE_NAME_CHANGED_CONTENT")
            return
        self.data[kind][name]=copy.deepcopy(item)
        self.writes+=1


def root_state(tf: str, label: str) -> NativeArchiveState:
    p=plan_native_sealed(batch(tf,(label,)),previous=None)
    assert p is not None
    return NativeArchiveState(
        last_manifest=p.manifest,latest_manifest_name=p.manifest_name,
        manifest_count=1,chunk_count=1,uncommitted_chunk_names=(),
    )


class P063NativeCapacityTests(TestCase):
    def test_01_pure_capacity_zero_at_256(self) -> None:
        s=NativeArchiveState(None,None,256,256,())
        self.assertEqual(native_append_slots_remaining(s),0)

    def test_02_pure_capacity_one_at_255(self) -> None:
        s=NativeArchiveState(None,None,255,255,())
        self.assertEqual(native_append_slots_remaining(s),1)

    def test_03_orphan_recovery_256th_chunk_allowed_255_manifests(self) -> None:
        s=NativeArchiveState(None,None,255,256,("existing_chunk",))
        self.assertEqual(native_append_slots_remaining(s),0)
        self.assertEqual(native_append_slots_remaining(
            s,reuse_existing_orphan=True),1)

    def test_04_invalid_negative_and_overlimit_counts_denied(self) -> None:
        for bad in (
            NativeArchiveState(None,None,-1,0,()),
            NativeArchiveState(None,None,0,257,()),
            NativeArchiveState(None,None,True,2,()),
        ):
            with self.subTest(bad=bad),self.assertRaisesRegex(
                    ValueError,"CAPACITY_STATE_INVALID"):
                native_append_slots_remaining(bad)

    def test_05_reuse_requires_exact_one_orphan(self) -> None:
        s=NativeArchiveState(None,None,1,1,())
        with self.assertRaisesRegex(ValueError,"CAPACITY_STATE_INVALID"):
            native_append_slots_remaining(s,reuse_existing_orphan=True)

    def test_06_root_at_cap_one_append_denied_without_half_write(self) -> None:
        drive=DriveMemory()
        with patch(f"{SEAL}.MAX_NATIVE_FILES",1):
            first=commit_native_batch(drive,batch("4h",H4[:1]))
            self.assertEqual(first.status,"NATIVE_BATCH_COMMITTED")
            old=copy.deepcopy(drive.data)
            with self.assertRaisesRegex(ValueError,
                                        "P063_NATIVE_ARCHIVE_AT_CAPACITY"):
                commit_native_batch(drive,batch("4h",H4[:2]))
            self.assertEqual(drive.data,old)
            self.assertEqual(drive.writes,2)
            self.assertEqual(
                audit_native_archive(drive,symbol="EUR/USD",
                                     interval="4h").manifest_count,1)

    def test_07_append_to_exact_last_capacity_slot_then_block(self) -> None:
        drive=DriveMemory()
        with patch(f"{SEAL}.MAX_NATIVE_FILES",2):
            commit_native_batch(drive,batch("4h",H4[:1]))
            second=commit_native_batch(drive,batch("4h",H4[:2]))
            self.assertEqual(second.status,"NATIVE_BATCH_COMMITTED")
            self.assertEqual(native_append_slots_remaining(
                audit_native_archive(drive,symbol="EUR/USD",
                                     interval="4h")),0)
            before=copy.deepcopy(drive.data)
            with self.assertRaisesRegex(ValueError,
                                        "P063_NATIVE_ARCHIVE_AT_CAPACITY"):
                commit_native_batch(drive,batch("4h",H4))
            self.assertEqual(drive.data,before)
            self.assertEqual(drive.writes,4)

    def test_08_recover_exact_last_chunk_orphan_without_second_chunk(self) -> None:
        drive=DriveMemory()
        with patch(f"{SEAL}.MAX_NATIVE_FILES",2):
            commit_native_batch(drive,batch("4h",H4[:1]))
            state=audit_native_archive(drive,symbol="EUR/USD",interval="4h")
            p=plan_native_sealed(batch("4h",H4[:2]),
                                 previous=state.last_manifest)
            assert p is not None
            drive.put_if_absent("chunk",p.chunk_name,p.chunk)
            before=drive.writes
            r=commit_native_batch(drive,batch("4h",H4[:2]))
            self.assertEqual(r.status,"RECOVERED_ORPHAN_AND_COMMITTED")
            self.assertEqual(r.drive_objects_created_max,1)
            self.assertEqual(drive.writes,before+1)
            self.assertEqual(native_append_slots_remaining(
                audit_native_archive(drive,symbol="EUR/USD",
                                     interval="4h")),0)

    def test_09_no_new_at_cap_remains_idempotent(self) -> None:
        drive=DriveMemory()
        with patch(f"{SEAL}.MAX_NATIVE_FILES",1):
            commit_native_batch(drive,batch("4h",H4[:1]))
            old=copy.deepcopy(drive.data)
            r=commit_native_batch(drive,batch("4h",H4[:1]))
            self.assertEqual(r.status,"NO_NEW_CLOSED_NATIVE_BAR")
            self.assertEqual(drive.data,old)
            self.assertEqual(drive.writes,2)

    def _writer_cap(self, state_h: NativeArchiveState,
                    state_d: NativeArchiveState,
                    now: datetime) -> str:
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
            "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED":"true",
        }),patch(f"{WRITER}._settings",return_value=("FAKE",{},400)),patch(
            f"{WRITER}._session",return_value="fake_session"),patch(
            f"{WRITER}.PrivateNativeDriveStore",
            side_effect=["fake_h4","fake_d1"]),patch(
            f"{WRITER}.audit_native_archive",
            side_effect=[state_h,state_d]),patch(
            f"{WRITER}._usage") as usage,patch(
            f"{WRITER}._read_payload") as vendor,patch(
            f"{WRITER}.commit_native_batch") as commit,patch(
            f"{WRITER}.datetime") as clock:
            clock.now.return_value=now
            with self.assertRaisesRegex(
                    ValueError,"P063_NATIVE_CAPACITY_EXHAUSTED_NO_VENDOR_CALL"):
                writer_main()
            usage.assert_not_called()
            vendor.assert_not_called()
            commit.assert_not_called()
        return "NO_VENDOR_NO_WRITE"

    def test_10_h4_full_due_blocks_even_vendor_usage_request(self) -> None:
        h=root_state("4h",H4[0])
        d=root_state("1day",D1[0])
        full=NativeArchiveState(h.last_manifest,h.latest_manifest_name,
                                256,256,())
        self.assertEqual(self._writer_cap(
            full,d,datetime(2026,11,11,9,15,tzinfo=UTC)),
            "NO_VENDOR_NO_WRITE")

    def test_11_d1_full_due_blocks_even_vendor_usage_request(self) -> None:
        h=root_state("4h",H4[2])
        d=root_state("1day",D1[0])
        full=NativeArchiveState(d.last_manifest,d.latest_manifest_name,
                                256,256,())
        self.assertEqual(self._writer_cap(
            h,full,datetime(2026,11,11,13,5,tzinfo=UTC)),
            "NO_VENDOR_NO_WRITE")

    def test_12_no_new_at_full_capacity_zero_vendor_no_failure(self) -> None:
        h=root_state("4h",H4[0])
        d=root_state("1day",D1[0])
        full_h=NativeArchiveState(h.last_manifest,h.latest_manifest_name,
                                  256,256,())
        full_d=NativeArchiveState(d.last_manifest,d.latest_manifest_name,
                                  256,256,())
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
            "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED":"true",
        }),patch(f"{WRITER}._settings",return_value=("FAKE",{},400)),patch(
            f"{WRITER}._session",return_value="fake_session"),patch(
            f"{WRITER}.PrivateNativeDriveStore",
            side_effect=["fake_h4","fake_d1"]),patch(
            f"{WRITER}.audit_native_archive",
            side_effect=[full_h,full_d]),patch(
            f"{WRITER}._usage") as usage,patch(
            f"{WRITER}._read_payload") as vendor,patch(
            f"{WRITER}.datetime") as clock:
            clock.now.return_value=datetime(2026,11,11,5,15,tzinfo=UTC)
            out=StringIO()
            with redirect_stdout(out):
                writer_main()
            usage.assert_not_called()
            vendor.assert_not_called()
            self.assertIn("NO_NEW_CLOSED_SLOTS_ZERO_VENDOR_CALLS",out.getvalue())

    def test_13_preview_full_due_reports_blocked_and_zero_vendor(self) -> None:
        h=DriveMemory()
        d=DriveMemory()
        with patch(f"{SEAL}.MAX_NATIVE_FILES",1):
            commit_native_batch(h,batch("4h",H4[:1]))
            commit_native_batch(d,batch("1day",D1[:1]))
            data=copy.deepcopy((h.data,d.data))
            receipt=preview_incremental_native_cache(
                {"4h":h,"1day":d},
                now_utc=datetime(2026,11,11,9,15,tzinfo=UTC))
            self.assertEqual(receipt["total_price_requests_if_approved"],0)
            self.assertEqual(receipt["real_provider_price_requests"],0)
            self.assertEqual(receipt["drive_writes"],0)
            self.assertEqual(receipt["intervals"][0]["decision"],
                         "NATIVE_ARCHIVE_CAPACITY_BLOCKED_NO_VENDOR_CALL")
            self.assertEqual(receipt["intervals"][0][
                "archive_append_slots_remaining"],0)
            self.assertIsNone(receipt["intervals"][0][
                "requested_outputsize_if_approved"])
            self.assertEqual((h.data,d.data),data)

    def test_14_preview_one_full_one_open_selective_price_advisory(self) -> None:
        h=DriveMemory()
        d=DriveMemory()
        with patch(f"{SEAL}.MAX_NATIVE_FILES",2):
            commit_native_batch(h,batch("4h",H4[:1]))
            commit_native_batch(h,batch("4h",H4[:2]))
            commit_native_batch(d,batch("1day",D1[:1]))
            receipt=preview_incremental_native_cache(
                {"4h":h,"1day":d},
                now_utc=datetime(2026,11,11,13,5,tzinfo=UTC))
            self.assertTrue(receipt["intervals"][0][
                "source_fetch_blocked_by_capacity"])
            self.assertFalse(receipt["intervals"][1][
                "source_fetch_blocked_by_capacity"])
            self.assertEqual(receipt["total_price_requests_if_approved"],1)
            self.assertEqual(receipt["real_provider_usage_requests"],0)
            self.assertEqual(receipt["drive_writes"],0)

    def test_15_current_real_archive_far_from_capacity(self) -> None:
        # Counts from independent owner Drive inventory immediately after
        # the first P0.59 successful LIVE H4 append. Not a live connector.
        h=NativeArchiveState(None,None,2,2,())
        d=NativeArchiveState(None,None,1,1,())
        self.assertEqual(native_append_slots_remaining(h),254)
        self.assertEqual(native_append_slots_remaining(d),255)

    def test_16_workflow_adds_hourly_four_way_gate(self) -> None:
        y=Path(".github/workflows/mfx-native-htf-incremental-commit.yml").read_text()
        self.assertIn("workflow_dispatch:",y)
        self.assertIn('cron: "25 * * * *"',y)
        self.assertIn("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED",y)

    def test_17_legacy_both_source_probed_but_zero_partial_drive_writes(self) -> None:
        # Unlike P059, legacy P055 probes both before authenticating Drive.
        # The new combined preflight must still prohibit an H4 write if
        # the second scope (D1) cannot accept another manifest.
        h=root_state("4h",H4[0])
        d=root_state("1day",D1[0])
        d_full=NativeArchiveState(d.last_manifest,d.latest_manifest_name,
                                   256,256,())
        target="tools.run_mfx_native_htf_drive_commit"
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
        }),patch(f"{target}._settings",return_value=("FAKE",{},400)),patch(
            f"{target}._usage",side_effect=[(1,400),(2,400)]),patch(
            f"{target}._probe_one",side_effect=[
                batch("4h",H4[:2]),batch("1day",D1[:2])]) as probe,patch(
            f"{target}._session",return_value="fake_session"),patch(
            f"{target}.PrivateNativeDriveStore",
            side_effect=["fake_h4","fake_d1"]),patch(
            f"{target}.audit_native_archive",
            side_effect=[h,d_full]),patch(
            f"{target}.commit_native_batch") as commit:
            from tools.run_mfx_native_htf_drive_commit import main
            with self.assertRaisesRegex(
                    ValueError,"P063_NATIVE_LEGACY_CAPACITY_NO_DRIVE_WRITES"):
                main()
            self.assertEqual(probe.call_count,2)
            commit.assert_not_called()


if __name__=="__main__":
    import unittest
    unittest.main()
