"""A04/P0.36 — publish a verifiable native GitHub MAIN-push CI commit status.

The GitHub Actions job calls this ONLY after Python 3.11/3.12 unittests and
cross-Python wheel parity succeed. This is GitHub-hosted CI traceability, NOT
owner-verified Forex numerics, a cryptographic signature or release approval.
All public test callers inject a fake sender; NO network calls in unittests.
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable, Mapping
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

CONTEXT = "mfx/main-push-full-ci"
REPOSITORY = "ngluonghoa/MFX"
MAIN_REF = "refs/heads/main"
OFFICIAL_API = "https://api.github.com"
OFFICIAL_SERVER = "https://github.com"
DESCRIPTION = "Main push CI: Python 3.11 + 3.12 + wheel parity passed"


def build_main_push_status_request(env: Mapping[str, str]) -> tuple[Request, str]:
    """Reject PR/untrusted branch, invalid SHA or spoofed API host *before* POST."""
    if (env.get("GITHUB_EVENT_NAME") != "push"
            or env.get("GITHUB_REF") != MAIN_REF
            or env.get("GITHUB_REPOSITORY") != REPOSITORY):
        raise ValueError("P036_ONLY_TRUSTED_MAIN_PUSH_MAY_ATTEST")
    sha = env.get("GITHUB_SHA", "")
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise ValueError("P036_INVALID_EXACT_MAIN_COMMIT_SHA")
    raw_run_id = env.get("GITHUB_RUN_ID", "")
    if (re.fullmatch(r"[1-9][0-9]{0,17}", raw_run_id) is None
            or int(raw_run_id) > 9223372036854775807):
        raise ValueError("P036_INVALID_EXACT_ACTIONS_RUN_ID")
    if (env.get("GITHUB_API_URL") != OFFICIAL_API
            or env.get("GITHUB_SERVER_URL") != OFFICIAL_SERVER):
        raise ValueError("P036_UNTRUSTED_GITHUB_STATUS_ENDPOINT")
    token = env.get("MFX_STATUS_TOKEN", "")
    if (not token or token.strip() != token
            or len(token) > 4096 or any(ord(c) <= 32 for c in token)):
        raise ValueError("P036_MISSING_OR_INVALID_SCOPED_GITHUB_TOKEN")

    target = f"{OFFICIAL_SERVER}/{REPOSITORY}/actions/runs/{raw_run_id}"
    data = {
        "state": "success",
        "context": CONTEXT,
        "description": DESCRIPTION,
        "target_url": target,
    }
    request = Request(
        f"{OFFICIAL_API}/repos/{REPOSITORY}/statuses/{sha}",
        data=json.dumps(data, sort_keys=True, separators=(",", ":")
                        ).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    return request, target


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def publish_main_push_status(
    env: Mapping[str, str],
    *,
    sender: Callable[[Request], int] | None = None,
) -> str:
    """Record completed prerequisite checks in a *native* GitHub SHA status.

    Strictly a pointer to the exact Actions run; consumers MUST follow the
    run URL and independently inspect its three predecessor job results.
    A simulated/mocked test never exercises the real GitHub REST endpoint.
    """
    request, target = build_main_push_status_request(env)
    if sender is not None:
        code = sender(request)
    else:
        # Honor runner's vetted HTTPS proxy with a strictly prevalidated
        # GitHub API URL and no redirect. Raw socket bypassed egress proxy.
        expected_path = f"/repos/{REPOSITORY}/statuses/{env['GITHUB_SHA']}"
        if request.full_url != OFFICIAL_API + expected_path or request.data is None:
            raise ValueError("P036_REQUEST_MUST_TARGET_EXACT_GITHUB_SHA")
        opener = build_opener(ProxyHandler(), NoRedirect())
        try:
            with opener.open(request, timeout=15) as response:
                code = response.status
                response.read(1024)
        except HTTPError as error:
            code = error.code
            error.read(1024)
    if type(code) is not int or code != 201:
        raise RuntimeError("P036_NATIVE_COMMIT_STATUS_NOT_ACCEPTED")
    return target


def main() -> None:
    target = publish_main_push_status(os.environ)
    # No token/header, provider credentials or private source evidence printed.
    print("MFX_A04_P36_MAIN_PUSH_CI_NATIVE_STATUS_CREATED")
    print("MFX_A04_P36_RUN_URL " + target)


if __name__ == "__main__":
    main()
