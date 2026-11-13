"""MFX P0.153: OHLC-first policy and dormant private Drive safe output, offline.

No live API, MT4/MT5 terminal, price ingestion, broker or unlicensed rights.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from unittest import TestCase

from mfx_research.ohlc_first_optional_bidask_policy import (
    VERSION, classify_ohlc_first_mode,
)
from mfx_research.signal_only_six_tf_response import (
    build_signal_only_research_response,
)
from tools.run_mfx_v1_manual_drive_six_tf import safe_summary
from test_mfx_v1_signal_only_six_tf_response import (
    technical, sealed,
)
from test_mfx_v1_six_tf_sealed_archive_consumer import (
    ASOF, consume,
)

def full():
    return build_signal_only_research_response(sealed())


def incomplete():
    return build_signal_only_research_response(sealed(
        t=technical(("M30", "H1", "H4", "D1"))))


class MfxOhlcFirstOptionalBidaskPolicyTests(TestCase):
    def test_01_complete_closed_ohlc_context_not_a_signal(self):
        s=classify_ohlc_first_mode(full())
        self.assertEqual(s.schema_version,VERSION)
        self.assertTrue(s.sealed_six_frame_context_complete)
        self.assertEqual(s.analysis_lane,"CLOSED_OHLC_RESEARCH_ONLY")
        self.assertEqual(s.source_quote_side,"MID")
        self.assertFalse(s.publishable_buy_sell)
        self.assertFalse(s.release_ready)

    def test_02_incomplete_m5_m15_never_synthesizes_context(self):
        s=classify_ohlc_first_mode(incomplete())
        self.assertFalse(s.sealed_six_frame_context_complete)
        self.assertEqual(s.frames_missing_or_stale,("M5","M15"))
        self.assertEqual(s.technical_status,"SIX_TF_INCOMPLETE_RESEARCH_ONLY")
        self.assertTrue(s.ohlc_research_implementation_may_proceed_offline)

    def test_03_mid_ohlc_research_does_not_depend_on_bidask_or_terminal(self):
        for report in (full(),incomplete()):
            decision=classify_ohlc_first_mode(report)
            self.assertFalse(decision.requires_bidask_for_closed_ohlc_pattern_research)
            self.assertFalse(decision.requires_mt4_or_mt5_terminal)
            self.assertFalse(decision.future_broker_connection_required)
            self.assertTrue(decision.ohlc_research_implementation_may_proceed_offline)

    def test_04_cost_aware_live_net_rr_requires_separate_licensed_bidask(self):
        s=classify_ohlc_first_mode(full())
        self.assertTrue(s.requires_bidask_for_executable_net_rr)
        self.assertEqual(s.future_bidask_route,"OPTIONAL_LICENSED_READ_ONLY_API")
        self.assertEqual(s.net_rr_status,"NOT_AVAILABLE_FROM_MID_OHLC")
        self.assertFalse(s.bidask_quote_observed_and_licensed)
        self.assertFalse(s.live_bidask_broker_fill_accuracy_proven)

    def test_05_approval_is_never_inferred_from_six_frames(self):
        s=classify_ohlc_first_mode(full())
        for k in ("original_numeric_rules_approved",
                  "source_data_account_rights_verified",
                  "bidask_quote_observed_and_licensed",
                  "publishable_buy_sell","release_ready",
                  "broker_order_integration"):
            with self.subTest(flag=k):
                self.assertIs(getattr(s,k),False)

    def test_06_no_vendor_calls_cache_writes_or_orders(self):
        s=classify_ohlc_first_mode(full())
        self.assertEqual((s.provider_requests,s.drive_price_cache_writes,
                          s.broker_orders),(0,0,0))

    def test_07_forged_buy_action_rejected(self):
        with self.assertRaisesRegex(ValueError,"FORGED_RIGHTS"):
            classify_ohlc_first_mode(replace(full(),action="BUY"))

    def test_08_forged_ask_bid_input_rejected(self):
        for side in ("ASK","BID","MBA",None):
            with self.subTest(side=side),self.assertRaisesRegex(
                    ValueError,"FORGED_RIGHTS"):
                classify_ohlc_first_mode(replace(full(),quote_side=side))

    def test_09_source_rights_or_entry_rules_cannot_be_self_approved(self):
        for field in ("verified_original_numeric_rules",
                      "account_data_rights_verified",
                      "bidask_execution_costs_verified",
                      "historical_oos_verified","may_publish_buy_sell",
                      "may_trade"):
            with self.subTest(field=field),self.assertRaisesRegex(
                    ValueError,"FORGED_RIGHTS"):
                classify_ohlc_first_mode(replace(full(),**{field:True}))

    def test_10_side_effect_counters_cannot_be_forged(self):
        for field in ("provider_requests","drive_cache_writes",
                      "broker_orders"):
            with self.subTest(field=field),self.assertRaisesRegex(
                    ValueError,"FORGED_RIGHTS"):
                classify_ohlc_first_mode(replace(full(),**{field:1}))

    def test_11_frames_missing_status_cannot_be_self_certified(self):
        with self.assertRaisesRegex(ValueError,"FRAME_OR_SOURCE"):
            classify_ohlc_first_mode(replace(full(),
                                             frames_missing_or_stale=("M5",)))

    def test_12_out_of_order_missing_frames_rejected(self):
        with self.assertRaisesRegex(ValueError,"FRAME_OR_SOURCE"):
            classify_ohlc_first_mode(replace(incomplete(),
                                             frames_missing_or_stale=("M15","M5")))

    def test_13_duplicates_in_frame_tuple_rejected(self):
        report=full()
        with self.assertRaisesRegex(ValueError,"FRAME_OR_SOURCE"):
            classify_ohlc_first_mode(replace(report,
                         frames_present=("M5","M5","M15","M30","H1","H4","D1")))

    def test_14_forged_technical_ready_status_denied(self):
        with self.assertRaisesRegex(ValueError,"TECHNICAL_STATUS"):
            classify_ohlc_first_mode(replace(incomplete(),
                    technical_status="SIX_TF_COMPLETE_RESEARCH_ONLY"))

    def test_15_deleted_owner_numeric_blocker_denied(self):
        report=full()
        reasons=tuple(x for x in report.reason_codes
                    if x!="ORIGINAL_SOURCE_NUMERIC_RULES_UNAPPROVED")
        with self.assertRaisesRegex(ValueError,"FRAME_OR_SOURCE"):
            classify_ohlc_first_mode(replace(report,reason_codes=reasons))

    def test_16_deleted_bidask_blocker_denied(self):
        report=full()
        reasons=tuple(x for x in report.reason_codes
                    if x!="BID_ASK_SPREAD_COST_SL_TP_NET_RR_UNVERIFIED")
        with self.assertRaisesRegex(ValueError,"FRAME_OR_SOURCE"):
            classify_ohlc_first_mode(replace(report,reason_codes=reasons))

    def test_17_wrong_provider_or_symbol_denied(self):
        report=full()
        for change in ({"source_provider":"SIM:OTHER"},
                       {"instrument":"GBP/USD"}):
            with self.subTest(change=change),self.assertRaisesRegex(
                    ValueError,"FORGED_RIGHTS"):
                classify_ohlc_first_mode(replace(report,**change))

    def test_18_untyped_input_rejected(self):
        for bad in (None,{},[],"NO_SIGNAL"):
            with self.subTest(bad=bad),self.assertRaisesRegex(
                    TypeError,"TYPED_SIGNAL_ONLY"):
                classify_ohlc_first_mode(bad)

    def test_19_deterministic_immutable_source_mode_receipt(self):
        a=classify_ohlc_first_mode(full())
        b=classify_ohlc_first_mode(full())
        self.assertEqual(a,b)
        with self.assertRaises(FrozenInstanceError):
            a.requires_mt4_or_mt5_terminal=True

    def test_20_actual_dormant_drive_safe_summary_includes_policy(self):
        s=safe_summary(consume(asof=ASOF),drive_gets=3)
        p=s["analysis_mode_decision"]
        self.assertEqual(p["analysis_lane"],"CLOSED_OHLC_RESEARCH_ONLY")
        self.assertEqual(p["market_quote_mode"],"MID_TECHNICAL_REFERENCE_ONLY")
        self.assertFalse(p["requires_mt4_or_mt5_terminal"])
        self.assertFalse(p["requires_bidask_for_closed_ohlc_pattern_research"])
        self.assertTrue(p["requires_bidask_for_executable_net_rr"])
        self.assertEqual(p["future_bidask_route"],"OPTIONAL_LICENSED_READ_ONLY_API")
        self.assertFalse(p["source_data_account_rights_verified"])
        self.assertFalse(p["publishable_buy_sell"])
        self.assertIsNone(s["signal_only_output"]["net_risk_reward"])

    def test_21_legacy_metadata_and_no_additional_drive_get(self):
        s=safe_summary(consume(asof=ASOF),drive_gets=5)
        self.assertEqual(s["drive_reads"],5)
        self.assertEqual(s["provider_price_requests"],0)
        self.assertEqual(s["drive_writes"],0)
        self.assertEqual(s["broker_orders"],0)
        self.assertEqual(s["action"],"NO_SIGNAL")
        self.assertIn("sha_verified_source_freshness_timing",s)

    def test_22_output_contains_no_prices_secrets_or_vendor_credentials(self):
        r=safe_summary(consume(asof=ASOF),drive_gets=0)
        serial=json.dumps(r,sort_keys=True)
        for token in ("1.1000","1.1020","oauth_client_secret",
                      "refresh_token","MT5_PASSWORD","api_key","file_id"):
            with self.subTest(token=token):
                self.assertNotIn(token,serial)
        self.assertNotIn("entry_price",r["analysis_mode_decision"])
        self.assertNotIn("net_risk_reward",r["analysis_mode_decision"])

    def test_23_sha_fingerprint_unchanged_by_separate_policy_projection(self):
        receipt=consume(asof=ASOF)
        prior=build_signal_only_research_response(receipt)
        status=safe_summary(receipt,drive_gets=1)
        self.assertEqual(status["signal_only_output"]
                         ["evidence_fingerprint_sha256"],
                         prior.evidence_fingerprint_sha256)

    def test_24_no_terminal_network_or_price_reader_dependency_in_policy(self):
        s=classify_ohlc_first_mode(full())
        self.assertFalse(s.broker_order_integration)
        self.assertFalse(s.requires_mt4_or_mt5_terminal)
        self.assertFalse(s.publishable_buy_sell)
        self.assertEqual(s.provider_requests,0)
