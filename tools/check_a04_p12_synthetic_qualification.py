"""CI only: P0.12 fully synthetic fail-closed scenario gate."""
from __future__ import annotations

import json

from tools.a04_p12_synthetic_qualification import read_report, verify_report


def main() -> None:
    receipt = verify_report(read_report())
    print("MFX_A04_P12_PINNED_SYNTHETIC_FAIL_CLOSED_PASS")
    print("MFX_A04_P12_RECEIPT " + json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
