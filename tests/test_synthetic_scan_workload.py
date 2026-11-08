import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from forex_trading.cache_core import (
    CachePartition, CandleSnapshot, IncrementalPolicy, SourceHeadClaim,
)
from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, MarketBar, MarketBarKey,
    Observation, SourceQuality, Timeframe,
)
from forex_trading.synthetic_scan_workload import (
    SyntheticScanFixture, SyntheticSweepVerdict,
    run_synthetic_five_minute_sweep,
)

UTC = timezone.utc
T = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
M = timedelta(minutes=1)
DECISION = T + 5*M + timedelta(seconds=1)
DURATIONS = {
    Timeframe.M5: timedelta(minutes=5),
    Timeframe.M15: timedelta(minutes=15),
    Timeframe.H1: timedelta(hours=1),
    Timeframe.H4: timedelta(hours=4),
    Timeframe.D1: timedelta(days=1),  # SYNTHETIC UTC ONLY, NOT real FX DST calendar
}
PER_PAIR = tuple(DURATIONS)


def make_bar(p: CachePartition, start: datetime, duration: timedelta, *,
             revision: int = 1, first_known: datetime | None = None):
    end = start + duration
    known = first_known if first_known is not None else end
    key = MarketBarKey(
        p.instrument_version, p.timeframe, start, end,
        p.calendar_version, p.aggregation_version, p.side,
    )
    obs = Observation(
        p.provider_id, f"synthetic-{p.side.value}",
        "SYNTHETIC_FIXTURE_NO_NETWORK", f"bar-{start.isoformat()}-r{revision}",
        f"{revision % 10}"*64, known, known, p.source_timezone_policy,
        "NO_VENDOR_DATA_RIGHTS",
    )
    return MarketBar(
        key, obs, revision, known,
        Decimal("1.1000"), Decimal("1.2000"), Decimal("1.0000"),
        Decimal("1.1400") if revision == 1 else Decimal("1.1500"),
        BarLifecycle.CLOSED, BarCoverage.COMPLETE, SourceQuality.VERIFIED,
    )


def make_fixture(symbol: str = "TESTPAIR00", side: BarSide = BarSide.BID,
                 tf: Timeframe = Timeframe.M5, *,
                 append: bool = False, correction_idx: int | None = None,
                 head_changed: bool | None = None, head_present: bool = True):
    p = CachePartition(
        "SYNTHETIC_VENDOR", "SYNTHETIC_PRODUCT", symbol, side, tf,
        "UTC_ONLY_TEST_NO_FX_SESSION", "SYNTHETIC_AGGREGATION",
        "UTC_ONLY", "RIGHT_NOT_GRANTED", "SYNTHETIC_SCHEMA_V1",
    )
    duration = DURATIONS[tf]
    old_bars = tuple(make_bar(p, T-(8-i)*duration, duration) for i in range(8))
    before = CandleSnapshot(p, old_bars, T+timedelta(seconds=1), "head-v1")
    source_bars = list(old_bars)
    if correction_idx is not None:
        original = old_bars[correction_idx]
        source_bars[correction_idx] = make_bar(
            p, original.key.bar_start_utc, duration, revision=2,
            first_known=DECISION,
        )
    if append:
        source_bars.append(make_bar(p, T, duration))
    current_head = "head-v2" if (
        (append or correction_idx is not None) if head_changed is None else head_changed
    ) else "head-v1"
    oracle = CandleSnapshot(p, tuple(source_bars), DECISION, current_head)
    head = None
    if head_present:
        head = SourceHeadClaim(
            p.fingerprint, current_head, source_bars[-1].key.bar_end_utc,
            DECISION,
        )
    return SyntheticScanFixture(before, oracle, head)


def workload(*, head_present=True):
    return tuple(
        make_fixture(f"TESTPAIR{i:02d}", side, tf,
                     append=(tf is Timeframe.M5), head_present=head_present)
        for i in range(20)
        for side in (BarSide.BID, BarSide.ASK)
        for tf in PER_PAIR
    )


POLICY = IncrementalPolicy(overlap_closed_bars=2, max_head_age=timedelta(minutes=5))


class SyntheticRepeatScanTests(unittest.TestCase):
    def test_20_pairs_bid_ask_five_timeframes_delta_math(self):
        scan = run_synthetic_five_minute_sweep(workload(), POLICY, DECISION)
        self.assertEqual(scan.pair_count, 20)
        self.assertEqual(scan.stream_count, 20*2*5)
        self.assertEqual(scan.baseline_naive_full_history_rows, 20*2*5*8+40)
        self.assertEqual(scan.planned_bounded_range_queries, 40)
        self.assertEqual(scan.simulated_head_claim_reuses, 160)
        self.assertEqual(scan.simulated_returned_bar_rows, 40*3)
        self.assertEqual(scan.hypothetical_history_rows_avoided, 1520)
        self.assertEqual(scan.old_cached_rows_retained, 1600)
        self.assertEqual(scan.appended, 40)
        self.assertEqual(scan.revised, 0)
        self.assertEqual(scan.unobservable_old_correction_cases, 0)
        self.assertTrue(all(
            v.verdict is SyntheticSweepVerdict.ORACLE_PARITY
            for v in scan.stream_results
        ))
        self.assertEqual(scan.actual_http_calls, 0)
        self.assertEqual(scan.actual_http_bytes, 0)
        self.assertFalse(scan.actual_elapsed_ms_measured)
        self.assertFalse(scan.may_run_real_scan)

    def test_no_provider_head_claim_bounded_overlap_not_full_redownload(self):
        scan=run_synthetic_five_minute_sweep(
            workload(head_present=False), POLICY, DECISION)
        self.assertEqual(scan.planned_bounded_range_queries,200)
        self.assertEqual(scan.simulated_head_claim_reuses,0)
        self.assertEqual(scan.simulated_returned_bar_rows,160*2+40*3)
        self.assertTrue(all(v.verdict is SyntheticSweepVerdict.ORACLE_PARITY
                            for v in scan.stream_results))
        self.assertFalse(scan.may_run_real_scan)

    def test_missing_ask_is_refused_not_partial_success(self):
        frames=tuple(x for x in workload() if x.cached.partition.side is BarSide.BID)
        with self.assertRaisesRegex(ValueError,"PAIR_REQUIRES"):
            run_synthetic_five_minute_sweep(frames,POLICY,DECISION)

    def test_mid_as_executable_side_rejected(self):
        f=make_fixture(side=BarSide.MID)
        with self.assertRaisesRegex(ValueError,"MISSING_EXECUTABLE"):
            run_synthetic_five_minute_sweep((f,),POLICY,DECISION)

    def test_duplicate_partition_rejected(self):
        f=make_fixture()
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            run_synthetic_five_minute_sweep((f,f),POLICY,DECISION)

    def test_no_range_endpoint_never_silently_get_full_history(self):
        pair=(make_fixture(side=BarSide.BID, head_present=False),
              make_fixture(side=BarSide.ASK, head_present=False))
        scan=run_synthetic_five_minute_sweep(
            pair,POLICY,DECISION,supports_bounded_range=False)
        self.assertEqual(scan.planned_bounded_range_queries,0)
        self.assertEqual(scan.simulated_returned_bar_rows,0)
        self.assertTrue(all(x.verdict is SyntheticSweepVerdict.SOURCE_RANGE_UNAVAILABLE
                            for x in scan.stream_results))

    def test_same_head_with_hidden_old_revision_is_flagged_by_test_oracle(self):
        frames=(
            make_fixture(side=BarSide.BID, correction_idx=0, head_changed=False),
            make_fixture(side=BarSide.ASK),
        )
        scan=run_synthetic_five_minute_sweep(frames,POLICY,DECISION)
        self.assertEqual(scan.unobservable_old_correction_cases,1)
        self.assertEqual(scan.simulated_returned_bar_rows,0)
        self.assertEqual(scan.stream_results[0].verdict,
                         SyntheticSweepVerdict.UNSEEN_HISTORY_CORRECTION)
        self.assertFalse(scan.may_run_real_scan)

    def test_head_change_but_revision_outside_overlap_is_not_detected_by_delta(self):
        frames=(
            make_fixture(side=BarSide.BID, correction_idx=0,head_changed=True),
            make_fixture(side=BarSide.ASK),
        )
        scan=run_synthetic_five_minute_sweep(frames,POLICY,DECISION)
        self.assertEqual(scan.planned_bounded_range_queries,1)
        self.assertEqual(scan.simulated_returned_bar_rows,2)
        self.assertEqual(scan.unobservable_old_correction_cases,1)

    def test_recent_revision_is_detected_by_overlap(self):
        frames=(
            make_fixture(side=BarSide.BID, correction_idx=7),
            make_fixture(side=BarSide.ASK),
        )
        scan=run_synthetic_five_minute_sweep(frames,POLICY,DECISION)
        self.assertEqual(scan.revised,1)
        self.assertEqual(scan.stream_results[0].first_dirty_utc,T-5*M)
        self.assertEqual(scan.unobservable_old_correction_cases,0)

    def test_repeat_fixture_is_deterministic(self):
        frames=(make_fixture(side=BarSide.BID,append=True),
                make_fixture(side=BarSide.ASK,append=True))
        a=run_synthetic_five_minute_sweep(frames,POLICY,DECISION)
        b=run_synthetic_five_minute_sweep(frames,POLICY,DECISION)
        self.assertEqual(a,b)

    def test_mismatched_source_partition_is_rejected(self):
        b=make_fixture(side=BarSide.BID)
        a=make_fixture(side=BarSide.ASK)
        with self.assertRaisesRegex(ValueError,"PARTITION"):
            replace(
                a.complete_oracle,
                partition=replace(a.complete_oracle.partition,provider_id="other"),
            )

    def test_future_oracle_snapshot_is_rejected(self):
        b=make_fixture(side=BarSide.BID)
        a=make_fixture(side=BarSide.ASK)
        b=replace(b,complete_oracle=replace(
            b.complete_oracle,checked_at_utc=DECISION+timedelta(seconds=1),
        ))
        with self.assertRaisesRegex(ValueError,"FUTURE_ORACLE"):
            run_synthetic_five_minute_sweep((b,a),POLICY,DECISION)
