"""P0.163 source-HOLD propagation: hermetic fixtures, no OAuth/Drive/vendor IO."""
from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
import json
from unittest import TestCase
from unittest.mock import patch

from mfx_research.signal_only_six_tf_response import (
    build_signal_only_research_response,
)
from mfx_research.six_tf_sealed_archive_consumer import (
    D1_HOLD_PUBLIC_STATUS, D1_KNOWN_SOURCE_REVISION_INCIDENT,
)
from tools.run_mfx_v1_manual_drive_six_tf import main, safe_summary
from test_mfx_v1_manual_signal_only_drive_output import settings
from test_mfx_v1_six_tf_sealed_archive_consumer import (
    SealedSixTFConsumerTests, fixtures,
)


def held():
    """Use the existing exact real-path mock, NOT a real provider/Drive claim."""
    m5, h4, d1, pins = fixtures()
    return SealedSixTFConsumerTests._reviewed_mode_with_in_memory_pinned_fixture(
        m5, h4, d1, pins,
    )


class P0163D1SourceHoldManualReportTests(TestCase):
    def test_01_typed_response_preserves_quarantine_and_no_signal(self):
        receipt = held()
        output = build_signal_only_research_response(receipt)
        self.assertEqual(output.action, "NO_SIGNAL")
        self.assertEqual(output.stage, "UNVERIFIED")
        self.assertEqual(output.technical_status,
                         "SIX_TF_SOURCE_QUARANTINED_NO_SIGNAL")
        self.assertIn(D1_HOLD_PUBLIC_STATUS, output.reason_codes)
        self.assertIsNone(output.entry_price)
        self.assertIsNone(output.stop_loss)
        self.assertIsNone(output.net_risk_reward)
        self.assertFalse(output.may_publish_buy_sell)
        self.assertFalse(output.may_trade)

    def test_02_manual_safe_summary_explicitly_holds_without_false_pass(self):
        report = safe_summary(held(), drive_gets=8)
        self.assertEqual(report["status"], D1_HOLD_PUBLIC_STATUS)
        self.assertEqual((report["action"], report["stage"]),
                         ("NO_SIGNAL", "UNVERIFIED"))
        self.assertEqual(report["drive_reads"], 8)
        self.assertEqual(report["broker_orders"], 0)
        self.assertTrue(report["technical_six_frame_ready"])
        self.assertFalse(report["source_authoritative_for_signals"])
        self.assertTrue(report["private_signal_research_suppressed_by_d1_hold"])
        self.assertEqual(
            report["native_d1_numeric_revision_quarantine_incident"],
            D1_KNOWN_SOURCE_REVISION_INCIDENT)
        for section in ("private_ohlc_geometry",
                        "private_multibar_research",
                        "private_pivot_sensitivity",
                        "private_m15_microbreak",
                        "b2_s2_source_computation_crosswalk"):
            self.assertEqual(report[section]["status"],
                             "NOT_RUN_D1_SOURCE_QUARANTINE")

    def test_03_halted_source_never_invokes_private_price_math(self):
        with patch(
            "tools.run_mfx_v1_manual_drive_six_tf."
            "compute_private_six_tf_candle_geometry",
            side_effect=AssertionError("NO_D1_PRIVATE_GEOMETRY")
        ), patch(
            "tools.run_mfx_v1_manual_drive_six_tf."
            "reconcile_b2s2_source_to_computation",
            side_effect=AssertionError("NO_D1_CROSSWALK")
        ), patch(
            "tools.run_mfx_v1_manual_drive_six_tf."
            "classify_ohlc_first_mode",
            side_effect=AssertionError("NO_D1_SOURCE_MODE")
        ):
            report = safe_summary(held(), drive_gets=0)
        self.assertEqual(report["action"], "NO_SIGNAL")

    def test_04_cli_prints_quarantine_and_nonzero_without_fake_pass(self):
        output = StringIO()
        with patch.dict("os.environ", settings(), clear=True), patch(
            "tools.run_mfx_v1_manual_drive_six_tf._drive_auth_info",
            return_value=object(),
        ), patch(
            "tools.run_mfx_v1_manual_drive_six_tf._require_oauth_cache_folders",
        ), patch(
            "tools.run_mfx_v1_manual_drive_six_tf._session",
            return_value=object(),
        ), patch(
            "tools.run_mfx_v1_manual_drive_six_tf.private_get_only_probe",
            return_value=(held(), 4),
        ), redirect_stdout(output):
            with self.assertRaises(SystemExit) as caught:
                main()
        self.assertEqual(caught.exception.code, 2)
        lines = output.getvalue().strip().splitlines()
        self.assertEqual(
            lines[0], "MFX_V1_MANUAL_DRIVE_GET_ONLY_D1_QUARANTINED_NO_SIGNAL")
        self.assertNotIn("TECHNICAL_AUDIT_PASS", output.getvalue())
        self.assertEqual(json.loads(lines[1])["status"], D1_HOLD_PUBLIC_STATUS)

    def test_05_forged_hold_missing_incident_or_suppression_denied(self):
        receipt = held()
        variants = (
            {"native_d1_numeric_revision_quarantine_active": False},
            {"native_d1_numeric_revision_quarantine_incident": ""},
            {"private_signal_research_suppressed_by_d1_hold": False},
            {"github_reviewed_m5_anchors_checked": False},
        )
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                safe_summary(replace(receipt, **variant), drive_gets=0)

    def test_06_forged_private_calculation_in_hold_denied(self):
        receipt = held()
        from test_mfx_v1_six_tf_sealed_archive_consumer import consume
        fake = consume()
        with self.assertRaisesRegex(
            ValueError, "D1_SOURCE_HOLD_RECEIPT_DRIFT"
        ):
            safe_summary(replace(
                receipt, private_multibar=fake.private_multibar,
            ), drive_gets=0)

    def test_07_undeclared_source_hold_flag_denied(self):
        receipt = held()
        with self.assertRaisesRegex(ValueError, "UNDECLARED_D1_SOURCE_HOLD"):
            build_signal_only_research_response(
                replace(receipt,
                        status="SEALED_READONLY_CACHE_TECHNICAL_RESEARCH_ONLY_NO_SIGNAL")
            )

    def test_08_no_raw_ohlc_secret_or_fake_entry_in_hold_json(self):
        report = safe_summary(held(), drive_gets=11)
        output = json.dumps(report, sort_keys=True)
        for forbidden in ("1.1000", "refresh_token", "oauth_client_secret",
                          "raw_ohlc", "file_id", '"BUY"', '"SELL"'):
            self.assertNotIn(forbidden, output)
        nested = report["signal_only_output"]
        for field in ("entry_price", "stop_loss", "take_profit",
                      "net_risk_reward", "publisher_first_known_utc"):
            self.assertIsNone(nested[field])
        self.assertEqual(report["drive_writes"], 0)
        self.assertEqual(report["provider_price_requests"], 0)

    def test_09_sha_corruption_and_forged_rights_remain_denied(self):
        receipt = held()
        for change in (
            {"d1_manifest_tip_sha256": "not-sha"},
            {"source_first_known_time_proven": True},
            {"source_numeric_entry_rules_approved": True},
            {"may_publish_buy_sell": True},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                safe_summary(replace(receipt, **change), drive_gets=0)

    def test_10_normal_fixture_report_path_unchanged(self):
        from test_mfx_v1_manual_signal_only_drive_output import mocked
        output = safe_summary(mocked(), drive_gets=2)
        self.assertEqual(
            output["status"], "MANUAL_AUTHENTICATED_DRIVE_GET_SOURCE_RESEARCH_ONLY")
        self.assertEqual(
            output["signal_only_output"]["technical_status"],
            "SIX_TF_COMPLETE_RESEARCH_ONLY")

    def test_11_ohlc_classifier_and_private_geometry_reject_source_hold(self):
        from mfx_research.ohlc_first_optional_bidask_policy import (
            classify_ohlc_first_mode,
        )
        from mfx_research.six_tf_private_candle_geometry import (
            compute_private_six_tf_candle_geometry,
        )
        receipt = held()
        public = build_signal_only_research_response(receipt)
        with self.assertRaisesRegex(ValueError, "TECHNICAL_STATUS_DRIFT"):
            classify_ohlc_first_mode(public)
        with self.assertRaisesRegex(ValueError, "TECHNICAL_STATUS_DRIFT"):
            compute_private_six_tf_candle_geometry(receipt)
