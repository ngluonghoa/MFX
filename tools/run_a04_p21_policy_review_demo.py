"""Cloud CI P0.21 hard fail-closed B2/S2 source-parameter review proof."""
from __future__ import annotations

import json
from pathlib import Path

from mfx_research.source_parameter_review import (
    BLOCKING_COUNT, read_review_register,
)


def main() -> None:
    path = Path("docs/MFX_A04_P21_SOURCE_PARAMETER_REGISTER.json")
    receipt, file_sha256 = read_review_register(path)
    if (receipt.pending_source_numerical_approvals != BLOCKING_COUNT
            or receipt.source_numeric_rules_approved != 0
            or receipt.simulated_research_examples != 14
            or receipt.stage.value != "UNVERIFIED"
            or not receipt.register_complete_for_review
            or receipt.may_send_confirmed_buy_sell_signal
            or receipt.original_forex_1to1_numerical_parity
            or receipt.may_write_real_drive_market_cache
            or receipt.may_execute_broker_order or receipt.may_release):
        raise ValueError("P021_PROMOTION_OR_MANIFEST_QA_FAILED")
    print("MFX_A04_P21_B2_S2_PARAMETER_REGISTER_REVIEW_PASS")
    print("MFX_A04_P21_RECEIPT " + json.dumps({
        **receipt.as_record(),
        "registry_sha256_not_authorization": file_sha256,
        "numeric_approval_scope": "NONE",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
