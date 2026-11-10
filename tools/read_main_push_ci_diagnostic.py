"""P0.37 — read-only GitHub-hosted diagnosis of missing MAIN-push CI status.

PR-only diagnostic, never an approval or a CI success attestation.
Reads branch main, Actions push runs, run jobs and native SHA statuses from
fixed api.github.com. No credentials, quotes or market sources printed.
"""
from __future__ import annotations

from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import json
import os
import re
from typing import Any, Callable, Mapping

REPO = "ngluonghoa/MFX"
API_HOST = "api.github.com"
CONTEXT = "mfx/main-push-full-ci"
_SHA = re.compile(r"[a-f0-9]{40}")


def validate_read_env(env: Mapping[str, str]) -> str:
    if (env.get("GITHUB_EVENT_NAME") != "pull_request"
            or env.get("GITHUB_REPOSITORY") != REPO
            or env.get("GITHUB_API_URL") != "https://api.github.com"):
        raise ValueError("P037_TRUSTED_PR_GITHUB_API_CONTEXT_REQUIRED")
    token = env.get("P037_READ_TOKEN", "")
    if (not token or len(token) > 4096
            or token.strip() != token
            or any(ord(c) <= 32 for c in token)):
        raise ValueError("P037_INVALID_SCOPED_READ_TOKEN")
    return token


def checked_main_sha(value: object) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise ValueError("P037_INVALID_EXACT_MAIN_SHA")
    return value


def summarize_push_evidence(
    sha: str, runs_doc: object, job_doc: object,
    statuses_doc: object,
) -> dict[str, object]:
    """Return an observable status, NEVER invent success for missing runs."""
    checked_main_sha(sha)
    if (not isinstance(runs_doc, dict)
            or not isinstance(runs_doc.get("workflow_runs"), list)
            or not isinstance(job_doc, dict)
            or not isinstance(job_doc.get("jobs"), list)
            or not isinstance(statuses_doc, list)):
        raise ValueError("P037_MALFORMED_GITHUB_RUNS_OR_STATUSES")
    matching = [
        r for r in runs_doc["workflow_runs"]
        if isinstance(r, dict) and r.get("head_sha") == sha
        and r.get("event") == "push"
        and r.get("head_branch") == "main"
        and type(r.get("id")) is int
    ]
    runs = [{
        "id": r["id"], "status": r.get("status"),
        "conclusion": r.get("conclusion"),
        "workflow": r.get("name"),
    } for r in matching]
    jobs = []
    for item in job_doc["jobs"]:
        if not isinstance(item, dict):
            raise ValueError("P037_MALFORMED_GITHUB_JOB")
        jobs.append({
            "id": item.get("id"), "name": item.get("name"),
            "status": item.get("status"),
            "conclusion": item.get("conclusion"),
        })
    contexts = []
    for item in statuses_doc:
        if not isinstance(item, dict):
            raise ValueError("P037_MALFORMED_GITHUB_STATUS")
        if item.get("context") == CONTEXT:
            contexts.append({
                "context": CONTEXT,
                "state": item.get("state"),
                "target_url": item.get("target_url"),
            })
    verified = bool(
        runs and runs[0]["status"] == "completed"
        and runs[0]["conclusion"] == "success"
        and len(jobs) == 4
        and sum(j.get("conclusion") == "success" for j in jobs) == 4
        and len(contexts) >= 1 and contexts[0]["state"] == "success"
    )
    return {
        "main_sha": sha, "matching_push_runs": runs[:3],
        "selected_run_jobs": jobs[:8],
        "native_statuses": contexts[:3],
        "push_jobs_and_native_status_verified": verified,
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _get_json(token: str, path: str) -> Any:
    if (not path.startswith(f"/repos/{REPO}/")
            or ".." in path or "://" in path
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in path)):
        raise ValueError("P037_UNTRUSTED_GITHUB_API_PATH")
    # Use the runner's vetted HTTPS proxy settings. Raw HTTPSConnection
    # bypassed them and returned a non-GitHub 403 without request ID.
    opener = build_opener(ProxyHandler(), NoRedirect())
    request = Request(
        "https://" + API_HOST + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    try:
        with opener.open(request, timeout=15) as response:
            status = response.status
            data = response.read(2500000)
            headers = response.headers
    except HTTPError as error:
        status = error.code
        data = error.read(2500000)
        headers = error.headers
    if status != 200:
        try:
            error_body = json.loads(data.decode("utf-8"))
            candidate = error_body.get("message", "") if isinstance(error_body, dict) else ""
            message = candidate if isinstance(candidate, str) else ""
        except (ValueError, UnicodeDecodeError):
            message = ""
        reason = (
            "GITHUB_TOKEN_INTEGRATION_DENIED"
            if message == "Resource not accessible by integration"
            else "GITHUB_RATE_LIMIT"
            if "rate limit" in message.lower()
            else "GITHUB_API_FORBIDDEN_OTHER"
            if message
            else "NON_JSON_OR_PROXY_REJECTION"
        )
        server = headers.get("Server", "") or ""
        print("P037_API_DENIAL_DIAGNOSTIC " + json.dumps({
            "status": status,
            "endpoint_kind": path.split("?")[0].rsplit("/", 1)[-1],
            "reason": reason,
            "server": server[:48],
            "github_request_id_present": bool(headers.get("X-GitHub-Request-Id")),
        }, sort_keys=True))
        raise RuntimeError("P037_READ_ONLY_GITHUB_API_HTTP_" +
                           str(status) + "_" + reason)
    return json.loads(data.decode("utf-8"))

def inspect_main_push(
    env: Mapping[str, str],
    sender: Callable[[str], Any] | None = None,
) -> dict[str, object]:
    token = validate_read_env(env)
    fetch = sender if sender is not None else lambda path: _get_json(token, path)
    branch = fetch(f"/repos/{REPO}/branches/main")
    if not isinstance(branch, dict) or not isinstance(branch.get("commit"), dict):
        raise ValueError("P037_MAIN_BRANCH_METADATA_MISSING")
    sha = checked_main_sha(branch["commit"].get("sha"))
    runs_doc = fetch(
        f"/repos/{REPO}/actions/runs?event=push&branch=main&per_page=30")
    if not isinstance(runs_doc, dict) or not isinstance(
        runs_doc.get("workflow_runs"), list
    ):
        raise ValueError("P037_MALFORMED_GITHUB_RUNS_OR_STATUSES")
    candidate = next((
        r for r in runs_doc["workflow_runs"]
        if isinstance(r, dict) and r.get("head_sha") == sha
        and r.get("event") == "push" and r.get("head_branch") == "main"
        and type(r.get("id")) is int
    ), None)
    jobs = (fetch(f"/repos/{REPO}/actions/runs/{candidate['id']}/jobs?per_page=100")
            if candidate else {"jobs": []})
    statuses = fetch(f"/repos/{REPO}/commits/{sha}/statuses?per_page=100")
    return summarize_push_evidence(sha, runs_doc, jobs, statuses)


def main() -> None:
    report = inspect_main_push(os.environ)
    print("MFX_A04_P37_MAIN_PUSH_READ_ONLY_DIAGNOSTIC")
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    # This read-only report is not a release or source-numeric approval.


if __name__ == "__main__":
    main()
