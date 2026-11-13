"""MFX v1 native SHA forensics with EXACT PrivateNativeDriveStore GET adapter.

No real network or credential: use existing v0.55 fake Google Drive wire.
Unlike the P0.145 synthetic ReadOnlyStore QA, these tests exercise the
production Drive list/media helper and exact writer's production-type path.
"""
from __future__ import annotations

import copy
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
import json
import os
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.native_fx_htf import NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from mfx_cache.native_htf_incremental import (
    IncrementalFetchPlan, validate_incremental_source,
)
from mfx_cache.native_htf_sha_forensics import (
    NativeAuditReadThroughWitness, classify_stored_vs_refetched_native,
)
from tools.mfx_native_htf_drive_seal import (
    PrivateNativeDriveStore, audit_native_archive,
    CHUNK_FOLDER, MANIFEST_FOLDER,
)
from tools.run_mfx_native_htf_incremental_commit import main as writer_main
from test_a04_p55_native_htf_drive import FakeDrive
from test_mfx_v1_six_tf_sealed_archive_consumer import _native

DAYS = ("2026-11-09", "2026-11-10", "2026-11-11")
HOURS = ("2026-11-12 00:00:00", "2026-11-12 04:00:00",
         "2026-11-12 08:00:00", "2026-11-12 12:00:00")
REVISION = "P059_SOURCE_NATIVE_REVISION_QUARANTINE"


def due_plan(interval: str, previous) -> IncrementalFetchPlan:
    return IncrementalFetchPlan(
        symbol="EUR/USD", interval=interval,
        status="INCREMENTAL_FETCH_REQUIRED",
        request={"symbol": "EUR/USD", "interval": interval,
                 "outputsize": "25"},
        last_native_open_label=(
            previous["last_native_open_label"] if previous else None),
        latest_expected_closed_label=(
            "2026-11-12" if interval == "1day"
            else "2026-11-12 16:00:00"),
        calendar_slots_behind=1, overlap_bar_count=(
            len(previous["recent_native_bar_index"]) if previous else 0),
        provider_requests_planned=1,
    )


def skip_plan(interval: str, previous) -> IncrementalFetchPlan:
    return IncrementalFetchPlan(
        symbol="EUR/USD", interval=interval,
        status="NO_NEW_CLOSED_SLOT_NO_VENDOR_CALL",
        request=None,
        last_native_open_label=(
            previous["last_native_open_label"] if previous else None),
        latest_expected_closed_label=(
            previous["last_native_open_label"] if previous else None),
        calendar_slots_behind=0, overlap_bar_count=0,
        provider_requests_planned=0,
    )


class RealDriveNativeForensicAdapterTests(TestCase):
    def setUp(self):
        self.drive = FakeDrive()
        self.media_patch = patch(
            "tools.mfx_native_htf_drive_seal._drive_get",
            side_effect=lambda session, ident: self.drive.read(ident),
        )
        self.media = self.media_patch.start()
        self.addCleanup(self.media_patch.stop)
        # All seeds are fixture side effects inside FakeDrive only.
        # A test invoking the real Drive POST helper is a bug.
        self.post_patch = patch(
            "tools.mfx_native_htf_drive_seal._drive_create",
            side_effect=AssertionError("FORBIDDEN_NATIVE_DRIVE_POST"),
        )
        self.post = self.post_patch.start()
        self.addCleanup(self.post_patch.stop)

    def adapter(self, interval):
        store = PrivateNativeDriveStore(
            self.drive, symbol="EUR/USD", interval=interval)
        self.assertIs(type(store), PrivateNativeDriveStore)
        return store

    def seed(self, interval, batches):
        prior = None
        for labels in batches:
            batch = _native(interval, tuple(labels))
            plan = plan_native_sealed(batch, previous=prior)
            self.assertIsNotNone(plan)
            self.drive.create(CHUNK_FOLDER, plan.chunk_name, plan.chunk)
            self.drive.create(MANIFEST_FOLDER, plan.manifest_name, plan.manifest)
            prior = plan.manifest
        return prior

    def snapshot(self):
        return copy.deepcopy((
            self.drive.objects, self.drive.names, self.drive.parents,
            self.drive.writes,
        ))

    def witnessed(self, interval):
        witness = NativeAuditReadThroughWitness(self.adapter(interval))
        state = audit_native_archive(
            witness, symbol="EUR/USD", interval=interval)
        old = witness.verified_recent_rows(
            state, symbol="EUR/USD", interval=interval)
        return state, old

    def test_01_real_h4_drive_media_list_same_io_as_original_full_audit(self):
        self.seed("4h", (HOURS,))
        baseline = audit_native_archive(
            self.adapter("4h"), symbol="EUR/USD", interval="4h")
        first_counts = (len(self.drive.requests), self.media.call_count)
        self.drive.requests.clear()
        self.media.reset_mock()
        observed, raw = self.witnessed("4h")
        self.assertEqual(observed, baseline)
        self.assertEqual((len(self.drive.requests), self.media.call_count),
                         first_counts)
        self.assertEqual(len(raw), 4)
        self.post.assert_not_called()

    def test_02_real_d1_drive_media_list_same_io_as_original_audit(self):
        self.seed("1day", (DAYS,))
        baseline = audit_native_archive(
            self.adapter("1day"), symbol="EUR/USD", interval="1day")
        first_counts = (len(self.drive.requests), self.media.call_count)
        self.drive.requests.clear()
        self.media.reset_mock()
        observed, raw = self.witnessed("1day")
        self.assertEqual(observed, baseline)
        self.assertEqual((len(self.drive.requests), self.media.call_count),
                         first_counts)
        self.assertEqual(len(raw), 3)
        self.post.assert_not_called()

    def test_03_real_drive_old_raw_sha_index_identical(self):
        original = self.seed("1day", (DAYS,))
        state, old = self.witnessed("1day")
        self.assertEqual(state.last_manifest, original)
        self.assertEqual(
            [(x.native_open_label, x.sha256()) for x in old],
            [(v["label"], v["sha256"])
             for v in original["recent_native_bar_index"]])

    def test_04_real_drive_multi_pair_sha_parent_witness_last16(self):
        labels = tuple(
            f"2026-11-{day:02d} {hour:02d}:00:00"
            for day in (7, 8, 9, 10)
            for hour in (0, 4, 8, 12, 16, 20))
        self.seed("4h", (labels[:17], labels[17:]))
        state, old = self.witnessed("4h")
        self.assertEqual(state.manifest_count, 2)
        self.assertEqual(len(old), 16)
        self.assertEqual(old[0].native_open_label, labels[-16])
        self.assertEqual(old[-1].native_open_label, labels[-1])
        self.assertEqual(len(state.last_manifest["recent_native_bar_index"]), 16)

    def test_05_real_drive_stored_vs_changed_numeric_d1_is_never_repaired(self):
        self.seed("1day", (DAYS,))
        original = self.snapshot()
        state, old = self.witnessed("1day")
        fresh = _native("1day", DAYS)
        fresh = replace(fresh, closed_bars=tuple(
            replace(b, high="1.1070")
            if b.native_open_label == "2026-11-11" else b
            for b in fresh.closed_bars))
        report = classify_stored_vs_refetched_native(
            previous=state.last_manifest, old_verified=old,
            fresh=fresh, quarantine_error=REVISION)
        self.assertEqual(report["numeric_ohlc_changed_count"], 1)
        self.assertEqual(report["first_changed_label"], "2026-11-11")
        self.assertEqual(report["additional_drive_gets"], 0)
        self.assertEqual(self.snapshot(), original)
        self.post.assert_not_called()

    def test_06_real_drive_stored_vs_equal_numeric_format_only(self):
        self.seed("1day", (DAYS,))
        state, old = self.witnessed("1day")
        fresh = _native("1day", DAYS)
        fresh = replace(fresh, closed_bars=tuple(
            replace(b, open="1.100")
            if b.native_open_label == "2026-11-11" else b
            for b in fresh.closed_bars))
        result = classify_stored_vs_refetched_native(
            previous=state.last_manifest, old_verified=old,
            fresh=fresh, quarantine_error=REVISION)
        self.assertEqual(result["numeric_ohlc_changed_count"], 0)
        self.assertEqual(result["equal_numeric_text_only_count"], 1)

    def test_07_real_drive_stored_vs_provenance_only(self):
        self.seed("1day", (DAYS,))
        state, old = self.witnessed("1day")
        fresh = _native("1day", DAYS)
        fresh = replace(fresh, closed_bars=tuple(
            replace(b, exchange_timezone_origin="PROVIDER_META")
            if b.native_open_label == "2026-11-11" else b
            for b in fresh.closed_bars))
        result = classify_stored_vs_refetched_native(
            previous=state.last_manifest, old_verified=old,
            fresh=fresh, quarantine_error=REVISION)
        self.assertEqual(result["numeric_ohlc_changed_count"], 0)
        self.assertEqual(result["equal_numeric_metadata_only_count"], 1)

    def test_08_real_drive_cross_native_scope_and_no_m5_pollution(self):
        self.seed("4h", (HOURS,))
        self.seed("1day", (DAYS,))
        self.drive.add_other_m5()
        original = self.snapshot()
        h4, rows_h4 = self.witnessed("4h")
        d1, rows_d1 = self.witnessed("1day")
        self.assertEqual(len(rows_h4), 4)
        self.assertEqual(len(rows_d1), 3)
        self.assertEqual((h4.manifest_count, d1.manifest_count), (1, 1))
        self.assertEqual(original, self.snapshot())
        for url, params in self.drive.requests:
            self.assertEqual(url, "https://www.googleapis.com/drive/v3/files")
            self.assertIn("in parents and name contains", params["q"])
            self.assertIn("trashed = false", params["q"])
        self.post.assert_not_called()

    def test_09_real_drive_corrupted_chunk_prevents_witness(self):
        self.seed("1day", (DAYS,))
        name = self.adapter("1day").list_names("chunk")[0]
        file_id = self.drive.names[name]
        self.drive.objects[file_id]["bars"][-1]["close"] = "1.2000"
        with self.assertRaises(ValueError):
            self.witnessed("1day")
        self.post.assert_not_called()

    def test_10_real_drive_missing_chunk_fails_before_attestation(self):
        self.seed("1day", (DAYS,))
        name = self.adapter("1day").list_names("chunk")[0]
        file_id = self.drive.names.pop(name)
        self.drive.objects.pop(file_id)
        with self.assertRaisesRegex(ValueError, "MISSING_REFERENCED_CHUNK"):
            self.witnessed("1day")
        self.post.assert_not_called()

    def test_11_exact_native_writer_real_adapter_logs_class_and_rethrows(self):
        self.seed("1day", (DAYS,))
        original = self.snapshot()
        old_bar = _native("1day", DAYS)
        fresh = replace(old_bar, closed_bars=tuple(
            replace(b, close="1.1100")
            if b.native_open_label == "2026-11-11" else b
            for b in old_bar.closed_bars))
        environment = {
            "MFX_REAL_CACHE_ENABLED": "true",
            "MFX_V2_BATCH_CACHE_ACCEPTED": "true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED": "true",
            "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED": "true",
            "GITHUB_EVENT_NAME": "schedule",
        }
        def fake_plan(*, interval, previous, now_utc):
            if interval == "4h":
                return skip_plan(interval, previous)
            self.assertEqual(interval, "1day")
            return due_plan(interval, previous)
        output = StringIO()
        with patch.dict(os.environ, environment, clear=True), \
             patch("tools.run_mfx_native_htf_incremental_commit._settings",
                   return_value=("TOPSECRET_API_KEY", {}, 400)), \
             patch("tools.run_mfx_native_htf_incremental_commit._session",
                   return_value=self.drive), \
             patch("tools.run_mfx_native_htf_incremental_commit.plan_native_fetch",
                   side_effect=fake_plan), \
             patch("tools.run_mfx_native_htf_incremental_commit._usage",
                   return_value=(1, 8)) as usage, \
             patch("tools.run_mfx_native_htf_incremental_commit._read_payload",
                   return_value={"fixture": True}) as price, \
             patch("tools.run_mfx_native_htf_incremental_commit.parse_native_forex",
                   return_value=fresh) as parse, \
             redirect_stdout(output):
            with self.assertRaisesRegex(ValueError, REVISION):
                writer_main()
        log = output.getvalue()
        self.assertIn("MFX_P059_NATIVE_OVERLAP_FORENSICS_NO_DRIVE_WRITE", log)
        self.assertIn('"numeric_ohlc_changed_count": 1', log)
        self.assertIn('"first_changed_label": "2026-11-11"', log)
        self.assertNotIn("TOPSECRET_API_KEY", log)
        self.assertNotIn("1.1100", log)
        self.assertEqual(original, self.snapshot())
        usage.assert_called_once()
        price.assert_called_once()
        parse.assert_called_once()
        self.post.assert_not_called()

    def test_12_exact_writer_real_adapter_format_only_quarantines(self):
        self.seed("1day", (DAYS,))
        original = self.snapshot()
        old = _native("1day", DAYS)
        fresh = replace(old, closed_bars=tuple(
            replace(b, open="1.100") if b.native_open_label == "2026-11-11"
            else b for b in old.closed_bars))
        environment = {
            "MFX_REAL_CACHE_ENABLED": "true",
            "MFX_V2_BATCH_CACHE_ACCEPTED": "true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED": "true",
            "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED": "true",
        }
        def fake_plan(*, interval, previous, now_utc):
            return due_plan(interval, previous) if interval == "1day" else skip_plan(interval, previous)
        output = StringIO()
        with patch.dict(os.environ, environment, clear=True), \
             patch("tools.run_mfx_native_htf_incremental_commit._settings",
                   return_value=("MASKED_KEY", {}, 400)), \
             patch("tools.run_mfx_native_htf_incremental_commit._session",
                   return_value=self.drive), \
             patch("tools.run_mfx_native_htf_incremental_commit.plan_native_fetch",
                   side_effect=fake_plan), \
             patch("tools.run_mfx_native_htf_incremental_commit._usage",
                   return_value=(1, 8)), \
             patch("tools.run_mfx_native_htf_incremental_commit._read_payload",
                   return_value={"fixture": True}) as price, \
             patch("tools.run_mfx_native_htf_incremental_commit.parse_native_forex",
                   return_value=fresh), \
             redirect_stdout(output):
            with self.assertRaisesRegex(ValueError, REVISION):
                writer_main()
        self.assertIn('"equal_numeric_text_only_count": 1', output.getvalue())
        self.assertIn('"numeric_ohlc_changed_count": 0', output.getvalue())
        self.assertEqual(original, self.snapshot())
        price.assert_called_once()
        self.post.assert_not_called()
