"""GitHub CI-only A04/P0.10 design matrix acceptance. No source/runtime IO."""
from __future__ import annotations

import json

from tools.a04_p10_mapper_matrix import read_matrix, verify_matrix


def main() -> None:
    receipt = verify_matrix(read_matrix())
    print("MFX_A04_P10_DESIGN_ONLY_PINNED_MATRIX_PASS")
    print("MFX_A04_P10_RECEIPT " + json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
