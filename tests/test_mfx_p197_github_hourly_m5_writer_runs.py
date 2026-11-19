"""P0.197: adversarial hermetic GitHub M5 writer schedule evidence only."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from tools.audit_mfx_m5_writer_runs import (
    MAX_RUNS, checked_environment, inspect_writer_runs,
)

UTC = timezone.utc
ASOF = datetime(2026, 11, 19, 18, 0, tzinfo=UTC)
TOKEN = "synthetic-test-token-not-for-github"


def item(
    number=445000001, *, created="2026-11-19T17:10:00Z",
    started="2026-11-19T17:12:00Z",
    status="completed", conclusion="success",
    event="schedule", branch="main",
):
    return {
        "id": number,
        "event": event,
        "head_branch": branch,
        "created_at": created,
        "run_started_at": started,
        "status": status,
        "conclusion": conclusion,
        # Never print these even if GitHub returns untrusted contents.
        "name": "PRIVATE_PRICE_OPEN_HIGH_LOW_CLOSE",
        "display_title": "PRIVATE_VENDOR_TOKEN=private",
        "html_url": "https://example.invalid/secret",
    }


def inspect(*rows, asof=ASOF):
    return inspect_writer_runs(
        {"workflow_runs": list(rows)}, asof_utc=asof,
    )


class P197GitHubScheduledM5WriterHistoryTests(TestCase):
    def test_01_100percent_masked_github_only_schedule_proof(self):
        r = inspect(item())
        self.assertEqual(
            r["schema"], "MFX_P197_GITHUB_SCHEDULED_M5_WRITER_READONLY_V1")
        self.assertEqual(r["recent_schedule_runs_observed"], 1)
        self.assertEqual(r["latest_schedule_run_id"], 445000001)
        self.assertEqual(r["recent_completed_success"], 1)
        self.assertEqual(
            r["last_24_observed_run_summaries"][0][
                "observed_created_to_started_seconds"], 120)
        self.assertEqual(r["last_24_observed_run_summaries"][0][
            "created_clock_minute"], 10)
        self.assertFalse(r["missed_or_skipped_schedule_events_inferred"])
        self.assertFalse(r["provider_api_response_and_quota_proven"])
        self.assertFalse(r["drive_cache_write_timing_proven_by_this_report"])
        self.assertEqual((r["market_price_requests"],
                          r["drive_writes"], r["broker_orders"]), (0, 0, 0))
        self.assertEqual(r["signal_action"], "NO_SIGNAL")

    def test_02_detects_observed_failed_run_not_missed_slot(self):
        a = item(number=1, status="completed", conclusion="failure")
        b = item(number=2, created="2026-11-19T16:10:00Z",
                 started="2026-11-19T16:15:00Z")
        r = inspect(a, b)
        self.assertEqual(r["recent_completed_failed_cancelled_timedout"], 1)
        self.assertEqual(r["recent_completed_success"], 1)
        self.assertEqual(r["recent_schedule_runs_observed"], 2)
        self.assertFalse(r["nominal_cron_dispatch_slots_independently_attested"])

    def test_03_queued_without_start_has_unknown_wait_not_zero(self):
        r = inspect(item(status="queued", conclusion=None, started=None))
        self.assertIsNone(r["last_24_observed_run_summaries"][0][
            "observed_created_to_started_seconds"])
        self.assertEqual(r["recent_in_progress_or_queued"], 1)

    def test_04_non_scheduled_or_wrong_branch_does_not_count(self):
        r = inspect(item(event="workflow_dispatch"), item(
            number=3, branch="dev"))
        self.assertEqual(r["recent_schedule_runs_observed"], 0)
        self.assertIsNone(r["latest_schedule_run_id"])
        self.assertEqual(r["result"],
                         "NO_RECENT_RUNS_OBSERVED_REASON_UNKNOWN")

    def test_05_no_runs_is_not_imaginary_success(self):
        r = inspect()
        self.assertEqual(r["recent_completed_success"], 0)
        self.assertEqual(r["last_24_observed_run_summaries"], [])
        self.assertFalse(r["missed_or_skipped_schedule_events_inferred"])

    def test_06_old_run_outside_window_not_recent(self):
        r = inspect(item(created="2026-11-17T00:10:00Z",
                         started="2026-11-17T00:12:00Z"))
        self.assertEqual(r["recent_schedule_runs_observed"], 0)

    def test_07_deterministic_sort_by_created_then_run_id(self):
        one = item(number=10, created="2026-11-19T14:10:00Z",
                   started="2026-11-19T14:11:00Z")
        two = item(number=11, created="2026-11-19T15:12:00Z",
                   started="2026-11-19T15:15:00Z")
        r = inspect(one, two)
        self.assertEqual(
            [x["run_id"] for x in r["last_24_observed_run_summaries"]],
            [11, 10],
        )

    def test_08_untrusted_original_urls_and_private_metadata_not_logged(self):
        import json
        r = inspect(item())
        raw = json.dumps(r)
        for secret in ("PRIVATE_PRICE", "PRIVATE_VENDOR_TOKEN",
                       "example.invalid", TOKEN, "PRIVATE_PRICE_OPEN"):
            self.assertNotIn(secret, raw)
        self.assertNotIn('"open"', raw)
        self.assertNotIn('"close"', raw)

    def test_09_duplicate_schedule_id_denied(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            inspect(item(), deepcopy(item()))

    def test_10_invalid_or_future_metadata_denied(self):
        for bad in (
            item(number=0),
            item(created="2026-11-19T19:10:00Z"),
            item(created="2026-11-19T17:10:00+00:00"),
            item(status="fake"),
            item(conclusion="verified_buy"),
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                inspect(bad)

    def test_11_reversed_created_started_order_not_turned_into_wait(self):
        r = inspect(item(started="2026-11-19T17:09:00Z"))
        row = r["last_24_observed_run_summaries"][0]
        self.assertIsNone(row["observed_created_to_started_seconds"])
        self.assertFalse(row["created_started_clock_order_valid"])

    def test_12_more_than_one_page_denied_not_silently_complete(self):
        records = [item(number=i+1) for i in range(MAX_RUNS+1)]
        with self.assertRaisesRegex(ValueError, "BOUNDED"):
            inspect(*records)

    def test_13_naive_and_non_utc_asof_denied(self):
        for clock in (
            ASOF.replace(tzinfo=None),
            ASOF.astimezone(timezone(timedelta(hours=7))),
        ):
            with self.subTest(clock=clock), self.assertRaises(ValueError):
                inspect(item(), asof=clock)

    def test_14_context_validation_only_main_and_actions_read_token(self):
        base = {
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_REPOSITORY": "ngluonghoa/MFX",
            "GITHUB_API_URL": "https://api.github.com",
            "MFX_P197_ACTIONS_READ_TOKEN": TOKEN,
        }
        self.assertEqual(checked_environment(base), TOKEN)
        for key, val in (
            ("GITHUB_EVENT_NAME", "pull_request"),
            ("GITHUB_REF", "refs/heads/dev"),
            ("GITHUB_REPOSITORY", "other/MFX"),
            ("GITHUB_API_URL", "https://other.github.invalid"),
            ("MFX_P197_ACTIONS_READ_TOKEN", ""),
            ("MFX_P197_ACTIONS_READ_TOKEN", "bad\nkey"),
        ):
            tampered = dict(base)
            tampered[key] = val
            with self.subTest(key=key), self.assertRaises(ValueError):
                checked_environment(tampered)
