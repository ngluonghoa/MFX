"""P0.37: eight isolated read-only exact-main-push evidence tests (no HTTP)."""
from __future__ import annotations

from pathlib import Path
import unittest

from forex_trading.catalog import ZONES, validate_catalog
from mfx_research.p030_approved_nonentry_design import read_22_zone_design_manifest
from mfx_research.p034_sim_adversarial_review import verify_owner_decision_dossier
from tools.read_main_push_ci_diagnostic import (
    CONTEXT, REPO, checked_main_sha, inspect_main_push,
    summarize_push_evidence, validate_read_env,
)


def env() -> dict[str, str]:
    return {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_API_URL": "https://api.github.com",
        "P037_READ_TOKEN": "mock-not-network-token",
    }


def data(sha: str = "a" * 40, *, state: str = "success") -> tuple[dict, dict, list]:
    runs = {"workflow_runs": [{
        "id": 1234567, "event": "push", "head_branch": "main",
        "head_sha": sha, "name": "MFX 1:1 parity CI and artifact smoke",
        "status": "completed", "conclusion": state,
    }]}
    jobs = {"jobs": [
        {"id": 1, "name": "python-unittest (3.11)", "status": "completed",
         "conclusion": "success"},
        {"id": 2, "name": "python-unittest (3.12)", "status": "completed",
         "conclusion": "success"},
        {"id": 3, "name": "Cross-Python wheel parity (3.11 / 3.12)",
         "status": "completed", "conclusion": "success"},
        {"id": 4, "name": "Publish independently readable main-push CI status (NO release)",
         "status": "completed", "conclusion": "success"},
    ]}
    statuses = [{
        "context": CONTEXT, "state": "success",
        "target_url": "https://github.com/ngluonghoa/MFX/actions/runs/1234567",
    }]
    return runs, jobs, statuses


class P037ReadOnlyMainPushDiagnosticsTests(unittest.TestCase):
    def test_01_ci_diagnostic_job_is_only_for_pr_not_push(self) -> None:
        text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertEqual(text.count("\n  p037-read-main-push:\n"), 1)
        diag = text.split("\n  p037-read-main-push:\n")[1]
        self.assertIn("github.event_name == 'pull_request'", diag)
        self.assertIn("github.repository == 'ngluonghoa/MFX'", diag)
        self.assertIn("actions: read", diag)
        self.assertIn("persist-credentials: false", diag)
        self.assertIn("run: python -m tools.read_main_push_ci_diagnostic", diag)

    def test_02_denies_untrusted_event_repo_or_api(self) -> None:
        for key, val in (
            ("GITHUB_EVENT_NAME", "push"),
            ("GITHUB_REPOSITORY", "fork/MFX"),
            ("GITHUB_API_URL", "https://evil.test"),
        ):
            e = env()
            e[key] = val
            with self.subTest(key=key), self.assertRaisesRegex(
                ValueError, "P037_TRUSTED_PR_GITHUB"
            ):
                validate_read_env(e)

    def test_03_credentials_not_printed_and_reject_missing(self) -> None:
        bad = env()
        bad["P037_READ_TOKEN"] = ""
        with self.assertRaisesRegex(ValueError, "P037_INVALID_SCOPED_READ_TOKEN"):
            validate_read_env(bad)
        text = Path("tools/read_main_push_ci_diagnostic.py").read_text(encoding="utf-8")
        self.assertNotIn("print(token)", text)
        self.assertNotIn("urlopen(", text)
        self.assertIn("build_opener(ProxyHandler(), NoRedirect())", text)

    def test_04_strict_main_sha_and_required_source_coverage(self) -> None:
        self.assertEqual(checked_main_sha("a" * 40), "a" * 40)
        for sha in ("A" * 40, "a" * 39, "z" * 40, None):
            with self.assertRaisesRegex(ValueError, "P037_INVALID_EXACT_MAIN_SHA"):
                checked_main_sha(sha)

    def test_05_valid_actual_run_four_jobs_and_status_required(self) -> None:
        sha = "a" * 40
        runs, jobs, statuses = data(sha)
        report = summarize_push_evidence(sha, runs, jobs, statuses)
        self.assertTrue(report["push_jobs_and_native_status_verified"])
        self.assertEqual(len(report["selected_run_jobs"]), 4)
        self.assertEqual(report["matching_push_runs"][0]["id"], 1234567)
        self.assertEqual(report["native_statuses"][0]["context"], CONTEXT)

    def test_06_missing_status_failed_job_or_run_denied(self) -> None:
        sha = "a" * 40
        r, j, s = data(sha)
        self.assertFalse(summarize_push_evidence(sha, r, j, [])[
            "push_jobs_and_native_status_verified"])
        r, j, s = data(sha, state="failure")
        self.assertFalse(summarize_push_evidence(sha, r, j, s)[
            "push_jobs_and_native_status_verified"])
        r, j, s = data(sha)
        j["jobs"][2]["conclusion"] = "failure"
        self.assertFalse(summarize_push_evidence(sha, r, j, s)[
            "push_jobs_and_native_status_verified"])
        r, j, s = data("b" * 40)
        self.assertFalse(summarize_push_evidence(sha, r, j, s)[
            "push_jobs_and_native_status_verified"])

    def test_07_mocked_four_gets_exact_repo_sha_and_no_network(self) -> None:
        sha = "a" * 40
        runs, jobs, statuses = data(sha)
        seen: list[str] = []

        def fake(path: str):
            seen.append(path)
            if path.endswith("/branches/main"):
                return {"commit": {"sha": sha}}
            if "/actions/runs?" in path:
                return runs
            if "/jobs?" in path:
                return jobs
            if "/statuses?" in path:
                return statuses
            raise AssertionError("unrequested API path: " + path)

        report = inspect_main_push(env(), sender=fake)
        self.assertTrue(report["push_jobs_and_native_status_verified"])
        self.assertEqual(len(seen), 4)
        self.assertTrue(all(x.startswith("/repos/ngluonghoa/MFX/") for x in seen))

    def test_08_inherited_source_numeric_governance_unmodified(self) -> None:
        validate_catalog(ZONES)
        self.assertEqual(len(ZONES), 18)
        self.assertEqual(len(read_22_zone_design_manifest().zones), 22)
        owner = verify_owner_decision_dossier()
        self.assertEqual(owner.pending_owner_decisions, 36)
        self.assertEqual(owner.original_numeric_rules_approved, 0)
        self.assertFalse(owner.may_release)


if __name__ == "__main__":
    unittest.main()
