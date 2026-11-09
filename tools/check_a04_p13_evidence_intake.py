"""Cloud CI-only P0.13 exact synthetic evidence intake denial."""
from __future__ import annotations

import json

from tools.a04_p13_evidence_intake import read_baseline, verify_baseline


def main() -> None:
    result = verify_baseline(read_baseline())
    print("MFX_A04_P13_EVIDENCE_ATTESTATION_GATE_PASS")
    print("MFX_A04_P13_RECEIPT " + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
