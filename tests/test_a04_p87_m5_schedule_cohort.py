"""A04/P0.87: 12 observed scheduled runs + hermetic negative chronology QA.

Event timestamps below are sanitized observations cross-checked with 12
GitHub Actions logs + Drive filename listings on 2026-11-12. Filenames use
FAKE SHA-shaped suffixes in tests: these fixtures do not re-attest live SHA.
No HTTP/Drive/vendor calls, production cron changes or trading.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from tools.mfx_m5_scheduler_cohort_evidence import (
    SCHEMA, ObservedM5Batch, ObservedScheduledRun,
    evaluate_observed_m5_schedule_cohort,
)

UTC = timezone.utc
FAKE_SHA = "a"*64


def dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def batch(hour: str, created: str, *, sha: str = FAKE_SHA) -> ObservedM5Batch:
    h = dt(hour)
    return ObservedM5Batch(
        hour_utc=h,
        manifest_name=(
            "MFX_TD_EURUSD_M5_V2_manifest_"
            + h.strftime("%Y%m%dT%H00Z") + "_" + sha + ".json"),
        manifest_created_utc=dt(created),
    )


def run(run_id: int, created: str, batches: tuple[ObservedM5Batch, ...],
        *, event="schedule", status=None, vendor_price_requests=1):
    if status is None:
        status = "BATCH_COMMITTED" if len(batches) == 1 else "BATCHES_COMMITTED"
    return ObservedScheduledRun(
        run_id=run_id, event=event, run_created_utc=dt(created),
        writer_status=status, vendor_price_requests=vendor_price_requests,
        batches=batches,
    )


def observations() -> tuple[ObservedScheduledRun, ...]:
    """12 real receipt times / 14 observed batch slots; fake SHA names only."""
    return (
        run(43158866760, "2026-11-12T05:04:06Z",
            (batch("2026-11-12T03:00:00Z", "2026-11-12T05:04:29.852Z"),)),
        run(43151652891, "2026-11-12T03:58:01Z",
            (batch("2026-11-12T02:00:00Z", "2026-11-12T03:58:23.357Z"),)),
        run(43144695651, "2026-11-12T02:55:29Z",
            (batch("2026-11-12T01:00:00Z", "2026-11-12T02:55:50.051Z"),)),
        run(43133264975, "2026-11-12T01:15:37Z", (
            batch("2026-11-11T23:00:00Z", "2026-11-12T01:15:59.054Z"),
            batch("2026-11-12T00:00:00Z", "2026-11-12T01:16:10.893Z"),
        )),
        run(43123068939, "2026-11-11T23:52:12Z",
            (batch("2026-11-11T22:00:00Z", "2026-11-11T23:52:30.321Z"),)),
        run(43115786422, "2026-11-11T22:55:44Z",
            (batch("2026-11-11T21:00:00Z", "2026-11-11T22:56:04.349Z"),)),
        run(43105022518, "2026-11-11T21:39:50Z", (
            batch("2026-11-11T19:00:00Z", "2026-11-11T21:40:14.949Z"),
            batch("2026-11-11T20:00:00Z", "2026-11-11T21:40:26.199Z"),
        )),
        run(43092969245, "2026-11-11T20:03:55Z",
            (batch("2026-11-11T18:00:00Z", "2026-11-11T20:04:12.030Z"),)),
        run(43082949666, "2026-11-11T18:59:30Z",
            (batch("2026-11-11T17:00:00Z", "2026-11-11T18:59:50.977Z"),)),
        run(43073227903, "2026-11-11T17:58:13Z",
            (batch("2026-11-11T16:00:00Z", "2026-11-11T17:58:29.330Z"),)),
        run(43063687329, "2026-11-11T16:59:19Z",
            (batch("2026-11-11T15:00:00Z", "2026-11-11T16:59:57.138Z"),)),
        run(43053200735, "2026-11-11T15:55:42Z",
            (batch("2026-11-11T14:00:00Z", "2026-11-11T15:56:01.047Z"),)),
    )


class ScheduledM5CohortTests(TestCase):
    def result(self, records=None):
        return evaluate_observed_m5_schedule_cohort(
            observations() if records is None else records)

    def test_01_source_sample_12_runs_14_batches(self):
        r = self.result()
        self.assertEqual((r.run_count, r.observed_manifest_count), (12, 14))
        self.assertEqual(r.schema, SCHEMA)

    def test_02_two_bounded_catchup_runs(self):
        r = self.result()
        self.assertEqual(r.multi_batch_recovery_runs, 2)
        self.assertEqual(r.total_writer_reported_vendor_requests, 12)

    def test_03_all_observed_14_hours_contiguous(self):
        r = self.result()
        self.assertEqual(r.missing_hours_between_observed_batches, 0)
        self.assertEqual(r.status,
            "OBSERVED_BATCH_TIMELINE_CONSISTENT_CAUSE_UNVERIFIED")
        self.assertEqual(r.latest_observed_batch_hour_utc,
                         "2026-11-12T03:00:00+00:00")

    def test_04_observed_medians_not_scheduler_cause(self):
        r = self.result()
        self.assertAlmostEqual(
            r.median_run_created_after_theoretical_tick_seconds/60, 48.12,
            places=2)
        self.assertAlmostEqual(
            r.median_manifest_after_hour_close_seconds/60, 58.44,
            places=2)
        self.assertAlmostEqual(
            r.median_run_created_to_manifest_seconds, 21.6, places=1)
        self.assertGreater(r.maximum_manifest_after_hour_close_seconds, 6000)

    def test_05_no_authentic_scheduled_tick_or_root_cause(self):
        r = self.result()
        self.assertFalse(r.github_scheduled_tick_for_run_authenticated)
        self.assertFalse(r.github_schedule_delay_cause_proven)
        self.assertFalse(r.github_concurrency_queue_delay_proven)
        self.assertFalse(r.vendor_publication_delay_cause_proven)

    def test_06_no_data_rights_trading_h4_or_live_v2_promotion(self):
        r = self.result()
        self.assertFalse(r.real_market_session_calendar_verified)
        self.assertFalse(r.entire_archive_sha_verified_by_this_module)
        self.assertFalse(r.cache_lag_permanently_fixed)
        self.assertFalse(r.native_h4_replacement_authorized)
        self.assertFalse(r.live_v2_authorized)
        self.assertFalse(r.numeric_signals_authorized)
        self.assertEqual((r.this_module_price_requests,
                          r.this_module_drive_writes,
                          r.this_module_broker_orders), (0,0,0))

    def test_07_duplicate_run_id_rejected(self):
        rs = observations()
        with self.assertRaisesRegex(ValueError, "UNTRUSTED"):
            self.result((rs[0], rs[0]))

    def test_08_duplicate_manifest_hour_across_runs_rejected(self):
        rs = observations()
        with self.assertRaisesRegex(ValueError, "BATCH_CLOCK"):
            self.result((rs[0], replace(rs[1], batches=rs[0].batches)))

    def test_09_wrong_event_rejected(self):
        rs = observations()
        with self.assertRaisesRegex(ValueError, "UNTRUSTED"):
            self.result((replace(rs[0], event="workflow_dispatch"),))

    def test_10_writer_status_mismatch_rejected(self):
        rs = observations()
        with self.assertRaisesRegex(ValueError, "UNTRUSTED"):
            self.result((replace(rs[0], writer_status="NO_COMMIT"),))

    def test_11_multi_batch_single_status_rejected(self):
        rs = observations()
        with self.assertRaisesRegex(ValueError, "UNTRUSTED"):
            self.result((replace(rs[3], writer_status="BATCH_COMMITTED"),))

    def test_12_boolean_vendor_request_rejected(self):
        rs = observations()
        with self.assertRaisesRegex(ValueError, "UNTRUSTED"):
            self.result((replace(rs[0], vendor_price_requests=True),))

    def test_13_more_than_one_price_request_receipt_denied(self):
        rs = observations()
        with self.assertRaisesRegex(ValueError, "UNTRUSTED"):
            self.result((replace(rs[0], vendor_price_requests=3),))

    def test_14_wrong_manifest_hour_label_denied(self):
        rs=observations()
        invalid=replace(rs[0].batches[0], manifest_name=(
            "MFX_TD_EURUSD_M5_V2_manifest_20261112T0200Z_" + FAKE_SHA + ".json"))
        with self.assertRaisesRegex(ValueError, "MANIFEST_FILENAME"):
            self.result((replace(rs[0], batches=(invalid,)),))

    def test_15_malformed_manifest_digest_denied(self):
        rs=observations()
        invalid=replace(rs[0].batches[0], manifest_name=(
            "MFX_TD_EURUSD_M5_V2_manifest_20261112T0300Z_bad.json"))
        with self.assertRaisesRegex(ValueError, "MANIFEST_FILENAME"):
            self.result((replace(rs[0], batches=(invalid,)),))

    def test_16_manifest_created_before_run_denied(self):
        rs=observations()
        invalid=replace(rs[0].batches[0],
            manifest_created_utc=dt("2026-11-12T05:04:05Z"))
        with self.assertRaisesRegex(ValueError, "BATCH_CLOCK"):
            self.result((replace(rs[0], batches=(invalid,)),))

    def test_17_manifest_earlier_than_grace_denied(self):
        r=run(99, "2026-11-12T04:04:00Z",
            (batch("2026-11-12T03:00:00Z","2026-11-12T04:04:30Z"),))
        with self.assertRaisesRegex(ValueError,"BATCH_CLOCK|GRACE"):
            self.result((r,))

    def test_18_not_yet_eligible_hour_denied(self):
        rs=observations()
        invalid=batch("2026-11-12T04:00:00Z",
                      "2026-11-12T05:04:29.852Z")
        with self.assertRaisesRegex(ValueError, "BATCH_CLOCK"):
            self.result((replace(rs[0], batches=(invalid,)),))

    def test_19_naive_run_time_denied(self):
        rs=observations()
        with self.assertRaisesRegex(ValueError, "UNTRUSTED"):
            self.result((replace(rs[0],
                run_created_utc=datetime(2026,11,12,5,4,6)),))

    def test_20_naive_manifest_time_denied(self):
        rs=observations()
        invalid=replace(rs[0].batches[0],
                         manifest_created_utc=datetime(2026,11,12,5,4,30))
        with self.assertRaisesRegex(ValueError, "BATCH_CLOCK"):
            self.result((replace(rs[0], batches=(invalid,)),))

    def test_21_unordered_hours_within_run_denied(self):
        rs=observations()
        with self.assertRaisesRegex(ValueError, "BATCH_CLOCK"):
            self.result((replace(rs[3], batches=tuple(reversed(rs[3].batches))),))

    def test_22_missing_one_hour_reported_not_hidden(self):
        rs=observations()
        result=self.result(tuple(x for x in rs if x.run_id != 43144695651))
        self.assertEqual(result.missing_hours_between_observed_batches,1)
        self.assertEqual(result.status,"OBSERVED_M5_HOUR_GAPS_RECHECK_REQUIRED")

    def test_23_nonconsecutive_hours_in_same_run_are_gaps_not_fabricated(self):
        r=run(99,"2026-11-12T05:39:50Z",(
            batch("2026-11-12T01:00:00Z","2026-11-12T05:40:01Z"),
            batch("2026-11-12T03:00:00Z","2026-11-12T05:40:12Z"),
        ))
        out=self.result((r,))
        self.assertEqual(out.missing_hours_between_observed_batches,1)
        self.assertEqual(out.status,"OBSERVED_M5_HOUR_GAPS_RECHECK_REQUIRED")

    def test_24_previous_delayed_run_can_commit_before_next_tick(self):
        r=run(99,"2026-11-12T04:07:00Z",(
            batch("2026-11-12T03:00:00Z","2026-11-12T04:07:22Z"),))
        out=self.result((r,))
        self.assertEqual(out.median_run_created_after_theoretical_tick_seconds,-180)
        self.assertFalse(out.github_scheduled_tick_for_run_authenticated)

    def test_25_boolean_run_id_denied(self):
        rs=observations()
        with self.assertRaisesRegex(ValueError,"UNTRUSTED"):
            self.result((replace(rs[0], run_id=True),))

    def test_26_empty_cohort_denied(self):
        with self.assertRaisesRegex(ValueError,"BOUND"):
            self.result(())

    def test_27_invalid_cohort_type_denied(self):
        with self.assertRaisesRegex(ValueError,"BOUND"):
            self.result(list(observations()))

    def test_28_more_than_100_runs_denied(self):
        rs=observations()
        with self.assertRaisesRegex(ValueError,"BOUND"):
            self.result(tuple(replace(rs[0], run_id=i+1)
                              for i in range(101)))

    def test_29_more_than_four_batches_per_run_denied(self):
        rs=observations()
        with self.assertRaisesRegex(ValueError,"UNTRUSTED"):
            self.result((replace(rs[0], batches=rs[0].batches*5,
                  writer_status="BATCHES_COMMITTED"),))

    def test_30_pure_receipt_no_market_prices_or_mutations(self):
        rs=observations()
        before=repr(rs)
        receipt=self.result(rs)
        self.assertEqual(repr(rs),before)
        self.assertNotIn("EURUSD.ohlc",repr(receipt))
        self.assertEqual(receipt.this_module_drive_writes,0)


if __name__=="__main__":
    from unittest import main
    main()
