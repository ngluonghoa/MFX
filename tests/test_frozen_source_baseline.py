"""A01/P0.1 offline source-tree and explicit-delta negative test evidence."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.verify_frozen_source_baseline import (
    EXCEPTION_FILE, SOURCE_TREE, assess_checkout, exception_entries,
    git_blob_sha, git_tree_sha, source_entries,
)

ROOT = Path(__file__).resolve().parents[1]


def _record(path, n):
    return {"path": path, "mode": "100644", "sha": format(n, "040x"), "bytes": n}


def _fixture():
    source = {f"src/m{i:02}.py": _record(f"src/m{i:02}.py", i + 1)
              for i in range(30)}
    source["README.md"] = _record("README.md", 80)
    actual = {p: (x["sha"], x["bytes"]) for p, x in source.items()}
    actual["README.md"] = ("a" * 40, 17)
    actual[EXCEPTION_FILE] = ("b" * 40, 130)
    allowed = {
        "README.md": {
            "path": "README.md", "change": "modified",
            "expected_current_sha": "a" * 40, "reason": "MFX identity PR",
        },
        EXCEPTION_FILE: {
            "path": EXCEPTION_FILE, "change": "added",
            "reason": "Manifest self-reference cannot pin its own hash",
        },
    }
    return source, actual, allowed


class FrozenSourceParityTests(unittest.TestCase):
    def test_original_git_hello_blob_sha(self):
        self.assertEqual(git_blob_sha(b"hello\n"),
                         "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_locked_manifest_exact_tree_sha_and_all_102_paths(self):
        doc = json.loads((ROOT / "docs" / "MFX_FROZEN_SOURCE_TREE.json").read_text())
        self.assertEqual(len(source_entries(doc)), 102)
        self.assertEqual(git_tree_sha(doc["files"]), SOURCE_TREE)

    def test_duplicate_git_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            git_tree_sha([_record("same.py", 1), _record("same.py", 2)])

    def test_path_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_MANIFEST_PATH"):
            git_tree_sha([_record("../outside", 1)])

    def test_nonregular_git_mode_rejected(self):
        x = _record("link", 1)
        x["mode"] = "120000"
        with self.assertRaisesRegex(ValueError, "UNEXPECTED_GIT_FILE_MODE"):
            git_tree_sha([x])

    def test_valid_is_qa_only_and_protects_30_core_sources(self):
        src, actual, allowed = _fixture()
        proof = assess_checkout(src, actual, allowed)
        self.assertEqual(proof["identical_original_paths"], 30)
        self.assertEqual(proof["domain_python_sources_byte_equal"], 30)
        self.assertEqual(proof["approved_existing_path_deltas"], 1)
        self.assertEqual(proof["approved_new_paths"], 1)
        self.assertFalse(proof["may_deploy_or_trade"])

    def test_hidden_change_in_domain_is_blocked(self):
        src, actual, allowed = _fixture()
        actual["src/m00.py"] = ("c" * 40, 7)
        with self.assertRaisesRegex(ValueError, "UNAPPROVED_SOURCE_MODIFICATION"):
            assess_checkout(src, actual, allowed)

    def test_new_unapproved_file_is_blocked(self):
        src, actual, allowed = _fixture()
        actual["tools/hidden.py"] = ("f" * 40, 10)
        with self.assertRaisesRegex(ValueError, "UNAPPROVED_NEW_PATH"):
            assess_checkout(src, actual, allowed)

    def test_missing_baseline_file_is_blocked(self):
        src, actual, allowed = _fixture()
        del actual["src/m07.py"]
        with self.assertRaisesRegex(ValueError, "MISSING_FROZEN_SOURCE_PATH"):
            assess_checkout(src, actual, allowed)

    def test_changed_exception_digest_is_blocked(self):
        src, actual, allowed = _fixture()
        allowed["README.md"]["expected_current_sha"] = "d" * 40
        with self.assertRaisesRegex(ValueError, "APPROVED_DELTA_SHA_CHANGED"):
            assess_checkout(src, actual, allowed)

    def test_redundant_exception_must_be_removed(self):
        src, actual, allowed = _fixture()
        actual["README.md"] = (src["README.md"]["sha"],
                               src["README.md"]["bytes"])
        with self.assertRaisesRegex(ValueError, "REDUNDANT_APPROVED_DELTA"):
            assess_checkout(src, actual, allowed)

    def test_core_source_exception_rejected_even_if_sha_is_pinned(self):
        doc = {
            "schema_version": 1, "kind": "MFX_APPROVED_PARITY_DELTAS",
            "source_tree_sha": SOURCE_TREE,
            "exceptions": [
                {"path": EXCEPTION_FILE, "change": "added", "reason": "self"},
                {"path": "src/core.py", "change": "modified",
                 "expected_current_sha": "a" * 40, "reason": "bad"},
            ],
        }
        with self.assertRaisesRegex(ValueError, "DOMAIN_SOURCE_DELTA"):
            exception_entries(doc)

    def test_malformed_unpinned_exception_is_rejected(self):
        doc = {
            "schema_version": 1, "kind": "MFX_APPROVED_PARITY_DELTAS",
            "source_tree_sha": SOURCE_TREE,
            "exceptions": [
                {"path": EXCEPTION_FILE, "change": "added", "reason": "self"},
                {"path": "new.py", "change": "added", "reason": "unpinned"},
            ],
        }
        with self.assertRaisesRegex(ValueError, "INVALID_GIT_BLOB_SHA"):
            exception_entries(doc)

    def test_self_exception_must_be_unique_and_not_pin_itself(self):
        doc = {
            "schema_version": 1, "kind": "MFX_APPROVED_PARITY_DELTAS",
            "source_tree_sha": SOURCE_TREE,
            "exceptions": [
                {"path": EXCEPTION_FILE, "change": "added",
                 "expected_current_sha": "b" * 40, "reason": "bad self sha"},
            ],
        }
        with self.assertRaisesRegex(ValueError, "SELF_MANIFEST_EXCEPTION_INVALID"):
            exception_entries(doc)


if __name__ == "__main__":
    unittest.main()
