"""A04/P0.28E: 20 preregistered FX-B9 MFX-only design scope QA methods.

The user's approval is for *design scope*, not Forex source numerical
calibration, signal publishing, quote licensing or order execution.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from forex_trading.catalog import ZONES, catalog_counts, validate_catalog
from forex_trading.model import ZoneDefinition, ZonePurpose
from mfx_research.p027_signal_source_audit import read_source_evidence_matrix
from mfx_research.p028e_fxb9_design_overlay import (
    FXB9_LABEL, MANIFEST, MfxSetupClassification,
    PredeclaredRangeScope, SimFalseBreakEvidence, _pairs_unique,
    classify_false_break_research, read_fxb9_design_manifest,
    verify_fxb9_design_manifest,
)

T = datetime(2026, 11, 10, tzinfo=timezone.utc)
OUTSIDE = PredeclaredRangeScope.OUTSIDE_PREDECLARED_RANGE
INSIDE = PredeclaredRangeScope.INSIDE_OR_AT_RANGE_LOWER_BAND
UNKNOWN = PredeclaredRangeScope.UNKNOWN


def fixture_manifest() -> dict:
    return json.loads(Path(MANIFEST).read_text(encoding="utf-8"))


def context(
    scope: PredeclaredRangeScope = OUTSIDE,
    **overrides: object,
) -> SimFalseBreakEvidence:
    props = dict(
        instrument_version="SIM:EURUSD",
        origin_event_id="SIM:FALSE_DOWN_BREAK_EVENT_01",
        provider_id="SIM:OFFLINE_SOURCE",
        stream_id="SIM:M15_CLOSED",
        calendar_version="SIM:UTC_RESEARCH",
        scope=scope,
        support_first_known_utc=T-timedelta(hours=1),
        candle_end_utc=T,
        first_known_utc=T+timedelta(seconds=1),
        retrieved_at_utc=T+timedelta(seconds=2),
        decision_utc=T+timedelta(seconds=3),
        predeclared_support_exists=True,
        break_observed=True,
        closed_reclaim_observed=True,
        downside_continuation=False,
    )
    props.update(overrides)
    return SimFalseBreakEvidence(**props)  # type: ignore[arg-type]


class P028EFXB9DesignOverlayOracles(unittest.TestCase):
    def test_01_original_18_and_explicit_fxb9_source_rejection(self) -> None:
        self.assertEqual(len(ZONES),18)
        validate_catalog(ZONES)
        self.assertEqual(sum(z.label==FXB9_LABEL for z in ZONES),0)
        fx=ZoneDefinition(FXB9_LABEL,"F8_FALSE_DOWN_BREAK",
                          ZonePurpose.ENTRY_LONG_CANDIDATE)
        with self.assertRaisesRegex(ValueError,"research-only"):
            validate_catalog(ZONES+(fx,))
        review=read_source_evidence_matrix()
        self.assertEqual(len(review.entries),18)

    def test_02_overlay_19_unique_source_subsequence_order(self) -> None:
        r=read_fxb9_design_manifest()
        self.assertEqual(len(r.original_labels),18)
        self.assertEqual(len(r.extended_labels),19)
        self.assertEqual(len(set(r.extended_labels)),19)
        self.assertEqual(tuple(x for x in r.extended_labels if x!="FX-B9"),
                         r.original_labels)
        self.assertEqual(
            r.extended_labels.index("FX-B9"),
            r.extended_labels.index("B8")+1,
        )
        self.assertEqual(
            r.extended_labels.index("S1"),r.extended_labels.index("FX-B9")+1,
        )

    def test_03_original_7_8_3_and_extended_8_8_3(self) -> None:
        r=read_fxb9_design_manifest()
        counts=catalog_counts(ZONES)
        self.assertEqual(counts[ZonePurpose.ENTRY_LONG_CANDIDATE],7)
        self.assertEqual(counts[ZonePurpose.ENTRY_SHORT_CANDIDATE],8)
        self.assertEqual(r.original_buy_candidates,7)
        self.assertEqual(r.extended_buy_candidates,8)
        self.assertEqual(r.short_candidates,8)
        self.assertEqual(r.non_entry_labels,("B7","S3","S8"))
        self.assertEqual(r.extended_buy_candidates+r.short_candidates,16)

    def test_04_only_one_new_long_extension_and_no_live_signal(self) -> None:
        r=read_fxb9_design_manifest()
        added=set(r.extended_labels)-set(r.original_labels)
        self.assertEqual(added,{"FX-B9"})
        d=fixture_manifest()["extension"]
        self.assertEqual(d["purpose"],"ENTRY_LONG_CANDIDATE")
        self.assertEqual(d["family"],"F8_FALSE_DOWN_BREAK")
        self.assertEqual(d["direction"],"LONG")
        self.assertEqual(d["future_entry_quote_side_if_numerically_approved"],
                         "ASK")
        self.assertFalse(d["action_eligible"])
        self.assertEqual(d["current_action"],"NO_SIGNAL")

    def test_05_watch_b7_and_protective_s3_s8_unchanged(self) -> None:
        self.assertIs(next(z for z in ZONES if z.label=="B7").purpose,
                      ZonePurpose.WATCH_ONLY)
        for k in ("S3","S8"):
            self.assertIs(next(z for z in ZONES if z.label==k).purpose,
                          ZonePurpose.EXIT_LONG_WARNING_ONLY)
        r=read_fxb9_design_manifest()
        self.assertEqual(r.non_entry_labels,("B7","S3","S8"))

    def test_06_four_phase_review_only_with_formula_pending(self) -> None:
        d=fixture_manifest()["extension"]
        self.assertEqual(d["phase_names"],["R0","R_C","R_E","R_F"])
        self.assertEqual(set(d["phase_descriptions"]),
                         {"R0","R_C","R_E","R_F"})
        for k in d["phase_names"]:
            self.assertIn("PENDING",d["phase_descriptions"][k])
        self.assertEqual(d["design_status"],
                         "APPROVED_DESIGN_SCOPE_FORMULA_PENDING")
        self.assertEqual(d["numeric_thresholds"],{})
        self.assertEqual(d["signal_stage"],"UNVERIFIED")

    def test_07_b3_inside_range_excludes_fxb9_outside(self) -> None:
        b3=classify_false_break_research(context(INSIDE))
        out=classify_false_break_research(context(OUTSIDE))
        self.assertIs(b3.classification,MfxSetupClassification.B3_RESEARCH_ONLY)
        self.assertEqual(b3.primary_design_label,"B3")
        self.assertIs(out.classification,
                      MfxSetupClassification.FXB9_RESEARCH_ONLY)
        self.assertEqual(out.primary_design_label,"FX-B9")
        self.assertNotEqual(b3.primary_design_label,out.primary_design_label)

    def test_08_fxb9_requires_earlier_known_support_origin(self) -> None:
        valid=classify_false_break_research(context())
        self.assertEqual(valid.primary_design_label,"FX-B9")
        missed=classify_false_break_research(
            context(predeclared_support_exists=False))
        self.assertIs(missed.classification,MfxSetupClassification.UNKNOWN)
        with self.assertRaisesRegex(ValueError,"FUTURE_KNOWN"):
            context(support_first_known_utc=T+timedelta(seconds=1))

    def test_09_unknown_scope_and_missing_predeclared_support_fail_closed(self):
        for evidence in (
            context(UNKNOWN),
            context(OUTSIDE,predeclared_support_exists=False),
            context(INSIDE,predeclared_support_exists=False),
        ):
            with self.subTest(scope=evidence.scope):
                result=classify_false_break_research(evidence)
                self.assertIs(result.classification,MfxSetupClassification.UNKNOWN)
                self.assertIsNone(result.primary_design_label)
                self.assertEqual(result.current_action,"NO_SIGNAL")

    def test_10_future_retrieval_and_naive_clock_denied(self) -> None:
        for mutation in (
            {"first_known_utc":T-timedelta(seconds=1)},
            {"retrieved_at_utc":T},
            {"decision_utc":T+timedelta(seconds=1)},
            {"support_first_known_utc":T+timedelta(seconds=1)},
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ValueError,"FUTURE_KNOWN"):
                    context(**mutation)
        with self.assertRaisesRegex(ValueError,"UTC_REQUIRED"):
            context(decision_utc=datetime(2026,11,10))

    def test_11_real_or_mixed_stream_identity_denied(self) -> None:
        for mutation in (
            {"instrument_version":"EURUSD"},
            {"origin_event_id":"LIVE:BAD"},
            {"provider_id":"REAL:NON_LICENSED"},
            {"stream_id":"M15_CLOSED"},
            {"calendar_version":"UTC"},
            {"quote_side":"BID"},
            {"source_numeric_approved":True},
            {"real_provider_license_claimed":True},
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ValueError,"SIM_ONLY|REAL_MARKET"):
                    context(**mutation)

    def test_12_same_origin_b3_fxb9_stays_one_research_id(self) -> None:
        a=classify_false_break_research(context(INSIDE))
        b=classify_false_break_research(context(OUTSIDE))
        self.assertEqual(a.research_opportunity_id,b.research_opportunity_id)
        self.assertEqual(len(a.research_opportunity_id),64)
        self.assertFalse(a.may_publish)
        self.assertFalse(b.may_publish)

    def test_13_distinct_origin_pairs_stay_distinct_no_signal(self) -> None:
        a=classify_false_break_research(context())
        b=classify_false_break_research(
            context(origin_event_id="SIM:FALSE_DOWN_BREAK_EVENT_02"))
        c=classify_false_break_research(
            context(instrument_version="SIM:GBPUSD"))
        self.assertEqual(len({a.research_opportunity_id,
                              b.research_opportunity_id,
                              c.research_opportunity_id}),3)
        for item in (a,b,c):
            self.assertEqual(item.current_action,"NO_SIGNAL")
            self.assertEqual(item.broker_orders,0)

    def test_14_no_hidden_numeric_thresholds_in_new_design(self) -> None:
        d=fixture_manifest()["extension"]
        self.assertEqual(d["numeric_thresholds"],{})
        for name in ("R0","R_C","R_E","R_F"):
            self.assertIn("PENDING",d["phase_descriptions"][name])
        self.assertFalse(fixture_manifest()["approval"]["numeric_formula_approved"])

    def test_15_forged_approval_source_or_quote_rights_rejected(self) -> None:
        for location,key,value in (
            ("approval","numeric_formula_approved",True),
            ("approval","real_buy_sell_authorized",True),
            ("approval","backtest_verified",True),
            ("extension","action_eligible",True),
            ("extension","signal_stage","CONFIRMED_SIGNAL"),
            ("extension","current_action","BUY"),
            ("stop_gates","live_market_signals_enabled",True),
            ("stop_gates","real_provider_calls",1),
            ("stop_gates","release_ready",True),
        ):
            d=fixture_manifest()
            d[location][key]=value
            with self.subTest(location=location,key=key):
                with self.assertRaisesRegex(ValueError,"DESIGN_SCOPE_NOT_APPROVED"):
                    verify_fxb9_design_manifest(d)

    def test_16_provenance_is_user_mfx_extension_not_original_1to1(self) -> None:
        d=fixture_manifest()
        self.assertEqual(d["approval"]["date"],"2026-11-10")
        self.assertEqual(
            d["approval"]["type"],"NEW_MFX_EXTENSION_NOT_ORIGINAL_FOREX_1TO1",
        )
        self.assertEqual(
            d["original_source"]["source_audit_fxb9_prior_exclusion_index"],255,
        )
        for field in ("date","type"):
            bad=deepcopy(d)
            bad["approval"][field]="FORGED"
            with self.assertRaisesRegex(ValueError,"DESIGN_SCOPE_NOT_APPROVED"):
                verify_fxb9_design_manifest(bad)

    def test_17_frozen_p27_stays_18_all_numeric_unapproved(self) -> None:
        p27=read_source_evidence_matrix()
        self.assertEqual(len(p27.entries),18)
        self.assertEqual(p27.approved_numeric_entry_rules,0)
        self.assertEqual(p27.b2_s2_source_numeric_pending,36)
        p28=read_fxb9_design_manifest()
        self.assertEqual(len(p28.extended_labels),19)
        self.assertEqual(p28.numeric_entry_approvals,0)
        self.assertEqual(p28.b2_s2_numeric_source_requirements_pending,36)

    def test_18_manifest_digest_stable_duplicates_and_extra_fields_denied(self):
        p=read_fxb9_design_manifest()
        self.assertEqual(p.extended_labels,
                         read_fxb9_design_manifest().extended_labels)
        with self.assertRaisesRegex(ValueError,"DUPLICATE_MANIFEST_KEY"):
            json.loads('{"schema":"X","schema":"Y"}',
                       object_pairs_hook=_pairs_unique)
        v=fixture_manifest()
        v["extension"]["fake_atr_multiplier"]="0.5"
        with self.assertRaisesRegex(ValueError,"EXACT_MANIFEST_KEYS"):
            verify_fxb9_design_manifest(v)

    def test_19_inside_range_and_continuing_break_not_fxb9(self) -> None:
        for kwargs in (
            {"break_observed":False},
            {"closed_reclaim_observed":False},
            {"downside_continuation":True},
        ):
            x=classify_false_break_research(context(OUTSIDE,**kwargs))
            self.assertIs(x.classification,
                          MfxSetupClassification.NOT_FALSE_BREAK)
            self.assertIsNone(x.primary_design_label)
        x=classify_false_break_research(context(INSIDE))
        self.assertEqual(x.primary_design_label,"B3")
        self.assertFalse(x.may_publish)

    def test_20_never_market_alert_drive_cache_or_trade(self) -> None:
        r=read_fxb9_design_manifest()
        out=classify_false_break_research(context(OUTSIDE))
        self.assertFalse(r.source_verified)
        self.assertEqual(r.real_buy_sell_alerts,0)
        self.assertEqual(r.market_provider_calls,0)
        self.assertEqual(r.drive_price_cache_writes,0)
        self.assertEqual(r.broker_orders,0)
        self.assertFalse(r.release_ready)
        self.assertEqual(out.current_action,"NO_SIGNAL")
        self.assertEqual(out.stage,"UNVERIFIED")
        self.assertFalse(out.source_numeric_approved)
        self.assertFalse(out.may_publish)
        self.assertEqual(out.real_provider_calls,0)
        self.assertEqual(out.real_drive_quote_cache_writes,0)
        self.assertEqual(out.broker_orders,0)
