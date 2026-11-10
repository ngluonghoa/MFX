"""A04/P0.36: 12 security and deterministic main-push CI status checks."""
from __future__ import annotations

import json
from pathlib import Path
import unittest
from urllib.request import Request

from forex_trading.catalog import ZONES, validate_catalog
from mfx_research.p030_approved_nonentry_design import read_22_zone_design_manifest
from mfx_research.p034_sim_adversarial_review import verify_owner_decision_dossier
from tools.postmain_ci_commit_status import (
    CONTEXT, DESCRIPTION, OFFICIAL_API, OFFICIAL_SERVER, REPOSITORY,
    build_main_push_status_request, publish_main_push_status,
)

CI = Path(".github/workflows/ci.yml")


def good_env() -> dict[str, str]:
    return {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "ngluonghoa/MFX",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "42777712345",
        "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_SERVER_URL": "https://github.com",
        "MFX_STATUS_TOKEN": "mock-ci-only-token-never-sent",
    }


def job_yaml() -> str:
    workflow = CI.read_text(encoding="utf-8")
    if workflow.count("\n  postmain-status:\n") != 1:
        raise AssertionError("P036_WORKFLOW_HAS_NO_SINGLE_MAIN_STATUS_JOB")
    return workflow.split("\n  postmain-status:\n")[1]


class P036PostMainStatusTests(unittest.TestCase):
    def test_01_workflow_original_pull_and_main_push_unchanged(self) -> None:
        text = CI.read_text(encoding="utf-8")
        self.assertIn("  pull_request:", text)
        self.assertIn("  push:\n    branches: [main]", text)
        self.assertIn("python-unittest:", text)
        self.assertIn("cross-python-wheel-parity:", text)

    def test_02_main_status_job_isolated_to_exact_push_branch_repo(self) -> None:
        text = job_yaml()
        self.assertIn("github.event_name == 'push'", text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn("github.repository == 'ngluonghoa/MFX'", text)
        self.assertIn("  postmain-status:", CI.read_text(encoding="utf-8"))

    def test_03_job_waits_for_python_matrix_and_wheel(self) -> None:
        text = job_yaml()
        self.assertIn("needs: [python-unittest, cross-python-wheel-parity]", text)
        self.assertIn("run: python -m tools.postmain_ci_commit_status", text)

    def test_04_status_permission_scoped_and_checkout_token_not_saved(self) -> None:
        text = job_yaml()
        self.assertIn("permissions:\n      contents: read\n      statuses: write",
                      text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("MFX_STATUS_TOKEN:", text)
        self.assertNotIn("issues: write", text)
        sender_source = Path("tools/postmain_ci_commit_status.py").read_text(encoding="utf-8")
        self.assertNotIn("urlopen(", sender_source)
        self.assertIn('HTTPSConnection("api.github.com", timeout=15)', sender_source)

    def test_05_exact_native_commit_context_payload_and_run_url(self) -> None:
        req, target = build_main_push_status_request(good_env())
        self.assertEqual(req.full_url,
                         OFFICIAL_API + "/repos/ngluonghoa/MFX/statuses/" +
                         "a" * 40)
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(target,
                         OFFICIAL_SERVER + "/ngluonghoa/MFX/actions/runs/42777712345")
        self.assertIsNotNone(req.data)
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload, {
            "state": "success", "context": CONTEXT,
            "description": DESCRIPTION, "target_url": target,
        })

    def test_06_no_token_in_public_status_payload(self) -> None:
        req, _ = build_main_push_status_request(good_env())
        assert req.data is not None
        raw = req.data.decode("utf-8")
        self.assertNotIn("mock-ci-only-token-never-sent", raw)
        self.assertNotIn("MFX_STATUS_TOKEN", raw)
        self.assertEqual(set(json.loads(raw)),
                         {"state", "context", "description", "target_url"})

    def test_07_invalid_git_sha_denied(self) -> None:
        for sha in ("x" * 40, "a" * 39, "A" * 40, "a" * 41, "", "0" * 8):
            v = good_env()
            v["GITHUB_SHA"] = sha
            with self.subTest(sha=sha), self.assertRaisesRegex(
                    ValueError, "P036_INVALID_EXACT_MAIN_COMMIT_SHA"):
                build_main_push_status_request(v)

    def test_08_pr_other_branch_or_repository_denied(self) -> None:
        for field, value in (
            ("GITHUB_EVENT_NAME", "pull_request"),
            ("GITHUB_EVENT_NAME", "workflow_dispatch"),
            ("GITHUB_REF", "refs/heads/feat/main"),
            ("GITHUB_REF", "refs/heads/release"),
            ("GITHUB_REPOSITORY", "attacker/MFX"),
        ):
            v = good_env()
            v[field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(
                    ValueError, "P036_ONLY_TRUSTED_MAIN_PUSH"):
                build_main_push_status_request(v)

    def test_09_bad_actions_run_id_denied(self) -> None:
        for rid in ("", "0", "-4", "00", "4.2", "a", "4" * 19):
            v = good_env()
            v["GITHUB_RUN_ID"] = rid
            with self.subTest(run=rid), self.assertRaisesRegex(
                    ValueError, "P036_INVALID_EXACT_ACTIONS_RUN_ID"):
                build_main_push_status_request(v)

    def test_10_api_server_or_missing_token_denied(self) -> None:
        for field, value, reason in (
            ("GITHUB_API_URL", "https://evil.test", "P036_UNTRUSTED"),
            ("GITHUB_SERVER_URL", "https://evil.test", "P036_UNTRUSTED"),
            ("MFX_STATUS_TOKEN", "", "P036_MISSING"),
            ("MFX_STATUS_TOKEN", "a\nb", "P036_MISSING"),
        ):
            v = good_env()
            v[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, reason):
                build_main_push_status_request(v)

    def test_11_injected_sender_201_only_and_no_real_network(self) -> None:
        requests: list[Request] = []

        def fake_sender(request: Request) -> int:
            requests.append(request)
            return 201

        target = publish_main_push_status(good_env(), sender=fake_sender)
        self.assertEqual(len(requests), 1)
        self.assertEqual(target, "https://github.com/ngluonghoa/MFX/actions/runs/42777712345")
        for fake in (lambda request: 200, lambda request: 403):
            with self.assertRaisesRegex(RuntimeError, "P036_NATIVE_COMMIT_STATUS"):
                publish_main_push_status(good_env(), sender=fake)

    def test_12_source_numeric_and_nontrading_gates_remain_unchanged(self) -> None:
        validate_catalog(ZONES)
        self.assertEqual(len(ZONES), 18)
        self.assertEqual(len(read_22_zone_design_manifest().zones), 22)
        owner = verify_owner_decision_dossier()
        self.assertEqual(owner.pending_owner_decisions, 36)
        self.assertEqual(owner.original_numeric_rules_approved, 0)
        self.assertFalse(owner.may_publish_confirmed_buy_sell)
        self.assertFalse(owner.may_release)
        self.assertEqual(REPOSITORY, "ngluonghoa/MFX")
        self.assertEqual(CONTEXT, "mfx/main-push-full-ci")


if __name__ == "__main__":
    unittest.main()
