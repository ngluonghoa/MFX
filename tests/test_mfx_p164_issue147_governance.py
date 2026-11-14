"""P0.164 hermetic GitHub webhook checks, no remote provider/Drive access."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from unittest import TestCase
from unittest.mock import patch

from tools.check_mfx_p164_issue147_governance import (
    REPO, ISSUE_NUMBER, INCIDENT, audit_issue_event, main,
)


def event(action="reopened", *, number=ISSUE_NUMBER, state=None):
    return {
        "action": action,
        "repository": {"full_name": REPO},
        "issue": {
            "number": number,
            "state": state if state is not None else (
                "closed" if action == "closed" else "open"
            ),
        },
    }


class P0164SourceIssueGovernanceTests(TestCase):
    def test_01_reopened_hold_has_explicit_no_signal_state(self):
        result = audit_issue_event(event(), repo=REPO)
        self.assertEqual(
            result, "MFX_P164_ISSUE147_REOPENED_D1_HOLD_PRESERVED_NO_SIGNAL")

    def test_02_closed_hold_is_not_a_green_github_check(self):
        with self.assertRaisesRegex(ValueError, "PREMATURE_CLOSURE"):
            audit_issue_event(event("closed"), repo=REPO)

    def test_03_reject_mismatched_issue_action_and_state(self):
        for e in (event("closed", state="open"),
                  event("reopened", state="closed")):
            with self.subTest(e=e), self.assertRaisesRegex(
                ValueError, "EVENT_STATE_MISMATCH"):
                audit_issue_event(e, repo=REPO)

    def test_04_unrelated_issue_is_not_mutated_or_promoted(self):
        self.assertEqual(
            audit_issue_event(event(number=27), repo=REPO),
            "MFX_P164_OTHER_ISSUE_IGNORED",
        )

    def test_05_wrong_repo_or_payload_repo_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNTRUSTED"):
            audit_issue_event(event(), repo="other/repo")
        bad = event()
        bad["repository"]["full_name"] = "other/repo"
        with self.assertRaisesRegex(ValueError, "UNTRUSTED"):
            audit_issue_event(bad, repo=REPO)

    def test_06_invalid_action_rejected(self):
        for name in ("edited", "opened", "resolved", "closed; echo secret"):
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError, "UNTRUSTED"):
                audit_issue_event(event(name), repo=REPO)

    def test_07_missing_or_non_integer_issue_identifier_rejected(self):
        for n in (None, "147", 147.0, True):
            with self.subTest(n=n), self.assertRaisesRegex(
                ValueError, "ISSUE_NUMBER_TYPE"):
                audit_issue_event(event(number=n), repo=REPO)

    def test_08_missing_or_malformed_webhook_fields_denied(self):
        for payload in (None, [], {}, {"action": "closed"},
                        {"action": "closed", "repository": {}, "issue": {}}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                audit_issue_event(payload, repo=REPO)

    def test_09_known_incident_is_pinned(self):
        self.assertEqual(
            INCIDENT, "EURUSD_SYDNEY_D1_2026_11_11_NUMERIC_OHLC_1_OF_16")

    def test_10_unauthorized_source_hold_removal_is_detected(self):
        with patch(
            "tools.check_mfx_p164_issue147_governance."
            "D1_KNOWN_SOURCE_REVISION_HOLD", False,
        ), self.assertRaisesRegex(ValueError, "POLICY_DRIFT"):
            audit_issue_event(event(), repo=REPO)

    def test_11_unauthorized_incident_switch_is_detected(self):
        with patch(
            "tools.check_mfx_p164_issue147_governance."
            "D1_KNOWN_SOURCE_REVISION_INCIDENT", "fake",
        ), self.assertRaisesRegex(ValueError, "POLICY_DRIFT"):
            audit_issue_event(event(), repo=REPO)

    def test_12_main_reopened_webhook_only_emits_nonprice_safe_marker(self):
        output = StringIO()
        with patch.dict("os.environ", {
                "GITHUB_EVENT_NAME": "issues",
                "GITHUB_EVENT_PATH": "/github/workflow/event.json",
                "GITHUB_REPOSITORY": REPO,
            }, clear=True), patch(
                "pathlib.Path.stat",
            ) as stat, patch(
                "pathlib.Path.read_text",
                return_value=json.dumps(event()),
            ), redirect_stdout(output):
            stat.return_value.st_size = 512
            main()
        self.assertEqual(
            output.getvalue().strip(),
            "MFX_P164_ISSUE147_REOPENED_D1_HOLD_PRESERVED_NO_SIGNAL")

    def test_13_main_closed_webhook_fail_closed_and_redacted(self):
        output = StringIO()
        with patch.dict("os.environ", {
                "GITHUB_EVENT_NAME": "issues",
                "GITHUB_EVENT_PATH": "/github/workflow/event.json",
                "GITHUB_REPOSITORY": REPO,
            }, clear=True), patch(
                "pathlib.Path.stat",
            ) as stat, patch(
                "pathlib.Path.read_text",
                return_value=json.dumps(event("closed")),
            ), redirect_stdout(output):
            stat.return_value.st_size = 512
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertIn("AUDIT_FAILED_CLOSED", str(raised.exception))
        self.assertEqual(output.getvalue(), "")

    def test_14_non_issues_event_cannot_run(self):
        with patch.dict("os.environ", {
                "GITHUB_EVENT_NAME": "push",
                "GITHUB_REPOSITORY": REPO,
            }, clear=True), self.assertRaisesRegex(
                SystemExit, "GITHUB_ISSUES_EVENT_REQUIRED"):
            main()

    def test_15_missing_github_event_file_denied(self):
        with patch.dict("os.environ", {
                "GITHUB_EVENT_NAME": "issues",
                "GITHUB_REPOSITORY": REPO,
            }, clear=True), self.assertRaisesRegex(
                SystemExit, "EVENT_PATH_REQUIRED"):
            main()

    def test_16_oversized_webhook_denied_without_read(self):
        with patch.dict("os.environ", {
                "GITHUB_EVENT_NAME": "issues",
                "GITHUB_EVENT_PATH": "/github/workflow/event.json",
                "GITHUB_REPOSITORY": REPO,
            }, clear=True), patch(
                "pathlib.Path.stat",
            ) as stat, patch(
                "pathlib.Path.read_text",
                side_effect=AssertionError("MUST_NOT_READ_LARGE_EVENT"),
            ), self.assertRaisesRegex(
                SystemExit, "AUDIT_FAILED_CLOSED"):
            stat.return_value.st_size = 2_000_001
            main()
