"""RE2 negative tests for wheel smoke verification; no publishing."""
import tempfile
from shutil import copyfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from tools.verify_build_artifact import inspect_wheel, verify_repeat_build_match


def wheel(path, *, name="forex-trading-core", version="0.1.0",
          include_source=True, extra_path=None):
    with ZipFile(path, "w") as z:
        base = "forex_trading_core-0.1.0.dist-info"
        z.writestr(base + "/METADATA",
                   "Metadata-Version: 2.3\nName: " + name +
                   "\nVersion: " + version + "\n")
        z.writestr(base + "/WHEEL", "Wheel-Version: 1.0\n")
        z.writestr(base + "/RECORD", "")
        if include_source:
            z.writestr("forex_trading/__init__.py", '"""synthetic only"""\n')
        if extra_path:
            z.writestr(extra_path, "fake")


class WheelVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.artifact = Path(self.tmp.name) / "test-0.1.0-py3-none-any.whl"

    def check(self):
        return inspect_wheel(
            self.artifact, project_name="forex-trading-core",
            project_version="0.1.0",
            expected_python_paths={"forex_trading/__init__.py"},
        )

    def test_valid_wheel_only_generates_nonrelease_receipt(self):
        wheel(self.artifact)
        r = self.check()
        self.assertEqual(len(r["wheel_sha256"]), 64)
        self.assertEqual(r["packaged_python_paths_verified"], 1)
        for flag in ("is_reproducible_build_proof", "is_signed_release",
                     "is_last_known_good", "may_deploy_or_trade"):
            self.assertFalse(r[flag])
        self.assertEqual(r["kind"], "CI_BUILD_SMOKE_ONLY")

    def test_wrong_project_name_rejected(self):
        wheel(self.artifact, name="other-package")
        with self.assertRaisesRegex(ValueError, "WHEEL_PROJECT_NAME_OR_VERSION_MISMATCH"):
            self.check()

    def test_wrong_version_rejected(self):
        wheel(self.artifact, version="2.0.0")
        with self.assertRaisesRegex(ValueError, "WHEEL_PROJECT_NAME_OR_VERSION_MISMATCH"):
            self.check()

    def test_missing_python_source_rejected(self):
        wheel(self.artifact, include_source=False)
        with self.assertRaisesRegex(ValueError, "MISSING_PACKAGED_PYTHON_SOURCE"):
            self.check()

    def test_unsafe_path_inside_wheel_rejected(self):
        wheel(self.artifact, extra_path="../secret.txt")
        with self.assertRaisesRegex(ValueError, "UNSAFE_WHEEL_CONTENTS"):
            self.check()

    def test_missing_wheel_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "CI_WHEEL_MISSING"):
            self.check()

    def test_identical_repeated_wheel_contents_pass(self):
        wheel(self.artifact)
        repeat = Path(self.tmp.name) / "repeat" / self.artifact.name
        repeat.parent.mkdir()
        copyfile(self.artifact, repeat)
        self.assertEqual(
            verify_repeat_build_match(self.artifact, repeat),
            self.check()["wheel_sha256"],
        )

    def test_repeated_build_with_different_bytes_fails(self):
        wheel(self.artifact)
        repeat = Path(self.tmp.name) / "repeat" / self.artifact.name
        repeat.parent.mkdir()
        wheel(repeat, extra_path="forex_trading/changed.py")
        with self.assertRaisesRegex(ValueError, "REPEATED_CI_BUILD_SHA256_MISMATCH"):
            verify_repeat_build_match(self.artifact, repeat)

    def test_missing_repeated_wheel_fails(self):
        wheel(self.artifact)
        absent = Path(self.tmp.name) / "repeat" / self.artifact.name
        with self.assertRaisesRegex(ValueError, "REPEATED_CI_BUILD_ARTIFACT_MISSING"):
            verify_repeat_build_match(self.artifact, absent)

    def test_expected_source_list_cannot_be_empty(self):
        wheel(self.artifact)
        with self.assertRaisesRegex(ValueError, "NO_EXPECTED_PYTHON"):
            inspect_wheel(
                self.artifact, project_name="forex-trading-core",
                project_version="0.1.0", expected_python_paths=set())


if __name__ == "__main__":
    unittest.main()
