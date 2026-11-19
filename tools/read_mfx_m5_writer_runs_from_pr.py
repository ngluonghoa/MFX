"""P0.198: PR-only real GitHub M5 writer schedule readback.

The repository already has a PR diagnostic job with the minimum Actions-read
GitHub token. Reuse that exact trust boundary to expose recent schedule run
IDs, without a new cron, vendor quote call, Drive access or broker action.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any, Callable, Mapping

from tools.audit_mfx_m5_writer_runs import _FIXED_PATH, inspect_writer_runs
from tools.read_main_push_ci_diagnostic import _get_json, validate_read_env


def inspect_pr_writer_runs(
    env: Mapping[str, str], *,
    now_utc: datetime,
    sender: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Obtain a bounded, non-authorizing GitHub-only run-history receipt."""
    token = validate_read_env(env)  # exact GitHub PR + official API
    fetch = sender if sender is not None else lambda p: _get_json(token, p)
    return inspect_writer_runs(
        fetch(_FIXED_PATH), asof_utc=now_utc,
    )


def main() -> None:
    report = inspect_pr_writer_runs(
        os.environ, now_utc=datetime.now(timezone.utc),
    )
    print("MFX_P198_PR_ONLY_REAL_GITHUB_M5_WRITER_RUN_HISTORY_PASS")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
