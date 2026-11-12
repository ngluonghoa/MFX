"""A04/P0.89 source-version provenance: real REST identities, hermetic QA.

All GH IDs/HEADs are from 12 existing successful schedule run metadata.
The SHA fixture authenticates only to the extent of independently reviewed
source fetches; these tests themselves never contact GitHub or Drive.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from test_a04_p87_m5_schedule_cohort import observations, dt
from test_a04_p88_m5_job_lifecycle_evidence import jobs
from tools.mfx_m5_schedule_source_provenance import (
    SCHEMA, REPOSITORY, WORKFLOW_PATH, WORKFLOW_ID, WORKFLOW_BLOB_SHA,
    CRON_EXPRESSION_IN_SOURCE, ObservedRunSource,
    classify_schedule_source_provenance,
)

HEADS = {
    43158866760: "d61fe9ecb7c4214699f3d027e17fabada42a3b63",
    43151652891: "9e9c76a47eaf769e4104600796c87c8dcd247621",
    43144695651: "f19c78e0892c5bf4790762ccf1459f55f2cf5db8",
    43133264975: "4c60644d0a812eabee0e89519a29e1cce9731b61",
    43123068939: "4c60644d0a812eabee0e89519a29e1cce9731b61",
    43115786422: "4c60644d0a812eabee0e89519a29e1cce9731b61",
    43105022518: "4c60644d0a812eabee0e89519a29e1cce9731b61",
    43092969245: "4c60644d0a812eabee0e89519a29e1cce9731b61",
    43082949666: "4c60644d0a812eabee0e89519a29e1cce9731b61",
    43073227903: "627509cc4971b3222ccdfc97eba93d85b14fb44c",
    43063687329: "61cd36e04e0e2eb73de1e38fb2b42af71040310f",
    43053200735: "28dd1d617a7223196f85d612b221ea5cccea8563",
}


def metadata() -> tuple[ObservedRunSource, ...]:
    return tuple(
        ObservedRunSource(
            run_id=run.run_id,
            run_attempt=1,
            event_name="schedule",
            workflow_id=WORKFLOW_ID,
            workflow_path=WORKFLOW_PATH,
            repository=REPOSITORY,
            head_sha=HEADS[run.run_id],
            checked_workflow_blob_sha=WORKFLOW_BLOB_SHA,
            created_at_utc=run.run_created_utc,
            run_started_at_utc=run.run_created_utc,
            conclusion="success",
        )
        for run in observations()
    )


def checked(runs=None, observed_jobs=None, sources=None):
    return classify_schedule_source_provenance(
        observations() if runs is None else runs,
        jobs() if observed_jobs is None else observed_jobs,
        metadata() if sources is None else sources,
    )


class M5ScheduleSourceProvenanceTests(TestCase):
    def test_01_12_observed_runs_14_batches(self):
        r = checked()
        self.assertEqual((r.run_count,r.observed_manifest_count),(12,14))
        self.assertEqual(r.schema,SCHEMA)

    def test_02_seven_distinct_github_heads_one_workflow_blob(self):
        r = checked()
        self.assertEqual(r.unique_head_commits_in_sample,7)
        self.assertEqual(r.distinct_workflow_blobs_in_sample,1)
        self.assertTrue(r.source_blob_identity_matches_pinned_review)

    def test_03_reviewed_workflow_config_pins(self):
        self.assertEqual(WORKFLOW_BLOB_SHA,
                         "c506c0c7212e17d20ea22090e1887fd8aa7bf38b")
        self.assertEqual(WORKFLOW_ID,413180668)
        self.assertEqual(CRON_EXPRESSION_IN_SOURCE,"10 * * * *")
        self.assertEqual(checked().source_controlled_cron_expression,"10 * * * *")

    def test_04_gh_run_started_equals_created_not_event_origin(self):
        r=checked()
        self.assertEqual(r.median_run_created_to_run_started_seconds,0)
        self.assertFalse(r.actual_scheduled_tick_utc_authenticated)
        self.assertFalse(r.internal_github_event_dispatch_utc_observed)

    def test_05_queue_3_seconds_runtime_22_point_5(self):
        r=checked()
        self.assertEqual(r.median_job_created_to_started_seconds,3)
        self.assertEqual(r.median_job_started_to_finished_seconds,22.5)

    def test_06_all_events_consistent_no_gaps(self):
        r=checked()
        self.assertEqual(r.status,"P089_WORKFLOW_BLOB_SAME_CAUSAL_ORIGIN_UNVERIFIED")
        self.assertEqual(r.historical_unverified_hour_gaps_in_sample,0)
        self.assertEqual(r.retry_attempts_need_separate_review,0)

    def test_07_original_scheduler_cause_unproven(self):
        r=checked()
        self.assertFalse(r.externally_authenticated_source_and_event_receipt)
        self.assertFalse(r.concurrency_wait_before_run_created_proven)
        self.assertFalse(r.gh_scheduler_root_cause_proven)
        self.assertFalse(r.vendor_first_available_candle_utc_observed)

    def test_08_never_authorize_prod_writes_h4_or_broker(self):
        r=checked()
        self.assertFalse(r.cron_or_workflow_change_authorized)
        self.assertFalse(r.provider_probe_authorized)
        self.assertFalse(r.live_cache_writer_change_authorized)
        self.assertFalse(r.native_h4_replacement_authorized)
        self.assertFalse(r.external_witness_cas_authorized)
        self.assertFalse(r.numeric_trading_or_broker_authorized)
        self.assertEqual((r.provider_calls_by_this_module,
                          r.drive_writes_by_this_module,
                          r.broker_orders_by_this_module),(0,0,0))

    def test_09_shuffled_run_source_order_uses_id_join(self):
        self.assertEqual(checked().run_count,
                         checked(sources=tuple(reversed(metadata()))).run_count)

    def test_10_missing_source_row_denied(self):
        with self.assertRaisesRegex(ValueError,"COHORT_BOUND"):
            checked(sources=metadata()[:-1])

    def test_11_empty_sources_denied(self):
        with self.assertRaisesRegex(ValueError,"COHORT_BOUND"):
            checked(sources=())

    def test_12_list_not_tuple_denied(self):
        with self.assertRaisesRegex(ValueError,"COHORT_BOUND"):
            checked(sources=list(metadata()))

    def test_13_duplicate_run_id_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(m[0],replace(m[1],run_id=m[0].run_id))+m[2:])

    def test_14_unknown_run_id_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"COVERAGE"):
            checked(sources=(replace(m[0],run_id=999999),)+m[1:])

    def test_15_wrong_event_type_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],event_name="workflow_dispatch"),)+m[1:])

    def test_16_wrong_workflow_id_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],workflow_id=413180669),)+m[1:])

    def test_17_boolean_workflow_id_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],workflow_id=True),)+m[1:])

    def test_18_wrong_repo_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],repository="fork/MFX"),)+m[1:])

    def test_19_wrong_workflow_path_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],
                workflow_path=".github/workflows/ci.yml"),)+m[1:])

    def test_20_changed_workflow_blob_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],
                checked_workflow_blob_sha="f"*40),)+m[1:])

    def test_21_nonhex_head_sha_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],head_sha="bad"),)+m[1:])

    def test_22_uppercase_head_sha_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],head_sha="F"*40),)+m[1:])

    def test_23_failed_conclusion_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],conclusion="cancelled"),)+m[1:])

    def test_24_zero_attempt_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],run_attempt=0),)+m[1:])

    def test_25_boolean_attempt_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],run_attempt=True),)+m[1:])

    def test_26_later_attempt_only_recheck_not_promote(self):
        m=metadata()
        r=checked(sources=(replace(m[0],run_attempt=2),)+m[1:])
        self.assertEqual(r.status,"P089_RETRY_ATTEMPT_RECHECK_REQUIRED")
        self.assertEqual(r.retry_attempts_need_separate_review,1)
        self.assertFalse(r.gh_scheduler_root_cause_proven)

    def test_27_naive_created_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],
                created_at_utc=datetime(2026,11,12,5,4,6)),)+m[1:])

    def test_28_nonutc_offset_denied(self):
        m=metadata()
        other_tz=timezone(timedelta(hours=7))
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],
                run_started_at_utc=m[0].run_started_at_utc.astimezone(other_tz)),)+m[1:])

    def test_29_run_created_timestamp_mismatch_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"CLOCK_JOIN"):
            checked(sources=(replace(m[0],
                created_at_utc=m[0].created_at_utc+timedelta(seconds=1)),)+m[1:])

    def test_30_run_started_before_created_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"CLOCK_JOIN"):
            checked(sources=(replace(m[0],
                run_started_at_utc=m[0].created_at_utc-timedelta(seconds=1)),)+m[1:])

    def test_31_run_started_after_job_started_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"CLOCK_JOIN"):
            checked(sources=(replace(m[0],
                run_started_at_utc=m[0].created_at_utc+timedelta(seconds=6)),)+m[1:])

    def test_32_missing_middle_hour_is_not_concealed(self):
        rs=tuple(x for x in observations() if x.run_id!=43144695651)
        js=tuple(x for x in jobs() if x.run_id!=43144695651)
        ms=tuple(x for x in metadata() if x.run_id!=43144695651)
        r=checked(runs=rs,observed_jobs=js,sources=ms)
        self.assertEqual(r.status,"P089_OBSERVED_HOURLY_GAPS_RECHECK_REQUIRED")
        self.assertEqual(r.historical_unverified_hour_gaps_in_sample,1)

    def test_33_boolean_run_id_denied(self):
        m=metadata()
        with self.assertRaisesRegex(ValueError,"SOURCE_EVENT_OR_CONFIG"):
            checked(sources=(replace(m[0],run_id=True),)+m[1:])

    def test_34_safe_pure_receipt_no_user_data_or_mutation(self):
        rs=observations()
        js=jobs()
        ms=metadata()
        old=(repr(rs),repr(js),repr(ms))
        r=checked(rs,js,ms)
        self.assertEqual((repr(rs),repr(js),repr(ms)),old)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY",repr(r))
        self.assertNotIn("MFX_GDRIVE_OAUTH_REFRESH_TOKEN",repr(r))
        self.assertEqual(r.provider_calls_by_this_module,0)


if __name__=="__main__":
    from unittest import main
    main()
