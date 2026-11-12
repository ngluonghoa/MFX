"""A04/P0.88: 12 actual GH job-stage UTC samples + hermetic negative QA.

Original job API timestamps were observed from GitHub 11–12 Nov 2026 and
paired to the real P0.87 run/Drive name sample. No live APIs in these tests.
"""
from dataclasses import replace
from datetime import datetime, timedelta
from unittest import TestCase

from test_a04_p87_m5_schedule_cohort import observations, dt
from tools.mfx_m5_job_lifecycle_evidence import (
    ObservedGitHubJob, M5JobStageReceipt, correlate_m5_job_stages, SCHEMA,
)


def job(run_id: int, job_id: int, run_created: str, created: str,
        started: str, finished: str, sync_start: str, sync_end: str):
    return ObservedGitHubJob(
        run_id=run_id, job_id=job_id,
        run_created_utc=dt(run_created),
        job_created_utc=dt(created),
        job_started_utc=dt(started),
        job_completed_utc=dt(finished),
        sync_step_started_utc=dt(sync_start),
        sync_step_completed_utc=dt(sync_end),
    )


def jobs() -> tuple[ObservedGitHubJob, ...]:
    return (
        job(43158866760, 130985079315,
            "2026-11-12T05:04:06Z", "2026-11-12T05:04:07Z",
            "2026-11-12T05:04:09Z", "2026-11-12T05:04:35Z",
            "2026-11-12T05:04:14Z", "2026-11-12T05:04:33Z"),
        job(43151652891, 130962013389,
            "2026-11-12T03:58:01Z", "2026-11-12T03:58:01Z",
            "2026-11-12T03:58:04Z", "2026-11-12T03:58:28Z",
            "2026-11-12T03:58:11Z", "2026-11-12T03:58:26Z"),
        job(43144695651, 130939653800,
            "2026-11-12T02:55:29Z", "2026-11-12T02:55:29Z",
            "2026-11-12T02:55:32Z", "2026-11-12T02:55:54Z",
            "2026-11-12T02:55:37Z", "2026-11-12T02:55:52Z"),
        job(43133264975, 130902310661,
            "2026-11-12T01:15:37Z", "2026-11-12T01:15:37Z",
            "2026-11-12T01:15:40Z", "2026-11-12T01:16:16Z",
            "2026-11-12T01:15:44Z", "2026-11-12T01:16:13Z"),
        job(43123068939, 130868165647,
            "2026-11-11T23:52:12Z", "2026-11-11T23:52:12Z",
            "2026-11-11T23:52:15Z", "2026-11-11T23:52:34Z",
            "2026-11-11T23:52:19Z", "2026-11-11T23:52:32Z"),
        job(43115786422, 130843288394,
            "2026-11-11T22:55:44Z", "2026-11-11T22:55:45Z",
            "2026-11-11T22:55:48Z", "2026-11-11T22:56:08Z",
            "2026-11-11T22:55:53Z", "2026-11-11T22:56:06Z"),
        job(43105022518, 130805991896,
            "2026-11-11T21:39:50Z", "2026-11-11T21:39:50Z",
            "2026-11-11T21:39:53Z", "2026-11-11T21:40:31Z",
            "2026-11-11T21:39:59Z", "2026-11-11T21:40:29Z"),
        job(43092969245, 130774495975,
            "2026-11-11T20:03:55Z", "2026-11-11T20:03:55Z",
            "2026-11-11T20:03:58Z", "2026-11-11T20:04:16Z",
            "2026-11-11T20:04:03Z", "2026-11-11T20:04:14Z"),
        job(43082949666, 130739959513,
            "2026-11-11T18:59:30Z", "2026-11-11T18:59:30Z",
            "2026-11-11T18:59:33Z", "2026-11-11T18:59:56Z",
            "2026-11-11T18:59:37Z", "2026-11-11T18:59:54Z"),
        job(43073227903, 130706313072,
            "2026-11-11T17:58:13Z", "2026-11-11T17:58:14Z",
            "2026-11-11T17:58:16Z", "2026-11-11T17:58:33Z",
            "2026-11-11T17:58:21Z", "2026-11-11T17:58:31Z"),
        job(43063687329, 130672806304,
            "2026-11-11T16:59:19Z", "2026-11-11T16:59:20Z",
            "2026-11-11T16:59:23Z", "2026-11-11T17:00:02Z",
            "2026-11-11T16:59:28Z", "2026-11-11T16:59:59Z"),
        job(43053200735, 130635604577,
            "2026-11-11T15:55:42Z", "2026-11-11T15:55:43Z",
            "2026-11-11T15:55:45Z", "2026-11-11T15:56:05Z",
            "2026-11-11T15:55:50Z", "2026-11-11T15:56:02Z"),
    )


def checked(run_rows=None, job_rows=None):
    return correlate_m5_job_stages(
        observations() if run_rows is None else run_rows,
        jobs() if job_rows is None else job_rows,
    )


class M5JobStageTests(TestCase):
    def test_01_actual_sample_12_runs_14_manifests(self):
        r = checked()
        self.assertIsInstance(r, M5JobStageReceipt)
        self.assertEqual(r.schema, SCHEMA)
        self.assertEqual((r.run_count, r.manifest_count), (12, 14))
        self.assertTrue(r.all_hours_contiguous_in_sample)

    def test_02_queuing_is_2_to_3_seconds_median_3(self):
        r = checked()
        self.assertEqual(r.median_job_queue_seconds, 3)
        self.assertEqual(r.maximum_job_queue_seconds, 3)

    def test_03_job_duration_median_22_point_5_max_39(self):
        r = checked()
        self.assertEqual(r.median_job_runtime_seconds, 22.5)
        self.assertEqual(r.maximum_job_runtime_seconds, 39)

    def test_04_sync_step_median_15_seconds(self):
        self.assertEqual(checked().median_sync_step_seconds, 15)

    def test_05_run_to_job_create_median_zero(self):
        self.assertEqual(checked().median_run_to_job_create_seconds, 0)

    def test_06_all_drive_manifest_times_inside_exact_job_step(self):
        r = checked()
        self.assertTrue(r.all_manifests_within_sync_step)
        self.assertGreater(r.median_run_to_first_manifest_seconds, 19)
        self.assertLess(r.median_run_to_first_manifest_seconds, 23)

    def test_07_no_scheduler_origin_claim(self):
        r = checked()
        self.assertFalse(r.original_event_dispatch_timestamp_authenticated)
        self.assertFalse(r.actual_scheduler_tick_matched_to_run)
        self.assertFalse(r.pre_run_github_delay_caused_by_scheduler_proven)
        self.assertFalse(r.concurrency_group_wait_proven)

    def test_08_no_vendor_first_publish_or_live_authorization(self):
        r = checked()
        self.assertFalse(r.vendor_first_price_availability_proven)
        self.assertFalse(r.full_m5_history_sha_attested_by_this_check)
        self.assertFalse(r.production_cron_edit_authorized)
        self.assertFalse(r.native_h4_replacement_authorized)
        self.assertFalse(r.live_v2_or_trading_authorized)
        self.assertEqual(
            (r.provider_requests_by_this_check, r.drive_writes_by_this_check,
             r.broker_orders_by_this_check), (0, 0, 0))

    def test_09_empty_job_collection_fails(self):
        with self.assertRaisesRegex(ValueError, "COHORT"):
            checked(job_rows=())

    def test_10_list_instead_tuple_fails(self):
        with self.assertRaisesRegex(ValueError, "COHORT"):
            checked(job_rows=list(jobs()))

    def test_11_job_coverage_missing_fails(self):
        with self.assertRaisesRegex(ValueError, "COHORT"):
            checked(job_rows=jobs()[:-1])

    def test_12_duplicate_run_id_fails(self):
        j = jobs()
        with self.assertRaisesRegex(ValueError, "ID_OR_CONCLUSION"):
            checked(job_rows=(j[0], replace(j[1], run_id=j[0].run_id))+j[2:])

    def test_13_duplicate_job_id_fails(self):
        j = jobs()
        with self.assertRaisesRegex(ValueError, "ID_OR_CONCLUSION"):
            checked(job_rows=(j[0], replace(j[1], job_id=j[0].job_id))+j[2:])

    def test_14_unrecognized_run_id_fails(self):
        j = jobs()
        with self.assertRaisesRegex(ValueError, "ID_OR_CONCLUSION"):
            checked(job_rows=(replace(j[0], run_id=999999),)+j[1:])

    def test_15_boolean_job_id_fails(self):
        j = jobs()
        with self.assertRaisesRegex(ValueError, "ID_OR_CONCLUSION"):
            checked(job_rows=(replace(j[0], job_id=True),)+j[1:])

    def test_16_failed_job_must_not_claim_good_manifest(self):
        j = jobs()
        with self.assertRaisesRegex(ValueError, "ID_OR_CONCLUSION"):
            checked(job_rows=(replace(j[0], job_conclusion="failure"),)+j[1:])

    def test_17_naive_job_clock_fails(self):
        j = jobs()
        with self.assertRaisesRegex(ValueError, "CLOCK_ORDER"):
            checked(job_rows=(replace(j[0],
                job_created_utc=datetime(2026, 11, 12, 5, 4, 7)),)+j[1:])

    def test_18_job_created_before_run_fails(self):
        j = jobs()
        with self.assertRaisesRegex(ValueError, "CLOCK_ORDER"):
            checked(job_rows=(replace(j[0],
                job_created_utc=dt("2026-11-12T05:04:05Z")),)+j[1:])

    def test_19_job_starts_before_created_fails(self):
        j = jobs()
        with self.assertRaisesRegex(ValueError, "CLOCK_ORDER"):
            checked(job_rows=(replace(j[0],
                job_started_utc=dt("2026-11-12T05:04:06Z")),)+j[1:])

    def test_20_sync_starts_before_job_starts_fails(self):
        j = jobs()
        with self.assertRaisesRegex(ValueError, "CLOCK_ORDER"):
            checked(job_rows=(replace(j[0],
                sync_step_started_utc=dt("2026-11-12T05:04:08Z")),)+j[1:])

    def test_21_sync_completed_before_it_starts_fails(self):
        j = jobs()
        with self.assertRaisesRegex(ValueError, "CLOCK_ORDER"):
            checked(job_rows=(replace(j[0],
                sync_step_completed_utc=dt("2026-11-12T05:04:12Z")),)+j[1:])

    def test_22_job_completed_before_sync_ends_fails(self):
        j = jobs()
        with self.assertRaisesRegex(ValueError, "CLOCK_ORDER"):
            checked(job_rows=(replace(j[0],
                job_completed_utc=dt("2026-11-12T05:04:32Z")),)+j[1:])

    def test_23_run_to_job_timestamp_mismatch_fails(self):
        j = jobs()
        with self.assertRaisesRegex(ValueError, "RUN_JOIN_TIMESTAMP"):
            checked(job_rows=(replace(j[0],
                run_created_utc=dt("2026-11-12T05:04:05Z")),)+j[1:])

    def test_24_drive_created_outside_writer_step_fails(self):
        r = observations()
        altered = replace(r[0].batches[0],
            manifest_created_utc=dt("2026-11-12T05:04:34Z"))
        bad_runs=(replace(r[0], batches=(altered,)),)+r[1:]
        with self.assertRaisesRegex(ValueError, "NOT_IN_MATCHED_WRITER_STEP"):
            checked(run_rows=bad_runs)

    def test_25_shuffled_job_order_still_matches_exact_ids(self):
        self.assertEqual(checked().run_count,
                         checked(job_rows=tuple(reversed(jobs()))).run_count)

    def test_26_single_consistent_run_remains_valid(self):
        r = checked(run_rows=(observations()[0],), job_rows=(jobs()[0],))
        self.assertEqual((r.run_count, r.manifest_count), (1, 1))
        self.assertFalse(r.actual_scheduler_tick_matched_to_run)

    def test_27_missing_hour_in_sample_is_reported_not_filled(self):
        rs = tuple(x for x in observations() if x.run_id != 43144695651)
        js = tuple(x for x in jobs() if x.run_id != 43144695651)
        r = checked(run_rows=rs, job_rows=js)
        self.assertFalse(r.all_hours_contiguous_in_sample)
        self.assertEqual(r.status, "OBSERVED_M5_HOUR_GAPS_RECHECK_REQUIRED")

    def test_28_output_is_research_only_and_inputs_are_not_mutated(self):
        rs=observations()
        js=jobs()
        old=(repr(rs),repr(js))
        self.assertEqual(checked(rs,js).status,
            "OBSERVED_GITHUB_JOB_STAGES_CONSISTENT_CAUSE_UNVERIFIED")
        self.assertEqual((repr(rs),repr(js)),old)


if __name__ == "__main__":
    from unittest import main
    main()
