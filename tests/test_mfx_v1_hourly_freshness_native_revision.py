"""Signal-first MFX: source freshness and native SHA quarantine diagnostics.

All inputs synthetic/in-memory; no HTTP, Google Drive, broker or raw price logs.
"""
from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from mfx_cache.native_htf_incremental import (
    IncrementalFetchPlan, validate_incremental_source,
)
from mfx_cache.native_htf_revision_diagnostics import (
    summarize_native_revision_quarantine,
)
from mfx_research.hourly_source_freshness import (
    diagnose_hourly_m5_freshness,
)
from tools.run_mfx_v1_manual_drive_six_tf import safe_summary
from test_mfx_v1_six_tf_sealed_archive_consumer import consume

UTC = timezone.utc
HOUR_16 = "2026-11-12T16:00:00+00:00"
ASOF_1727 = datetime(2026, 11, 12, 17, 27, 49, tzinfo=UTC)
PRICE = dict(open="1.1000", high="1.1020", low="1.0990", close="1.1010")
AXES = {"4h": "UTC_INTRADAY_OPEN", "1day": "EXCHANGE_LOCAL_SESSION_DATE"}


def native(interval="4h", labels=None, origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT"):
    if labels is None:
        labels = ("2026-11-12 08:00:00", "2026-11-12 12:00:00") if interval == "4h" else ("2026-11-10", "2026-11-11")
    return NativeFXBatch(
        symbol="EUR/USD", interval=interval,
        exchange_timezone="Australia/Sydney",
        time_reference=AXES[interval], incomplete_excluded=0,
        closed_bars=tuple(NativeFXBar(
            symbol="EUR/USD", interval=interval,
            native_open_label=label, time_reference=AXES[interval],
            exchange_timezone="Australia/Sydney",
            exchange_timezone_origin=origin, **PRICE,
        ) for label in labels),
    )


def manifest(batch):
    p = plan_native_sealed(batch, previous=None)
    if p is None:
        raise AssertionError("missing synthetic plan")
    return copy.deepcopy(p.manifest)


def plan(interval):
    return IncrementalFetchPlan(
        symbol="EUR/USD", interval=interval,
        status="INCREMENTAL_FETCH_REQUIRED",
        request={"symbol": "EUR/USD", "interval": interval},
        last_native_open_label=None,
        latest_expected_closed_label="2026-11-12",
        calendar_slots_behind=1, overlap_bar_count=2,
        provider_requests_planned=1,
    )


class MFXSourceFreshnessAndNativeQuarantineTests(TestCase):
    def test_01_actual_live_proof_1727_exact_intraday_gap(self):
        r = diagnose_hourly_m5_freshness(
            m5_latest_hour_utc=HOUR_16, asof_utc=ASOF_1727)
        self.assertEqual(r["m5_last_archived_closed_end_utc"],
                         "2026-11-12T17:00:00+00:00")
        self.assertEqual(r["m5_latest_archived_close_age_seconds"], 1669)
        self.assertEqual(r["closed_source_slot_gaps"],
                         {"M5": 5, "M15": 1, "M30": 0, "H1": 0})
        self.assertEqual(r["required_last_closed_end_utc"]["M5"],
                         "2026-11-12T17:25:00+00:00")
        self.assertEqual(r["required_last_closed_end_utc"]["M15"],
                         "2026-11-12T17:15:00+00:00")
        self.assertFalse(r["intraday_m5_m15_source_tip_meets_freshness"])

    def test_02_at_1701_all_four_intraday_frames_align(self):
        r = diagnose_hourly_m5_freshness(
            m5_latest_hour_utc=HOUR_16,
            asof_utc=datetime(2026, 11, 12, 17, 1, tzinfo=UTC))
        self.assertEqual(r["closed_source_slot_gaps"],
                         {"M5": 0, "M15": 0, "M30": 0, "H1": 0})

    def test_03_at_1707_only_m5_missing(self):
        r = diagnose_hourly_m5_freshness(
            m5_latest_hour_utc=HOUR_16,
            asof_utc=datetime(2026, 11, 12, 17, 7, tzinfo=UTC))
        self.assertEqual(r["closed_source_slot_gaps"],
                         {"M5": 1, "M15": 0, "M30": 0, "H1": 0})

    def test_04_at_1716_m5_and_m15_gap(self):
        r = diagnose_hourly_m5_freshness(
            m5_latest_hour_utc=HOUR_16,
            asof_utc=datetime(2026, 11, 12, 17, 16, tzinfo=UTC))
        self.assertEqual(r["closed_source_slot_gaps"]["M5"], 3)
        self.assertEqual(r["closed_source_slot_gaps"]["M15"], 1)

    def test_05_at_1746_m5_m15_m30_gap_but_not_h1(self):
        r = diagnose_hourly_m5_freshness(
            m5_latest_hour_utc=HOUR_16,
            asof_utc=datetime(2026, 11, 12, 17, 46, tzinfo=UTC))
        self.assertEqual(r["closed_source_slot_gaps"],
                         {"M5": 9, "M15": 3, "M30": 1, "H1": 0})

    def test_06_at_1800_10_seconds_close_grace_does_not_advance(self):
        r = diagnose_hourly_m5_freshness(
            m5_latest_hour_utc=HOUR_16,
            asof_utc=datetime(2026, 11, 12, 18, 0, 10, tzinfo=UTC))
        self.assertEqual(r["closed_source_slot_gaps"]["H1"], 0)
        self.assertEqual(r["required_last_closed_end_utc"]["H1"],
                         "2026-11-12T17:00:00+00:00")

    def test_07_at_1800_16_seconds_new_h1_needed(self):
        r = diagnose_hourly_m5_freshness(
            m5_latest_hour_utc=HOUR_16,
            asof_utc=datetime(2026, 11, 12, 18, 0, 16, tzinfo=UTC))
        self.assertEqual(r["closed_source_slot_gaps"]["H1"], 1)

    def test_08_source_tip_future_rejected(self):
        with self.assertRaisesRegex(ValueError, "NOT_YET_CLOSED"):
            diagnose_hourly_m5_freshness(
                m5_latest_hour_utc=HOUR_16,
                asof_utc=datetime(2026, 11, 12, 16, 59, tzinfo=UTC))

    def test_09_invalid_hour_grid_rejected(self):
        with self.assertRaisesRegex(ValueError, "UTC_HOUR_GRID"):
            diagnose_hourly_m5_freshness(
                m5_latest_hour_utc="2026-11-12T16:05:00+00:00",
                asof_utc=ASOF_1727)

    def test_10_non_utc_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "UTC_HOUR_GRID"):
            diagnose_hourly_m5_freshness(
                m5_latest_hour_utc="2026-11-12T23:00:00+07:00",
                asof_utc=ASOF_1727)

    def test_11_naive_or_non_utc_asof_rejected(self):
        for date in (datetime(2026, 11, 12, 17, 27),
                     ASOF_1727.astimezone(timezone(timedelta(hours=7)))):
            with self.subTest(date=date), self.assertRaisesRegex(
                    ValueError, "EXACT_UTC"):
                diagnose_hourly_m5_freshness(
                    m5_latest_hour_utc=HOUR_16, asof_utc=date)

    def test_12_noncanonical_source_hour_rejected(self):
        for text in ("garbage", "2026-11-12T16:00:00",
                     "2026-11-12 16:00:00+00:00"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                diagnose_hourly_m5_freshness(
                    m5_latest_hour_utc=text, asof_utc=ASOF_1727)

    def test_13_freshness_diagnostic_has_no_price_or_price_call(self):
        r = diagnose_hourly_m5_freshness(
            m5_latest_hour_utc=HOUR_16, asof_utc=ASOF_1727)
        self.assertEqual((r["provider_price_requests"], r["cache_writes"],
                          r["broker_orders"]), (0, 0, 0))
        self.assertFalse(r["source_numeric_signals_approved"])
        self.assertNotIn("1.1010", json.dumps(r))

    def test_14_manual_summary_has_verified_timestamp_evidence(self):
        r = replace(consume(), github_reviewed_m5_anchors_checked=True)
        v = safe_summary(r, drive_gets=42)
        fresh = v["sha_verified_source_freshness_timing"]
        self.assertEqual(fresh["closed_source_slot_gaps"],
                         {"M5": 0, "M15": 0, "M30": 0, "H1": 0})
        self.assertEqual(v["action"], "NO_SIGNAL")
        self.assertEqual(v["drive_writes"], 0)

    def test_15_manual_summary_fails_closed_on_forged_hour(self):
        r = replace(consume(), github_reviewed_m5_anchors_checked=True,
                    m5_latest_source_hour_utc=HOUR_16)
        with self.assertRaises(ValueError):
            safe_summary(r, drive_gets=42)

    def test_16_native_price_revision_same_label_raises_original(self):
        a = native()
        prev = manifest(a)
        changed = replace(a, closed_bars=(
            replace(a.closed_bars[0], close="1.1011"),
            a.closed_bars[1],
        ))
        with self.assertRaisesRegex(
                ValueError, "P059_SOURCE_NATIVE_REVISION_QUARANTINE"):
            validate_incremental_source(
                changed, previous=prev, plan=plan("4h"))

    def test_17_sha_change_diagnostic_no_raw_ohlc(self):
        a = native()
        prev = manifest(a)
        changed = replace(a, closed_bars=(
            replace(a.closed_bars[0], close="1.1011"),
            a.closed_bars[1],
        ))
        r = summarize_native_revision_quarantine(
            previous=prev, batch=changed,
            error_code="P059_SOURCE_NATIVE_REVISION_QUARANTINE")
        self.assertEqual(r["overlap_sha_changed_count"], 1)
        self.assertEqual(r["overlap_sha_unchanged_count"], 1)
        self.assertEqual(r["overlap_labels_missing_count"], 0)
        self.assertEqual(r["first_changed_label"], "2026-11-12 08:00:00")
        self.assertEqual(r["last_changed_label"], "2026-11-12 08:00:00")
        self.assertFalse(r["actual_numeric_price_revision_confirmed"])
        self.assertTrue(r["quarantine_still_enforced"])
        self.assertEqual((r["provider_price_requests_added_by_diagnostic"],
                          r["drive_reads_added_by_diagnostic"],
                          r["drive_writes"]), (0, 0, 0))
        self.assertNotIn("1.1011", json.dumps(r))

    def test_18_same_numeric_price_format_can_change_sha(self):
        a = native()
        prev = manifest(a)
        changed = replace(a, closed_bars=(
            replace(a.closed_bars[0], open="1.100"),
            a.closed_bars[1],
        ))
        self.assertNotEqual(a.closed_bars[0].sha256(),
                            changed.closed_bars[0].sha256())
        r = summarize_native_revision_quarantine(
            previous=prev, batch=changed,
            error_code="P059_SOURCE_NATIVE_REVISION_QUARANTINE")
        self.assertEqual(r["overlap_sha_changed_count"], 1)
        self.assertFalse(r["actual_numeric_price_revision_confirmed"])

    def test_19_same_ohlc_timezone_provenance_changed_sha(self):
        a = native()
        prev = manifest(a)
        changed = replace(a, closed_bars=(
            replace(a.closed_bars[0],
                    exchange_timezone_origin="PROVIDER_META"),
            a.closed_bars[1],
        ))
        self.assertNotEqual(a.closed_bars[0].sha256(),
                            changed.closed_bars[0].sha256())
        r = summarize_native_revision_quarantine(
            previous=prev, batch=changed,
            error_code="P059_SOURCE_NATIVE_REVISION_QUARANTINE")
        self.assertEqual(r["overlap_sha_changed_count"], 1)
        self.assertFalse(r["actual_numeric_price_revision_confirmed"])

    def test_20_d1_native_quarantine_also_reports_only_labels(self):
        a = native(interval="1day")
        prev = manifest(a)
        changed = replace(a, closed_bars=(
            a.closed_bars[0],
            replace(a.closed_bars[1], high="1.1030"),
        ))
        r = summarize_native_revision_quarantine(
            previous=prev, batch=changed,
            error_code="P059_SOURCE_NATIVE_REVISION_QUARANTINE")
        self.assertEqual(r["interval"], "1day")
        self.assertEqual(r["overlap_sha_changed_count"], 1)
        self.assertEqual(r["last_changed_label"], "2026-11-11")

    def test_21_two_native_sha_changes_counted(self):
        a = native()
        prev = manifest(a)
        changed = replace(a, closed_bars=tuple(
            replace(bar, high="1.1050") for bar in a.closed_bars))
        r = summarize_native_revision_quarantine(
            previous=prev, batch=changed,
            error_code="P059_SOURCE_NATIVE_REVISION_QUARANTINE")
        self.assertEqual(r["overlap_sha_changed_count"], 2)
        self.assertEqual(r["first_changed_label"], "2026-11-12 08:00:00")
        self.assertEqual(r["last_changed_label"], "2026-11-12 12:00:00")

    def test_22_missing_overlap_remains_quarantine_without_rewrite(self):
        a = native()
        prev = manifest(a)
        missing = replace(a, closed_bars=(a.closed_bars[-1],))
        with self.assertRaisesRegex(
                ValueError, "P059_SOURCE_MISSING_SHA_OVERLAP"):
            validate_incremental_source(
                missing, previous=prev, plan=plan("4h"))
        r = summarize_native_revision_quarantine(
            previous=prev, batch=missing,
            error_code="P059_SOURCE_MISSING_SHA_OVERLAP")
        self.assertEqual(r["overlap_labels_missing_count"], 1)
        self.assertEqual(r["overlap_sha_changed_count"], 0)
        self.assertIsNone(r["first_changed_label"])
        self.assertEqual(r["first_missing_label"], "2026-11-12 08:00:00")

    def test_23_no_change_claimed_as_quarantine_denied(self):
        a = native()
        with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_MISMATCH"):
            summarize_native_revision_quarantine(
                previous=manifest(a), batch=a,
                error_code="P059_SOURCE_NATIVE_REVISION_QUARANTINE")

    def test_24_wrong_failure_code_denied(self):
        a = native()
        with self.assertRaisesRegex(ValueError, "SCOPE_DENIED"):
            summarize_native_revision_quarantine(
                previous=manifest(a), batch=a,
                error_code="P059_DISABLE_SHA_ALL_ALLOW")

    def test_25_missing_code_without_any_missing_denied(self):
        a = native()
        with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_MISMATCH"):
            summarize_native_revision_quarantine(
                previous=manifest(a), batch=a,
                error_code="P059_SOURCE_MISSING_SHA_OVERLAP")

    def test_26_duplicate_returned_labels_denied(self):
        a = native()
        prev = manifest(a)
        duplicate = replace(a, closed_bars=(a.closed_bars[0],
                                            a.closed_bars[0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_LABEL"):
            summarize_native_revision_quarantine(
                previous=prev, batch=duplicate,
                error_code="P059_SOURCE_NATIVE_REVISION_QUARANTINE")

    def test_27_corrupt_prior_index_denied(self):
        a = native()
        prev = manifest(a)
        prev["recent_native_bar_index"][0]["sha256"] = "wrong"
        with self.assertRaises(ValueError):
            summarize_native_revision_quarantine(
                previous=prev, batch=a,
                error_code="P059_SOURCE_NATIVE_REVISION_QUARANTINE")

    def test_28_untrusted_batch_interval_denied(self):
        a = native()
        prev = manifest(a)
        bad = replace(a, interval="30min")
        with self.assertRaisesRegex(ValueError, "SCOPE_DENIED"):
            summarize_native_revision_quarantine(
                previous=prev, batch=bad,
                error_code="P059_SOURCE_NATIVE_REVISION_QUARANTINE")

    def test_29_writer_diagnostic_does_not_hide_original_quarantine(self):
        # No network; use exact source pattern as defense-in-depth contract.
        from pathlib import Path
        source = Path(
            "tools/run_mfx_native_htf_incremental_commit.py"
        ).read_text(encoding="utf-8")
        self.assertIn("summarize_native_revision_quarantine(", source)
        self.assertIn("P059_NATIVE_OVERLAP_QUARANTINED_NO_DRIVE_WRITE", source)
        self.assertIn("            raise\n        proposal =", source)
        self.assertNotIn("P059_RETRY_WITHOUT_SHA", source)

    def test_30_diagnostic_does_not_claim_publisher_rights(self):
        a = native()
        prev = manifest(a)
        changed = replace(a, closed_bars=(
            replace(a.closed_bars[0], high="1.1200"), a.closed_bars[1]))
        r = summarize_native_revision_quarantine(
            previous=prev, batch=changed,
            error_code="P059_SOURCE_NATIVE_REVISION_QUARANTINE")
        self.assertFalse(r["source_numeric_signals_approved"])
        self.assertFalse(r["vendor_metadata_or_format_revision_excluded"])
        self.assertEqual(r["broker_orders"], 0)
