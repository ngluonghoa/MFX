"""P0.150 hermetic test: dormant OAuth GET-only probe consumes P0.149 response.

Uses synthetic sealed archives only. NEVER authenticates to real Google Drive
or qualifies market quotes/source-owner rules or submits broker orders.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import replace
from datetime import timedelta
from io import StringIO
import json
from unittest import TestCase
from unittest.mock import patch

from tools.run_mfx_v1_manual_drive_six_tf import (
    CONFIRMATION, EXISTING_GATES, READ_APPROVAL, main, safe_summary,
)
from test_mfx_v1_six_tf_sealed_archive_consumer import ASOF, consume


def mocked(*, asof=ASOF):
    """Synthetic P0.141 receipt, NOT real reviewed GitHub source read."""
    return replace(
        consume(asof=asof), github_reviewed_m5_anchors_checked=True,
    )


def settings():
    return {
        READ_APPROVAL: "true",
        "MFX_V1_READONLY_CONFIRMATION": CONFIRMATION,
        **{k: "true" for k in EXISTING_GATES},
    }


class P0150ManualSignalOnlyIntegrationTests(TestCase):
    def test_01_existing_get_only_summary_kept_and_nested_response_added(self):
        report = safe_summary(mocked(), drive_gets=12)
        self.assertEqual(report["action"], "NO_SIGNAL")
        self.assertEqual(report["drive_reads"], 12)
        nested = report["signal_only_output"]
        self.assertEqual((nested["action"], nested["stage"]),
                         ("NO_SIGNAL", "UNVERIFIED"))
        self.assertEqual(nested["technical_status"],
                         "SIX_TF_COMPLETE_RESEARCH_ONLY")
        self.assertEqual(nested["frames_present"],
                         ["M5", "M15", "M30", "H1", "H4", "D1"])

    def test_02_no_fake_entry_sl_tp_net_rr_or_first_known(self):
        nested = safe_summary(mocked(), drive_gets=0)["signal_only_output"]
        for name in ("entry_price", "stop_loss", "take_profit",
                     "net_risk_reward", "publisher_first_known_utc",
                     "zone_label"):
            with self.subTest(name=name):
                self.assertIsNone(nested[name])
        self.assertEqual(nested["quote_side"], "MID")

    def test_03_numerical_rights_oos_trade_flags_all_false(self):
        nested = safe_summary(mocked(), drive_gets=1)["signal_only_output"]
        for name in ("source_numeric_rules_approved",
                     "source_account_license_verified",
                     "bid_ask_economics_approved", "historical_oos_approved",
                     "may_publish_buy_sell", "may_trade"):
            self.assertIs(nested[name], False, name)

    def test_04_source_owner_blockers_visible_not_missing_approval(self):
        nested = safe_summary(mocked(), drive_gets=2)["signal_only_output"]
        reasons = nested["reason_codes"]
        self.assertIn("ORIGINAL_SOURCE_NUMERIC_RULES_UNAPPROVED", reasons)
        self.assertIn("ACCOUNT_SPECIFIC_DATA_RIGHTS_UNVERIFIED", reasons)
        self.assertIn("BID_ASK_SPREAD_COST_SL_TP_NET_RR_UNVERIFIED", reasons)
        self.assertIn("CAUSAL_OOS_AND_RELEASE_NOT_ACCEPTED", reasons)

    def test_05_current_intrahour_M5_M15_missing_are_exposed(self):
        report = safe_summary(
            mocked(asof=ASOF + timedelta(minutes=18)), drive_gets=5)
        nested = report["signal_only_output"]
        self.assertEqual(nested["frames_missing_or_stale"], ["M5", "M15"])
        self.assertEqual(nested["technical_status"],
                         "SIX_TF_INCOMPLETE_RESEARCH_ONLY")
        self.assertEqual(report["sha_verified_source_freshness_timing"]
                         ["closed_source_slot_gaps"]["M5"], 3)
        self.assertIn("FRAME_MISSING_OR_STALE_M15", nested["reason_codes"])
        self.assertEqual(nested["action"], "NO_SIGNAL")

    def test_06_source_tip_change_alters_only_local_evidence_fingerprint(self):
        initial=mocked()
        a=safe_summary(initial, drive_gets=4)
        changed=replace(initial,d1_manifest_tip_sha256="b"*64)
        b=safe_summary(changed, drive_gets=4)
        self.assertNotEqual(
            a["signal_only_output"]["evidence_fingerprint_sha256"],
            b["signal_only_output"]["evidence_fingerprint_sha256"],
        )
        self.assertEqual(b["signal_only_output"]["action"], "NO_SIGNAL")

    def test_07_no_raw_ohlc_token_drive_file_id_or_secret_in_rendered_json(self):
        report=safe_summary(mocked(), drive_gets=9)
        serialized=json.dumps(report)
        for forbidden in ("1.1000","1.1020", "refresh_token",
                          "oauth_client_secret", "raw_ohlc", "file_id"):
            self.assertNotIn(forbidden, serialized)
        self.assertTrue(len(report["signal_only_output"]
                             ["evidence_fingerprint_sha256"]) == 64)

    def test_08_manually_forged_vendor_rights_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "FORGED_SOURCE"):
            safe_summary(replace(
                mocked(), provider_account_data_rights_verified=True),
                drive_gets=1)

    def test_09_manually_forged_original_numeric_rule_rejected(self):
        with self.assertRaisesRegex(ValueError, "FORGED_SOURCE"):
            safe_summary(replace(
                mocked(), source_numeric_entry_rules_approved=True),
                drive_gets=1)

    def test_10_malformed_hash_denied_before_output(self):
        with self.assertRaisesRegex(ValueError,"INVALID_SOURCE_SHA"):
            safe_summary(replace(
                mocked(), d1_manifest_tip_sha256="bad-sha"),
                drive_gets=1)

    def test_11_actual_CLI_main_uses_one_existing_probe_result_no_more_IO(self):
        output=StringIO()
        calls=[]
        receipt=mocked()
        def probe(*args,**kwargs):
            calls.append("probe")
            return receipt, 6
        with patch.dict("os.environ",settings(),clear=True), \
             patch("tools.run_mfx_v1_manual_drive_six_tf._drive_auth_info",
                   return_value=object()), \
             patch("tools.run_mfx_v1_manual_drive_six_tf._require_oauth_cache_folders"), \
             patch("tools.run_mfx_v1_manual_drive_six_tf._session",
                   return_value=object()), \
             patch("tools.run_mfx_v1_manual_drive_six_tf.private_get_only_probe",
                   side_effect=probe), redirect_stdout(output):
            main()
        self.assertEqual(calls,["probe"])
        lines=output.getvalue().strip().splitlines()
        self.assertEqual(lines[0],"MFX_V1_MANUAL_DRIVE_GET_ONLY_TECHNICAL_AUDIT_PASS")
        payload=json.loads(lines[1])
        self.assertEqual(payload["drive_reads"],6)
        self.assertEqual(payload["signal_only_output"]["action"],"NO_SIGNAL")
        self.assertIsNone(payload["signal_only_output"]["entry_price"])

    def test_12_invalid_receipt_main_fails_closed_without_leaking(self):
        output=StringIO()
        receipt=replace(mocked(), source_first_known_time_proven=True)
        with patch.dict("os.environ",settings(),clear=True), \
             patch("tools.run_mfx_v1_manual_drive_six_tf._drive_auth_info",
                   return_value=object()), \
             patch("tools.run_mfx_v1_manual_drive_six_tf._require_oauth_cache_folders"), \
             patch("tools.run_mfx_v1_manual_drive_six_tf._session",
                   return_value=object()), \
             patch("tools.run_mfx_v1_manual_drive_six_tf.private_get_only_probe",
                   return_value=(receipt, 2)), redirect_stdout(output):
            with self.assertRaises(SystemExit) as context:
                main()
        self.assertEqual(context.exception.code, 1)
        self.assertEqual(output.getvalue().strip(),
                         "MFX_V1_MANUAL_DRIVE_GET_ONLY_FAILED_FAIL_CLOSED")

    def test_13_owner_flag_off_never_calls_OAuth_probe(self):
        output=StringIO()
        with patch.dict("os.environ",{},clear=True), \
             patch("tools.run_mfx_v1_manual_drive_six_tf._drive_auth_info",
                   side_effect=AssertionError("no auth")), \
             patch("tools.run_mfx_v1_manual_drive_six_tf.private_get_only_probe",
                   side_effect=AssertionError("no Drive")), \
             redirect_stdout(output):
            main()
        self.assertEqual(output.getvalue().strip(),
                         "MFX_V1_MANUAL_DRIVE_GET_ONLY_DISABLED_OWNER_GATE")

    def test_14_output_not_a_signal_release_even_six_frames_complete(self):
        report=safe_summary(mocked(),drive_gets=0)
        self.assertTrue(report["technical_six_frame_ready"])
        self.assertEqual(report["signal_only_output"]["technical_status"],
                         "SIX_TF_COMPLETE_RESEARCH_ONLY")
        self.assertFalse(report["may_publish_buy_sell"])
        self.assertFalse(report["signal_only_output"]["may_publish_buy_sell"])
        self.assertEqual(report["broker_orders"],0)

    def test_15_json_encoding_failure_never_prints_premature_PASS(self):
        output=StringIO()
        with patch.dict("os.environ",settings(),clear=True), \
             patch("tools.run_mfx_v1_manual_drive_six_tf._drive_auth_info",
                   return_value=object()), \
             patch("tools.run_mfx_v1_manual_drive_six_tf._require_oauth_cache_folders"), \
             patch("tools.run_mfx_v1_manual_drive_six_tf._session",
                   return_value=object()), \
             patch("tools.run_mfx_v1_manual_drive_six_tf.private_get_only_probe",
                   return_value=(mocked(),2)), \
             patch("tools.run_mfx_v1_manual_drive_six_tf.safe_summary",
                   return_value={"nonserializable_private":object()}), \
             redirect_stdout(output):
            with self.assertRaises(SystemExit) as context:
                main()
        self.assertEqual(context.exception.code,1)
        self.assertEqual(output.getvalue().strip(),
                         "MFX_V1_MANUAL_DRIVE_GET_ONLY_FAILED_FAIL_CLOSED")
