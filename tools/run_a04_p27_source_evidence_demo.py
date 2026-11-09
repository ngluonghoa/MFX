"""A04/P0.27 hosted original Forex source-evidence 18-label/15-entry audit."""
from __future__ import annotations

import json
import unittest

from mfx_research.p027_signal_source_audit import (
    read_source_evidence_matrix,
)


def main() -> None:
    suite = unittest.defaultTestLoader.discover(
        "tests", pattern="test_a04_p27_signal_source_audit.py",
    )
    count = suite.countTestCases()
    if count != 20:
        raise ValueError("P027_20_PRE_REGISTERED_SOURCE_TESTS_REQUIRED")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise ValueError("P027_SOURCE_EVIDENCE_ORACLE_FAILED")
    review = read_source_evidence_matrix()
    if (
        len(review.entries) != 18
        or review.long_entry_candidate_count != 7
        or review.short_entry_candidate_count != 8
        or review.protective_or_watch_count != 3
        or review.b2_s2_source_numeric_pending != 36
        or review.other_entry_candidate_numeric_unmapped != 13
        or review.approved_numeric_entry_rules != 0
        or review.may_send_verified_buy_sell
        or review.may_release
        or review.may_trade
    ):
        raise ValueError("P027_SOURCE_ORIGINAL_NUMERIC_GATES_NOT_PROVEN")
    print("MFX_A04_P27_18_ZONE_SOURCE_EVIDENCE_PASS")
    print("MFX_A04_P27_RECEIPT " + json.dumps(
        review.as_record() | {
            "pre_registered_grouped_methods": count,
            "source_matrix_git_blob_sha": review.matrix_git_blob_sha,
            "source_matrix_sha256": review.matrix_sha256,
            "source_quote_approval": "QUALITATIVE_DESIGN_ONLY",
            "b2_s2_p21_synthetic_examples_unapproved":
                review.unapproved_sim_examples,
            "verified_live_buy_sell_signals": 0,
            "source_first_party_numeric_calibration": "PENDING",
            "source_data_vendor_license": "BLOCKED_ISSUE_27",
            "release_ready": False,
        }, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
