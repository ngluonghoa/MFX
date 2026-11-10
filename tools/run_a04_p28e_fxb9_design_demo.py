"""A04/P0.28E: Cloud-hosted SIM-only 8BUY/8SELL FX-B9 overlay QA receipt."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import unittest

from mfx_research.p028e_fxb9_design_overlay import (
    MfxSetupClassification, PredeclaredRangeScope,
    SimFalseBreakEvidence, classify_false_break_research,
    read_fxb9_design_manifest,
)


def main() -> None:
    suite = unittest.defaultTestLoader.discover(
        "tests", pattern="test_a04_p28e_fxb9_design_overlay.py",
    )
    count = suite.countTestCases()
    if count != 20:
        raise ValueError("P028E_PRE_REGISTERED_20_METHOD_DRIFT")
    tested = unittest.TextTestRunner(verbosity=1).run(suite)
    if not tested.wasSuccessful():
        raise ValueError("P028E_FXB9_B3_SOURCE_SCOPE_ORACLE_FAILED")
    review = read_fxb9_design_manifest()
    known = datetime(2026, 11, 10, tzinfo=timezone.utc)
    common = dict(
        instrument_version="SIM:EURUSD",
        origin_event_id="SIM:P028E_CI_FALSE_BREAK_EVENT",
        provider_id="SIM:OFFLINE_NO_REAL_FEED",
        stream_id="SIM:M15_CLOSED",
        calendar_version="SIM:UTC_FIXED",
        support_first_known_utc=known-timedelta(minutes=30),
        candle_end_utc=known,
        first_known_utc=known+timedelta(seconds=1),
        retrieved_at_utc=known+timedelta(seconds=2),
        decision_utc=known+timedelta(seconds=3),
        predeclared_support_exists=True,
        break_observed=True,
        closed_reclaim_observed=True,
    )
    b3=classify_false_break_research(
        SimFalseBreakEvidence(
            scope=PredeclaredRangeScope.INSIDE_OR_AT_RANGE_LOWER_BAND,
            **common,
        )
    )
    fx=classify_false_break_research(
        SimFalseBreakEvidence(
            scope=PredeclaredRangeScope.OUTSIDE_PREDECLARED_RANGE,
            **common,
        )
    )
    if (b3.classification is not MfxSetupClassification.B3_RESEARCH_ONLY
            or fx.classification is not MfxSetupClassification.FXB9_RESEARCH_ONLY
            or b3.research_opportunity_id != fx.research_opportunity_id
            or len(review.extended_labels) != 19
            or review.extended_buy_candidates != 8
            or review.short_candidates != 8
            or review.non_entry_labels != ("B7","S3","S8")
            or review.numeric_entry_approvals != 0
            or review.b2_s2_numeric_source_requirements_pending != 36
            or fx.may_publish or b3.may_publish
            or review.real_buy_sell_alerts != 0):
        raise ValueError("P028E_INVALID_SOURCE_DESIGN_OR_PROMOTION")
    print("MFX_A04_P28E_FXB9_DESIGN_ONLY_PASS")
    print("MFX_A04_P28E_RECEIPT "+json.dumps({
        "preregistered_test_methods":count,
        "source_original_labels":len(review.original_labels),
        "mfx_extended_design_labels":len(review.extended_labels),
        "design_buy_candidates":review.extended_buy_candidates,
        "design_sell_candidates":review.short_candidates,
        "watch_and_protective":len(review.non_entry_labels),
        "fxb9_user_design_approval":"2026-11-10",
        "fxb9_numerical_formula_approved":False,
        "b3_inside_range_not_fxb9":True,
        "shared_origin_research_opportunity_deduplicated":True,
        "source_numeric_entry_rules_approved":0,
        "b2_s2_original_numeric_source_obligations_pending":36,
        "real_buy_sell_alerts":0,
        "real_market_provider_calls":0,
        "real_drive_market_cache_writes":0,
        "broker_orders":0,
        "release_ready":False,
    },sort_keys=True))


if __name__ == "__main__":
    main()
