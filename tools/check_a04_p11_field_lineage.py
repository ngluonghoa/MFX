"""A04/P0.11 CI-only field lineage validator."""
from __future__ import annotations

import json

from tools.a04_p11_field_lineage import read_pinned, verify_exact


def main() -> None:
    receipt = verify_exact(read_pinned())
    print("MFX_A04_P11_EXACT_FIELD_LINEAGE_PASS")
    print("MFX_A04_P11_RECEIPT " + json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
