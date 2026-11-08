"""Extract declared PEP 517 build requirements for a bounded pip-audit.

This audits a currently resolved version satisfying each requirement; it does
not pin or prove the isolated build environment used by pip wheel.
"""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path


def build_requires(pyproject_bytes: bytes) -> tuple[str, ...]:
    document = tomllib.loads(pyproject_bytes.decode("utf-8", errors="strict"))
    build = document.get("build-system")
    if not isinstance(build, dict):
        raise ValueError("MISSING_BUILD_SYSTEM")
    requires = build.get("requires")
    if not isinstance(requires, list) or not requires:
        raise ValueError("EMPTY_BUILD_REQUIREMENTS")
    for item in requires:
        if (
            not isinstance(item, str)
            or not item.strip()
            or "\n" in item
            or "\r" in item
            or item.startswith("-")
        ):
            raise ValueError("UNSAFE_BUILD_REQUIREMENT")
    if len(set(requires)) != len(requires):
        raise ValueError("DUPLICATE_BUILD_REQUIREMENTS")
    return tuple(requires)


def main() -> int:
    if len(sys.argv) != 2:
        print("USAGE: write_build_audit_requirements.py OUTPUT_FILE", file=sys.stderr)
        return 2
    project = Path(__file__).resolve().parent.parent
    target = Path(sys.argv[1])
    if target.exists():
        print("BUILD_REQUIREMENTS_OUTPUT_ALREADY_EXISTS", file=sys.stderr)
        return 2
    try:
        requirements = build_requires((project / "pyproject.toml").read_bytes())
        target.write_text("\n".join(requirements) + "\n", encoding="utf-8")
    except (OSError, UnicodeError, ValueError, tomllib.TOMLDecodeError) as err:
        print(f"BUILD_REQUIREMENTS_AUDIT_UNVERIFIED: {type(err).__name__}", file=sys.stderr)
        return 2
    print(f"BUILD_REQUIREMENTS_EXTRACTED count={len(requirements)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
