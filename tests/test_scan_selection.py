"""M2/P0.7 synthetic scope isolation and cache reuse regression tests."""
import unittest
from dataclasses import replace

from forex_trading.cache_core import IncrementalPolicy
from forex_trading.market_data import BarSide, Timeframe
from forex_trading.scan_selection import (
    ScanMode, plan_scan_selection, run_selected_synthetic_scan,
)
from forex_trading.synthetic_scan_workload import (
    SyntheticSweepVerdict,
)
from test_synthetic_scan_workload import (
    DECISION, POLICY, make_fixture, workload,
)


UNIVERSE = tuple(f"TESTPAIR{i:02d}" for i in range(20))


class ScanSelectionTests(unittest.TestCase):
    def test_single_selects_only_one_without_loading_other_pair_history(self):
        result = plan_scan_selection(UNIVERSE, ScanMode.SINGLE, ("TESTPAIR07",))
        self.assertEqual(result.selected_pairs, ("TESTPAIR07",))
        self.assertEqual(len(result.skipped_pairs), 19)
        self.assertNotIn("TESTPAIR07", result.skipped_pairs)
        self.assertFalse(result.may_fetch_real_data)
        self.assertFalse(result.may_trade)

    def test_custom_preserves_requested_order_and_skips_other_pairs(self):
        result = plan_scan_selection(
            UNIVERSE, ScanMode.CUSTOM,
            ("TESTPAIR09", "TESTPAIR00", "TESTPAIR05"),
        )
        self.assertEqual(
            result.selected_pairs, ("TESTPAIR09", "TESTPAIR00", "TESTPAIR05")
        )
        self.assertEqual(len(result.skipped_pairs), 17)

    def test_all_uses_catalog_order_and_no_skipped_pairs(self):
        result = plan_scan_selection(UNIVERSE, ScanMode.ALL)
        self.assertEqual(result.selected_pairs, UNIVERSE)
        self.assertEqual(result.skipped_pairs, ())

    def test_duplicate_catalog_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CATALOG"):
            plan_scan_selection(UNIVERSE[:-1] + ("TESTPAIR00",), ScanMode.ALL)

    def test_catalog_must_have_20(self):
        with self.assertRaisesRegex(ValueError, "TWENTY_PAIR"):
            plan_scan_selection(UNIVERSE[:-1], ScanMode.ALL)

    def test_invalid_catalog_symbol_fails(self):
        with self.assertRaisesRegex(ValueError, "INVALID_CATALOG"):
            plan_scan_selection(UNIVERSE[:-1] + ("eur/usd",), ScanMode.ALL)

    def test_unknown_requested_symbol_fails(self):
        with self.assertRaisesRegex(ValueError, "PAIR_NOT_IN"):
            plan_scan_selection(UNIVERSE, ScanMode.SINGLE, ("EURUSD",))

    def test_duplicate_requested_symbol_fails(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_REQUESTED"):
            plan_scan_selection(
                UNIVERSE, ScanMode.CUSTOM, ("TESTPAIR00", "TESTPAIR00"),
            )

    def test_single_must_have_exactly_one(self):
        for selection in ((), ("TESTPAIR00", "TESTPAIR01")):
            with self.subTest(selection=selection):
                with self.assertRaisesRegex(ValueError, "SINGLE_REQUIRES"):
                    plan_scan_selection(UNIVERSE, ScanMode.SINGLE, selection)

    def test_custom_must_have_two_to_nineteen(self):
        for selection in (
            (), ("TESTPAIR00",), UNIVERSE,
        ):
            with self.subTest(n=len(selection)):
                with self.assertRaisesRegex(ValueError, "CUSTOM_REQUIRES"):
                    plan_scan_selection(UNIVERSE, ScanMode.CUSTOM, selection)

    def test_all_mode_does_not_accept_explicit_selected_pairs(self):
        with self.assertRaisesRegex(ValueError, "ALL_MODE"):
            plan_scan_selection(UNIVERSE, ScanMode.ALL, ("TESTPAIR00",))

    def test_typed_mode_and_immutable_request(self):
        with self.assertRaisesRegex(TypeError, "TYPED_SCAN_MODE"):
            plan_scan_selection(UNIVERSE, "SINGLE", ("TESTPAIR00",))
        with self.assertRaisesRegex(TypeError, "IMMUTABLE"):
            plan_scan_selection(UNIVERSE, ScanMode.SINGLE, ["TESTPAIR00"])
        with self.assertRaisesRegex(TypeError, "INVALID_REQUESTED_PAIR"):
            plan_scan_selection(UNIVERSE, ScanMode.SINGLE, (None,))


class SelectedSyntheticScanTests(unittest.TestCase):
    def test_single_pair_is_ten_streams_and_never_200(self):
        report = run_selected_synthetic_scan(
            workload(), POLICY, DECISION, universe=UNIVERSE,
            mode=ScanMode.SINGLE, requested_pairs=("TESTPAIR07",),
        )
        self.assertEqual(report.selection.selected_pairs, ("TESTPAIR07",))
        self.assertEqual(report.sweep.pair_count, 1)
        self.assertEqual(report.sweep.stream_count, 10)
        self.assertEqual(report.sweep.baseline_naive_full_history_rows, 82)
        self.assertEqual(report.sweep.planned_bounded_range_queries, 2)
        self.assertEqual(report.sweep.simulated_head_claim_reuses, 8)
        self.assertEqual(report.sweep.simulated_returned_bar_rows, 6)
        self.assertEqual(report.sweep.appended, 2)
        self.assertEqual(report.sweep.old_cached_rows_retained, 80)
        self.assertEqual(report.actual_provider_requests, 0)
        self.assertFalse(report.may_run_real_scan)
        self.assertFalse(report.sweep.may_run_real_scan)

    def test_custom_three_pairs_only_30_streams(self):
        report = run_selected_synthetic_scan(
            workload(), POLICY, DECISION, universe=UNIVERSE,
            mode=ScanMode.CUSTOM,
            requested_pairs=("TESTPAIR12", "TESTPAIR00", "TESTPAIR07"),
        )
        self.assertEqual(report.sweep.pair_count, 3)
        self.assertEqual(report.sweep.stream_count, 30)
        self.assertEqual(report.sweep.planned_bounded_range_queries, 6)
        self.assertEqual(report.sweep.simulated_head_claim_reuses, 24)
        self.assertEqual(report.sweep.simulated_returned_bar_rows, 18)
        self.assertEqual(report.sweep.appended, 6)
        self.assertEqual(len(report.selection.skipped_pairs), 17)

    def test_all_preserves_existing_twenty_pair_benchmark(self):
        report = run_selected_synthetic_scan(
            workload(), POLICY, DECISION,
            universe=UNIVERSE, mode=ScanMode.ALL,
        )
        self.assertEqual(report.sweep.pair_count, 20)
        self.assertEqual(report.sweep.stream_count, 200)
        self.assertEqual(report.sweep.planned_bounded_range_queries, 40)
        self.assertEqual(report.sweep.simulated_returned_bar_rows, 120)
        self.assertEqual(report.sweep.hypothetical_history_rows_avoided, 1520)

    def test_only_selected_fixtures_required_other_19_not_loaded(self):
        # Critical isolation: request can contain only one pair's 10 partitions.
        selected = tuple(
            f for f in workload()
            if f.cached.partition.instrument_version == "TESTPAIR04"
        )
        report = run_selected_synthetic_scan(
            selected, POLICY, DECISION, universe=UNIVERSE,
            mode=ScanMode.SINGLE, requested_pairs=("TESTPAIR04",),
        )
        self.assertEqual(report.sweep.stream_count, 10)

    def test_unselected_hidden_correction_does_not_invalidate_selected_pair(self):
        fixtures = list(workload())
        other = next(
            i for i, f in enumerate(fixtures)
            if f.cached.partition.instrument_version == "TESTPAIR18"
            and f.cached.partition.side is BarSide.BID
            and f.cached.partition.timeframe is Timeframe.M5
        )
        fixtures[other] = make_fixture(
            "TESTPAIR18", BarSide.BID, Timeframe.M5,
            correction_idx=0, head_changed=False,
        )
        before = fixtures[other]
        report = run_selected_synthetic_scan(
            tuple(fixtures), POLICY, DECISION, universe=UNIVERSE,
            mode=ScanMode.SINGLE, requested_pairs=("TESTPAIR03",),
        )
        self.assertEqual(report.sweep.unobservable_old_correction_cases, 0)
        self.assertEqual(report.sweep.stream_count, 10)
        self.assertIs(fixtures[other], before)
        self.assertEqual(
            fixtures[other].cached.fingerprint, before.cached.fingerprint
        )

    def test_selected_pair_missing_fails_closed_even_when_others_exist(self):
        selected = tuple(
            f for f in workload()
            if f.cached.partition.instrument_version != "TESTPAIR02"
        )
        with self.assertRaisesRegex(ValueError, "SELECTED_PAIR_FIXTURES_MISSING"):
            run_selected_synthetic_scan(
                selected, POLICY, DECISION, universe=UNIVERSE,
                mode=ScanMode.SINGLE, requested_pairs=("TESTPAIR02",),
            )

    def test_selected_pair_requires_bid_and_ask(self):
        selected = tuple(
            f for f in workload()
            if f.cached.partition.instrument_version == "TESTPAIR05"
            and f.cached.partition.side is BarSide.BID
        )
        with self.assertRaisesRegex(ValueError, "PAIR_REQUIRES_BOTH"):
            run_selected_synthetic_scan(
                selected, POLICY, DECISION, universe=UNIVERSE,
                mode=ScanMode.SINGLE, requested_pairs=("TESTPAIR05",),
            )

    def test_selected_pair_requires_complete_fixture_for_all_timeframes(self):
        selected = tuple(
            f for f in workload()
            if f.cached.partition.instrument_version == "TESTPAIR05"
        )
        selected = tuple(
            f for f in selected
            if not (f.cached.partition.side is BarSide.ASK
                    and f.cached.partition.timeframe is Timeframe.M15)
        )
        with self.assertRaisesRegex(ValueError, "PAIR_REQUIRES_BOTH"):
            run_selected_synthetic_scan(
                selected, POLICY, DECISION, universe=UNIVERSE,
                mode=ScanMode.SINGLE, requested_pairs=("TESTPAIR05",),
            )

    def test_repeat_scan_without_mutating_history(self):
        fixtures = workload()
        snapshots = tuple(f.cached.fingerprint for f in fixtures)
        a = run_selected_synthetic_scan(
            fixtures, POLICY, DECISION, universe=UNIVERSE,
            mode=ScanMode.SINGLE, requested_pairs=("TESTPAIR00",),
        )
        b = run_selected_synthetic_scan(
            fixtures, POLICY, DECISION, universe=UNIVERSE,
            mode=ScanMode.SINGLE, requested_pairs=("TESTPAIR00",),
        )
        self.assertEqual(a, b)
        self.assertEqual(
            snapshots, tuple(f.cached.fingerprint for f in fixtures)
        )

    def test_selected_missing_bounded_endpoint_is_blocked_not_full_reload(self):
        result = run_selected_synthetic_scan(
            tuple(
                make_fixture(
                    "TESTPAIR07", side, Timeframe.M5, head_present=False
                )
                for side in (BarSide.BID, BarSide.ASK)
            ),
            POLICY, DECISION,
            universe=UNIVERSE, mode=ScanMode.SINGLE,
            requested_pairs=("TESTPAIR07",), supports_bounded_range=False,
        )
        self.assertEqual(result.sweep.planned_bounded_range_queries, 0)
        self.assertEqual(result.sweep.simulated_returned_bar_rows, 0)
        self.assertTrue(all(
            x.verdict is SyntheticSweepVerdict.SOURCE_RANGE_UNAVAILABLE
            for x in result.sweep.stream_results
        ))

    def test_invalid_fixture_type_fails(self):
        with self.assertRaisesRegex(TypeError, "Typed SyntheticScanFixture"):
            run_selected_synthetic_scan(
                (None,), POLICY, DECISION,
                universe=UNIVERSE, mode=ScanMode.SINGLE,
                requested_pairs=("TESTPAIR07",),
            )


if __name__ == "__main__":
    unittest.main()
