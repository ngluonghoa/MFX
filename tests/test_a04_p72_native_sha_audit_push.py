"""A04/P0.72: native H4+D1 full-SHA audit runs on protected-main changes.

New push trigger is READ ONLY and additional to existing UTC :45 schedule.
Synthetic native D1 child SHA re-read tests do not call API or Drive.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path
import unittest

from tools.run_mfx_native_htf_cache_audit import audit_native_cache
from test_a04_p58_native_htf_cache_audit import ReadOnlyFakeStore, native

UTC=timezone.utc
WORKFLOW=Path(".github/workflows/mfx-native-htf-cache-audit.yml")


def native_d1_two_pairs() -> ReadOnlyFakeStore:
    store=ReadOnlyFakeStore()
    store.seed(native("1day",("2026-11-09","2026-11-10")))
    store.seed(native("1day",("2026-11-10","2026-11-11")))
    return store


class NativeReadOnlyOnChangeTests(unittest.TestCase):
    def test_01_push_trigger_only_protected_main(self) -> None:
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("  push:\n    branches: [main]",text)
        self.assertNotIn("branches: [develop]",text)

    def test_02_targeted_native_sha_source_paths(self) -> None:
        text=WORKFLOW.read_text(encoding="utf-8")
        for path in (
            "tools/run_mfx_native_htf_cache_audit.py",
            "tools/mfx_native_htf_drive_seal.py",
            "mfx_cache/native_fx_htf.py",
            "mfx_cache/native_htf_archive.py",
            ".github/workflows/mfx-native-htf-cache-audit.yml",
        ):
            self.assertIn(f'      - "{path}"',text)

    def test_03_original_cron_and_dispatch_are_unchanged(self) -> None:
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "45 * * * *"',text)
        self.assertIn("workflow_dispatch:",text)
        self.assertEqual(text.count("cron:"),1)

    def test_04_shared_lock_and_no_concurrent_cancel(self) -> None:
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: mfx-twelvedata-private-cache",text)
        self.assertIn("cancel-in-progress: false",text)

    def test_05_three_existing_owner_gates_must_remain(self) -> None:
        text=WORKFLOW.read_text(encoding="utf-8")
        for gate in (
            "vars.MFX_REAL_CACHE_ENABLED == 'true'",
            "vars.MFX_V2_BATCH_CACHE_ACCEPTED == 'true'",
            "vars.MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED == 'true'",
        ):
            self.assertIn(gate,text)

    def test_06_no_vendor_price_key_or_mutating_workflow(self) -> None:
        text=WORKFLOW.read_text(encoding="utf-8")
        for forbidden in (
            "MFX_TWELVE_DATA_API_KEY",
            "run_mfx_native_htf_drive_commit",
            "run_mfx_native_htf_incremental_commit",
            "secrets.GITHUB_TOKEN",
            "permissions: write-all",
        ):
            self.assertNotIn(forbidden,text)
        self.assertIn("contents: read",text)
        self.assertIn("python -m tools.run_mfx_native_htf_cache_audit",text)

    def test_07_synthetic_first_d1_child_all_sha_parents(self) -> None:
        store=native_d1_two_pairs()
        before=copy.deepcopy(store.data)
        report=audit_native_cache(
            store,interval="1day",
            now_utc=datetime(2026,11,11,13,40,tzinfo=UTC))
        self.assertEqual(report["last_native_open_label"],"2026-11-11")
        self.assertEqual(report["total_closed_native_bars"],3)
        self.assertEqual(report["historical_manifest_chunk_pairs_verified"],2)
        self.assertTrue(report["full_bounded_archive_verified"])
        self.assertEqual(report["lag"],0)
        self.assertEqual(report["twelve_data_api_calls"],0)
        self.assertEqual(report["drive_writes"],0)
        self.assertEqual(report["broker_orders"],0)
        self.assertEqual(store.data,before)

    def test_08_tampered_old_native_d1_parent_chunk_fails_full_audit(self) -> None:
        store=native_d1_two_pairs()
        old_name=sorted(store.data["chunk"])[0]
        store.data["chunk"][old_name]["bars"][0]["high"]="999.0"
        with self.assertRaises(ValueError):
            audit_native_cache(
                store,interval="1day",
                now_utc=datetime(2026,11,11,13,40,tzinfo=UTC))

    def test_09_missing_native_d1_manifest_fails(self) -> None:
        store=native_d1_two_pairs()
        old_name=sorted(store.data["manifest"])[0]
        del store.data["manifest"][old_name]
        with self.assertRaises(ValueError):
            audit_native_cache(
                store,interval="1day",
                now_utc=datetime(2026,11,11,13,40,tzinfo=UTC))


if __name__=="__main__":
    unittest.main()
