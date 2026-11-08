"""MFX-only cloud CI guard against silently importing the Forex source distribution.

MFX intentionally preserves the frozen `forex_trading` import API while its
wheel distribution is `mfx-forex-core`. Both distributions MUST NOT share one
Python environment: they would overwrite the same import namespace.
This is a read-only build/QA check, not an execution, broker, or release gate.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from importlib import metadata
from pathlib import Path

MFX_DISTRIBUTION = "mfx-forex-core"
FOREX_DISTRIBUTION = "forex-trading-core"
IMPORT_PACKAGE = "forex_trading"


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def assess_mfx_import_ownership(
    *,
    distribution_name: str | None,
    distribution_version: str | None,
    forex_distribution_present: bool,
    package_owners: tuple[str, ...],
    import_origin: Path | None,
    environment_root: Path,
    is_virtual_environment: bool,
) -> dict[str, object]:
    """Fail closed for duplicate/ambiguous imports or missing isolated runtime."""
    if distribution_name is None or _canonical(distribution_name) != MFX_DISTRIBUTION:
        raise ValueError("MFX_DISTRIBUTION_MISSING_OR_WRONG")
    if not distribution_version:
        raise ValueError("MFX_DISTRIBUTION_VERSION_MISSING")
    if forex_distribution_present:
        raise ValueError("FOREX_DISTRIBUTION_CO_INSTALLED")
    if not is_virtual_environment:
        raise ValueError("ISOLATED_PYTHON_RUNTIME_REQUIRED")
    owners = tuple(sorted(_canonical(owner) for owner in package_owners))
    if owners != (MFX_DISTRIBUTION,):
        raise ValueError("FOREX_IMPORT_NAMESPACE_OWNER_AMBIGUOUS")
    if import_origin is None:
        raise ValueError("FOREX_IMPORT_MODULE_MISSING")
    if not import_origin.resolve().is_relative_to(environment_root.resolve()):
        raise ValueError("FOREX_IMPORT_OUTSIDE_ISOLATED_RUNTIME")
    return {
        "kind": "MFX_RUNTIME_IMPORT_OWNERSHIP_QA_ONLY",
        "distribution": MFX_DISTRIBUTION,
        "distribution_version": distribution_version,
        "import_package": IMPORT_PACKAGE,
        "single_distribution_owner_verified": True,
        "isolated_virtual_environment_verified": True,
        "is_strategy_parity_proof": False,
        "is_production_release": False,
        "may_deploy_or_trade": False,
    }


def _get_distribution(name: str) -> metadata.Distribution | None:
    try:
        return metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return None


def main() -> None:
    installed = _get_distribution(MFX_DISTRIBUTION)
    origin_spec = importlib.util.find_spec(IMPORT_PACKAGE)
    receipt = assess_mfx_import_ownership(
        distribution_name=installed.metadata.get("Name") if installed else None,
        distribution_version=installed.version if installed else None,
        forex_distribution_present=_get_distribution(FOREX_DISTRIBUTION) is not None,
        package_owners=tuple(
            metadata.packages_distributions().get(IMPORT_PACKAGE, ())
        ),
        import_origin=(
            Path(origin_spec.origin)
            if origin_spec is not None and origin_spec.origin is not None
            else None
        ),
        environment_root=Path(sys.prefix),
        is_virtual_environment=sys.prefix != sys.base_prefix,
    )
    print("MFX_RUNTIME_IMPORT_OWNERSHIP_PASS " + json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
