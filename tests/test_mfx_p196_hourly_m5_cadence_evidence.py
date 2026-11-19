"""P0.196: evidence-only separation of hourly M5 backlog and expected slots.

No vendor, OAuth, Drive writer, live price, source-owner numeric approval,
or trade capability. All examples are synthetic UTC timestamps.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import TestCase

from mfx_research.hourly_source_freshness import (
    diagnose_hourly_m5_freshness,
)
from test_mfx_p193_six_tf_owner_nov18_no_splice import consume_nov18
from tools.run_mfx_v1_manual_drive_six_tf import safe_summary

UTC = timezone.utc
ASOF = datetime(2026, 11, 19, 0, 28, 40, tzinfo=UTC)
SOURCE_LAST = "2026-11-18T22:00:00+00:00"


def calculate(hour=SOURCE_LAST, asof=ASOF):
    return diagnose_hourly_m5_freshness(
        m5_latest_hour_utc=hour, asof_utc=asof,
    )


class P196HourlyM5CadenceEvidenceTests(TestCase):
    def test_01_reproduces_real_manual_run_m5_17_missing_slots(self):
        r = calculate()
        c = r["sealed_hourly_m5_cadence_evidence"]
        self.assertEqual(r["closed_source_slot_gaps"]["M5"], 17)
        self.assertEqual(
            c["latest_eligible_full_hour_utc"],
            "2026-11-18T23:00:00+00:00",
        )
        self.assertEqual(
            c["eligible_complete_hour_batches_missing_from_archive"], 1,
        )
        self.assertEqual(c["m5_closed_slots_outside_writer_eligible_hours"], 5)
        self.assertEqual(c["observed_closed_m5_slots_missing"], 17)
        self.assertTrue(c["m5_slot_accounting_verified"])
        self.assertEqual(c["full_hour_archival_status"],
                         "ELIGIBLE_FULL_HOUR_BACKLOG")

    def test_02_even_on_time_hourly_writer_cannot_produce_latest_m5(self):
        r = calculate("2026-11-18T23:00:00+00:00")
        c = r["sealed_hourly_m5_cadence_evidence"]
        self.assertEqual(c["eligible_complete_hour_batches_missing_from_archive"], 0)
        self.assertEqual(c["m5_closed_slots_outside_writer_eligible_hours"], 5)
        self.assertEqual(r["closed_source_slot_gaps"]["M5"], 5)
        self.assertEqual(c["full_hour_archival_status"],
                         "ALL_ELIGIBLE_FULL_HOURS_ARCHIVED")
        self.assertFalse(r["intraday_m5_m15_source_tip_meets_freshness"])

    def test_03_two_overdue_complete_batches_accounted_as_24_m5(self):
        r = calculate("2026-11-18T21:00:00+00:00")
        c = r["sealed_hourly_m5_cadence_evidence"]
        self.assertEqual(c["eligible_complete_hour_batches_missing_from_archive"], 2)
        self.assertEqual(c["m5_closed_slots_outside_writer_eligible_hours"], 5)
        self.assertEqual(r["closed_source_slot_gaps"]["M5"], 29)

    def test_04_close_plus_5minute_writer_grace_not_prematurely_due(self):
        a = datetime(2026, 11, 19, 0, 2, tzinfo=UTC)
        r = calculate("2026-11-18T22:00:00+00:00", a)
        c = r["sealed_hourly_m5_cadence_evidence"]
        self.assertEqual(c["latest_eligible_full_hour_utc"],
                         "2026-11-18T22:00:00+00:00")
        self.assertEqual(c["eligible_complete_hour_batches_missing_from_archive"], 0)
        self.assertEqual(c["m5_closed_slots_outside_writer_eligible_hours"], 12)
        self.assertEqual(r["closed_source_slot_gaps"]["M5"], 12)

    def test_05_exact_first_writer_eligible_minute(self):
        r = calculate("2026-11-18T23:00:00+00:00",
                      datetime(2026, 11, 19, 0, 5, tzinfo=UTC))
        c = r["sealed_hourly_m5_cadence_evidence"]
        self.assertEqual(c["eligible_complete_hour_batches_missing_from_archive"], 0)
        self.assertEqual(c["m5_closed_slots_outside_writer_eligible_hours"], 0)
        self.assertEqual(r["closed_source_slot_gaps"]["M5"], 0)

    def test_06_current_new_cache_observation_19nov_still_one_due_hour(self):
        r = calculate("2026-11-19T08:00:00+00:00",
                      datetime(2026, 11, 19, 10, 26, tzinfo=UTC))
        c = r["sealed_hourly_m5_cadence_evidence"]
        self.assertEqual(c["latest_eligible_full_hour_utc"],
                         "2026-11-19T09:00:00+00:00")
        self.assertEqual(c["eligible_complete_hour_batches_missing_from_archive"], 1)
        self.assertEqual(r["closed_source_slot_gaps"]["M5"], 17)

    def test_07_unverified_writer_run_or_provider_license_never_inferred(self):
        c = calculate()["sealed_hourly_m5_cadence_evidence"]
        self.assertFalse(c["github_writer_run_result_independently_observed"])
        self.assertFalse(c["provider_publisher_first_known_verified"])
        self.assertFalse(c["permission_to_publish_live_buy_sell"])
        self.assertTrue(c["missing_slots_explained_by_hourly_grace_or_intrahour_design"])

    def test_08_future_source_denied_but_early_close_not_reinterpreted(self):
        with self.assertRaises(ValueError):
            calculate("2026-11-19T00:00:00+00:00")
        early = calculate("2026-11-18T23:00:00+00:00",
                          datetime(2026, 11, 19, 0, 2, tzinfo=UTC))
        c = early["sealed_hourly_m5_cadence_evidence"]
        self.assertTrue(c["source_ahead_of_standard_writer_plus5_grace"])
        self.assertFalse(c["m5_slot_accounting_verified"])
        self.assertEqual(c["full_hour_archival_status"],
                         "SOURCE_AHEAD_OF_STANDARD_WRITER_GRACE_NOT_ATTESTED")
        self.assertEqual(early["closed_source_slot_gaps"]["M5"], 0)

    def test_09_non_utc_and_malformed_source_denied(self):
        for a in (ASOF.replace(tzinfo=None),
                  ASOF.replace(tzinfo=timezone(timedelta(hours=7)))):
            with self.subTest(asof=a), self.assertRaises(ValueError):
                calculate(asof=a)
        with self.assertRaises(ValueError):
            calculate(hour="bad source timestamp")

    def test_10_real_six_tf_readonly_public_json_inherits_cadence(self):
        # Uses existing hermetic P193 sealed cache and mocked SHA anchors.
        # No external Drive session or mutable market data.
        evidence = consume_nov18()
        out = safe_summary(evidence, drive_gets=12)
        freshness = out["sha_verified_source_freshness_timing"]
        cadence = freshness["sealed_hourly_m5_cadence_evidence"]
        # Hermetic P193 fixture closes a valid full source hour ahead of
        # the conventional writer +5m guard. Its source SHA is still valid,
        # but no real writer-cadence completion is attested by that fixture.
        self.assertFalse(cadence["m5_slot_accounting_verified"])
        self.assertTrue(cadence["source_ahead_of_standard_writer_plus5_grace"])
        self.assertEqual(out["action"], "NO_SIGNAL")
        self.assertEqual(out["stage"], "UNVERIFIED")
        self.assertFalse(out["may_publish_buy_sell"])
        self.assertEqual(out["provider_price_requests"], 0)
        self.assertEqual(out["drive_writes"], 0)
        self.assertEqual(out["broker_orders"], 0)
