"""Cloud CI-only P0.30 22-label design register demo, not market execution."""
from __future__ import annotations

import json

from mfx_research.p030_approved_nonentry_design import (
    ADDITIONS, nonentry_design_preview, read_22_zone_design_manifest,
)


def main() -> None:
    r = read_22_zone_design_manifest()
    if (len(r.zones) != 22
            or len(r.entry_long_labels) != 8
            or len(r.entry_short_labels) != 8
            or r.watch_labels != ("B7", "FX-S11")
            or r.exit_long_warning_labels != ("S3", "S8")
            or r.exit_short_warning_labels != ("FX-B10", "FX-B11")
            or r.approved_new_labels != ADDITIONS
            or r.numerical_rules_approved != 0
            or r.b2_s2_source_obligations_pending != 36
            or r.release_ready):
        raise RuntimeError("P030_22_ZONE_DESIGN_COUNTS_OR_SOURCE_GATES_FAIL")
    for label in ADDITIONS:
        for claimed in (False, True):
            preview = nonentry_design_preview(label, claimed)
            if (preview.action != "NO_SIGNAL" or preview.may_auto_exit
                    or preview.may_open_position or preview.may_publish
                    or preview.broker_orders != 0):
                raise RuntimeError("P030_NONENTRY_SAFETY_GATES_FAIL")
    print("MFX_A04_P30_USER_APPROVED_22_ZONE_DESIGN_ONLY_PASS")
    print("MFX_A04_P30_RECEIPT " + json.dumps({
        "current_mfx_design_labels": len(r.zones),
        "original_forex_labels": len(r.original_labels),
        "previous_mfx_design_labels": len(r.previous_mfx_19_labels),
        "entry_long_candidates": len(r.entry_long_labels),
        "entry_short_candidates": len(r.entry_short_labels),
        "watch_only": list(r.watch_labels),
        "exit_long_warning_only": list(r.exit_long_warning_labels),
        "exit_short_warning_only": list(r.exit_short_warning_labels),
        "new_user_approved_nonentry_labels": list(r.approved_new_labels),
        "numeric_predicates_approved": r.numerical_rules_approved,
        "b2_s2_numeric_obligations_pending": r.b2_s2_source_obligations_pending,
        "market_calls": r.real_quote_calls,
        "drive_quote_cache_writes": r.market_drive_cache_writes,
        "broker_orders": r.broker_orders,
        "real_buy_sell_or_exit_alerts": r.live_signals + r.live_exit_warnings,
        "may_release": r.release_ready,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
