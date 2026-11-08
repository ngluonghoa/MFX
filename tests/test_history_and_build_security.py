"""RE4c2 scanner and build requirement negative tests using synthetic Git."""
import tempfile
import unittest
from pathlib import Path
from subprocess import run

from tools.check_git_history_secrets import scan_history
from tools.write_build_audit_requirements import build_requires


def make_repo(root: Path) -> None:
    run(["git", "-C", str(root), "init", "-q"], check=True)
    run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
    run(["git", "-C", str(root), "config", "user.name", "Synthetic Test"], check=True)


def commit_path(root: Path, name: str, content: bytes) -> None:
    (root / name).write_bytes(content)
    run(["git", "-C", str(root), "add", name], check=True)
    run(["git", "-C", str(root), "commit", "-qm", "synthetic"], check=True)


class HistorySecurityGateTests(unittest.TestCase):
    def test_clean_reachable_blob(self):
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            make_repo(root)
            commit_path(root, "clean.txt", b"safe text\n")
            self.assertEqual(scan_history(root), (1, 0, ()))

    def test_deleted_historical_secret_still_blocks_without_echo(self):
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            make_repo(root)
            token = ("gh" + "p_" + "A" * 36).encode()
            commit_path(root, "old.txt", b"token=" + token + b"\n")
            (root / "old.txt").write_text("not a secret\n", encoding="utf-8")
            run(["git", "-C", str(root), "add", "old.txt"], check=True)
            run(["git", "-C", str(root), "commit", "-qm", "replace"], check=True)
            scanned, skipped, findings = scan_history(root)
            self.assertEqual(scanned, 2)
            self.assertEqual(skipped, 0)
            self.assertTrue(any(kind == "GITHUB_CLASSIC_PAT" for _, kind in findings))
            self.assertNotIn(token.decode(), repr(findings))

    def test_binary_history_blob_is_explicitly_counted(self):
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            make_repo(root)
            commit_path(root, "blob.dat", b"\x00\xff")
            self.assertEqual(scan_history(root), (0, 1, ()))

    def test_empty_history_fails_closed(self):
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            make_repo(root)
            with self.assertRaises(ValueError):
                scan_history(root)


class BuildRequirementsTests(unittest.TestCase):
    def test_build_system_range_extracted(self):
        self.assertEqual(
            build_requires(b'[build-system]\nrequires=["setuptools>=70,<80"]\n'),
            ("setuptools>=70,<80",),
        )

    def test_missing_build_system_fails_closed(self):
        with self.assertRaises(ValueError):
            build_requires(b'[project]\nname="forex"\n')

    def test_empty_build_system_fails_closed(self):
        with self.assertRaises(ValueError):
            build_requires(b'[build-system]\nrequires=[]\n')

    def test_requirement_injection_blocked(self):
        with self.assertRaises(ValueError):
            build_requires(b'[build-system]\nrequires=["-e /tmp/test"]\n')

    def test_duplicate_requirements_blocked(self):
        with self.assertRaises(ValueError):
            build_requires(
                b'[build-system]\nrequires=["setuptools>=70", "setuptools>=70"]\n'
            )


if __name__ == "__main__":
    unittest.main()
