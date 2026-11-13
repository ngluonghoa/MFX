"""P0.156: private strict right-closed pivot research on real code paths.

Fixtures are synthetic immutable SHA-store test doubles, NEVER actual licensed
quotes or approved Forex strategy values. Both 1L/1R and 2L/2R are SIM ONLY.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal as D
import json
from unittest import TestCase

from mfx_research.sealed_private_pivot_sensitivity import (
    POLICY_WINDOWS, VERSION, PrivatePivotSensitivityReceipt,
    scan_private_sealed_pivot_sensitivity,
)
from mfx_research.sealed_multibar_private_features import (
    calculate_private_multibar_from_sealed_rows,
)
from mfx_research.six_tf_readonly_context import (
    build_six_timeframe_readonly_context,
)
from test_mfx_v1_sealed_multibar_private_features import archived
from test_mfx_v1_six_tf_sealed_archive_consumer import (
    ASOF, _seed_native, consume, fixtures,
)
from test_mfx_v1_manual_signal_only_drive_output import mocked
from tools.run_mfx_v1_manual_drive_six_tf import safe_summary


def receipt():
    return consume()


def sim_scan(m5_updates):
    m5,h4,d1,_=archived()
    result=list(m5)
    for index,kw in m5_updates.items():
        result[index]=replace(result[index],**kw)
    source=tuple(result)
    tech=build_six_timeframe_readonly_context(
        source[-12:],h4,d1,asof_utc=ASOF,
    )
    private=calculate_private_multibar_from_sealed_rows(
        source,h4,d1,tech,asof_utc=ASOF,
    )
    return scan_private_sealed_pivot_sensitivity(private,tech)


def study(data,frame="M5",left=1,right=1):
    return next(
        x for x in data.studied if x.frame==frame
        and x.left_bars==left and x.right_bars==right
    )


class MfxP156SealedPivotResearchTests(TestCase):
    def test_01_actual_consumer_attaches_private_research(self):
        r=receipt()
        x=r.private_pivot_sensitivity
        self.assertIsInstance(x,PrivatePivotSensitivityReceipt)
        self.assertEqual(x.version,VERSION)
        self.assertEqual(x.asof_utc,r.technical.asof_utc)
        self.assertEqual(x.source_private_multibar_digest_sha256,
                         r.private_multibar.private_input_digest_sha256)

    def test_02_both_sim_windows_are_scanned_independently(self):
        x=receipt().private_pivot_sensitivity
        self.assertEqual(POLICY_WINDOWS,((1,1),(2,2)))
        self.assertEqual(len(x.studied),12)
        self.assertEqual(
            tuple((p.frame,p.left_bars,p.right_bars) for p in x.studied),
            tuple((f,a,b) for a,b in POLICY_WINDOWS for f in
                  ("M5","M15","M30","H1","H4","D1")),
        )

    def test_03_actual_ohlc_history_eligibility_is_not_signal(self):
        r=receipt()
        x=r.private_pivot_sensitivity
        self.assertEqual(
            tuple(f.frame for f in x.studied[:6]
                  if f.status.startswith("PRIVATE_RESEARCH")),
            ("M5","M15","M30"),
        )
        self.assertEqual(
            tuple(f.frame for f in x.studied[6:]
                  if f.status.startswith("PRIVATE_RESEARCH")),
            ("M5","M15"),
        )
        self.assertEqual((x.action,x.stage),("NO_SIGNAL","UNVERIFIED"))

    def test_04_constant_prices_have_no_strict_pivots(self):
        x=receipt().private_pivot_sensitivity
        for s in x.studied:
            self.assertEqual(s.pivots,())

    def test_05_high_pivot_only_after_right_bar_close(self):
        x=sim_scan({-4:{"high":"1.1050"}})
        p=[p for p in study(x).pivots if p.kind=="HIGH"]
        self.assertEqual(len(p),1)
        self.assertEqual(p[0].candidate_mid_price,D("1.1050"))
        self.assertEqual(p[0].candidate_source_open_label,
                         "2026-11-12T11:40:00+00:00")
        self.assertEqual(p[0].right_confirmation_source_open_label,
                         "2026-11-12T11:45:00+00:00")
        self.assertEqual(p[0].right_candle_closed_utc,
                         "2026-11-12T11:50:00+00:00")
        self.assertFalse(p[0].independently_proven_first_known)

    def test_06_same_high_valid_with_two_closed_right_bars(self):
        x=sim_scan({-4:{"high":"1.1050"}})
        pivots=[p for p in study(x,left=2,right=2).pivots
                if p.kind=="HIGH"]
        self.assertEqual(len(pivots),1)
        self.assertEqual(pivots[0].right_candle_closed_utc,
                         "2026-11-12T11:55:00+00:00")
        self.assertFalse(pivots[0].source_owner_numeric_rule_approved)

    def test_07_one_right_bar_not_two_right_bars(self):
        x=sim_scan({-2:{"high":"1.1050"}})
        self.assertEqual(len(study(x).pivots),1)
        self.assertEqual(study(x,left=2,right=2).pivots,())
        self.assertEqual(study(x).pivots[0].right_candle_closed_utc,
                         "2026-11-12T12:00:00+00:00")

    def test_08_open_latest_candle_cannot_confirm_its_own_pivot(self):
        x=sim_scan({-1:{"high":"1.1050"}})
        self.assertEqual(study(x).pivots,())
        self.assertEqual(study(x,left=2,right=2).pivots,())

    def test_09_low_pivot_uses_strict_neighbor_lows(self):
        x=sim_scan({-4:{"low":"1.0950"}})
        p=[x for x in study(x).pivots if x.kind=="LOW"]
        self.assertEqual(len(p),1)
        self.assertEqual(p[0].candidate_mid_price,D("1.0950"))

    def test_10_ambiguous_high_and_low_same_bar_is_dropped(self):
        x=sim_scan({-4:{"high":"1.1100","low":"1.0900"}})
        self.assertEqual(study(x).pivots,())
        self.assertEqual(study(x,left=2,right=2).pivots,())

    def test_11_equal_neighbor_high_disqualifies_strict_pivot(self):
        x=sim_scan({-4:{"high":"1.1050"},-3:{"high":"1.1050"}})
        self.assertEqual(study(x).pivots,())
        self.assertEqual(study(x,left=2,right=2).pivots,())

    def test_12_equal_neighbor_low_disqualifies_strict_pivot(self):
        x=sim_scan({-4:{"low":"1.0950"},-3:{"low":"1.0950"}})
        self.assertEqual(study(x).pivots,())
        self.assertEqual(study(x,left=2,right=2).pivots,())

    def test_13_multiple_nonoverlapping_highs_can_be_found(self):
        x=sim_scan({-10:{"high":"1.1050"},-4:{"high":"1.1050"}})
        values=[p for p in study(x).pivots if p.kind=="HIGH"]
        self.assertEqual(len(values),2)
        self.assertLess(values[0].right_candle_closed_utc,
                        values[1].right_candle_closed_utc)

    def test_14_two_profiles_never_choose_strategy_parameters(self):
        x=sim_scan({-4:{"high":"1.1050"}})
        self.assertEqual(x.policy_authority,
                         "TWO_SIM_RESEARCH_WINDOWS_NOT_FOREX_1TO1_RULES")
        self.assertFalse(x.original_forex_numeric_pivot_policy_approved)
        self.assertFalse(x.may_publish_price_derived_values_or_signals)

    def test_15_one_native_h4_insufficient_for_even_1_1(self):
        x=receipt().private_pivot_sensitivity
        for left,right in POLICY_WINDOWS:
            s=study(x,"H4",left,right)
            self.assertEqual(s.status,"INSUFFICIENT_CONTIGUOUS_CLOSED_BARS")
            self.assertEqual(s.pivots,())

    def test_16_three_real_native_h4_closed_rows_enable_1_1_only(self):
        m,h,d,p=fixtures()
        h.objects={"manifest":{},"chunk":{}}
        _seed_native(h,"4h",(
            "2026-11-12 00:00:00","2026-11-12 04:00:00",
            "2026-11-12 08:00:00",
        ))
        x=consume(m,h,d,p).private_pivot_sensitivity
        self.assertTrue(study(x,"H4").status.startswith("PRIVATE_RESEARCH"))
        self.assertEqual(study(x,"H4",2,2).status,
                         "INSUFFICIENT_CONTIGUOUS_CLOSED_BARS")

    def test_17_two_separate_native_h4_rows_not_enough(self):
        m,h,d,p=fixtures()
        h.objects={"manifest":{},"chunk":{}}
        _seed_native(h,"4h",("2026-11-12 04:00:00",
                            "2026-11-12 08:00:00"))
        x=consume(m,h,d,p).private_pivot_sensitivity
        self.assertEqual(study(x,"H4").status,
                         "INSUFFICIENT_CONTIGUOUS_CLOSED_BARS")

    def test_18_d1_calendar_not_scanned_even_if_many_closed_dates(self):
        m,h,d,p=fixtures()
        d.objects={"manifest":{},"chunk":{}}
        _seed_native(d,"1day",(
            "2026-11-07","2026-11-08","2026-11-09",
            "2026-11-10","2026-11-11",
        ))
        x=consume(m,h,d,p).private_pivot_sensitivity
        for left,right in POLICY_WINDOWS:
            st=study(x,"D1",left,right)
            self.assertEqual(st.observations,5)
            self.assertEqual(st.status,
                             "D1_SOURCE_SESSION_CALENDAR_UNVERIFIED")
            self.assertEqual(st.pivots,())
        self.assertFalse(x.real_d1_session_continuity_qualified)

    def test_19_stale_m5_m15_absent_not_backfilled(self):
        x=consume(asof=ASOF+timedelta(minutes=18)).private_pivot_sensitivity
        self.assertEqual(x.frames_missing_or_stale,("M5","M15"))
        self.assertNotIn("M5",tuple(p.frame for p in x.studied))
        self.assertNotIn("M15",tuple(p.frame for p in x.studied))

    def test_20_no_first_known_or_oos_claim_from_closed_candles(self):
        x=receipt().private_pivot_sensitivity
        for flag in ("data_license_and_redistribution_verified",
                     "real_historical_first_known_verified",
                     "chronological_oos_acceptance",
                     "original_forex_numeric_pivot_policy_approved",
                     "real_d1_session_continuity_qualified",
                     "net_bidask_rr_available","may_trade"):
            with self.subTest(flag=flag):
                self.assertFalse(getattr(x,flag))

    def test_21_zero_provider_drive_and_broker_side_effects(self):
        x=receipt().private_pivot_sensitivity
        self.assertEqual((x.provider_requests,x.drive_cache_writes,
                          x.broker_orders),(0,0,0))

    def test_22_private_input_local_sha_is_bound_without_extra_reads(self):
        r=receipt()
        self.assertEqual(
            r.private_pivot_sensitivity.source_private_multibar_digest_sha256,
            r.private_multibar.private_input_digest_sha256,
        )
        self.assertEqual(len(
            r.private_pivot_sensitivity.source_private_multibar_digest_sha256),64)

    def test_23_tampered_historical_private_input_detected(self):
        r=receipt()
        multi=r.private_multibar
        histories=list(multi.private_closed_histories)
        name,rows=histories[0]
        histories[0]=(name,(replace(rows[0],high="1.1060"),)+rows[1:])
        with self.assertRaisesRegex(ValueError,"PRIVATE_INPUT_SHA_MISMATCH"):
            scan_private_sealed_pivot_sensitivity(
                replace(multi,private_closed_histories=tuple(histories)),
                r.technical,
            )

    def test_24_tampered_latest_source_sha_detected(self):
        r=receipt()
        multi=r.private_multibar
        histories=list(multi.private_closed_histories)
        name,rows=histories[0]
        histories[0]=(name,rows[:-1]+(
            replace(rows[-1],sha_claim="f"*64),))
        with self.assertRaisesRegex(ValueError,"SOURCE_CANDLE_SHA_MISMATCH"):
            scan_private_sealed_pivot_sensitivity(
                replace(multi,private_closed_histories=tuple(histories)),
                r.technical,
            )

    def test_25_price_beyond_ohlc_envelope_denied(self):
        r=receipt()
        multi=r.private_multibar
        histories=list(multi.private_closed_histories)
        name,rows=histories[0]
        histories[0]=(name,(replace(rows[0],high="0.1"),)+rows[1:])
        with self.assertRaisesRegex(ValueError,"INVALID_CLOSED_OHLC"):
            scan_private_sealed_pivot_sensitivity(
                replace(multi,private_closed_histories=tuple(histories)),
                r.technical,
            )

    def test_26_reject_untyped_receipt(self):
        r=receipt()
        for bad in (None,{},[],"EUR/USD"):
            with self.subTest(bad=bad),self.assertRaisesRegex(
                    ValueError,"TYPED_INPUT_REQUIRED"):
                scan_private_sealed_pivot_sensitivity(bad,r.technical)

    def test_27_reject_untyped_technical_context(self):
        data=receipt().private_multibar
        for bad in (None,{},[],"D1"):
            with self.subTest(bad=bad),self.assertRaisesRegex(
                    ValueError,"TYPED_INPUT_REQUIRED"):
                scan_private_sealed_pivot_sensitivity(data,bad)

    def test_28_forged_numeric_source_approval_denied(self):
        r=receipt()
        changed=replace(r.private_multibar,
                        original_forex_numeric_source_approved=True)
        with self.assertRaisesRegex(ValueError,"TYPED_INPUT_REQUIRED"):
            scan_private_sealed_pivot_sensitivity(changed,r.technical)

    def test_29_forged_publisher_first_known_denied(self):
        r=receipt()
        changed=replace(r.private_multibar,
                        first_known_publisher_verified=True)
        with self.assertRaisesRegex(ValueError,"TYPED_INPUT_REQUIRED"):
            scan_private_sealed_pivot_sensitivity(changed,r.technical)

    def test_30_forged_public_signal_denied(self):
        r=receipt()
        changed=replace(r.private_multibar,action="BUY")
        with self.assertRaisesRegex(ValueError,"TYPED_INPUT_REQUIRED"):
            scan_private_sealed_pivot_sensitivity(changed,r.technical)

    def test_31_original_source_102_blobs_and_no_licence_still_unverified(self):
        r=receipt()
        self.assertFalse(r.github_reviewed_m5_anchors_checked)
        self.assertFalse(r.provider_account_data_rights_verified)
        self.assertFalse(r.source_numeric_entry_rules_approved)
        self.assertFalse(r.historical_asof_replay_proven)
        self.assertEqual((r.technical.action,r.technical.stage),
                         ("NO_SIGNAL","UNVERIFIED"))

    def test_32_public_safe_summary_includes_only_no_signal_coverage(self):
        report=safe_summary(mocked(),drive_gets=7)
        s=report["private_pivot_sensitivity"]
        self.assertEqual(s["status"],
                         "TWO_SIM_ONLY_RESEARCH_POLICIES_NO_SIGNAL")
        self.assertEqual(s["sim_research_only_profiles"],
                         ["SIM_1_LEFT_1_RIGHT","SIM_2_LEFT_2_RIGHT"])
        self.assertEqual(s["frames_with_enough_contiguous_closed_history_by_profile"],
                         [["M5","M15","M30"],["M5","M15"]])
        self.assertFalse(s["publisher_first_known_verified"])
        self.assertFalse(s["original_forex_numeric_pivot_policy_approved"])
        self.assertEqual((report["drive_reads"],report["broker_orders"]),(7,0))

    def test_33_no_price_or_private_pivots_in_public_log(self):
        report=safe_summary(mocked(),drive_gets=1)
        rendered=json.dumps(report)
        for forbidden in ("candidate_mid_price","candidate_source_open_label",
                          "right_confirmation_source_open_label",
                          "right_candle_closed_utc","private_closed_histories",
                          "source_private_multibar_digest_sha256",
                          "1.1010","1.0990","refresh_token","file_id"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,rendered)
        self.assertFalse(report["private_pivot_sensitivity"]
                         ["reported_pivot_prices_or_directions"])

    def test_34_missing_private_study_fails_closed_in_manual_report(self):
        r=mocked()
        with self.assertRaisesRegex(ValueError,"PIVOT_SENSITIVITY_AUTHORITY_DRIFT"):
            safe_summary(replace(r,private_pivot_sensitivity=None),
                         drive_gets=0)

    def test_35_spoofed_study_source_rights_denied_in_manual_report(self):
        r=mocked()
        pivot=r.private_pivot_sensitivity
        altered=replace(pivot,original_forex_numeric_pivot_policy_approved=True)
        with self.assertRaisesRegex(ValueError,"PIVOT_SENSITIVITY_AUTHORITY_DRIFT"):
            safe_summary(replace(r,private_pivot_sensitivity=altered),
                         drive_gets=0)

    def test_36_spoofed_d1_calendar_release_denied(self):
        r=mocked()
        pivot=r.private_pivot_sensitivity
        s=list(pivot.studied)
        d1index=5
        s[d1index]=replace(s[d1index],
                           status="PRIVATE_RESEARCH_RIGHT_BARS_CLOSED_NO_FIRST_KNOWN_PROOF")
        with self.assertRaisesRegex(ValueError,"PIVOT_SOURCE_POLICY_DRIFT"):
            safe_summary(replace(r,private_pivot_sensitivity=replace(
                pivot,studied=tuple(s))),drive_gets=0)

    def test_37_immutable_receipt_and_points(self):
        a=sim_scan({-4:{"high":"1.1050"}})
        with self.assertRaises(FrozenInstanceError):
            a.action="BUY"
        p=study(a).pivots[0]
        with self.assertRaises(FrozenInstanceError):
            p.may_publish_buy_sell=True

    def test_38_studies_not_published_as_buy_sell(self):
        a=sim_scan({-4:{"high":"1.1050"}})
        self.assertEqual(a.action,"NO_SIGNAL")
        self.assertTrue(all(not s.may_publish_buy_sell
                            and not s.source_numeric_policy_verified
                            for s in a.studied))
        self.assertTrue(all(not p.may_publish_buy_sell
                            and not p.independently_proven_first_known
                            for s in a.studied for p in s.pivots))

    def test_39_private_multibar_may_be_replayed_with_same_content(self):
        r1,r2=receipt(),receipt()
        self.assertEqual(r1.private_pivot_sensitivity,
                         r2.private_pivot_sensitivity)
        self.assertEqual(r1.private_multibar.private_closed_histories,
                         r2.private_multibar.private_closed_histories)

    def test_40_no_new_vendor_broker_or_drive_writer_needed(self):
        r=receipt()
        self.assertEqual((r.provider_price_calls,r.drive_cache_writes,
                          r.broker_orders),(0,0,0))
        self.assertFalse(r.private_pivot_sensitivity.may_trade)
        self.assertFalse(r.private_pivot_sensitivity.net_bidask_rr_available)
