"""P0.154: hermetic private six-TF MID OHLC body/wick math and safe report.

Actual source contract through preexisting sealed fixture adapter; all figures
are SYNTHETIC, no vendor rights/real market prices/publishable alerts or broker.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal as D
from hashlib import sha256
import json
from unittest import TestCase

from mfx_research.six_tf_private_candle_geometry import (
    VERSION, compute_private_six_tf_candle_geometry,
)
from tools.run_mfx_v1_manual_drive_six_tf import safe_summary
from test_mfx_v1_manual_signal_only_drive_output import mocked, ASOF


def changed(receipt, frame="M5", **kw):
    old=receipt.technical
    frames=tuple(replace(x, **kw) if x.frame==frame else x
                 for x in old.frames)
    return replace(receipt, technical=replace(old, frames=frames))


def result(receipt=None):
    return compute_private_six_tf_candle_geometry(
        mocked() if receipt is None else receipt,
    )


def shape(frame="M5", receipt=None):
    for r in result(receipt).shapes:
        if r.frame == frame:
            return r
    raise AssertionError("frame unavailable")


class V1PrivateSixTfGeometryTests(TestCase):
    def test_01_full_six_frames_actual_private_computation(self):
        r=result()
        self.assertEqual(r.version,VERSION)
        self.assertEqual(tuple(x.frame for x in r.shapes),
                         ("M5","M15","M30","H1","H4","D1"))
        self.assertEqual(len(r.shapes),6)
        self.assertTrue(r.technical_six_frame_complete)
        self.assertEqual(r.frames_missing_or_stale,())
        self.assertEqual(r.source_price_side,"MID")

    def test_02_reference_math_on_one_real_derived_frame_object(self):
        b=changed(mocked(),frame="M5",open="1.1000",
                  high="1.1050",low="1.0990",close="1.1030")
        x=shape(receipt=b)
        self.assertEqual(x.shape,"CLOSE_ABOVE_OPEN")
        self.assertEqual(x.price_range,D("0.0060"))
        self.assertEqual(x.real_body,D("0.0030"))
        self.assertEqual(x.upper_shadow,D("0.0020"))
        self.assertEqual(x.lower_shadow,D("0.0010"))
        self.assertEqual(x.body_fraction_of_range,D("0.0030")/D("0.0060"))
        self.assertEqual(x.close_position_in_range,
                         D("0.0040")/D("0.0060"))

    def test_03_down_close_math_not_a_sell_signal(self):
        b=changed(mocked(),open="1.1030",high="1.1050",
                  low="1.0990",close="1.1000")
        x=shape(receipt=b)
        self.assertEqual(x.shape,"CLOSE_BELOW_OPEN")
        self.assertEqual(x.price_range,D("0.0060"))
        self.assertEqual(x.real_body,D("0.0030"))
        self.assertEqual(x.upper_shadow,D("0.0020"))
        self.assertEqual(x.lower_shadow,D("0.0010"))
        self.assertFalse(x.may_publish_buy_sell)

    def test_04_open_equals_close_with_nonzero_wicks(self):
        b=changed(mocked(),open="1.1000",high="1.1020",
                  low="1.0990",close="1.1000")
        x=shape(receipt=b)
        self.assertEqual(x.shape,"CLOSE_EQUALS_OPEN")
        self.assertEqual(x.real_body,D(0))
        self.assertEqual(x.body_fraction_of_range,D(0))
        self.assertEqual(x.close_position_in_range,D("0.0010")/D("0.0030"))

    def test_05_exact_flat_bar_does_not_divide_by_zero(self):
        b=changed(mocked(),open="1.101",high="1.101",
                  low="1.101",close="1.101")
        x=shape(receipt=b)
        self.assertEqual((x.price_range,x.real_body,x.upper_shadow,
                          x.lower_shadow),(D(0),)*4)
        self.assertIsNone(x.close_position_in_range)
        self.assertIsNone(x.body_fraction_of_range)

    def test_06_upper_boundary_close_is_exact_one(self):
        b=changed(mocked(),open="1.100",high="1.105",
                  low="1.099",close="1.105")
        x=shape(receipt=b)
        self.assertEqual(x.close_position_in_range,D(1))
        self.assertEqual(x.upper_shadow,D(0))

    def test_07_lower_boundary_close_is_exact_zero(self):
        b=changed(mocked(),open="1.105",high="1.105",
                  low="1.099",close="1.099")
        x=shape(receipt=b)
        self.assertEqual(x.close_position_in_range,D(0))
        self.assertEqual(x.lower_shadow,D(0))

    def test_08_all_six_frames_have_body_wick_invariant(self):
        for x in result().shapes:
            with self.subTest(frame=x.frame):
                self.assertEqual(x.price_range,
                                 x.real_body+x.upper_shadow+x.lower_shadow)
                self.assertGreaterEqual(x.price_range,D(0))
                if x.body_fraction_of_range is not None:
                    self.assertTrue(D(0) <= x.body_fraction_of_range <= D(1))
                    self.assertTrue(D(0) <= x.close_position_in_range <= D(1))

    def test_09_incomplete_hourly_cache_preserves_missing_m5_m15(self):
        r=result(mocked(asof=ASOF+timedelta(minutes=18)))
        self.assertFalse(r.technical_six_frame_complete)
        self.assertEqual(r.frames_missing_or_stale,("M5","M15"))
        self.assertEqual(tuple(x.frame for x in r.shapes),
                         ("M30","H1","H4","D1"))
        self.assertEqual(len(r.shapes),4)

    def test_10_no_trend_pivot_source_approval_from_one_bar(self):
        r=result()
        self.assertEqual(r.resolution,
                         "ONE_LATEST_CLOSED_CANDLE_PER_PRESENT_FRAME")
        for f in ("indicator_trend_or_confirmed_pivot_inferred",
                  "external_data_license_and_derived_distribution_approved",
                  "real_first_known_attribution_verified",
                  "numeric_forex_1to1_strategy_approved",
                  "independent_causal_oos_proven",
                  "bidask_cost_net_rr_available",
                  "may_publish_prices_or_derived_signals",
                  "may_trade"):
            with self.subTest(f=f):
                self.assertFalse(getattr(r,f))
        self.assertEqual((r.action,r.stage),("NO_SIGNAL","UNVERIFIED"))

    def test_11_missing_frame_never_fabricates_technical_output(self):
        rec=mocked(asof=ASOF+timedelta(minutes=18))
        x=result(rec)
        self.assertNotIn("M5",tuple(s.frame for s in x.shapes))
        self.assertNotIn("M15",tuple(s.frame for s in x.shapes))

    def test_12_evidence_fingerprint_links_existing_source_receipt(self):
        from mfx_research.signal_only_six_tf_response import (
            build_signal_only_research_response,
        )
        rec=mocked()
        s=build_signal_only_research_response(rec)
        x=result(rec)
        self.assertEqual(x.source_fingerprint_sha256,
                         s.evidence_fingerprint_sha256)
        self.assertEqual(len(x.private_geometry_fingerprint_sha256),64)

    def test_13_private_geometry_hash_deterministic(self):
        self.assertEqual(result(),result())
        self.assertEqual(result().private_geometry_fingerprint_sha256,
                         result().private_geometry_fingerprint_sha256)

    def test_14_modify_one_ohlc_changes_private_digest(self):
        a=result()
        rec=mocked()
        original=rec.technical.frames[0]
        # Change closed value with preserved high/low bounds in SIM metadata
        widened=changed(rec,"M5",high=str(D(original.high)+D("0.00001")))
        b=result(widened)
        self.assertNotEqual(a.private_geometry_fingerprint_sha256,
                            b.private_geometry_fingerprint_sha256)
        # Underlying metadata SHAs are caller claims, not live attestation.
        self.assertEqual(a.source_fingerprint_sha256,
                         b.source_fingerprint_sha256)

    def test_15_zero_external_io_and_broker_orders(self):
        r=result()
        self.assertEqual((r.provider_requests,r.drive_price_cache_writes,
                          r.broker_orders),(0,0,0))

    def test_16_reject_negative_zero_or_nonfinite_prices(self):
        for val in ("0","-1","NaN","Infinity","-Infinity","sNaN"):
            with self.subTest(val=val),self.assertRaisesRegex(
                    ValueError,"FINITE_POSITIVE"):
                result(changed(mocked(),close=val))

    def test_17_reject_untyped_invalid_price(self):
        for val in (None,1.0,D("1.1"),[],{}):
            with self.subTest(val=val),self.assertRaisesRegex(
                    ValueError,"DECIMAL_PRICE_STRING"):
                result(changed(mocked(),open=val))

    def test_18_reject_non_numeric_or_too_long_price(self):
        for val in ("garbage","x"*65,""):
            with self.subTest(val=val),self.assertRaisesRegex(
                    ValueError,"DECIMAL_PRICE_STRING"):
                result(changed(mocked(),low=val))

    def test_19_reject_open_high_low_close_outside_envelope(self):
        for bad in (
            {"high":"0.99"},
            {"low":"1.99"},
            {"open":"1.99"},
            {"close":"1.99"},
        ):
            with self.subTest(bad=bad),self.assertRaisesRegex(
                    ValueError,"INVALID_CLOSED_OHLC"):
                result(changed(mocked(),**bad))

    def test_20_reject_wrong_native_or_derived_source_shape(self):
        for changes in (
            {"native":False},
            {"source_bar_count":3},
            {"time_basis":"UTC_INTRADAY_WINDOW"},
        ):
            with self.subTest(changes=changes),self.assertRaisesRegex(
                    ValueError,"SOURCE_SCOPE"):
                result(changed(mocked(),frame="M5",**changes))

    def test_21_reject_m15_wrong_aggregation_size(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_SCOPE"):
            result(changed(mocked(),frame="M15",source_bar_count=2))

    def test_22_reject_h1_wrong_source_count(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_SCOPE"):
            result(changed(mocked(),frame="H1",source_bar_count=11))

    def test_23_reject_d1_claim_of_utc_close(self):
        with self.assertRaisesRegex(ValueError,"D1_SESSION"):
            result(changed(mocked(),frame="D1",
                           end_utc="2026-11-12T12:00:00+00:00"))

    def test_24_reject_open_future_non_utc_frame_end(self):
        for value in ("2099-01-01T00:00:00+00:00",
                      "2026-11-12T12:00:00+07:00",
                      "2026-11-12T12:00:00"):
            with self.subTest(value=value),self.assertRaisesRegex(
                    ValueError,"OPEN_OR_FUTURE"):
                result(changed(mocked(),frame="H4",end_utc=value))

    def test_25_reject_unparseable_frame_end(self):
        for value in (None,"NOT_A_DATE"):
            with self.subTest(value=value),self.assertRaisesRegex(
                    ValueError,"INVALID_FRAME_END"):
                result(changed(mocked(),frame="M30",end_utc=value))

    def test_26_original_source_flags_stay_fail_closed(self):
        for flags in ({"provider_account_data_rights_verified":True},
                      {"source_numeric_entry_rules_approved":True},
                      {"may_publish_buy_sell":True}):
            with self.subTest(flags=flags),self.assertRaisesRegex(
                    ValueError,"FORGED_SOURCE"):
                result(replace(mocked(),**flags))

    def test_27_reject_forged_bid_ask_frame(self):
        with self.assertRaisesRegex(ValueError,"FRAME_AUTHORITY_OR_SIDE"):
            result(changed(mocked(),source_price_side="BID"))

    def test_28_reject_untyped_receipt(self):
        for x in (None,{},[],"EUR/USD"):
            with self.subTest(x=x),self.assertRaisesRegex(
                    TypeError,"TYPED_SEALED"):
                compute_private_six_tf_candle_geometry(x)

    def test_29_readonly_safe_report_runs_geometry_but_omits_prices(self):
        r=safe_summary(mocked(),drive_gets=7)
        sub=r["private_ohlc_geometry"]
        self.assertEqual(sub["status"],"COMPUTED_IN_MEMORY_NEVER_PUBLISHED")
        self.assertEqual(sub["frames_computed"],6)
        self.assertTrue(sub["six_frame_technical_complete"])
        self.assertEqual(sub["source_side"],"MID")
        self.assertFalse(sub["prices_and_derived_values_published"])
        for field in ("shape","upper_shadow","lower_shadow","real_body",
                      "price_range","close_position_in_range"):
            self.assertNotIn(field,sub)

    def test_30_incomplete_safe_report_has_count_four(self):
        r=safe_summary(mocked(asof=ASOF+timedelta(minutes=18)),drive_gets=3)
        sub=r["private_ohlc_geometry"]
        self.assertEqual(sub["frames_computed"],4)
        self.assertEqual(sub["frames_missing_or_stale"],["M5","M15"])
        self.assertFalse(sub["six_frame_technical_complete"])
        self.assertEqual(r["action"],"NO_SIGNAL")

    def test_31_metadata_no_credential_bidask_or_price_leak(self):
        r=safe_summary(mocked(),drive_gets=0)
        output=json.dumps(r)
        for forbidden in ("1.1000","1.1040","raw_ohlc",
                          "oauth_client_secret","refresh_token",
                          "source_bid","source_ask","file_id"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,output)
        self.assertEqual(r["provider_price_requests"],0)
        self.assertEqual(r["drive_writes"],0)
        self.assertEqual(r["broker_orders"],0)

    def test_32_manual_report_preserves_sha_and_optional_api_decision(self):
        r=safe_summary(mocked(),drive_gets=2)
        self.assertEqual(r["drive_reads"],2)
        self.assertEqual(r["signal_only_output"]["action"],"NO_SIGNAL")
        self.assertFalse(r["analysis_mode_decision"]["requires_mt4_or_mt5_terminal"])
        self.assertTrue(r["analysis_mode_decision"]["requires_bidask_for_executable_net_rr"])
        self.assertFalse(r["private_ohlc_geometry"]["external_derived_data_rights_verified"])

    def test_33_output_immutable(self):
        r=result()
        with self.assertRaises(FrozenInstanceError):
            r.action="BUY"
        with self.assertRaises(FrozenInstanceError):
            r.shapes[0].shape="PUBLISHABLE_BUY"

    def test_34_source_price_basis_never_promoted_to_bidask(self):
        r=result()
        self.assertEqual(r.source_price_side,"MID")
        self.assertTrue(all(x.price_side=="MID" for x in r.shapes))
        self.assertFalse(r.bidask_cost_net_rr_available)

    def test_35_no_fake_strategy_from_candle_up_close(self):
        b=changed(mocked(),open="1.1000",high="1.1050",
                  low="1.0990",close="1.1030")
        r=result(b)
        self.assertEqual(r.shapes[0].shape,"CLOSE_ABOVE_OPEN")
        self.assertEqual(r.action,"NO_SIGNAL")
        self.assertFalse(r.indicator_trend_or_confirmed_pivot_inferred)
        self.assertFalse(r.may_publish_prices_or_derived_signals)
