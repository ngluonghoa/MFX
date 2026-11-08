"""RE5a synthetic negative tests: detached cross-Python wheel artifacts."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from tools.check_cross_python_artifacts import check_cross_python_artifacts


def make_wheel(path: Path, content: bytes, *, extra: str | None = None) -> None:
    base = "forex_trading_core-0.1.0.dist-info"
    with ZipFile(path, "w") as archive:
        archive.writestr(base + "/METADATA",
                         "Metadata-Version: 2.3\nName: forex-trading-core\n"
                         "Version: 0.1.0\n")
        archive.writestr(base + "/WHEEL", "Wheel-Version: 1.0\n")
        archive.writestr(base + "/RECORD", "")
        archive.writestr("forex_trading/__init__.py", content)
        if extra is not None:
            archive.writestr(extra, "unexpected")


class CrossPythonArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.src = self.root / "src" / "forex_trading"
        self.src.mkdir(parents=True)
        self.src_file = self.src / "__init__.py"
        self.src_file.write_bytes(b"# synthetic source\n")
        (self.root / "pyproject.toml").write_text(
            '[project]\nname="forex-trading-core"\nversion="0.1.0"\n',
            encoding="utf-8",
        )
        self.left = self.root / "p311"
        self.right = self.root / "p312"
        self.left.mkdir()
        self.right.mkdir()
        self.filename = "forex_trading_core-0.1.0-py3-none-any.whl"

    def make(self, left: bytes = b"# synthetic source\n",
             right: bytes = b"# synthetic source\n") -> None:
        make_wheel(self.left / self.filename, left)
        make_wheel(self.right / self.filename, right)

    def check(self) -> dict[str, object]:
        return check_cross_python_artifacts(self.root, self.left, self.right)

    def test_good_build_parity_remains_nonrelease(self) -> None:
        self.make()
        proof = self.check()
        self.assertTrue(proof["cross_python_wheel_byte_parity_observed"])
        self.assertEqual(proof["source_python_files_verified"], 1)
        for field in (
            "is_cross_host_reproducibility_proof",
            "is_signed_supply_chain_attestation",
            "is_last_known_good",
            "may_deploy_or_trade",
        ):
            self.assertFalse(proof[field])

    def test_missing_second_wheel_fails_closed(self) -> None:
        make_wheel(self.left / self.filename, self.src_file.read_bytes())
        with self.assertRaisesRegex(
            ValueError, "EXACTLY_ONE_CROSS_PYTHON_ARTIFACT_REQUIRED",
        ):
            self.check()

    def test_multiple_wheels_fails_closed(self) -> None:
        self.make()
        make_wheel(self.left / "extra.whl", self.src_file.read_bytes())
        with self.assertRaisesRegex(
            ValueError, "EXACTLY_ONE_CROSS_PYTHON_ARTIFACT_REQUIRED",
        ):
            self.check()

    def test_same_directory_rejected(self) -> None:
        self.make()
        with self.assertRaisesRegex(
            ValueError, "SAME_CROSS_PYTHON_ARTIFACT_DIRECTORY",
        ):
            check_cross_python_artifacts(self.root, self.left, self.left)

    def test_source_tampering_even_if_two_wheels_identical_is_blocked(self) -> None:
        self.make(left=b"# stale source\n", right=b"# stale source\n")
        with self.assertRaisesRegex(
            ValueError, "CROSS_PYTHON_PACKAGED_SOURCE_MISMATCH",
        ):
            self.check()

    def test_different_python_wheel_contents_rejected(self) -> None:
        self.make()
        with ZipFile(self.right / self.filename, "a") as archive:
            archive.writestr("data/extra.txt", "changed")
        with self.assertRaisesRegex(
            ValueError, "CROSS_PYTHON_WHEEL_SHA256_MISMATCH",
        ):
            self.check()

    def test_extra_packaged_python_source_fails_closed(self) -> None:
        self.make()
        for folder in (self.left, self.right):
            with ZipFile(folder / self.filename, "a") as archive:
                archive.writestr("forex_trading/hidden.py", "# unexpected\n")
        with self.assertRaisesRegex(
            ValueError, "CROSS_PYTHON_EXTRA_OR_MISSING_SOURCE",
        ):
            self.check()

    def test_unsafe_wheel_zip_path_rejected(self) -> None:
        self.make()
        with ZipFile(self.left / self.filename, "a") as archive:
            archive.writestr("../private.txt", "forbidden")
        with self.assertRaisesRegex(
            ValueError, "UNSAFE_WHEEL_CONTENTS",
        ):
            self.check()

    def test_wrong_project_version_rejected(self) -> None:
        self.make()
        (self.root / "pyproject.toml").write_text(
            '[project]\nname="forex-trading-core"\nversion="9.0.0"\n',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            ValueError, "WHEEL_PROJECT_NAME_OR_VERSION_MISMATCH",
        ):
            self.check()


if __name__ == "__main__":
    unittest.main()
