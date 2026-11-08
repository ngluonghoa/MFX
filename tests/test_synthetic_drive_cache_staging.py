"""M2/P0.8 Google Drive STAGING synthetic cross-scope cache acceptance."""
import unittest
from datetime import timedelta

from forex_trading.market_data import BarSide, Timeframe
from forex_trading.scan_selection import ScanMode
from forex_trading.synthetic_drive_cache_staging import (
    SyntheticDriveCacheStaging, run_mixed_scope_synthetic_drive_scan,
)
from test_synthetic_scan_workload import (
    T, DECISION, POLICY, make_fixture, workload,
)

FOLDER = "SYNTHETIC_DRIVE_FOLDER_ONLY"
UNIVERSE = tuple("TESTPAIR%02d" % i for i in range(20))
FIVE = UNIVERSE[:5]


class ObservedSource(dict):
    def __init__(self, other):
        super().__init__(other)
        self.accessed = []

    def __getitem__(self, key):
        self.accessed.append(key)
        return super().__getitem__(key)


def per_pair(*, live_oracle=False):
    result = {}
    for fixture in workload():
        pair = fixture.cached.partition.instrument_version
        result.setdefault(pair, []).append(
            fixture.complete_oracle if live_oracle else fixture.cached
        )
    return ObservedSource({key: tuple(value) for key, value in result.items()})


def run(store, source, mode, at, selected=()):
    return run_mixed_scope_synthetic_drive_scan(
        store, source, UNIVERSE, mode, POLICY, at, requested_pairs=selected,
    )


class SyntheticDriveCacheStagingTests(unittest.TestCase):
    def test_5_to_20_to_1_to_20_reuses_existing_candles_across_modes(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        first_source = per_pair()
        first = run(cache, first_source, ScanMode.CUSTOM, T + timedelta(seconds=1), FIVE)
        self.assertEqual(first.selection.selected_pairs, FIVE)
        self.assertEqual(first_source.accessed, list(FIVE))
        self.assertEqual(first.bootstrapped_streams, 50)
        self.assertEqual(first.delta_plans, 0)
        self.assertEqual(first.source_rows_selected_from_oracle, 400)
        self.assertEqual(first.simulated_new_chunk_writes, 50)
        self.assertEqual(cache.partition_count, 50)
        old_partitions = set(cache._active_names)
        old_manifest_digests = dict(cache._active_digests)

        updated_source = per_pair(live_oracle=True)
        second = run(cache, updated_source, ScanMode.ALL, DECISION)
        self.assertEqual(updated_source.accessed, list(UNIVERSE))
        self.assertEqual(second.bootstrapped_streams, 150)
        self.assertEqual(second.delta_plans, 50)
        self.assertEqual(second.appended, 10)
        self.assertEqual(second.revised, 0)
        self.assertEqual(second.simulated_new_chunk_writes, 160)
        self.assertEqual(second.source_rows_selected_from_oracle, 1340)
        self.assertEqual(cache.partition_count, 200)
        self.assertTrue(old_partitions.issubset(cache._active_names))
        self.assertTrue(any(
            cache._active_digests[k] == old_manifest_digests[k]
            for k in old_partitions
        ))  # M15+ TF unchanged; not rewritten just because ALL was chosen.

        one_source = per_pair(live_oracle=True)
        before_one = dict(cache._active_digests)
        third = run(
            cache, one_source, ScanMode.SINGLE,
            DECISION + timedelta(minutes=5), (UNIVERSE[2],),
        )
        self.assertEqual(one_source.accessed, [UNIVERSE[2]])
        self.assertEqual(third.delta_plans, 10)
        self.assertEqual(third.bootstrapped_streams, 0)
        self.assertEqual(third.appended, 0)
        self.assertEqual(third.revised, 0)
        self.assertEqual(third.simulated_new_chunk_writes, 0)
        self.assertEqual(third.unchanged_streams, 10)
        self.assertEqual(cache._active_digests, before_one)

        last_source = per_pair(live_oracle=True)
        final = run(
            cache, last_source, ScanMode.ALL,
            DECISION + timedelta(minutes=10),
        )
        self.assertEqual(final.delta_plans, 200)
        self.assertEqual(final.bootstrapped_streams, 0)
        self.assertEqual(final.simulated_new_chunk_writes, 0)
        self.assertEqual(final.unchanged_streams, 200)
        self.assertEqual(final.source_rows_selected_from_oracle, 400)
        self.assertEqual(cache.partition_count, 200)
        self.assertEqual(cache._active_digests, before_one)
        self.assertEqual(cache.simulated_chunk_count, 210)
        self.assertEqual(final.actual_drive_api_calls, 0)
        self.assertEqual(final.actual_vendor_api_calls, 0)
        self.assertFalse(final.may_store_real_market_data)
        self.assertFalse(final.may_trade)

    def test_one_selected_pair_does_not_read_other_19_even_when_known(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        source = per_pair()
        run(cache, source, ScanMode.SINGLE, T+timedelta(seconds=1), (UNIVERSE[11],))
        self.assertEqual(source.accessed, [UNIVERSE[11]])
        self.assertEqual(cache.partition_count, 10)
        self.assertEqual(len(cache.read_partition_ids), 10)
        self.assertEqual(len(cache.write_partition_ids), 10)

    def test_late_revision_inside_overlap_updates_only_selected_partition(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        base = per_pair()
        run(cache, base, ScanMode.CUSTOM, T+timedelta(seconds=1), FIVE)
        before = dict(cache._active_digests)
        new = per_pair(live_oracle=True)
        targeted = next(i for i, s in enumerate(new[UNIVERSE[1]])
                        if s.partition.side is BarSide.BID
                        and s.partition.timeframe is Timeframe.M5)
        corrected = make_fixture(
            UNIVERSE[1], BarSide.BID, Timeframe.M5,
            append=True, correction_idx=7,
        )
        replacement = list(new[UNIVERSE[1]])
        replacement[targeted] = corrected.complete_oracle
        new[UNIVERSE[1]] = tuple(replacement)
        result = run(cache, new, ScanMode.SINGLE, DECISION, (UNIVERSE[1],))
        self.assertEqual(result.revised, 1)
        self.assertEqual(result.appended, 2)
        self.assertEqual(result.simulated_new_chunk_writes, 2)
        self.assertEqual(
            {k for k in before if cache._active_digests[k] != before[k]},
            {f.partition.fingerprint for f in replacement
             if f.partition.timeframe is Timeframe.M5},
        )
        self.assertEqual(result.actual_vendor_api_calls, 0)

    def test_staging_crash_does_not_advance_active_pointer(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        source = per_pair()
        old = source[UNIVERSE[0]][0]
        self.assertTrue(cache.stage_and_commit(
            old, T+timedelta(seconds=1), expected_active_sha256=None,
        ))
        before = cache.manifest_history(old.partition.fingerprint)
        previous_sha = before[-1].manifest_sha256
        replacement = per_pair(live_oracle=True)[UNIVERSE[0]][0]
        # First source is BID M5; this produces a different snapshot fingerprint.
        with self.assertRaisesRegex(RuntimeError, "CRASH_BEFORE_PUBLISH"):
            cache.stage_and_commit(
                replacement, DECISION, expected_active_sha256=previous_sha,
                inject_crash_before_publish=True,
            )
        self.assertEqual(cache.manifest_history(old.partition.fingerprint), before)
        self.assertEqual(cache.load(old.partition.fingerprint).fingerprint,
                         old.fingerprint)
        self.assertTrue(cache.stage_and_commit(
            replacement, DECISION, expected_active_sha256=previous_sha,
        ))
        self.assertEqual(len(cache.manifest_history(old.partition.fingerprint)), 2)

    def test_stale_writer_fails_closed_and_preserves_latest(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        initial = per_pair()[UNIVERSE[0]][0]
        latest = per_pair(live_oracle=True)[UNIVERSE[0]][0]
        cache.stage_and_commit(initial, T+timedelta(seconds=1),
                               expected_active_sha256=None)
        old_digest = cache.manifest_history(initial.partition.fingerprint)[-1].manifest_sha256
        cache.stage_and_commit(latest, DECISION,
                               expected_active_sha256=old_digest)
        with self.assertRaisesRegex(ValueError, "STALE_GENERATION"):
            cache.stage_and_commit(initial, DECISION+timedelta(minutes=1),
                                   expected_active_sha256=old_digest)
        self.assertEqual(cache.load(initial.partition.fingerprint).fingerprint,
                         latest.fingerprint)

    def test_missing_active_chunk_is_detected_and_no_silent_refetch(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        first = per_pair()[UNIVERSE[0]][0]
        cache.stage_and_commit(first, T+timedelta(seconds=1),
                               expected_active_sha256=None)
        cache.simulate_corrupt_active_chunk_for_test(first.partition.fingerprint)
        with self.assertRaisesRegex(ValueError, "CHUNK_MISSING_OR_CORRUPT"):
            cache.load(first.partition.fingerprint)
        # Do not silently promote a missing/corrupt chunk to BOOTSTRAP.

    def test_bad_active_manifest_pointer_fails_closed(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        first = per_pair()[UNIVERSE[0]][0]
        cache.stage_and_commit(first, T+timedelta(seconds=1),
                               expected_active_sha256=None)
        cache._active_digests[first.partition.fingerprint] = "0"*64
        with self.assertRaisesRegex(ValueError, "ACTIVE_POINTER"):
            cache.load(first.partition.fingerprint)

    def test_missing_ask_preflight_prevents_partial_writes(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        source = per_pair()
        pair = UNIVERSE[0]
        source[pair] = tuple(s for s in source[pair]
                             if s.partition.side is BarSide.BID)
        with self.assertRaisesRegex(ValueError, "BID_ASK_TF_INCOMPLETE"):
            run(cache, source, ScanMode.SINGLE, T+timedelta(seconds=1), (pair,))
        self.assertEqual(cache.partition_count, 0)

    def test_missing_late_pair_preflight_prevents_any_partial_writes(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        source = per_pair()
        source.pop(UNIVERSE[4])
        with self.assertRaisesRegex(ValueError, "NOT_IN_SYNTHETIC_ORACLE"):
            run(cache, source, ScanMode.CUSTOM, T+timedelta(seconds=1), FIVE)
        self.assertEqual(cache.partition_count, 0)

    def test_duplicate_tf_or_side_fails_closed(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        source = per_pair()
        pair = UNIVERSE[0]
        source[pair] = source[pair][:-1] + (source[pair][0],)
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_OR_DUPLICATE"):
            run(cache, source, ScanMode.SINGLE, T+timedelta(seconds=1), (pair,))

    def test_future_source_oracle_rejected(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        source = per_pair(live_oracle=True)
        with self.assertRaisesRegex(ValueError, "FUTURE_SOURCE_ORACLE"):
            run(cache, source, ScanMode.SINGLE, T+timedelta(seconds=1), (UNIVERSE[0],))

    def test_unknown_catalog_pair_fails(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        with self.assertRaisesRegex(ValueError, "PAIR_NOT_IN_APPROVED_CATALOG"):
            run(cache, per_pair(), ScanMode.SINGLE,
                T+timedelta(seconds=1), ("SOMEUNKNOWN",))

    def test_invalid_folder_or_input_type(self):
        with self.assertRaisesRegex(ValueError, "INVALID_DRIVE_FOLDER"):
            SyntheticDriveCacheStaging("https://example.com")
        with self.assertRaisesRegex(TypeError, "SyntheticDriveCacheStaging"):
            run_mixed_scope_synthetic_drive_scan(
                None, per_pair(), UNIVERSE, ScanMode.ALL,
                POLICY, DECISION,
            )

    def test_no_actual_drive_or_vendor_io_on_any_path(self):
        cache = SyntheticDriveCacheStaging(FOLDER)
        r1 = run(cache, per_pair(), ScanMode.SINGLE,
                 T+timedelta(seconds=1), (UNIVERSE[0],))
        r2 = run(cache, per_pair(live_oracle=True), ScanMode.SINGLE,
                 DECISION, (UNIVERSE[0],))
        for result in (r1, r2):
            self.assertEqual(result.actual_drive_api_calls, 0)
            self.assertEqual(result.actual_vendor_api_calls, 0)
            self.assertFalse(result.may_store_real_market_data)


if __name__ == "__main__":
    unittest.main()
