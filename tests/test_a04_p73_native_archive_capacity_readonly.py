"""A04/P0.73: native H4+D1 archive capacity read-only early warning.

Pure Hermetic tests; no provider, Drive writes, trading, schedule edits,
or scaling permission. Boundary values refer to immutable append PAIRS,
not market days, H4 observations, candles, or forecast duration.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path
import unittest

from tools.mfx_native_htf_drive_seal import (
    MAX_NATIVE_FILES, NativeArchiveState,
)
from tools.run_mfx_native_htf_cache_audit import (
    CAPACITY_EARLY_REVIEW_SLOTS,
    CAPACITY_URGENT_REVIEW_SLOTS,
    audit_native_cache,
    native_capacity_readonly_receipt,
)
from test_a04_p58_native_htf_cache_audit import d1, h4

UTC = timezone.utc


def state_at(count: int) -> NativeArchiveState:
    return NativeArchiveState(None, None, count, count, ())


class NativeArchiveCapacityReadOnlyTests(unittest.TestCase):
    def test_01_cap_is_same_existing_drive_bound(self) -> None:
        self.assertEqual(MAX_NATIVE_FILES, 256)
        self.assertEqual(CAPACITY_EARLY_REVIEW_SLOTS, 64)
        self.assertEqual(CAPACITY_URGENT_REVIEW_SLOTS, 16)

    def test_02_ample_65_remaining_is_not_warning(self) -> None:
        r = native_capacity_readonly_receipt(state_at(MAX_NATIVE_FILES - 65))
        self.assertEqual(r["native_archive_append_pairs_remaining"], 65)
        self.assertEqual(r["native_archive_capacity_status"],
                         "WITHIN_CURRENT_BOUND")

    def test_03_early_warning_exactly_64_and_below(self) -> None:
        for slots in (64, 33, 17):
            with self.subTest(slots=slots):
                r = native_capacity_readonly_receipt(
                    state_at(MAX_NATIVE_FILES - slots))
                self.assertEqual(r["native_archive_append_pairs_remaining"], slots)
                self.assertEqual(r["native_archive_capacity_status"],
                                 "EARLY_SCALING_REVIEW_ONLY")

    def test_04_urgent_warning_exactly_16_and_below(self) -> None:
        for slots in (16, 1):
            with self.subTest(slots=slots):
                r = native_capacity_readonly_receipt(
                    state_at(MAX_NATIVE_FILES - slots))
                self.assertEqual(r["native_archive_capacity_status"],
                                 "URGENT_SCALING_REVIEW_ONLY")

    def test_05_at_hard_bound_is_explicit_no_auto_expand(self) -> None:
        r = native_capacity_readonly_receipt(state_at(MAX_NATIVE_FILES))
        self.assertEqual(r["native_archive_append_pairs_remaining"], 0)
        self.assertEqual(r["native_archive_capacity_status"],
                         "AT_LIMIT_NEXT_APPEND_FAILS_CLOSED")
        self.assertFalse(r["native_archive_auto_expansion_authorized"])
        self.assertTrue(r["native_archive_capacity_observation_only"])
        self.assertTrue(r["native_archive_capacity_is_not_market_session_forecast"])

    def test_06_over_limit_cannot_be_called_ok(self) -> None:
        with self.assertRaisesRegex(ValueError, "CAPACITY_STATE_INVALID"):
            native_capacity_readonly_receipt(state_at(MAX_NATIVE_FILES + 1))

    def test_07_h4_live_shaped_root_readonly_and_no_secret_output(self) -> None:
        s = h4()
        before = copy.deepcopy(s.data)
        r = audit_native_cache(
            s, interval="4h",
            now_utc=datetime(2026, 11, 11, 5, 15, tzinfo=UTC))
        self.assertEqual(r["native_archive_append_pairs_remaining"], 255)
        self.assertEqual(r["native_archive_max_files_per_bucket"], 256)
        self.assertEqual(r["native_archive_capacity_status"],
                         "WITHIN_CURRENT_BOUND")
        self.assertEqual(r["historical_manifest_chunk_pairs_verified"], 1)
        self.assertTrue(r["full_bounded_archive_verified"])
        self.assertEqual(r["twelve_data_api_calls"], 0)
        self.assertEqual(r["drive_writes"], 0)
        self.assertEqual(r["broker_orders"], 0)
        self.assertEqual(s.data, before)

    def test_08_d1_native_capacity_does_not_change_lag_or_clock(self) -> None:
        s = d1()
        r = audit_native_cache(
            s, interval="1day",
            now_utc=datetime(2026, 11, 11, 5, 15, tzinfo=UTC))
        self.assertEqual(r["latest_publication_eligible_label"], "2026-11-10")
        self.assertEqual(r["lag"], 0)
        self.assertEqual(r["native_archive_append_pairs_remaining"], 255)
        self.assertEqual(r["numeric_buy_sell_signals"], 0)

    def test_09_source_archive_orphan_still_fails_closed(self) -> None:
        s = h4()
        s.data["chunk"]["MFX_TD_EURUSD_H4_NATIVE_V1_chunk_orphan.json"] = {}
        with self.assertRaisesRegex(ValueError, "UNCOMMITTED_NATIVE_CHUNK"):
            audit_native_cache(
                s, interval="4h",
                now_utc=datetime(2026, 11, 11, 5, 15, tzinfo=UTC))

    def test_10_readonly_audit_and_writer_schedules_remain_untouched(self) -> None:
        audit_yaml = Path(
            ".github/workflows/mfx-native-htf-cache-audit.yml"
        ).read_text(encoding="utf-8")
        writer_yaml = Path(
            ".github/workflows/mfx-native-htf-incremental-commit.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('cron: "45 * * * *"', audit_yaml)
        self.assertIn('cron: "25 * * * *"', writer_yaml)
        self.assertIn("cancel-in-progress: false", audit_yaml)
        self.assertIn("contents: read", audit_yaml)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY", audit_yaml)
        self.assertIn("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED", writer_yaml)


if __name__ == "__main__":
    unittest.main()
