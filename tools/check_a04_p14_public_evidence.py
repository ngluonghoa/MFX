"""CI only — A04/P0.14 official-public-document register and no grant."""
from __future__ import annotations

import json

from tools.a04_p14_public_vendor_evidence import read_register, verify_public_register


def main() -> None:
    result = verify_public_register(read_register())
    print("MFX_A04_P14_OFFICIAL_PUBLIC_EVIDENCE_FAIL_CLOSED_PASS")
    print("MFX_A04_P14_RECEIPT " + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
