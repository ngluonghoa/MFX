"""A04/P0.84 regression suite: sanitized real-event UTC timings plus fake negatives."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from tools.mfx_m5_schedule_reconciliation import (
    M5TimelineObservation, M5TimelineReceipt, reconcile_m5_timeline, SCHEMA
)

UTC = timezone.utc
T = datetime(2026, 11, 12, tzinfo=UTC)
SHA = "478840990e3a8bc4a745da5d694a98193aa5f614bd1abad92f487a530a213d76"


def sample(**changes):
    observation = M5TimelineObservation(
        audit_at_utc=T + timedelta(hours=3, minutes=21, seconds=30),
        audit_last_manifest_hour_utc=T + timedelta(hours=1),
        audit_reported_lag_hours=1,
        audit_full_history_claim=False,
        writer_run_created_utc=T + timedelta(hours=3, minutes=58, seconds=1),
        writer_run_completed_utc=T + timedelta(hours=3, minutes=58, seconds=29),
        writer_committed_hour_utc=T + timedelta(hours=2),
        writer_status="BATCH_COMMITTED",
        drive_manifest_created_utc=T + timedelta(hours=3, minutes=58, seconds=23),
        drive_manifest_name=(
            "MFX_TD_EURUSD_M5_V2_manifest_20261112T0200Z_" + SHA + ".json"
        ),
    )
    return replace(observation, **changes)


def checked(observation=None, *, as_of=None):
    return reconcile_m5_timeline(
        observation if observation is not None else sample(),
        as_of_utc=as_of if as_of is not None else T + timedelta(hours=4)
    )


class M5TimelineTests(TestCase):
    def test_01_observed_late_next_slot_present_not_full_history(self):
        r = checked()
        self.assertEqual(r.status, "LATE_NEXT_SLOT_MANIFEST_OBSERVED")
        self.assertTrue(r.observed_next_hour_manifest)
        self.assertFalse(r.independently_verified_full_history)

    def test_02_only_elapsed_after_theoretical_tick_not_cause(self):
        r = checked()
        self.assertEqual(r.seconds_after_earliest_hourly_tick, 48 * 60 + 1)
        self.assertFalse(r.github_scheduler_cause_proven)
        self.assertFalse(r.incident_cause_proven)

    def test_03_fake_full_history_boolean_never_attests(self):
        r = checked(sample(audit_full_history_claim=True))
        self.assertFalse(r.independently_verified_full_history)

    def test_04_frozen_research_receipt_and_no_side_effects(self):
        r = checked()
        self.assertIsInstance(r, M5TimelineReceipt)
        self.assertEqual(r.schema, SCHEMA)
        self.assertEqual((r.provider_calls, r.drive_writes, r.broker_orders), (0, 0, 0))
        self.assertFalse(r.h4_source_substitution_authorized)
        self.assertFalse(r.live_v2_authorized)
        self.assertFalse(r.forex_session_calendar_verified)

    def test_05_same_old_hour_not_a_new_slot(self):
        r = checked(sample(writer_committed_hour_utc=T + timedelta(hours=1)))
        self.assertEqual(r.status, "NONCONTIGUOUS_NEXT_SLOT_RECHECK_REQUIRED")
        self.assertFalse(r.observed_next_hour_manifest)

    def test_06_skip_an_hour_needs_more_evidence(self):
        r = checked(sample(audit_last_manifest_hour_utc=T))
        self.assertEqual(r.status, "NONCONTIGUOUS_NEXT_SLOT_RECHECK_REQUIRED")

    def test_07_no_commit_receipt_fails_closed(self):
        r = checked(sample(writer_status="NO_COMMIT"))
        self.assertEqual(r.status, "WRITER_RECEIPT_RECHECK_REQUIRED")

    def test_08_mismatched_filename_hour(self):
        r = checked(sample(
            drive_manifest_name="MFX_TD_EURUSD_M5_V2_manifest_20261112T0100Z_" + SHA + ".json"))
        self.assertEqual(r.status, "MANIFEST_IDENTITY_RECHECK_REQUIRED")

    def test_09_bad_sha_filename(self):
        r = checked(sample(
            drive_manifest_name="MFX_TD_EURUSD_M5_V2_manifest_20261112T0200Z_foobar.json"))
        self.assertEqual(r.status, "MANIFEST_IDENTITY_RECHECK_REQUIRED")

    def test_10_wrong_audit_lag_counter(self):
        r = checked(sample(audit_reported_lag_hours=0))
        self.assertEqual(r.status, "AUDIT_LAG_COUNTER_RECHECK_REQUIRED")

    def test_11_old_audit_cannot_promote_current(self):
        r = checked(as_of=T + timedelta(hours=6))
        self.assertEqual(r.status, "STALE_AUDIT_RECHECK_REQUIRED")

    def test_12_overlapping_writer_started_before_audit(self):
        r = checked(sample(
            writer_run_created_utc=T + timedelta(hours=3, minutes=15)))
        self.assertEqual(r.status, "TIMELINE_ORDER_RECHECK_REQUIRED")

    def test_13_drive_created_before_writer_run(self):
        r = checked(sample(
            drive_manifest_created_utc=T + timedelta(hours=3, minutes=57)))
        self.assertEqual(r.status, "TIMELINE_ORDER_RECHECK_REQUIRED")

    def test_14_drive_created_after_writer_completion(self):
        r = checked(sample(
            drive_manifest_created_utc=T + timedelta(hours=3, minutes=59)))
        self.assertEqual(r.status, "TIMELINE_ORDER_RECHECK_REQUIRED")

    def test_15_naive_audit_clock_rejected(self):
        with self.assertRaises(ValueError):
            checked(sample(audit_at_utc=datetime(2026, 11, 12, 3, 21, 30)))

    def test_16_future_audit_clock_rejected(self):
        with self.assertRaises(ValueError):
            checked(as_of=T + timedelta(hours=2))

    def test_17_boolean_lag_counter_rejected(self):
        with self.assertRaises(ValueError):
            checked(sample(audit_reported_lag_hours=True))

    def test_18_negative_lag_counter_rejected(self):
        with self.assertRaises(ValueError):
            checked(sample(audit_reported_lag_hours=-1))

    def test_19_wrong_source_rejected(self):
        with self.assertRaises(ValueError):
            checked(sample(source="UNVERIFIED_FOREX_FEED"))

    def test_20_wrong_symbol_rejected(self):
        with self.assertRaises(ValueError):
            checked(sample(symbol="USD/JPY"))

    def test_21_completion_before_creation_rejected(self):
        with self.assertRaises(ValueError):
            checked(sample(
                writer_run_completed_utc=T + timedelta(hours=3, minutes=57)))

    def test_22_invalid_writer_status_rejected(self):
        with self.assertRaises(ValueError):
            checked(sample(writer_status="TRADING_READY"))

    def test_23_off_hour_slot_rejected(self):
        with self.assertRaises(ValueError):
            checked(sample(
                writer_committed_hour_utc=T + timedelta(hours=2, minutes=5)))

    def test_24_datetime_type_and_untrusted_type_rejected(self):
        with self.assertRaises(ValueError):
            reconcile_m5_timeline(object(), as_of_utc=T + timedelta(hours=4))
