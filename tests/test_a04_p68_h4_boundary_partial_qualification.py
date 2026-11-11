"""A04/P0.68: archived M5 H4 start/end partials cannot veto seven-day parity.

A real M5 archive began at UTC 18:00, inside the 16:00 H4 window.
Boundary partials are excluded from the comparison domain; interior
holes and source-native mismatches remain fail-closed. Synthetic-only.
"""
from __future__ import annotations

from datetime import timedelta
import unittest

from test_a04_p66_readonly_m5_h4_live_parity import (
    NOW, START, ReadOnlyStore, seed_m5, seed_native,
)
from tools.run_mfx_m5_h4_live_parity_audit import audit_live_m5_h4_parity


def fixtures_boundary(
    *, missing_hour: int | None = None, native_high: str="1.10100",
) -> tuple[ReadOnlyStore,ReadOnlyStore]:
    m=ReadOnlyStore()
    hours=tuple(i for i in range(2,194) if i != missing_hour)
    seed_m5(m,hours)
    n=ReadOnlyStore()
    seed_native(n,49,high=native_high)
    return m,n


class H4BoundaryPartialQualificationTests(unittest.TestCase):
    def test_01_bootstrap_and_trailing_partials_excluded_from_week_gate(self) -> None:
        m,n=fixtures_boundary()
        r=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertEqual(r["m5_h4_complete_windows"],47)
        self.assertEqual(r["h4_compared_match"],47)
        self.assertEqual(r["m5_h4_boundary_partial_windows"],2)
        self.assertEqual(r["m5_h4_interior_incomplete_windows"],0)
        self.assertEqual(r["m5_h4_incomplete_windows"],2)
        self.assertTrue(r["h4_consecutive_4h_grid"])
        self.assertTrue(r["h4_span_at_least_7_days"])
        self.assertTrue(r["h4_parity_observation_threshold_met"])
        self.assertEqual(
            r["status"],"SOURCE_PARITY_WINDOW_MET_OWNER_CUTOVER_STILL_DENIED")
        self.assertFalse(r["may_replace_native_h4"])
        self.assertFalse(r["may_reduce_native_h4_requests"])

    def test_02_interior_missing_m5_hour_still_blocks(self) -> None:
        m,n=fixtures_boundary(missing_hour=65)
        r=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertEqual(r["m5_h4_interior_incomplete_windows"],1)
        self.assertIn((START+timedelta(hours=64)).isoformat(),
                      r["m5_h4_interior_incomplete_samples_utc"])
        self.assertFalse(r["h4_consecutive_4h_grid"])
        self.assertFalse(r["h4_parity_observation_threshold_met"])
        self.assertEqual(r["status"],"INCOMPLETE_M5_WINDOWS_REVIEW_REQUIRED")

    def test_03_native_ohlc_mismatch_never_waived_by_boundary_rule(self) -> None:
        m,n=fixtures_boundary(native_high="1.10101")
        r=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertEqual(r["m5_h4_boundary_partial_windows"],2)
        self.assertEqual(r["h4_compared_mismatch"],47)
        self.assertFalse(r["h4_parity_observation_threshold_met"])
        self.assertEqual(r["status"],"SOURCE_PARITY_REVIEW_REQUIRED")

    def test_04_unavailable_native_still_forbids_cutover(self) -> None:
        m=ReadOnlyStore()
        seed_m5(m,range(2,194))
        n=ReadOnlyStore()
        seed_native(n,10)
        r=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertGreater(r["h4_native_missing"],0)
        self.assertFalse(r["h4_parity_observation_threshold_met"])

    def test_05_short_window_boundary_ignorable_but_not_qualified(self) -> None:
        m,n=ReadOnlyStore(),ReadOnlyStore()
        seed_m5(m,range(2,10))
        seed_native(n,3)
        r=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertEqual(r["m5_h4_complete_windows"],1)
        self.assertEqual(r["h4_compared_match"],1)
        self.assertEqual(r["m5_h4_boundary_partial_windows"],2)
        self.assertEqual(r["m5_h4_interior_incomplete_windows"],0)
        self.assertFalse(r["h4_parity_observation_threshold_met"])
        self.assertEqual(r["status"],"OBSERVATION_WINDOW_NOT_YET_QUALIFIED")

    def test_06_zero_ohcl_in_logs_and_no_writes(self) -> None:
        m,n=fixtures_boundary()
        before_m=m.records.copy()
        before_n=n.records.copy()
        receipt=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        from json import dumps
        printed=dumps(receipt)
        self.assertNotIn("1.10000",printed)
        self.assertNotIn("1.10100",printed)
        self.assertEqual(receipt["provider_api_calls"],0)
        self.assertEqual(receipt["drive_writes"],0)
        self.assertEqual(receipt["broker_orders"],0)
        self.assertEqual(m.records,before_m)
        self.assertEqual(n.records,before_n)


if __name__ == "__main__":
    unittest.main()
