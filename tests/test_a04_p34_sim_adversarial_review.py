"""P0.34: 24 preregistered adversarial SIM replay & owner intake tests.

No original Forex numerical policies are fabricated or promoted.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha1
import json
from pathlib import Path
import unittest

from forex_trading.catalog import ZONES, validate_catalog
from mfx_research.p030_approved_nonentry_design import read_22_zone_design_manifest
from mfx_research.p034_sim_adversarial_review import (
    DOSSIER, DOSSIER_BLOB_SHA, P021, P021_BLOB_SHA, SCENARIOS, VERSION,
    _blob_sha, run_p034_adversarial_stress, verify_owner_decision_dossier,
)
from mfx_research.source_parameter_review import (
    REQUIREMENTS, read_review_register,
)
from tools.run_a04_p33_replay_demo import fixture

EXPECTED_ERRORS = {
    "DUPLICATE_ORIGIN_IDENTICAL": "DUPLICATE_OR_REVISED",
    "DUPLICATE_ORIGIN_REVISED": "DUPLICATE_OR_REVISED",
    "CLOCK_REORDER": "NONINCREASING_REPLAY",
    "FUTURE_GLOBAL_ASOF": "FUTURE_REPLAY_WINDOW",
    "OPEN_LAST_M15": "OPEN_PROVISIONAL",
    "PARTIAL_LAST_M15": "INCOMPLETE_COVERAGE",
    "FUTURE_KNOWN_H4": "FUTURE_KNOWN",
    "FUTURE_RETRIEVED_H1": "FUTURE_KNOWN",
    "REAL_PROVIDER_H1": "REJECT_REAL_MARKET_SOURCE",
    "REVISED_HISTORY_D1": "REJECT_REAL_MARKET_SOURCE",
    "CALENDAR_MISMATCH_H1": "CROSS_TIMEFRAME_IDENTITY",
    "STREAM_MISMATCH_H1": "INTRA_TIMEFRAME_STREAM",
    "TAMPER_CHAIN_PAYLOAD": "HASH_CHAIN_TAMPER",
}


class P034AdversarialStressOwnerDossierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.first = fixture("B2", 0)
        cls.second = fixture("S2", 1)
        cls.report = run_p034_adversarial_stress(cls.first, cls.second)
        cls.scenarios = {x.scenario: x for x in cls.report.cases}

    def _rejected(self, name: str) -> None:
        case = self.scenarios[name]
        self.assertEqual(case.outcome, "EXPECTED_REJECTION")
        self.assertEqual(case.observed_error, EXPECTED_ERRORS[name])
        self.assertTrue(case.prior_prefix_unchanged)
        self.assertIsNone(case.resulting_tip_sha256)
        self.assertEqual(case.action, "NO_SIGNAL")
        self.assertFalse(case.may_publish)
        self.assertEqual(case.market_orders, 0)

    def test_01_original_forex18_and_approved_mfx22_still_pinned(self) -> None:
        validate_catalog(ZONES)
        self.assertEqual(len(ZONES), 18)
        m = read_22_zone_design_manifest()
        self.assertEqual(len(m.zones), 22)
        self.assertEqual((len(m.entry_long_labels),
                          len(m.entry_short_labels),
                          len(m.watch_labels),
                          len(m.exit_long_warning_labels) +
                          len(m.exit_short_warning_labels)), (8, 8, 2, 4))

    def test_02_original_p021_git_sha_and_36_pending(self) -> None:
        self.assertEqual(_blob_sha(P021.read_bytes()), P021_BLOB_SHA)
        receipt, _ = read_review_register(P021)
        self.assertEqual(receipt.pending_source_numerical_approvals, 36)
        self.assertEqual(receipt.source_numeric_rules_approved, 0)
        self.assertEqual(self.report.owner_decisions.pending_owner_decisions, 36)

    def test_03_fourteen_sim_examples_never_numeric_approvals(self) -> None:
        src = json.loads(P021.read_text(encoding="utf-8"))
        examples = sum(
            x["research_sim_example"] is not None
            for rule in src["rules"] for x in rule["requirements"]
        )
        self.assertEqual(examples, 14)
        self.assertEqual(self.report.owner_decisions.sim_examples_not_approved, 14)
        self.assertFalse(self.report.owner_decisions.signed_owner_evidence)

    def test_04_exact_source_ids_phases_and_paragraph_anchors_18_per_side(self) -> None:
        rows = self.report.owner_decisions.rows
        self.assertEqual(len(rows), 36)
        self.assertEqual(rows[:18], tuple(
            ("B2", name, phase, b) for name, phase, b, _ in REQUIREMENTS))
        self.assertEqual(rows[18:], tuple(
            ("S2", name, phase, s) for name, phase, _, s in REQUIREMENTS))

    def test_05_no_approved_values_in_sealed_decision_dossier(self) -> None:
        self.assertEqual(_blob_sha(DOSSIER.read_bytes()), DOSSIER_BLOB_SHA)
        dossier = json.loads(DOSSIER.read_text(encoding="utf-8"))
        self.assertEqual(len(dossier["requirements"]), 36)
        self.assertTrue(all(
            row["owner_decision"] == "AWAITING_SOURCE_OWNER"
            and row["source_approved_value"] is None
            and row["independently_verified_evidence"] is None
            and row["never_promote_sim_example"] is True
            for row in dossier["requirements"]
        ))
        self.assertFalse(dossier["action_gates"][
            "may_publish_confirmed_buy_sell"])

    def test_06_exact_sixteen_predeclared_stress_cases(self) -> None:
        self.assertEqual(
            tuple(x.scenario for x in self.report.cases), SCENARIOS)
        self.assertEqual(len(self.report.cases), 16)
        self.assertEqual(
            sum(x.outcome == "ACCEPTED_RESEARCH_ONLY"
                for x in self.report.cases), 3)
        self.assertEqual(
            sum(x.outcome == "EXPECTED_REJECTION"
                for x in self.report.cases), 13)

    def test_07_future_append_keeps_first_snapshot_prefix(self) -> None:
        x = self.scenarios["FUTURE_APPEND_PREFIX"]
        self.assertEqual(x.outcome, "ACCEPTED_RESEARCH_ONLY")
        self.assertTrue(x.prior_prefix_unchanged)
        self.assertEqual(x.resulting_tip_sha256,
                         self.report.baseline_tip_sha256)
        self.assertNotEqual(x.resulting_tip_sha256,
                            self.report.prefix_chain_sha256)

    def test_08_later_valid_ohlc_change_is_detected_without_prefix_drift(self) -> None:
        x = self.scenarios["MUTATE_LATER_H1_VALID"]
        self.assertEqual(x.outcome, "ACCEPTED_RESEARCH_ONLY")
        self.assertTrue(x.prior_prefix_unchanged)
        self.assertNotEqual(x.resulting_tip_sha256,
                            self.report.baseline_tip_sha256)
        self.assertEqual(x.action, "NO_SIGNAL")

    def test_09_no_pattern_late_m15_removes_last_research_label(self) -> None:
        x = self.scenarios["NO_PATTERN_LAST"]
        self.assertEqual(x.outcome, "ACCEPTED_RESEARCH_ONLY")
        self.assertTrue(x.prior_prefix_unchanged)
        self.assertNotEqual(x.resulting_tip_sha256,
                            self.report.baseline_tip_sha256)
        self.assertFalse(x.may_publish)

    def test_10_duplicate_origin_identical_denied(self) -> None:
        self._rejected("DUPLICATE_ORIGIN_IDENTICAL")

    def test_11_duplicate_origin_revised_price_denied(self) -> None:
        self._rejected("DUPLICATE_ORIGIN_REVISED")

    def test_12_backward_decision_clock_denied(self) -> None:
        self._rejected("CLOCK_REORDER")

    def test_13_global_asof_before_later_window_denied(self) -> None:
        self._rejected("FUTURE_GLOBAL_ASOF")

    def test_14_open_m15_bar_denied(self) -> None:
        self._rejected("OPEN_LAST_M15")

    def test_15_partial_m15_bar_denied(self) -> None:
        self._rejected("PARTIAL_LAST_M15")

    def test_16_future_known_h4_denied(self) -> None:
        self._rejected("FUTURE_KNOWN_H4")

    def test_17_future_retrieved_h1_denied(self) -> None:
        self._rejected("FUTURE_RETRIEVED_H1")

    def test_18_real_provider_claim_denied(self) -> None:
        self._rejected("REAL_PROVIDER_H1")

    def test_19_revised_d1_history_denied(self) -> None:
        self._rejected("REVISED_HISTORY_D1")

    def test_20_cross_calendar_h1_denied(self) -> None:
        self._rejected("CALENDAR_MISMATCH_H1")

    def test_21_mixed_stream_h1_denied(self) -> None:
        self._rejected("STREAM_MISMATCH_H1")

    def test_22_canonical_replay_chain_payload_tamper_denied(self) -> None:
        self._rejected("TAMPER_CHAIN_PAYLOAD")

    def test_23_no_market_alert_cost_oos_trade_or_release_promotion(self) -> None:
        r = self.report
        self.assertEqual(r.source_approved_numeric_entry_rules, 0)
        self.assertEqual(r.confirmed_real_signals, 0)
        self.assertEqual(r.actual_market_out_of_sample_metrics, 0)
        self.assertEqual(r.real_market_data_calls, 0)
        self.assertEqual(r.real_drive_quote_writes, 0)
        self.assertEqual(r.alerts_published, 0)
        self.assertEqual(r.broker_orders, 0)
        self.assertFalse(r.release_ready)
        self.assertFalse(r.owner_decisions.vendor_rights_verified)
        self.assertFalse(r.owner_decisions.may_release)

    def test_24_deterministic_replay_version_and_strict_typed_input(self) -> None:
        second = run_p034_adversarial_stress(self.first, self.second)
        self.assertEqual(second, self.report)
        self.assertEqual(VERSION,
                         "MFX_A04_P34_ADVERSARIAL_SIM_STRESS_AND_36_OWNER_DOSSIER_V1")
        with self.assertRaisesRegex(TypeError, "P034_TYPED_TWO_SYNTHETIC"):
            run_p034_adversarial_stress(
                self.first, object())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "P034_TWO_SNAPSHOT_CAUSAL_ORDER"):
            run_p034_adversarial_stress(
                self.second, self.first)
        self.assertEqual(_blob_sha(DOSSIER.read_bytes()),
                         DOSSIER_BLOB_SHA)
        self.assertEqual(len(verify_owner_decision_dossier().rows), 36)


if __name__ == "__main__":
    unittest.main()
