"""A04/P0.70 dual-provider H4 UTC-grid session-gap research tests.

Every gap remains a QUARANTINED diagnostic. No weekend is assumed closed,
no actual source calls or Drive writes, no changes to H4 cutover gates.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from tools.mfx_h4_source_coverage import (
    MAX_SHADOW_SPAN_H4_SLOTS, VERSION, h4_dual_source_grid_diagnostics,
)
from tools.run_mfx_m5_h4_live_parity_audit import audit_live_m5_h4_parity
from test_a04_p66_readonly_m5_h4_live_parity import NOW, fixtures

UTC = timezone.utc
FIRST = datetime(2026, 11, 6, 20, tzinfo=UTC)  # Friday
H4 = timedelta(hours=4)


def s(when: datetime) -> str:
    return when.isoformat()


def n(when: datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M:%S")


class H4SourceCoverageTests(unittest.TestCase):
    def test_01_all_consecutive_grid_slots_are_both_present(self) -> None:
        stamps = tuple(FIRST + i * H4 for i in range(4))
        d = h4_dual_source_grid_diagnostics(
            tuple(map(s, stamps)),tuple(map(n, stamps)))
        self.assertEqual(d["h4_utc_grid_slots_scanned"], 4)
        self.assertEqual(d["h4_both_sources_present_grid_slots"], 4)
        self.assertEqual(d["h4_both_sources_absent_grid_slots"], 0)
        self.assertEqual(d["h4_coverage_report_version"], VERSION)
        self.assertFalse(d["h4_weekend_gaps_auto_waived"])
        self.assertFalse(d["h4_weekend_session_policy_proven"])

    def test_02_weekend_dual_absence_only_candidate_not_waiver(self) -> None:
        monday = datetime(2026, 11, 9, 0, tzinfo=UTC)
        d = h4_dual_source_grid_diagnostics(
            (s(FIRST),s(monday)),(n(FIRST),n(monday)))
        self.assertEqual(d["h4_utc_grid_slots_scanned"],14)
        self.assertEqual(d["h4_both_sources_absent_grid_slots"],12)
        self.assertEqual(d["h4_weekend_dual_absence_candidates"],12)
        self.assertEqual(d["h4_weekday_dual_absence_unexplained"],0)
        self.assertFalse(d["h4_weekend_session_policy_proven"])
        self.assertFalse(d["h4_weekend_gaps_auto_waived"])

    def test_03_native_present_m5_missing_detected(self) -> None:
        stamps = tuple(FIRST+i*H4 for i in range(3))
        d = h4_dual_source_grid_diagnostics(
            (s(stamps[0]),s(stamps[2])),tuple(map(n, stamps)))
        self.assertEqual(d["h4_native_present_m5_missing_slots"],1)
        self.assertEqual(d["h4_m5_present_native_missing_slots"],0)
        self.assertEqual(d["h4_both_sources_absent_grid_slots"],0)
        self.assertEqual(d["h4_native_present_m5_missing_samples_utc"],
                         [s(stamps[1])])

    def test_04_m5_present_native_missing_detected(self) -> None:
        stamps=tuple(FIRST+i*H4 for i in range(3))
        d=h4_dual_source_grid_diagnostics(
            tuple(map(s, stamps)),(n(stamps[0]),n(stamps[2])))
        self.assertEqual(d["h4_m5_present_native_missing_slots"],1)
        self.assertEqual(d["h4_m5_present_native_missing_samples_utc"],
                         [s(stamps[1])])

    def test_05_weekday_both_absent_is_unexplained(self) -> None:
        monday = datetime(2026,11,9,0,tzinfo=UTC)
        d=h4_dual_source_grid_diagnostics(
            (s(monday),s(monday+3*H4)),(n(monday),n(monday+3*H4)))
        self.assertEqual(d["h4_both_sources_absent_grid_slots"],2)
        self.assertEqual(d["h4_weekday_dual_absence_unexplained"],2)
        self.assertEqual(d["h4_weekend_dual_absence_candidates"],0)

    def test_06_no_shadow_returns_empty_but_unverified(self) -> None:
        d=h4_dual_source_grid_diagnostics((),(n(FIRST),))
        self.assertEqual(d["h4_utc_grid_slots_scanned"],0)
        self.assertEqual(d["h4_both_sources_present_grid_slots"],0)
        self.assertFalse(d["h4_weekend_session_policy_proven"])

    def test_07_wrong_container_types_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"TYPED_TUPLE"):
            h4_dual_source_grid_diagnostics([s(FIRST)],(n(FIRST),))
        with self.assertRaisesRegex(ValueError,"TYPED_TUPLE"):
            h4_dual_source_grid_diagnostics((s(FIRST),),[n(FIRST)])

    def test_08_duplicate_shadow_label_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"UNSORTED"):
            h4_dual_source_grid_diagnostics(
                (s(FIRST),s(FIRST)),(n(FIRST),))

    def test_09_duplicate_or_unsorted_native_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"UNSORTED"):
            h4_dual_source_grid_diagnostics(
                (s(FIRST),),(n(FIRST+H4),n(FIRST)))

    def test_10_naive_or_wrong_timezone_shadow_denied(self) -> None:
        for bad in ("2026-11-06T20:00:00", 
                    "2026-11-07T03:00:00+07:00",
                    "2026-11-06T20:04:00+00:00"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    h4_dual_source_grid_diagnostics((bad,),())

    def test_11_non_grid_or_malformed_native_denied(self) -> None:
        for bad in ("2026-11-06 21:00:00","not-a-time",
                    "2026-11-06T20:00:00+00:00"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    h4_dual_source_grid_diagnostics((s(FIRST),),(bad,))

    def test_12_73_h4_slots_fail_bounded_research_only(self) -> None:
        with self.assertRaisesRegex(ValueError,"SPAN_BOUNDED"):
            h4_dual_source_grid_diagnostics(
                (s(FIRST),s(FIRST+MAX_SHADOW_SPAN_H4_SLOTS*H4)),())

    def test_13_one_slot_is_legitimate(self) -> None:
        d=h4_dual_source_grid_diagnostics((s(FIRST),),(n(FIRST),))
        self.assertEqual(d["h4_utc_grid_slots_scanned"],1)
        self.assertEqual(d["h4_both_sources_present_grid_slots"],1)

    def test_14_sampling_no_broker_no_raw_prices(self) -> None:
        d=h4_dual_source_grid_diagnostics(
            (s(FIRST),s(FIRST+3*H4)),
            (n(FIRST),n(FIRST+3*H4)))
        self.assertNotIn("1.10000",str(d))
        self.assertTrue(d["h4_coverage_diagnostics_research_only"])

    def test_15_actual_auditor_happy_path_remains_no_cutover(self) -> None:
        m,nstore=fixtures()
        d=audit_live_m5_h4_parity(m,nstore,now_utc=NOW)
        self.assertEqual(d["h4_both_sources_present_grid_slots"],2)
        self.assertEqual(d["h4_both_sources_absent_grid_slots"],0)
        self.assertEqual(d["h4_native_present_m5_missing_slots"],0)
        self.assertEqual(d["h4_compared_match"],2)
        self.assertFalse(d["h4_parity_observation_threshold_met"])
        self.assertFalse(d["may_replace_native_h4"])
        self.assertEqual((d["provider_api_calls"],d["drive_writes"],
                          d["broker_orders"]),(0,0,0))

    def test_16_dual_absence_cannot_become_accepted_by_label_only(self) -> None:
        monday = datetime(2026,11,9,0,tzinfo=UTC)
        d=h4_dual_source_grid_diagnostics(
            (s(FIRST),s(monday)),(n(FIRST),n(monday)))
        self.assertGreater(d["h4_weekend_dual_absence_candidates"],0)
        self.assertFalse(d["h4_weekend_session_policy_proven"])
        self.assertFalse(d["h4_weekend_gaps_auto_waived"])
        self.assertTrue(d["h4_coverage_diagnostics_research_only"])


if __name__=="__main__":
    unittest.main()
