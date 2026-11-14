"""MFX P0.164: read-only GitHub issue-event guard for unresolved native D1 HOLD.

Runs only on GitHub-hosted Actions. Reads the provided GitHub issue webhook
JSON; never uses an API key, vendor feed, Drive object, broker, or price.
This is an alert, NOT an issue-state writer, owner signoff or price authority.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mfx_research.six_tf_sealed_archive_consumer import (
    D1_KNOWN_SOURCE_REVISION_HOLD,
    D1_KNOWN_SOURCE_REVISION_INCIDENT,
)

REPO = "ngluonghoa/MFX"
ISSUE_NUMBER = 147
INCIDENT = "EURUSD_SYDNEY_D1_2026_11_11_NUMERIC_OHLC_1_OF_16"
ACTIONS = frozenset(("closed", "reopened"))
MAX_EVENT_BYTES = 2_000_000


def audit_issue_event(payload: Any, *, repo: str) -> str:
    """Return a safe event result or fail closed on premature closure.

    This only checks process state: a GitHub issue's text and status are
    never independent vendor source evidence, legal authorization or as-of
    revision first-known proof.
    """
    if (type(repo) is not str or repo != REPO
            or type(payload) is not dict
            or type(payload.get("repository")) is not dict
            or payload["repository"].get("full_name") != REPO
            or type(payload.get("action")) is not str
            or payload["action"] not in ACTIONS
            or type(payload.get("issue")) is not dict):
        raise ValueError("MFX_P164_UNTRUSTED_ISSUE_EVENT_SCOPE")

    issue = payload["issue"]
    if type(issue.get("number")) is not int:
        raise ValueError("MFX_P164_ISSUE_NUMBER_TYPE")
    if issue["number"] != ISSUE_NUMBER:
        # Even when invoked without GitHub's job-level issue-number filter,
        # other issues cannot change this incident's decision.
        return "MFX_P164_OTHER_ISSUE_IGNORED"

    if (D1_KNOWN_SOURCE_REVISION_HOLD is not True
            or D1_KNOWN_SOURCE_REVISION_INCIDENT != INCIDENT):
        raise ValueError("MFX_P164_PINNED_SOURCE_HOLD_POLICY_DRIFT")

    action = payload["action"]
    state = issue.get("state")
    if state != ("closed" if action == "closed" else "open"):
        raise ValueError("MFX_P164_ISSUE_EVENT_STATE_MISMATCH")

    if action == "closed":
        raise ValueError("MFX_P164_ISSUE147_PREMATURE_CLOSURE_D1_SOURCE_HOLD")

    return "MFX_P164_ISSUE147_REOPENED_D1_HOLD_PRESERVED_NO_SIGNAL"


def main() -> None:
    """Use the GitHub-delivered event file only; never fetch or mutate issues."""
    if os.environ.get("GITHUB_EVENT_NAME") != "issues":
        raise SystemExit("MFX_P164_GITHUB_ISSUES_EVENT_REQUIRED")
    path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not path or len(path) > 4096:
        raise SystemExit("MFX_P164_EVENT_PATH_REQUIRED")
    try:
        event_path = Path(path)
        if event_path.stat().st_size > MAX_EVENT_BYTES:
            raise ValueError("MFX_P164_EVENT_TOO_LARGE")
        payload = json.loads(event_path.read_text(encoding="utf-8"))
        outcome = audit_issue_event(
            payload, repo=os.environ.get("GITHUB_REPOSITORY", ""))
    except (OSError, ValueError, TypeError):
        # Avoid logging attacker-controlled webhook content or account data.
        raise SystemExit("MFX_P164_SOURCE_GOVERNANCE_AUDIT_FAILED_CLOSED") from None
    print(outcome)


if __name__ == "__main__":
    main()
