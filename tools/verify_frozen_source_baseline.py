"""A01/P0.1: offline, fail-closed frozen Forex -> MFX Git blob parity receipt.

The original Forex source commit/tree is immutable input. This checker runs
entirely in hosted GitHub Actions, does not fetch vendor data and does not
grant deployment or broker/trading authority.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

SOURCE_TREE = "5df2058346f6dc96ed5bb02581b139fe2aa2d803"
SOURCE_COMMIT = "7e1c1c012b1b189be5ad7b9d07756eac012a8309"
EXCEPTION_FILE = "docs/MFX_ALLOWED_BASELINE_DELTAS.json"
HEX_SHA = re.compile(r"^[0-9a-f]{40}$")


def git_blob_sha(data: bytes) -> str:
    payload = b"blob " + str(len(data)).encode("ascii") + b"\x00" + data
    return hashlib.sha1(payload).hexdigest()  # nosec B324 - exact Git SHA-1 object ID, not a security digest


def _check_path(path: object) -> str:
    if not isinstance(path, str) or not path or "\\" in path:
        raise ValueError("INVALID_MANIFEST_PATH")
    if any(part in ("", ".", "..") for part in path.split("/")):
        raise ValueError("INVALID_MANIFEST_PATH")
    return path


def _check_sha(value: object) -> str:
    if not isinstance(value, str) or HEX_SHA.fullmatch(value) is None:
        raise ValueError("INVALID_GIT_BLOB_SHA")
    return value


def git_tree_sha(files: list[dict[str, Any]]) -> str:
    """Rebuild Git's exact tree-object SHA from recursively nested 100644 blobs."""
    root: dict[str, Any] = {}
    for item in files:
        path = _check_path(item["path"])
        sha = _check_sha(item["sha"])
        if item["mode"] != "100644":
            raise ValueError("UNEXPECTED_GIT_FILE_MODE")
        parts = path.split("/")
        node = root
        for name in parts[:-1]:
            if name not in node:
                node[name] = {}
            if not isinstance(node[name], dict):
                raise ValueError("FILE_DIRECTORY_COLLISION")
            node = node[name]
        if parts[-1] in node:
            raise ValueError("DUPLICATE_OR_COLLIDING_SOURCE_PATH")
        node[parts[-1]] = sha

    def visit(node: dict[str, Any]) -> str:
        buffer = bytearray()
        entries = sorted(node.items(), key=lambda kv: (
            kv[0] + ("/" if isinstance(kv[1], dict) else "")
        ).encode("utf-8"))
        for name, item in entries:
            directory = isinstance(item, dict)
            mode = "40000" if directory else "100644"
            oid = visit(item) if directory else item
            buffer.extend((mode + " " + name).encode("utf-8") + b"\x00")
            buffer.extend(bytes.fromhex(oid))
        data = bytes(buffer)
        return hashlib.sha1(
            b"tree " + str(len(data)).encode("ascii") + b"\x00" + data
        ).hexdigest()  # nosec B324 - exact Git tree-object SHA-1, not a security digest

    return visit(root)


def source_entries(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if (manifest.get("schema_version") != 1 or
            manifest.get("kind") != "MFX_FROZEN_FOREX_SOURCE_TREE" or
            manifest.get("source_commit") != SOURCE_COMMIT or
            manifest.get("source_tree_sha") != SOURCE_TREE or
            manifest.get("source_repo") != "ngluonghoa/forex-trading-1-0"):
        raise ValueError("FROZEN_SOURCE_IDENTITY_MISMATCH")
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) != 102:
        raise ValueError("FROZEN_SOURCE_FILE_COUNT_MISMATCH")
    if manifest.get("source_file_count") != len(entries):
        raise ValueError("FROZEN_SOURCE_DECLARED_COUNT_MISMATCH")
    for record in entries:
        if not isinstance(record, dict):
            raise ValueError("FROZEN_SOURCE_RECORD_MALFORMED")
        if type(record.get("bytes")) is not int or record["bytes"] < 0:
            raise ValueError("FROZEN_SOURCE_FILE_LENGTH_INVALID")
    if git_tree_sha(entries) != SOURCE_TREE:
        raise ValueError("FROZEN_SOURCE_TREE_SHA_MISMATCH")
    return {item["path"]: item for item in entries}


def exception_entries(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if (document.get("schema_version") != 1 or
            document.get("kind") != "MFX_APPROVED_PARITY_DELTAS" or
            document.get("source_tree_sha") != SOURCE_TREE):
        raise ValueError("APPROVED_DELTAS_IDENTITY_MISMATCH")
    entries = document.get("exceptions")
    if not isinstance(entries, list):
        raise ValueError("APPROVED_DELTAS_MALFORMED")
    result: dict[str, dict[str, Any]] = {}
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("APPROVED_DELTA_RECORD_MALFORMED")
        path = _check_path(item.get("path"))
        if path in result:
            raise ValueError("DUPLICATE_APPROVED_DELTA")
        if path.startswith("src/"):
            raise ValueError("DOMAIN_SOURCE_DELTA_NOT_AUTHORIZED_AT_A01_P0_1")
        if item.get("change") not in ("modified", "added", "removed"):
            raise ValueError("APPROVED_DELTA_CHANGE_INVALID")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise ValueError("APPROVED_DELTA_REASON_MISSING")
        target = item.get("expected_current_sha")
        if path == EXCEPTION_FILE:
            if target is not None or item["change"] != "added":
                raise ValueError("SELF_MANIFEST_EXCEPTION_INVALID")
        elif item["change"] != "removed":
            _check_sha(target)
        elif target is not None:
            raise ValueError("REMOVED_DELTA_SHA_MUST_BE_NULL")
        result[path] = item
    if EXCEPTION_FILE not in result:
        raise ValueError("MISSING_SELF_MANIFEST_EXCEPTION")
    return result


def assess_checkout(
    source: dict[str, dict[str, Any]],
    actual: dict[str, tuple[str, int]],
    exceptions: dict[str, dict[str, Any]],
) -> dict[str, object]:
    """Compare only tracked bytes; require explicit pinned exceptions for every diff."""
    unexpected = set(actual) - (set(source) | set(exceptions))
    if unexpected:
        raise ValueError("UNAPPROVED_NEW_PATH:" + ",".join(sorted(unexpected)))
    if set(exceptions) - (set(source) | set(actual)):
        raise ValueError("STALE_MISSING_APPROVED_EXCEPTION")
    identical = 0
    changed = 0
    added = 0
    for path, expected in source.items():
        current = actual.get(path)
        allowance = exceptions.get(path)
        if current is None:
            if allowance is None or allowance["change"] != "removed":
                raise ValueError("MISSING_FROZEN_SOURCE_PATH:" + path)
            changed += 1
            continue
        sha, length = current
        if sha == expected["sha"] and length == expected["bytes"]:
            if allowance is not None:
                raise ValueError("REDUNDANT_APPROVED_DELTA:" + path)
            identical += 1
            continue
        if allowance is None or allowance["change"] != "modified":
            raise ValueError("UNAPPROVED_SOURCE_MODIFICATION:" + path)
        if allowance["expected_current_sha"] != sha:
            raise ValueError("APPROVED_DELTA_SHA_CHANGED:" + path)
        changed += 1
    for path, allowance in exceptions.items():
        if path in source:
            continue
        if allowance["change"] != "added" or path not in actual:
            raise ValueError("APPROVED_NEW_PATH_MISSING:" + path)
        if path != EXCEPTION_FILE and allowance["expected_current_sha"] != actual[path][0]:
            raise ValueError("APPROVED_NEW_PATH_SHA_CHANGED:" + path)
        added += 1
    domain = [p for p in source if p.startswith("src/")]
    if len(domain) != 30 or any(
        p in exceptions or actual.get(p) != (source[p]["sha"], source[p]["bytes"])
        for p in domain
    ):
        raise ValueError("FROZEN_DOMAIN_SOURCE_PARITY_LOST")
    return {
        "kind": "MFX_A01_FROZEN_SOURCE_PATH_PARITY_QA_ONLY",
        "source_commit": SOURCE_COMMIT,
        "source_tree_sha": SOURCE_TREE,
        "frozen_source_files": len(source),
        "identical_original_paths": identical,
        "approved_existing_path_deltas": changed,
        "approved_new_paths": added,
        "domain_python_sources_byte_equal": len(domain),
        "all_unapproved_path_or_byte_changes_blocked": True,
        "is_live_strategy_parity_proof": False,
        "is_signed_release": False,
        "may_deploy_or_trade": False,
    }


def tracked_checkout(repo_root: Path) -> dict[str, tuple[str, int]]:
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--"], cwd=repo_root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    out: dict[str, tuple[str, int]] = {}
    for raw in completed.stdout.split(b"\x00"):
        if not raw:
            continue
        path = _check_path(raw.decode("utf-8"))
        file = repo_root / path
        if not file.is_file() or file.is_symlink():
            raise ValueError("UNSAFE_OR_MISSING_TRACKED_FILE:" + path)
        data = file.read_bytes()
        out[path] = git_blob_sha(data), len(data)
    return out


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = source_entries(json.loads(
        (root / "docs" / "MFX_FROZEN_SOURCE_TREE.json").read_text(encoding="utf-8")
    ))
    approved = exception_entries(json.loads(
        (root / EXCEPTION_FILE).read_text(encoding="utf-8")
    ))
    proof = assess_checkout(source, tracked_checkout(root), approved)
    print("MFX_A01_FROZEN_SOURCE_PARITY_PASS " + json.dumps(proof, sort_keys=True))


if __name__ == "__main__":
    main()
