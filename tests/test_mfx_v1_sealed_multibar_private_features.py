"""MFX P0.155: real multi-candle technical arithmetic from already sealed rows.

Hermetic source/Drive store double only. Never proves vendor licence,
publisher first-known, historical OOS, source-owner numeric rules, BID/ASK,
real market prices or publishable BUY/SELL.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
from decimal import Decimal as D
import json
from unittest import TestCase

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_research.sealed_multibar_private_features import (
    VERSION, PrivateMultiBarReceipt,
    calculate_private_multibar_from_sealed_rows,
)
from mfx_research.six_tf_readonly_context import (
    build_six_timeframe_readonly_context,
)
from mfx_research.six_tf_sealed_archive_consumer import (
    _m5_pinned_rows, _native_pinned_rows,
)
from tools.run_mfx_v1_manual_drive_six_tf import safe_summary
from test_mfx_v1_six_tf_sealed_archive_consumer import (
    ASOF, PRICES, _seed_native, consume, fixtures,
)
from test_mfx_v1_manual_signal_only_drive_output import mocked


def archived():
    m, h, d, p = fixtures()
    m5, _ = _m5_pinned_rows(m, asof_utc=ASOF, fixture_pins=p)
    native4, _, _ = _native_pinned_rows(h, interval="4h")
    native1, _, _ = _native_pinned_rows(d, interval="1day")
    return m5, native4, native1, consume(m, h, d, p).technical


def frame(name, source=None):
    data = (consume().private_multibar if source is None else source)
    return next(x for x in data.frames if x.frame == name)


def calculate(m5=None, native4=None, native1=None, technical=None, *, asof=ASOF):
    orig = archived()
    return calculate_private_multibar_from_sealed_rows(
        orig[0] if m5 is None else m5,
        orig[1] if native4 is None else native4,
        orig[2] if native1 is None else native1,
        orig[3] if technical is None else technical,
        asof_utc=asof,
    )


class MfxSealedPrivateMultibarTests(TestCase):
    def test_01_all_six_frames_reused_without_new_source_reads(self):
        r=consume()
        x=r.private_multibar
        self.assertIsInstance(x,PrivateMultiBarReceipt)
        self.assertEqual(x.version,VERSION)
        self.assertEqual(tuple(f.frame for f in x.frames),
                         ("M5","M15","M30","H1","H4","D1"))
        self.assertTrue(x.public_technical_context_complete)
        self.assertEqual(x.frames_missing_or_stale,())
        self.assertEqual(x.asof_utc,r.technical.asof_utc)

    def test_02_proves_actual_multibar_input_counts(self):
        x=consume().private_multibar
        self.assertEqual(
            tuple(f.observed_closed_candles for f in x.frames),
            (16,8,4,2,1,1),
        )
        self.assertEqual(
            tuple(f.analysis_status for f in x.frames[-2:]),
            ("INSUFFICIENT_CLOSED_HISTORY",)*2,
        )

    def test_03_m5_exact_prior_close_delta_and_true_range(self):
        x=frame("M5")
        self.assertEqual(x.latest_close_change,D(0))
        self.assertEqual(x.latest_true_range,D("0.0030"))
        self.assertEqual(x.observed_mean_true_range,D("0.0030"))
        self.assertEqual(x.observed_low,D("1.0990"))
        self.assertEqual(x.observed_high,D("1.1020"))
        self.assertEqual(x.latest_two_close_direction,"CLOSE_UNCHANGED")

    def test_04_m15_uses_exact_3_m5_source_windows(self):
        x=frame("M15")
        self.assertEqual(x.observed_closed_candles,8)
        self.assertEqual(x.latest_source_label,
                         "2026-11-12T11:45:00+00:00")
        self.assertEqual(x.latest_true_range,D("0.0030"))
        self.assertEqual(x.continuity,"EXACT_CONTIGUOUS_UTC_GRID_ONLY")

    def test_05_m30_two_timeframe_windows(self):
        x=frame("M30")
        self.assertEqual(x.observed_closed_candles,4)
        self.assertEqual(x.latest_source_label,
                         "2026-11-12T11:30:00+00:00")

    def test_06_h1_exact_two_closed_hours(self):
        x=frame("H1")
        self.assertEqual(x.observed_closed_candles,2)
        self.assertEqual(x.latest_source_label,
                         "2026-11-12T11:00:00+00:00")
        self.assertEqual(x.analysis_status,
                         "MULTIBAR_RESEARCH_CALCULATED_NOT_APPROVED")

    def test_07_native_h4_and_sydney_d1_do_not_fabricate_history(self):
        x=consume().private_multibar
        for n in ("H4","D1"):
            y=frame(n,x)
            self.assertEqual(y.observed_closed_candles,1)
            self.assertIsNone(y.latest_close_change)
            self.assertIsNone(y.latest_true_range)
            self.assertIsNone(y.observed_low)
            self.assertEqual(y.latest_two_close_direction,
                             "NO_TWO_CLOSED_CANDLES")
        self.assertEqual(frame("D1",x).continuity,
                         "D1_LOCAL_SESSION_GAPS_UNVERIFIED")

    def test_08_h4_native_two_real_closed_source_rows(self):
        m,h,d,p=fixtures()
        h.objects={"manifest":{},"chunk":{}}
        _seed_native(h,"4h",("2026-11-12 04:00:00",
                            "2026-11-12 08:00:00"))
        x=consume(m,h,d,p).private_multibar
        h4=frame("H4",x)
        self.assertEqual(h4.observed_closed_candles,2)
        self.assertEqual(h4.latest_true_range,D("0.0030"))

    def test_09_d1_two_session_days_still_not_calendar_authenticated(self):
        m,h,d,p=fixtures()
        d.objects={"manifest":{},"chunk":{}}
        _seed_native(d,"1day",("2026-11-10","2026-11-11"))
        x=consume(m,h,d,p).private_multibar
        y=frame("D1",x)
        self.assertEqual(y.observed_closed_candles,2)
        self.assertIsNotNone(y.latest_true_range)
        self.assertEqual(y.continuity,"D1_LOCAL_SESSION_GAPS_UNVERIFIED")
        self.assertFalse(x.historical_asof_replay_proven)

    def test_10_sydney_session_weekend_gap_never_called_contiguous_utc(self):
        m,h,d,p=fixtures()
        d.objects={"manifest":{},"chunk":{}}
        _seed_native(d,"1day",("2026-11-08","2026-11-11"))
        y=frame("D1",consume(m,h,d,p).private_multibar)
        self.assertEqual(y.observed_closed_candles,2)
        self.assertEqual(y.continuity,"D1_LOCAL_SESSION_GAPS_UNVERIFIED")

    def test_11_no_missing_m5_m15_backfill(self):
        r=consume(asof=ASOF+timedelta(minutes=18))
        x=r.private_multibar
        self.assertEqual(x.frames_missing_or_stale,("M5","M15"))
        self.assertEqual(tuple(f.frame for f in x.frames),
                         ("M30","H1","H4","D1"))
        self.assertFalse(x.public_technical_context_complete)

    def test_12_explicit_m5_history_gap_discards_before_gap(self):
        bars,h4,d1,tech=archived()
        first=tuple(replace(x,start_utc=(
            (ASOF.replace(hour=9,minute=0,second=0,microsecond=0)+timedelta(minutes=5*i))
             .isoformat())) for i,x in enumerate(bars[:12]))
        # Older 09:00-10:00; actual latest 11:00-12:00; missing 10:00-11:00.
        gapped=first+bars[12:]
        receipt=calculate(m5=gapped,native4=h4,native1=d1,technical=tech)
        self.assertEqual(frame("M5",receipt).observed_closed_candles,12)
        self.assertEqual(frame("H1",receipt).observed_closed_candles,1)
        self.assertEqual(frame("M15",receipt).observed_closed_candles,4)
        self.assertEqual(frame("M30",receipt).observed_closed_candles,2)
        self.assertEqual(frame("H1",receipt).analysis_status,
                         "INSUFFICIENT_CLOSED_HISTORY")

    def test_13_widened_true_range_uses_prior_close_gap(self):
        m5,h4,d1,_=archived()
        changed=tuple(m5[:-2])+(replace(
            m5[-2], high="1.1080",close="1.1060"),m5[-1])
        technical=build_six_timeframe_readonly_context(
            changed[-12:],h4,d1,asof_utc=ASOF)
        x=calculate(m5=changed,native4=h4,native1=d1,
                    technical=technical)
        self.assertEqual(frame("M5",x).latest_true_range,D("0.0070"))
        self.assertEqual(frame("M5",x).latest_close_change,D("-0.0050"))
        self.assertEqual(frame("M5",x).latest_two_close_direction,
                         "CLOSE_DECREASED")

    def test_14_private_digest_bound_to_actual_source_prices(self):
        m5,h4,d1,tech=archived()
        a=calculate(m5=m5,native4=h4,native1=d1,technical=tech)
        changed=m5[:-15]+(replace(m5[-15],close="1.1005"),)+m5[-14:]
        b=calculate(m5=changed,native4=h4,native1=d1,technical=tech)
        self.assertNotEqual(a.private_input_digest_sha256,
                            b.private_input_digest_sha256)

    def test_15_private_digest_is_deterministic(self):
        a,b=consume().private_multibar,consume().private_multibar
        self.assertEqual(a,b)
        self.assertEqual(len(a.private_input_digest_sha256),64)

    def test_16_latest_row_must_equal_existing_source_frame(self):
        m5,h4,d1,tech=archived()
        altered=tuple(m5[:-1])+(replace(m5[-1],close="1.1015"),)
        with self.assertRaisesRegex(ValueError,"SOURCE_PRICE_SHA_MISMATCH"):
            calculate(m5=altered,native4=h4,native1=d1,technical=tech)

    def test_17_forged_source_sha_denied(self):
        m5,h4,d1,tech=archived()
        wrong=replace(tech.frames[-1],evidence_sha256="f"*64)
        forged=replace(tech,frames=tech.frames[:-1]+(wrong,))
        with self.assertRaisesRegex(ValueError,"SOURCE_PRICE_SHA_MISMATCH"):
            calculate(m5=m5,native4=h4,native1=d1,technical=forged)

    def test_18_wrong_source_last_label_denied(self):
        m5,h4,d1,tech=archived()
        wrong=replace(tech.frames[1],source_label="2020-01-01T00:00:00+00:00")
        frames=tech.frames[:1]+(wrong,)+tech.frames[2:]
        with self.assertRaisesRegex(ValueError,"LAST_CLOSED_SOURCE_LABEL"):
            calculate(m5=m5,native4=h4,native1=d1,
                      technical=replace(tech,frames=frames))

    def test_19_wrong_price_in_native_h4_denied(self):
        m5,h4,d1,tech=archived()
        bad=replace(h4,closed_bars=(replace(
            h4.closed_bars[-1],close="1.1015"),))
        with self.assertRaisesRegex(ValueError,"SOURCE_PRICE_SHA_MISMATCH"):
            calculate(m5=m5,native4=bad,native1=d1,technical=tech)

    def test_20_future_h4_source_rejected(self):
        m5,h4,d1,tech=archived()
        bad=replace(h4,closed_bars=(replace(
            h4.closed_bars[-1],native_open_label="2026-11-12 12:00:00"),))
        with self.assertRaisesRegex(ValueError,"NATIVE_H4_OPEN_OR_FUTURE"):
            calculate(m5=m5,native4=bad,native1=d1,technical=tech)

    def test_21_future_d1_local_session_denied(self):
        m5,h4,d1,tech=archived()
        bad=replace(d1,closed_bars=(replace(
            d1.closed_bars[-1],native_open_label="2026-11-12"),))
        with self.assertRaisesRegex(ValueError,"NATIVE_D1_LOCAL_DATE_NOT_CLOSED"):
            calculate(m5=m5,native4=h4,native1=bad,technical=tech)

    def test_22_wrong_source_numeric_authority_denied(self):
        m5,h4,d1,tech=archived()
        with self.assertRaisesRegex(ValueError,"NO_AUTHORITY"):
            calculate(m5=m5,native4=h4,native1=d1,technical=replace(
                tech,forex_1to1_numerical_parity_verified=True))

    def test_23_forged_trade_or_buy_action_denied(self):
        for kw in ({"action":"BUY"},{"may_trade":True},
                   {"may_publish_verified_buy_sell":True},
                   {"source_feed_subscription_verified":True}):
            m5,h4,d1,tech=archived()
            with self.subTest(kw=kw),self.assertRaisesRegex(
                    ValueError,"NO_AUTHORITY"):
                calculate(m5=m5,native4=h4,native1=d1,
                          technical=replace(tech,**kw))

    def test_24_invalid_decision_clock_denied(self):
        m5,h4,d1,tech=archived()
        for stamp in (ASOF.replace(tzinfo=None),
                      ASOF+timedelta(days=1),
                      ASOF.astimezone(timezone(timedelta(hours=7)))):
            with self.subTest(stamp=stamp),self.assertRaises(ValueError):
                calculate(m5=m5,native4=h4,native1=d1,
                          technical=tech,asof=stamp)

    def test_25_wrong_typed_technical_receipt_denied(self):
        m5,h4,d1,_=archived()
        for value in (None,{},[],1):
            with self.subTest(value=value),self.assertRaisesRegex(
                    ValueError,"NO_AUTHORITY"):
                calculate_private_multibar_from_sealed_rows(
                    m5,h4,d1,value,asof_utc=ASOF)

    def test_26_corrupt_source_candle_envelope_rejected(self):
        m5,h4,d1,tech=archived()
        broken=tuple(m5[:-1])+(replace(m5[-1],high="0.1"),)
        with self.assertRaises(ValueError):
            calculate(m5=broken,native4=h4,native1=d1,technical=tech)

    def test_27_zero_side_effects_and_no_numeric_source_permissions(self):
        r=consume().private_multibar
        self.assertEqual((r.provider_requests,r.drive_market_cache_writes,
                          r.broker_orders),(0,0,0))
        self.assertEqual((r.action,r.stage),("NO_SIGNAL","UNVERIFIED"))
        self.assertFalse(r.may_publish_prices_or_signals)
        self.assertFalse(r.original_forex_numeric_source_approved)
        self.assertFalse(r.bidask_net_rr_available)
        self.assertFalse(r.vendor_source_license_verified)
        self.assertFalse(r.first_known_publisher_verified)

    def test_28_no_pivot_or_wilder_atr_claim(self):
        x=consume().private_multibar
        self.assertFalse(x.confirmed_pivot_or_original_trend_inferred)
        self.assertFalse(x.historical_asof_replay_proven)
        self.assertEqual(x.source_price_side,"MID")
        self.assertFalse(any(f.publishable_buy_sell for f in x.frames))

    def test_29_original_source_chains_still_verified(self):
        r=consume()
        self.assertTrue(r.all_three_bounded_sha_chains_verified)
        self.assertFalse(r.github_reviewed_m5_anchors_checked)
        self.assertEqual(len(r.m5_manifest_tip_sha256),64)
        self.assertFalse(r.provider_account_data_rights_verified)

    def test_30_safe_existing_manual_report_integrates_multibar(self):
        r=safe_summary(mocked(),drive_gets=7)
        sub=r["private_multibar_research"]
        self.assertEqual(sub["status"],
                         "MULTIBAR_COMPUTED_PRIVATE_NO_VALUES_PUBLISHED")
        self.assertEqual(sub["frames_processed"],6)
        self.assertEqual(sub["frames_with_two_or_more_closed_candles"],
                         ["M5","M15","M30","H1"])
        self.assertEqual(sub["frames_with_insufficient_closed_history"],
                         ["H4","D1"])
        self.assertEqual(r["drive_reads"],7)

    def test_31_safe_manual_report_missing_m5_m15_never_covered(self):
        r=safe_summary(
            mocked(asof=ASOF+timedelta(minutes=18)),drive_gets=0)
        sub=r["private_multibar_research"]
        self.assertEqual(sub["missing_or_stale_frames"],["M5","M15"])
        self.assertEqual(sub["frames_processed"],4)
        self.assertEqual(r["action"],"NO_SIGNAL")

    def test_32_never_log_private_price_or_true_range_or_digest(self):
        r=safe_summary(mocked(),drive_gets=1)
        serialized=json.dumps(r)
        for key in ("latest_close_change","observed_mean_true_range",
                    "observed_low","latest_true_range",
                    "private_input_digest_sha256",
                    "1.1000","1.1010","1.0990","api_key",
                    "refresh_token","file_id"):
            with self.subTest(key=key):
                self.assertNotIn(key,serialized)
        self.assertFalse(r["private_multibar_research"]
                         ["published_raw_or_derived_price_values"])

    def test_33_forged_input_privileges_rejected_by_manual_report(self):
        receipt=mocked()
        x=receipt.private_multibar
        changed=replace(x,may_publish_prices_or_signals=True)
        with self.assertRaisesRegex(ValueError,"MULTIBAR_PRIVATE_SCOPE_DRIFT"):
            safe_summary(replace(receipt,private_multibar=changed),
                         drive_gets=0)

    def test_34_forged_frame_source_sha_denied_by_manual_report(self):
        receipt=mocked()
        x=receipt.private_multibar
        change=replace(x.frames[0],latest_source_sha256_claim="0"*64)
        tampered=replace(x,frames=(change,)+x.frames[1:])
        with self.assertRaisesRegex(ValueError,"MULTIBAR_SOURCE_DRIFT"):
            safe_summary(replace(receipt,private_multibar=tampered),
                         drive_gets=0)

    def test_35_missing_private_multibar_denied(self):
        receipt=mocked()
        with self.assertRaisesRegex(ValueError,"MULTIBAR_PRIVATE_SCOPE_DRIFT"):
            safe_summary(replace(receipt,private_multibar=None),
                         drive_gets=0)

    def test_36_immutable_receipt_and_frame(self):
        rec=consume().private_multibar
        with self.assertRaises(FrozenInstanceError):
            rec.action="BUY"
        with self.assertRaises(FrozenInstanceError):
            rec.frames[0].latest_close_change=D(42)

    def test_37_no_price_claim_from_closed_bar_alone(self):
        x=consume().private_multibar
        self.assertTrue(x.actual_multi_bar_technical_arithmetic)
        self.assertFalse(x.confirmed_pivot_or_original_trend_inferred)
        self.assertFalse(x.may_trade)
        self.assertFalse(x.may_publish_prices_or_signals)
