"""Fail-closed high-confidence secret scan of reachable Git history text blobs.

Requirements: complete (non-shallow) checkout, git, and Python 3.11+.
Scans every blob reachable from local refs via git rev-list --objects --all.
Reports only object ID prefixes and pattern names, never candidate secret text.
Binary/non-UTF8 history blobs are counted and EXCLUDED, not silently claimed
scanned. Unreachable/reflog-only objects and erased remote refs are not covered.
"""
from __future__ import annotations

import re
import subprocess
import sys
from io import BytesIO
from pathlib import Path

from tools.check_repo_secrets import scan_bytes

OID = re.compile(rb"[0-9a-f]{40}|[0-9a-f]{64}")
MAX_BLOBS = 50_000
MAX_BYTES = 128 * 1024 * 1024


def git(repo: Path, *args: str, input_data: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], input=input_data,
        capture_output=True, check=True,
    )
    return result.stdout


def scan_history(repo: Path) -> tuple[int, int, tuple[tuple[str, str], ...]]:
    """Return scanned text count, omitted binary count, safe finding IDs."""
    if git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("SHALLOW_GIT_HISTORY_UNVERIFIED")
    raw_objects = git(repo, "rev-list", "--objects", "--all")
    object_ids = tuple(dict.fromkeys(
        line.split(b" ", 1)[0] for line in raw_objects.splitlines() if line
    ))
    if not object_ids or len(object_ids) > MAX_BLOBS * 4:
        raise ValueError("GIT_HISTORY_OBJECT_COUNT_UNVERIFIED")
    if any(OID.fullmatch(object_id) is None for object_id in object_ids):
        raise ValueError("INVALID_GIT_OBJECT_ID")
    input_ids = b"\n".join(object_ids) + b"\n"
    checks = git(repo, "cat-file", "--batch-check", input_data=input_ids)
    metadata = checks.splitlines()
    if len(metadata) != len(object_ids):
        raise ValueError("INCOMPLETE_GIT_OBJECT_METADATA")
    blobs: list[bytes] = []
    total = 0
    for object_id, line in zip(object_ids, metadata, strict=True):
        fields = line.split()
        if len(fields) != 3 or fields[0] != object_id:
            raise ValueError("BAD_GIT_OBJECT_METADATA")
        if fields[1] != b"blob":
            continue
        try:
            size = int(fields[2])
        except ValueError as exc:
            raise ValueError("BAD_GIT_BLOB_SIZE") from exc
        if size < 0 or size > MAX_BYTES:
            raise ValueError("OVERSIZED_HISTORY_BLOB_UNVERIFIED")
        blobs.append(object_id)
        total += size
        if total > MAX_BYTES or len(blobs) > MAX_BLOBS:
            raise ValueError("HISTORY_SCAN_BUDGET_EXCEEDED")
    if not blobs:
        raise ValueError("NO_REACHABLE_GIT_BLOBS")
    body = git(repo, "cat-file", "--batch", input_data=b"\n".join(blobs) + b"\n")
    reader = BytesIO(body)
    scanned = skipped_binary = 0
    findings: list[tuple[str, str]] = []
    for oid in blobs:
        header = reader.readline().split()
        if len(header) != 3 or header[0] != oid or header[1] != b"blob":
            raise ValueError("GIT_BLOB_STREAM_MISMATCH")
        size = int(header[2])
        content = reader.read(size)
        if len(content) != size or reader.read(1) != b"\n":
            raise ValueError("TRUNCATED_GIT_BLOB")
        if b"\0" in content:
            skipped_binary += 1
            continue
        try:
            content.decode("utf-8", errors="strict")
        except UnicodeError:
            skipped_binary += 1
            continue
        scanned += 1
        findings.extend((oid.decode("ascii")[:12], key) for key in scan_bytes(content))
    if reader.read(1):
        raise ValueError("TRAILING_GIT_BLOB_OUTPUT")
    return scanned, skipped_binary, tuple(findings)


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    try:
        scanned, binary, findings = scan_history(repo)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"HISTORY_SECRET_SCAN_UNVERIFIED: {type(error).__name__}", file=sys.stderr)
        return 2
    if findings:
        for oid, signature in findings:
            print(
                f"HISTORY_SECRET_SCAN_BLOCKED object={oid} signature={signature}",
                file=sys.stderr,
            )
        return 1
    print(
        "HISTORY_SECRET_HIGH_CONFIDENCE_PASS "
        f"reachable_text_blobs={scanned} skipped_binary_blobs={binary}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
