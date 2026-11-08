"""P2.1-B synthetic store/orchestrator isolation and old API compatibility."""
import ast
import inspect
import subprocess
import sys
import unittest
from datetime import timedelta

from forex_trading import (
    synthetic_drive_cache_staging as legacy,
    synthetic_drive_cache_store as store,
    synthetic_drive_scan_orchestrator as orchestrator,
)
from forex_trading.scan_contract import ScanMode
from forex_trading.market_data import BarSide, Timeframe
from test_synthetic_scan_workload import T, DECISION, POLICY, workload


FOLDER = "SYNTHETIC_DRIVE_FOLDER_ONLY"
UNIVERSE = tuple("TESTPAIR%02d" % i for i in range(20))


def oracle(*, latest=False):
    result = {}
    for item in workload():
        snapshot = item.complete_oracle if latest else item.cached
        result.setdefault(snapshot.partition.instrument_version, []).append(snapshot)
    return {pair: tuple(snapshots) for pair, snapshots in result.items()}


class SyntheticCacheBoundaryTests(unittest.TestCase):
    def test_all_legacy_api_reexports_have_identical_objects(self):
        for name in ("SyntheticDriveCacheStaging", "SyntheticCacheAction",
                     "SyntheticChunk"):
            with self.subTest(name=name):
                self.assertIs(getattr(legacy, name), getattr(store, name))
        self.assertIs(legacy.MixedScanResult, orchestrator.MixedScanResult)
        self.assertIs(legacy.run_mixed_scope_synthetic_drive_scan,
                      orchestrator.run_mixed_scope_synthetic_drive_scan)
        self.assertEqual(inspect.signature(
            legacy.run_mixed_scope_synthetic_drive_scan),
            inspect.signature(
                orchestrator.run_mixed_scope_synthetic_drive_scan))

    def test_store_imports_do_not_depend_on_scan_orchestrator(self):
        tree = ast.parse(inspect.getsource(store))
        internal_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level > 0
        }
        self.assertNotIn("synthetic_drive_scan_orchestrator", internal_imports)
        self.assertNotIn("scan_selection", internal_imports)
        self.assertNotIn("scan_contract", internal_imports)
        self.assertNotIn("synthetic_scan_workload", internal_imports)
        self.assertIn("synthetic_drive_cache_store", {
            node.module for node in ast.walk(
                ast.parse(inspect.getsource(orchestrator)))
            if isinstance(node, ast.ImportFrom) and node.level > 0
        })

    def test_canonical_modules_import_cleanly_in_new_process(self):
        script = (
            "from forex_trading.synthetic_drive_scan_orchestrator "
            "import run_mixed_scope_synthetic_drive_scan as runner; "
            "from forex_trading.synthetic_drive_cache_store "
            "import SyntheticDriveCacheStaging as cache; "
            "from forex_trading.synthetic_drive_cache_staging "
            "import run_mixed_scope_synthetic_drive_scan as old; "
            "assert old is runner; assert cache.__module__.endswith("
            "'synthetic_drive_cache_store')"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script], capture_output=True,
            text=True, check=False, timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_mixed_scope_5_20_1_20_parity_both_import_paths(self):
        actions = (
            (ScanMode.CUSTOM, UNIVERSE[:5], T + timedelta(seconds=1), False),
            (ScanMode.ALL, (), DECISION, True),
            (ScanMode.SINGLE, (UNIVERSE[2],),
             DECISION + timedelta(minutes=5), True),
            (ScanMode.ALL, (), DECISION + timedelta(minutes=10), True),
        )
        a, b = store.SyntheticDriveCacheStaging(FOLDER), legacy.SyntheticDriveCacheStaging(FOLDER)
        for mode, selected, at, latest in actions:
            with self.subTest(mode=mode, selected=selected):
                source = oracle(latest=latest)
                current = orchestrator.run_mixed_scope_synthetic_drive_scan(
                    a, source, UNIVERSE, mode, POLICY, at, requested_pairs=selected)
                historical = legacy.run_mixed_scope_synthetic_drive_scan(
                    b, source, UNIVERSE, mode, POLICY, at, requested_pairs=selected)
                self.assertEqual(current, historical)
                self.assertEqual(a._active_names, b._active_names)
                self.assertEqual(a._active_digests, b._active_digests)
                self.assertEqual(a.simulated_chunk_count, b.simulated_chunk_count)
                self.assertEqual(current.actual_drive_api_calls, 0)
                self.assertEqual(current.actual_vendor_api_calls, 0)
                self.assertFalse(current.may_store_real_market_data)
                self.assertFalse(current.may_trade)
        self.assertEqual(a.partition_count, 200)
        self.assertEqual(a.simulated_chunk_count, 210)

    def test_missing_selected_ask_preflight_keeps_store_empty(self):
        cache = store.SyntheticDriveCacheStaging(FOLDER)
        feed = oracle()
        pair = UNIVERSE[0]
        feed[pair] = tuple(s for s in feed[pair]
                           if s.partition.side is BarSide.BID)
        with self.assertRaisesRegex(ValueError, "BID_ASK_TF_INCOMPLETE"):
            orchestrator.run_mixed_scope_synthetic_drive_scan(
                cache, feed, UNIVERSE, ScanMode.SINGLE, POLICY,
                T + timedelta(seconds=1), requested_pairs=(pair,))
        self.assertEqual(cache.partition_count, 0)

    def test_corrupt_store_chunk_is_not_silently_bootstrapped(self):
        cache = store.SyntheticDriveCacheStaging(FOLDER)
        snapshot = oracle()[UNIVERSE[0]][0]
        cache.stage_and_commit(snapshot, T + timedelta(seconds=1),
                               expected_active_sha256=None)
        cache.simulate_corrupt_active_chunk_for_test(
            snapshot.partition.fingerprint)
        with self.assertRaisesRegex(ValueError, "CHUNK_MISSING_OR_CORRUPT"):
            orchestrator.run_mixed_scope_synthetic_drive_scan(
                cache, oracle(latest=True), UNIVERSE, ScanMode.SINGLE,
                POLICY, DECISION, requested_pairs=(UNIVERSE[0],))

    def test_unchanged_store_does_not_depend_on_external_io(self):
        cache = store.SyntheticDriveCacheStaging(FOLDER)
        report = orchestrator.run_mixed_scope_synthetic_drive_scan(
            cache, oracle(), UNIVERSE, ScanMode.SINGLE, POLICY,
            T + timedelta(seconds=1), requested_pairs=(UNIVERSE[2],),
            timeframes=(Timeframe.M5, Timeframe.M15, Timeframe.H1,
                        Timeframe.H4, Timeframe.D1))
        self.assertEqual(report.bootstrapped_streams, 10)
        self.assertEqual(report.simulated_new_chunk_writes, 10)
        self.assertEqual(report.actual_drive_api_calls, 0)
        self.assertEqual(report.actual_vendor_api_calls, 0)


if __name__ == "__main__":
    unittest.main()
