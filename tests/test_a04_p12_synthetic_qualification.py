"""A04/P0.12 synthetic-only quote/rights/clock negative fixtures."""
from __future__ import annotations

from copy import deepcopy
import unittest

from tools.a04_p12_synthetic_qualification import (
    BASE, CASES, DENIED, _fixture, evaluate_synthetic,
    expected_report, read_report, verify_report,
)


class P12SyntheticQualification(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = expected_report()

    def test_pinned_expected_synthetic_report(self) -> None:
        receipt = verify_report(read_report())
        self.assertEqual(receipt["cases"], 32)
        self.assertIs(receipt["can_trade"], False)

    def test_every_fixture_is_synthetic_and_fail_closed(self) -> None:
        self.assertEqual(len(CASES), 32)
        for case in CASES:
            with self.subTest(scenario=case["id"]):
                self.assertEqual(evaluate_synthetic(_fixture(case)), case["expected_reason"])
        self.assertTrue(all(not row["may_trade"] and not row["may_write_real_cache"]
                            and row["source_kind"] == "SYNTHETIC_ONLY"
                            for row in self.report["results"]))

    def test_fully_structural_case_still_denies_real_rights(self) -> None:
        self.assertEqual(evaluate_synthetic(dict(BASE)), "BLOCKED_EXTERNAL_RIGHTS_UNVERIFIED")

    def test_real_source_identity_and_market_claim_cannot_be_forged(self) -> None:
        for key in DENIED:
            fake = deepcopy(self.report)
            fake["absolute_denials"][key] = True
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "P012_CASE_OR_AUTHORITY_TAMPERED"):
                verify_report(fake)

    def test_quote_side_and_broker_product_negative_cases(self) -> None:
        scenarios = {x["id"]: x for x in CASES}
        for name in ("indicative_not_native_bidask", "broker_product_mismatch",
                     "native_bid_missing", "native_ask_missing", "crossed_bid_ask"):
            with self.subTest(name=name):
                case = scenarios[name]
                self.assertEqual(evaluate_synthetic(_fixture(case)), case["expected_reason"])

    def test_causal_clock_and_unsupported_calendar_negative_cases(self) -> None:
        scenario_names = ("future_quote", "stale_quote", "future_first_known",
                          "provisional_bar", "future_revision",
                          "first_known_before_close", "revision_before_first_known",
                          "calendar_dst_unverified", "non_utc_offset_timestamp")
        scenarios = {x["id"]: x for x in CASES}
        for name in scenario_names:
            with self.subTest(name=name):
                self.assertEqual(evaluate_synthetic(_fixture(scenarios[name])),
                                 scenarios[name]["expected_reason"])

    def test_missing_field_and_extra_field_rejected(self) -> None:
        source = dict(BASE)
        source.pop("ask")
        self.assertEqual(evaluate_synthetic(source), "SCHEMA_KEYS_INVALID")
        source = dict(BASE, unreviewed_signal="BUY")
        self.assertEqual(evaluate_synthetic(source), "SCHEMA_KEYS_INVALID")

    def test_floating_point_and_nonfinite_price_denied(self) -> None:
        for price in (float("nan"), float("inf"), 1.2, "NaN", "1e10", "-1", "0"):
            data = dict(BASE, bid=price)
            with self.subTest(price=str(price)):
                self.assertEqual(evaluate_synthetic(data), "INVALID_BID_ASK")

    def test_invalid_time_formats_do_not_bypass_first_known(self) -> None:
        for s in ("2026-11-09T15:45:02+07:00", "2026-02-30T08:45:02Z",
                  "2026-11-09 08:45:02", "2026-11-09T08:45:02.000Z"):
            with self.subTest(time=s):
                self.assertEqual(evaluate_synthetic(dict(BASE, first_known_utc=s)),
                                 "INVALID_UTC_TIMESTAMP")

    def test_live_licence_or_trade_permissions_are_not_inferred(self) -> None:
        for flag, reason in (
            ("external_rights_verified", "FORGED_VENDOR_ENTITLEMENT"),
            ("drive_retention_verified", "FORGED_DRIVE_RETENTION"),
            ("can_trade", "FORGED_TRADING_AUTHORITY"),
        ):
            with self.subTest(flag=flag):
                self.assertEqual(evaluate_synthetic(dict(BASE, **{flag: True})), reason)

    def test_untrusted_instrument_or_timeframe_is_denied(self) -> None:
        self.assertEqual(evaluate_synthetic(dict(BASE, symbol="EURUSD")), "NON_SYNTHETIC_SYMBOL")
        self.assertEqual(evaluate_synthetic(dict(BASE, timeframe="S1")), "UNSUPPORTED_TIMEFRAME")

    def test_case_mutation_drop_or_expected_reason_edit_breaks_pinned_report(self) -> None:
        for key, value in (
            ("expected_reason", "AUTHORIZED"),
            ("changes", {"price_basis": "REAL_EXECUTION"}),
            ("id", "FORGED"),
        ):
            fake = deepcopy(self.report)
            fake["scenarios"][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "P012_CASE_OR_AUTHORITY_TAMPERED"):
                verify_report(fake)

    def test_recording_positive_runtime_approval_is_rejected(self) -> None:
        for key, value in (("may_trade", True), ("may_write_real_cache", True),
                           ("reason_code", "LIVE_READY")):
            fake = deepcopy(self.report)
            fake["results"][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "P012_CASE_OR_AUTHORITY_TAMPERED"):
                verify_report(fake)

    def test_ancestor_source_sha_and_p11_field_count_are_immutable(self) -> None:
        for key, value in (("p11_crosswalk_git_blob_sha", "0" * 40),
                           ("p11_frozen_field_obligations", 57),
                           ("frozen_forex_source_commit", "0" * 40)):
            fake = deepcopy(self.report)
            fake[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "P012_CASE_OR_AUTHORITY_TAMPERED"):
                verify_report(fake)
