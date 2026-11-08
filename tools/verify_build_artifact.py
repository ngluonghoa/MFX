"""Standard-library CI wheel smoke audit (not a release or signature).

Validate the *built* wheel against pyproject metadata and packaged Python
sources, and print a content digest. No upload, tag, deploy, broker/Drive call
or assertion of reproducible builds or release approval is performed.
"""
import argparse
from email.parser import Parser
from hashlib import sha256
from json import dumps
from pathlib import Path, PurePosixPath
from re import sub
import tomllib
from zipfile import ZipFile


def _canonical_name(name: str) -> str:
    return sub(r"[-_.]+", "-", name).lower()


def inspect_wheel(
    path: Path,
    *,
    project_name: str,
    project_version: str,
    expected_python_paths: set[str],
) -> dict[str, object]:
    """Reject wrong artifact metadata, missing code and dangerous zip paths."""
    if not path.is_file() or path.suffix != ".whl":
        raise ValueError("CI_WHEEL_MISSING_OR_INVALID_EXTENSION")
    if not expected_python_paths:
        raise ValueError("NO_EXPECTED_PYTHON_PACKAGE_FILES")
    with ZipFile(path, "r") as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise ValueError("DUPLICATED_WHEEL_PATH")
        for item in infos:
            pure = PurePosixPath(item.filename)
            if (pure.is_absolute() or ".." in pure.parts
                    or "\\" in item.filename or
                    ((item.external_attr >> 16) & 0o170000) == 0o120000):
                raise ValueError("UNSAFE_WHEEL_CONTENTS")
        actual = set(names)
        missing = expected_python_paths - actual
        if missing:
            raise ValueError("MISSING_PACKAGED_PYTHON_SOURCE:" + ",".join(sorted(missing)))
        metadata_paths = [p for p in names if p.endswith(".dist-info/METADATA")]
        wheel_paths = [p for p in names if p.endswith(".dist-info/WHEEL")]
        record_paths = [p for p in names if p.endswith(".dist-info/RECORD")]
        if not (len(metadata_paths) == len(wheel_paths) == len(record_paths) == 1):
            raise ValueError("INCOMPLETE_WHEEL_DIST_INFO")
        meta = Parser().parsestr(archive.read(metadata_paths[0]).decode("utf-8"))
        if (_canonical_name(meta.get("Name", "")) != _canonical_name(project_name)
                or meta.get("Version") != project_version):
            raise ValueError("WHEEL_PROJECT_NAME_OR_VERSION_MISMATCH")
    digest = sha256(path.read_bytes()).hexdigest()
    return {
        "kind": "CI_BUILD_SMOKE_ONLY",
        "project": project_name,
        "declared_version": project_version,
        "wheel_name": path.name,
        "wheel_sha256": digest,
        "packaged_python_paths_verified": len(expected_python_paths),
        "is_reproducible_build_proof": False,
        "is_signed_release": False,
        "is_last_known_good": False,
        "may_deploy_or_trade": False,
    }


def verify_repeat_build_match(
    first: Path, second: Path,
) -> str:
    """Same-environment repeated-wheel hash equality; not external attestation."""
    if not first.is_file() or not second.is_file():
        raise ValueError("REPEATED_CI_BUILD_ARTIFACT_MISSING")
    if first.name != second.name:
        raise ValueError("REPEATED_WHEEL_NAME_MISMATCH")
    first_sha = sha256(first.read_bytes()).hexdigest()
    second_sha = sha256(second.read_bytes()).hexdigest()
    if first_sha != second_sha:
        raise ValueError("REPEATED_CI_BUILD_SHA256_MISMATCH")
    return first_sha


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel_dir", type=Path)
    parser.add_argument("--repeat-wheel-dir", type=Path, default=None)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    project = args.repository_root
    with (project / "pyproject.toml").open("rb") as handle:
        metadata = tomllib.load(handle)["project"]
    wheels = sorted(args.wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("EXACTLY_ONE_CI_WHEEL_REQUIRED")
    expected = {
        p.relative_to(project / "src").as_posix()
        for p in (project / "src" / "forex_trading").rglob("*.py")
    }
    result = inspect_wheel(
        wheels[0], project_name=metadata["name"],
        project_version=metadata["version"],
        expected_python_paths=expected,
    )
    if args.repeat_wheel_dir is not None:
        repeat_paths = sorted(args.repeat_wheel_dir.glob("*.whl"))
        if len(repeat_paths) != 1:
            raise ValueError("EXACTLY_ONE_REPEAT_CI_WHEEL_REQUIRED")
        repeated = inspect_wheel(
            repeat_paths[0], project_name=metadata["name"],
            project_version=metadata["version"],
            expected_python_paths=expected,
        )
        if verify_repeat_build_match(wheels[0], repeat_paths[0]) != result["wheel_sha256"]:
            raise ValueError("REPEAT_BUILD_INTERNAL_DIGEST_ERROR")
        result["repeat_build_sha256"] = repeated["wheel_sha256"]
        result["same_environment_repeated_build_verified"] = True
        # This does NOT claim reproducibility across Python versions, hosts,
        # build toolchains, package mirrors, operating systems or dates.
    print(dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
