"""P0.199 hermetic PR-only native H4/D1 writer GH metadata tests."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from unittest import TestCase

from tools.audit_mfx_m5_writer_runs import (
    NATIVE_EXPECTED_CRON_MINUTE, NATIVE_WRITER_WORKFLOW,
    inspect_writer_runs,
)
from tools.read_mfx_native_writer_runs_from_pr import (
    NATIVE_PATH, inspect_native_writer_from_pr,
)
from test_mfx_p197_github_hourly_m5_writer_runs import item

ASOF = datetime(2026, 11, 19, 18, 0, tzinfo=timezone.utc)
ENV = {
    "GITHUB_EVENT_NAME": "pull_request",
    "GITHUB_REPOSITORY": "ngluonghoa/MFX",
    "GITHUB_API_URL": "https://api.github.com",
    "P037_READ_TOKEN": "synthetic-actions-read-token-do-not-output",
}


class P199NativeWriterGitHubReadOnlyHistoryTests(TestCase):
    def test_01_exact_native_writer_schedule_scope_and_status(self):
        calls = []
        def send(path):
            calls.append(path)
            return {"workflow_runs": [
                item(123456789, created="2026-11-19T17:25:00Z",
                     started="2026-11-19T17:25:25Z"),
            ]}
        r = inspect_native_writer_from_pr(
            ENV, now_utc=ASOF, sender=send)
        self.assertEqual(calls, [NATIVE_PATH])
        self.assertEqual(r["workflow"], NATIVE_WRITER_WORKFLOW)
        self.assertEqual(r["nominal_cron_utc_minute"],
                         NATIVE_EXPECTED_CRON_MINUTE)
        self.assertEqual(r["schema"],
                         "MFX_P199_GITHUB_SCHEDULED_NATIVE_WRITER_READONLY_V1")
        self.assertEqual(r["latest_schedule_run_id"], 123456789)
        self.assertEqual(r["recent_completed_success"], 1)
        self.assertFalse(r["missed_or_skipped_schedule_events_inferred"])
        self.assertFalse(r["provider_api_response_and_quota_proven"])
        self.assertFalse(r["drive_cache_write_timing_proven_by_this_report"])
        self.assertEqual((r["market_price_requests"],
                          r["drive_writes"],r["broker_orders"]), (0, 0, 0))

    def test_02_refuse_unreviewed_workflow_or_mislabelled_cron(self):
        with self.assertRaisesRegex(ValueError, "P199_UNREVIEWED"):
            inspect_writer_runs(
                {"workflow_runs": []}, asof_utc=ASOF,
                workflow="arbitrary-user-workflow.yml",
                expected_cron_minute=25,
            )
        with self.assertRaisesRegex(ValueError, "P199_UNREVIEWED"):
            inspect_writer_runs(
                {"workflow_runs": []}, asof_utc=ASOF,
                workflow=NATIVE_WRITER_WORKFLOW,
                expected_cron_minute=10,
            )

    def test_03_invalid_pr_token_prevents_any_github_api_read(self):
        x = dict(ENV)
        x["P037_READ_TOKEN"] = ""
        seen = []
        with self.assertRaises(ValueError):
            inspect_native_writer_from_pr(
                x, now_utc=ASOF,
                sender=lambda path: seen.append(path),
            )
        self.assertEqual(seen, [])

    def test_04_an_empty_schedule_history_is_not_a_green_source(self):
        r = inspect_native_writer_from_pr(
            ENV, now_utc=ASOF, sender=lambda _: {"workflow_runs": []})
        self.assertEqual(r["recent_schedule_runs_observed"], 0)
        self.assertEqual(r["result"],
                         "NO_RECENT_RUNS_OBSERVED_REASON_UNKNOWN")
        self.assertFalse(r["may_publish_buy_sell"])

    def test_05_no_source_prices_or_oauth_secret_in_diagnostic_output(self):
        r = inspect_native_writer_from_pr(
            ENV, now_utc=ASOF, sender=lambda _: {"workflow_runs": [item()]})
        serialized = json.dumps(r)
        self.assertNotIn(ENV["P037_READ_TOKEN"], serialized)
        self.assertNotIn("PRIVATE_PRICE_OPEN_HIGH_LOW_CLOSE", serialized)
        self.assertNotIn('"open"',serialized)
        self.assertEqual(r["signal_action"], "NO_SIGNAL")
