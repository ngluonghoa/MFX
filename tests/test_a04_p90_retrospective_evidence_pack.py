"""A04/P0.90: SHA-pinned historical cross-plane evidence, hermetic guards."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from test_a04_p87_m5_schedule_cohort import observations
from test_a04_p88_m5_job_lifecycle_evidence import jobs
from test_a04_p89_schedule_source_provenance import metadata
from tools.mfx_m5_retrospective_evidence_pack import (
    AUDIT_ATTEMPT, AUDIT_FINISHED_UTC, AUDIT_HEAD_HOUR_UTC,
    AUDIT_HEAD_SHA256, AUDIT_JOB_ID, AUDIT_MARKER, AUDIT_RUN_ID,
    SCHEMA, ObservedReviewedFullM5Audit,
    correlate_pinned_historical_m5_evidence,
)


def audit() -> ObservedReviewedFullM5Audit:
    return ObservedReviewedFullM5Audit(
        audit_run_id=AUDIT_RUN_ID, attempt=AUDIT_ATTEMPT, job_id=AUDIT_JOB_ID,
        pass_marker=AUDIT_MARKER, finished_utc=AUDIT_FINISHED_UTC,
        head_hour_utc=AUDIT_HEAD_HOUR_UTC,
        head_manifest_sha256=AUDIT_HEAD_SHA256,
        full_sha_manifest_chunk_pairs=40, closed_m5_bars=480,
        full_bounded_chain_verified=True, native_h4_archive_pairs=8,
        native_h4_closed_bars=126, exact_complete_h4_matches=9,
        h4_mismatches=0, provider_requests=0, drive_writes=0, broker_orders=0,
    )


def receipt(rs=None, js=None, ms=None, a=None, asof=None):
    return correlate_pinned_historical_m5_evidence(
        observations() if rs is None else rs,
        jobs() if js is None else js,
        metadata() if ms is None else ms,
        audit() if a is None else a,
        report_as_of_utc=(AUDIT_FINISHED_UTC + timedelta(seconds=1)
                          if asof is None else asof),
    )


class RetrospectiveCrossPlaneTests(TestCase):
    def test_01_source_archive_join(self):
        r = receipt()
        self.assertEqual(r.schema, SCHEMA)
        self.assertEqual((r.reviewed_scheduled_run_count,
                          r.reviewed_manifest_batch_count,
                          r.reviewed_unique_source_heads), (12, 14, 7))

    def test_02_reviewed_40_pairs_480_bars_pinned(self):
        r = receipt()
        self.assertEqual((r.historical_full_sha_pairs,
                          r.historical_closed_m5_bars), (40, 480))
        self.assertEqual(r.historical_head_sha256, AUDIT_HEAD_SHA256)

    def test_03_reviewed_h4_not_promoted(self):
        r = receipt()
        self.assertEqual(r.historical_h4_exact_matches, 9)
        self.assertFalse(r.native_h4_source_replacement_authorized)

    def test_04_unverified_clock_and_causality(self):
        r = receipt()
        self.assertFalse(r.actual_github_cron_event_dispatch_utc_attested)
        self.assertFalse(r.vendor_first_available_utc_attested)
        self.assertFalse(r.gh_scheduler_root_cause_proven)
        self.assertEqual(r.source_cron_expression, "10 * * * *")

    def test_05_not_a_fresh_current_sha_scan(self):
        r = receipt()
        self.assertFalse(r.independently_authenticated_this_invocation)
        self.assertFalse(r.latest_current_cache_head_verified)
        self.assertIn("CURRENT_HEAD_UNPROVEN", r.status)

    def test_06_no_vendor_storage_rights_assumed(self):
        r = receipt()
        self.assertFalse(r.provider_license_and_calendar_verified)
        self.assertFalse(r.missing_market_session_gap_proven)

    def test_07_prod_changes_denied(self):
        r = receipt()
        self.assertFalse(r.production_cron_edit_authorized)
        self.assertFalse(r.live_v2_witness_or_writer_authorized)
        self.assertFalse(r.numeric_buy_sell_or_broker_authorized)

    def test_08_module_pure_and_no_keys(self):
        r = receipt()
        self.assertEqual((r.provider_calls_by_this_module,
                          r.drive_writes_by_this_module,
                          r.broker_orders_by_this_module), (0, 0, 0))
        self.assertNotIn("OAUTH", repr(r))

    def test_09_elapsed_from_historical_audit_not_freshness(self):
        r = receipt(asof=AUDIT_FINISHED_UTC + timedelta(days=2))
        self.assertEqual(r.time_since_historical_audit_seconds, 172800)
        self.assertFalse(r.latest_current_cache_head_verified)

    def test_10_strict_audit_run_id(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), audit_run_id=AUDIT_RUN_ID + 1))

    def test_11_bool_run_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), audit_run_id=True))

    def test_12_attempt_mismatch(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), attempt=3))

    def test_13_job_mismatch(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), job_id=123))

    def test_14_false_pass_marker(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), pass_marker="SUCCESS"))

    def test_15_modified_historical_sha_denied(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), head_manifest_sha256="0"*64))

    def test_16_different_archive_hour_denied(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), head_hour_utc=AUDIT_HEAD_HOUR_UTC
                              + timedelta(hours=1)))

    def test_17_m5_bars_mismatch(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), closed_m5_bars=468))

    def test_18_not_a_full_chain_denied(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), full_bounded_chain_verified=False))

    def test_19_h4_mismatch_denied(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), h4_mismatches=1))

    def test_20_h4_count_mismatch_denied(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), exact_complete_h4_matches=30))

    def test_21_faked_drive_write_denied(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), drive_writes=1))

    def test_22_faked_provider_call_denied(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), provider_requests=1))

    def test_23_naive_asof_denied(self):
        with self.assertRaisesRegex(ValueError, "HISTORICAL_ASOF"):
            receipt(asof=datetime(2026,11,12,10,24))

    def test_24_before_audit_complete_denied(self):
        with self.assertRaisesRegex(ValueError, "HISTORICAL_ASOF"):
            receipt(asof=AUDIT_FINISHED_UTC-timedelta(seconds=1))

    def test_25_modified_historical_time_denied(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), finished_utc=AUDIT_FINISHED_UTC
                              -timedelta(seconds=1)))

    def test_26_source_head_swap_denied(self):
        m = metadata()
        with self.assertRaisesRegex(ValueError, "RUN_HEAD_SUBSTITUTION"):
            receipt(ms=(replace(m[0], head_sha=m[-1].head_sha),) + m[1:])

    def test_27_substitute_one_run_id_denied(self):
        m = metadata()
        with self.assertRaises(ValueError):
            receipt(ms=(replace(m[0], run_id=999),) + m[1:])

    def test_28_missing_run_denied(self):
        with self.assertRaises(ValueError):
            receipt(rs=observations()[:-1],
                    js=jobs()[:-1], ms=metadata()[:-1])

    def test_29_bad_workflow_blob_denied(self):
        m = metadata()
        with self.assertRaises(ValueError):
            receipt(ms=(replace(m[0], checked_workflow_blob_sha="f"*40),)+m[1:])

    def test_30_utc_offset_not_utc_denied(self):
        z = timezone(timedelta(hours=7))
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(),
                              finished_utc=AUDIT_FINISHED_UTC.astimezone(z)))

    def test_31_audit_bool_zero_integer_field_denied(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), broker_orders=False))

    def test_32_audit_bool_closed_count_denied(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_PIN"):
            receipt(a=replace(audit(), closed_m5_bars=True))

    def test_33_mutable_input_not_modified(self):
        rs, js, ms, a = observations(), jobs(), metadata(), audit()
        original = (repr(rs), repr(js), repr(ms), repr(a))
        receipt(rs, js, ms, a)
        self.assertEqual((repr(rs), repr(js), repr(ms), repr(a)), original)

    def test_34_report_timestamp_future_never_upgrades_to_live(self):
        r = receipt(asof=AUDIT_FINISHED_UTC+timedelta(days=365))
        self.assertFalse(r.latest_current_cache_head_verified)
        self.assertFalse(r.live_v2_witness_or_writer_authorized)


if __name__ == "__main__":
    from unittest import main
    main()
