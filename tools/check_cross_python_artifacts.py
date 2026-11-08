"""RE5a same-run cross-Python wheel parity, NOT signed supply-chain provenance.

Compare CI artifacts uploaded from the Python 3.11 and Python 3.12 matrix.
Do not treat filenames, matching hashes or GitHub artifact transport as
cryptographically signed provenance or an approved release.
"""
from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from zipfile import ZipFile

from tools.verify_build_artifact import inspect_wheel

MAX_WHEEL_BYTES = 32 * 1024 * 1024


def _single_wheel(directory: Path) -> Path:
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("CROSS_PYTHON_ARTIFACT_DIRECTORY_INVALID")
    candidates = sorted(directory.iterdir())
    if len(candidates) != 1:
        raise ValueError("EXACTLY_ONE_CROSS_PYTHON_ARTIFACT_REQUIRED")
    wheel = candidates[0]
    if (not wheel.is_file() or wheel.is_symlink() or
            wheel.suffix != ".whl"):
        raise ValueError("CROSS_PYTHON_WHEEL_MISSING_OR_SYMLINK")
    if wheel.stat().st_size > MAX_WHEEL_BYTES:
        raise ValueError("CROSS_PYTHON_WHEEL_TOO_LARGE")
    return wheel


def check_cross_python_artifacts(
    source_root: Path,
    wheel_311_dir: Path,
    wheel_312_dir: Path,
) -> dict[str, object]:
    """Validate package source bytes as well as equal wheel bytes."""
    if wheel_311_dir.resolve() == wheel_312_dir.resolve():
        raise ValueError("SAME_CROSS_PYTHON_ARTIFACT_DIRECTORY")
    with (source_root / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    source_dir = source_root / "src"
    source_files = tuple(
        sorted((source_dir / "forex_trading").rglob("*.py"))
    )
    if not source_files:
        raise ValueError("NO_SOURCE_PYTHON_FILES")
    expected = {}
    for file in source_files:
        if not file.is_file() or file.is_symlink():
            raise ValueError("UNSAFE_OR_UNREADABLE_PYTHON_SOURCE")
        expected[file.relative_to(source_dir).as_posix()] = file.read_bytes()
    left = _single_wheel(wheel_311_dir)
    right = _single_wheel(wheel_312_dir)
    if left.name != right.name:
        raise ValueError("CROSS_PYTHON_WHEEL_FILENAME_MISMATCH")
    digests = []
    for wheel in (left, right):
        detail = inspect_wheel(
            wheel,
            project_name=project["name"],
            project_version=project["version"],
            expected_python_paths=set(expected),
        )
        with ZipFile(wheel) as archive:
            python_names = {
                name for name in archive.namelist() if name.endswith(".py")
            }
            if python_names != set(expected):
                raise ValueError("CROSS_PYTHON_EXTRA_OR_MISSING_SOURCE")
            for relative, original in expected.items():
                if archive.read(relative) != original:
                    raise ValueError("CROSS_PYTHON_PACKAGED_SOURCE_MISMATCH")
        digests.append(detail["wheel_sha256"])
    if digests[0] != digests[1]:
        raise ValueError("CROSS_PYTHON_WHEEL_SHA256_MISMATCH")
    return {
        "kind": "CI_CROSS_PYTHON_WHEEL_PARITY_ONLY",
        "python_versions": ["3.11", "3.12"],
        "wheel_name": left.name,
        "wheel_sha256": digests[0],
        "source_python_files_verified": len(expected),
        "cross_python_wheel_byte_parity_observed": True,
        "is_cross_host_reproducibility_proof": False,
        "is_signed_supply_chain_attestation": False,
        "is_last_known_good": False,
        "may_deploy_or_trade": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel_311_dir", type=Path)
    parser.add_argument("wheel_312_dir", type=Path)
    parser.add_argument(
        "--repository-root", type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    result = check_cross_python_artifacts(
        args.repository_root,
        args.wheel_311_dir,
        args.wheel_312_dir,
    )
    print("CI_CROSS_PYTHON_WHEEL_PARITY_PASS " + json.dumps(
        result, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
