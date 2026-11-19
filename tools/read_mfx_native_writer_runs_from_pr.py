"""P0.199: PR-only native H4/D1 writer scheduled run IDs, GitHub-only."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any, Callable, Mapping

from tools.audit_mfx_m5_writer_runs import (
    MAX_RUNS, NATIVE_EXPECTED_CRON_MINUTE, NATIVE_WRITER_WORKFLOW,
    inspect_writer_runs,
)
from tools.read_main_push_ci_diagnostic import _get_json, validate_read_env

REPO = "ngluonghoa/MFX"
NATIVE_PATH = (
    f"/repos/{REPO}/actions/workflows/{NATIVE_WRITER_WORKFLOW}/runs"
    f"?event=schedule&per_page={MAX_RUNS}"
)


def inspect_native_writer_from_pr(
    env: Mapping[str, str], *, now_utc: datetime,
    sender: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Uses existing P037 PR trust boundary, no new workflow permission."""
    token = validate_read_env(env)
    fetch = sender if sender is not None else lambda path: _get_json(token, path)
    return inspect_writer_runs(
        fetch(NATIVE_PATH),
        asof_utc=now_utc,
        workflow=NATIVE_WRITER_WORKFLOW,
        expected_cron_minute=NATIVE_EXPECTED_CRON_MINUTE,
    )


def main() -> None:
    report = inspect_native_writer_from_pr(
        os.environ, now_utc=datetime.now(timezone.utc),
    )
    print("MFX_P199_PR_ONLY_REAL_GITHUB_NATIVE_H4_D1_WRITER_HISTORY_PASS")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
