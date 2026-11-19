"""P0.198 hermetic tests of PR-only GitHub M5 writer run enumeration."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase
import json

from tools.audit_mfx_m5_writer_runs import _FIXED_PATH
from tools.read_mfx_m5_writer_runs_from_pr import inspect_pr_writer_runs
from test_mfx_p197_github_hourly_m5_writer_runs import item

UTC = timezone.utc
ASOF = datetime(2026, 11, 19, 18, 0, tzinfo=UTC)
ENV = {
    "GITHUB_EVENT_NAME": "pull_request",
    "GITHUB_REPOSITORY": "ngluonghoa/MFX",
    "GITHUB_API_URL": "https://api.github.com",
    "P037_READ_TOKEN": "test-opaque-actions-read-token-no-secret",
}


class P198PrOnlyM5WriterActualRunMetadataTests(TestCase):
    def test_01_calls_only_the_fixed_existing_writer_history_endpoint(self):
        called = []
        def send(path):
            called.append(path)
            return {"workflow_runs": [item()]}
        result = inspect_pr_writer_runs(ENV, now_utc=ASOF, sender=send)
        self.assertEqual(called, [_FIXED_PATH])
        self.assertEqual(result["latest_schedule_run_id"], 445000001)
        self.assertEqual(result["recent_completed_success"], 1)
        self.assertFalse(result["missed_or_skipped_schedule_events_inferred"])
        self.assertFalse(result["provider_api_response_and_quota_proven"])
        self.assertEqual(result["signal_action"], "NO_SIGNAL")

    def test_02_observed_failed_job_does_not_infer_provider_or_skip(self):
        result = inspect_pr_writer_runs(
            ENV, now_utc=ASOF,
            sender=lambda _: {"workflow_runs": [
                item(status="completed", conclusion="failure"),
            ]},
        )
        self.assertEqual(result["recent_completed_failed_cancelled_timedout"], 1)
        self.assertFalse(result["nominal_cron_dispatch_slots_independently_attested"])
        self.assertFalse(result["drive_cache_write_timing_proven_by_this_report"])

    def test_03_missing_or_malformed_history_fails_closed(self):
        with self.assertRaises(ValueError):
            inspect_pr_writer_runs(
                ENV, now_utc=ASOF, sender=lambda _: {"success": True},
            )

    def test_04_pr_token_and_repository_required_before_any_http_call(self):
        for k, v in (
            ("GITHUB_EVENT_NAME", "schedule"),
            ("GITHUB_REPOSITORY", "outsider/repo"),
            ("GITHUB_API_URL", "http://example.invalid"),
            ("P037_READ_TOKEN", ""),
        ):
            invalid = dict(ENV)
            invalid[k] = v
            touched = []
            with self.subTest(key=k), self.assertRaises(ValueError):
                inspect_pr_writer_runs(
                    invalid, now_utc=ASOF,
                    sender=lambda p: touched.append(p),
                )
            self.assertEqual(touched, [])

    def test_05_no_api_secret_or_untrusted_price_in_summary(self):
        result = inspect_pr_writer_runs(
            ENV, now_utc=ASOF, sender=lambda _: {"workflow_runs": [item()]})
        printed = json.dumps(result)
        self.assertNotIn(ENV["P037_READ_TOKEN"], printed)
        self.assertNotIn("PRIVATE_PRICE_OPEN_HIGH_LOW_CLOSE", printed)
        self.assertNotIn("example.invalid", printed)
        self.assertEqual(result["market_price_requests"], 0)
        self.assertEqual(result["drive_writes"], 0)
        self.assertEqual(result["broker_orders"], 0)
