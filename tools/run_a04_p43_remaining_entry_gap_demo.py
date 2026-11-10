"""Hosted GitHub-only P0.43 14-entry source-gap review receipt (NO_SIGNAL)."""
from __future__ import annotations

import json

from mfx_research.p043_remaining_entry_source_gaps import (
    read_remaining_entry_gap_report,
)


def main() -> None:
    r = read_remaining_entry_gap_report()
    if (len(r.rules) != 14
            or r.qualitative_phase_review_slots != 56
            or r.original_source_anchored_phases != 52
            or r.mfx_design_only_phases_without_original_anchor != 4
            or r.owner_signed_numeric_approvals_across_all_entries != 0
            or r.published_confirmed_signals != 0
            or r.broker_orders != 0 or r.release_ready):
        raise RuntimeError("P043_NO_NUMERIC_APPROVAL_OR_COVERAGE_GUARD")
    print("MFX_A04_P43_14_ENTRY_56_QUALITATIVE_SOURCE_GAPS_NO_SIGNAL_PASS")
    print("MFX_A04_P43_RECEIPT " + json.dumps({
        "version": r.version,
        "frozen_forex_catalog_labels": r.original_forex_source_labels,
        "approved_mfx_design_labels": r.approved_mfx_design_labels,
        "separately_indexed_b2_s2_labels": r.separately_indexed_b2_s2_labels,
        "original_b2_s2_owner_decisions_pending":
            r.original_b2_s2_numeric_owner_decisions_pending,
        "additional_entry_review_labels": [x.label for x in r.rules],
        "remaining_entry_qualitative_stage_slots":
            r.qualitative_phase_review_slots,
        "original_source_anchored_phases":
            r.original_source_anchored_phases,
        "mfx_design_only_phases": r.mfx_design_only_phases_without_original_anchor,
        "entry_source_numeric_approvals": 0,
        "confirmed_signals": r.published_confirmed_signals,
        "real_market_provider_calls": r.real_market_provider_calls,
        "broker_orders": r.broker_orders,
        "external_action": r.action,
        "ready_for_release": r.release_ready,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
