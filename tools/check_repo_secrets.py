"""RE4c high-confidence scanner for committed text; no secret values in output.

Uses only Python stdlib and Git's index (not Git history, untracked files,
provider tokens, encrypted blobs, or an enterprise secret scanning service).
Deliberately narrow signatures; scanning without findings is not proof of no
secrets. Reads all currently tracked repository files, including docs.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PATTERNS: dict[str, re.Pattern[bytes]] = {
    "PRIVATE_KEY_PEM": re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    "GITHUB_CLASSIC_PAT": re.compile(rb"\bgh[pousr]_[A-Za-z0-9_]{36,}\b"),
    "GITHUB_FINE_GRAINED_PAT": re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    "AWS_ACCESS_KEY_ID": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "GOOGLE_API_KEY": re.compile(rb"\bAIza[A-Za-z0-9_-]{35}\b"),
    "SLACK_TOKEN": re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "STRIPE_LIVE_SECRET": re.compile(rb"\bsk_live_[A-Za-z0-9]{24,}\b"),
}


def scan_bytes(content: bytes) -> tuple[str, ...]:
    """Return signature IDs only: NEVER echo candidate credential bytes."""
    return tuple(name for name, pattern in PATTERNS.items() if pattern.search(content))


def tracked_files(repo: Path) -> tuple[Path, ...]:
    completed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--cached", "-z"],
        capture_output=True, check=True,
    )
    paths = tuple(
        Path(raw.decode("utf-8", errors="strict"))
        for raw in completed.stdout.split(b"\0") if raw
    )
    if not paths:
        raise ValueError("EMPTY_GIT_TRACKED_FILE_LIST")
    return paths


def scan_repository(repo: Path) -> tuple[int, tuple[tuple[str, str], ...]]:
    """Fail closed on unreadable, missing, symlinked, binary or non-UTF8 files."""
    findings: list[tuple[str, str]] = []
    count = 0
    for relpath in tracked_files(repo):
        pathname = repo / relpath
        if not pathname.is_file() or pathname.is_symlink():
            findings.append((relpath.as_posix(), "UNREADABLE_OR_SYMLINK"))
            continue
        try:
            content = pathname.read_bytes()
            if b"\0" in content:
                raise ValueError("BINARY_FILE_NOT_SCANNED")
            content.decode("utf-8", errors="strict")
        except (OSError, ValueError, UnicodeError):
            findings.append((relpath.as_posix(), "UNREADABLE_OR_NONTEXT"))
            continue
        count += 1
        findings.extend((relpath.as_posix(), code) for code in scan_bytes(content))
    return count, tuple(findings)


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    try:
        checked, findings = scan_repository(repo)
    except (OSError, subprocess.CalledProcessError, ValueError, UnicodeError) as error:
        print(f"SECRET_SCAN_UNVERIFIED: {type(error).__name__}", file=sys.stderr)
        return 2
    # No matched strings or credential substrings are printed.
    if findings:
        for path, signature in findings:
            print(f"SECRET_SCAN_BLOCKED path={path} signature={signature}", file=sys.stderr)
        return 1
    print(f"SECRET_SCAN_HIGH_CONFIDENCE_PASS tracked_text_files={checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
