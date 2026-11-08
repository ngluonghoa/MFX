import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from forex_trading.market_data import (
    MarketBar, MarketBarKey, Observation, Timeframe, BarSide,
    BarCoverage, BarLifecycle, SourceQuality,
)
from forex_trading.cache_core import (
    CachePartition, CandleSnapshot, ChangeKind, IncrementalPolicy,
    RefreshMode, SourceHeadClaim, plan_incremental_refresh,
    reconcile_closed_delta,
)

T = datetime(2026, 11, 7, tzinfo=timezone.utc)
M = timedelta(minutes=1)


def partition(**kwargs):
    obj = dict(
        provider_id="synthetic-fx-vendor", broker_product_ref="DEMO-PRODUCT",
        instrument_version="EURUSD-synth-v1", side=BarSide.BID,
        timeframe=Timeframe.M5, calendar_version="calendar-synth-v1",
        aggregation_version="aggregation-v1", source_timezone_policy="UTC-v1",
        rights_policy_ref="NOT-APPROVED", schema_version="cache-schema-v1",
    )
    obj.update(kwargs)
    return CachePartition(**obj)


def bar(index, *, revision=1, known_minute=None, close="1.14",
        side=BarSide.BID, instrument="EURUSD-synth-v1", provider="synthetic-fx-vendor",
        coverage=BarCoverage.COMPLETE, lifecycle=BarLifecycle.CLOSED,
        quality=SourceQuality.VERIFIED, source_revision=None):
    start = T + index * timedelta(minutes=5)
    end = start + timedelta(minutes=5)
    if known_minute is None:
        known = end + timedelta(seconds=1)
    else:
        known = T + timedelta(minutes=known_minute)
    key = MarketBarKey(instrument, Timeframe.M5, start, end,
                       "calendar-synth-v1", "aggregation-v1", side)
    obs = Observation(
        provider_id=provider, stream_id="bid-synthetic", endpoint="FIXTURE_ONLY",
        revision_id=source_revision or f"synthetic-rev-{revision}",
        raw_sha256=f"{revision % 10}"*64,
        first_known_utc=known, retrieved_at_utc=known,
        source_timezone_policy="UTC-v1", license_scope_claim="NO_REAL_RIGHTS",
    )
    return MarketBar(
        key, obs, revision, known,
        Decimal("1.10"), Decimal("1.20"), Decimal("1.00"), Decimal(close),
        lifecycle, coverage, quality,
    )


def snapshot(bars=None, **kwargs):
    arr = tuple(bar(i) for i in range(3)) if bars is None else bars
    args = dict(partition=partition(), closed_bars=arr,
                checked_at_utc=T + timedelta(minutes=16),
                source_head_claim="synthetic-head-1")
    args.update(kwargs)
    return CandleSnapshot(**args)


def policy():
    return IncrementalPolicy(overlap_closed_bars=2, max_head_age=timedelta(minutes=5))


class ForexCacheCoreTests(unittest.TestCase):
    def test_partition_separates_bid_ask(self):
        self.assertNotEqual(partition().fingerprint,
                            partition(side=BarSide.ASK).fingerprint)

    def test_partition_separates_pair_provider_product_and_calendar(self):
        base = partition().fingerprint
        for kwargs in (
            {"instrument_version": "GBPUSD-synth"},
            {"provider_id": "other"},
            {"broker_product_ref": "another-product"},
            {"calendar_version": "calendar-v2"},
            {"rights_policy_ref": "rights-v2"},
            {"aggregation_version": "aggregation-v2"},
            {"timeframe": Timeframe.M15},
        ):
            with self.subTest(kwargs=kwargs):
                self.assertNotEqual(partition(**kwargs).fingerprint, base)

    def test_invalid_partition_type_rejected(self):
        with self.assertRaises(TypeError):
            partition(side="BID")
        with self.assertRaises(ValueError):
            partition(provider_id="")

    def test_initial_snapshot_is_immutable_and_ordered(self):
        cache = snapshot()
        self.assertEqual(len(cache.closed_bars), 3)
        self.assertEqual(cache.last_closed_end_utc, T + 15*M)
        self.assertEqual(len(cache.fingerprint), 64)

    def test_asof_cache_rejects_future_known(self):
        with self.assertRaisesRegex(ValueError, "FUTURE"):
            snapshot(bars=(bar(3),))

    def test_provisional_bar_is_never_promoted_to_closed_cache(self):
        with self.assertRaisesRegex(ValueError, "PROVISIONAL"):
            snapshot(bars=(bar(0, lifecycle=BarLifecycle.OPEN),))

    def test_incomplete_bar_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "QUALITY"):
            snapshot(bars=(bar(0, coverage=BarCoverage.PARTIAL),))

    def test_unverified_source_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "QUALITY"):
            snapshot(bars=(bar(0, quality=SourceQuality.UNVERIFIED),))

    def test_mixed_provider_rejected(self):
        with self.assertRaisesRegex(ValueError, "PARTITION"):
            snapshot(bars=(bar(0, provider="different"),))

    def test_wrong_quote_side_rejected(self):
        with self.assertRaisesRegex(ValueError, "PARTITION"):
            snapshot(bars=(bar(0, side=BarSide.ASK),))

    def test_duplicate_closed_bar_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CANDLE"):
            snapshot(bars=(bar(0), bar(0)))

    def test_out_of_order_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNSORTED"):
            snapshot(bars=(bar(1), bar(0)))

    def test_late_recheck_does_not_change_candle_fingerprint(self):
        c=snapshot()
        later=replace(c, checked_at_utc=T+timedelta(minutes=25),
                      source_head_claim="synthetic-head-new")
        self.assertEqual(c.fingerprint, later.fingerprint)

    def test_5min_refresh_bounded_overlap_only(self):
        c = snapshot()
        plan = plan_incremental_refresh(c,policy(),T+20*M,
                                        supports_bounded_range=True)
        self.assertEqual(plan.mode, RefreshMode.DELTA_WINDOW)
        self.assertEqual(plan.from_utc, T+5*M)
        self.assertFalse(plan.may_fetch_real_data)

    def test_missing_range_support_blocks_instead_of_full_redownload(self):
        plan = plan_incremental_refresh(snapshot(),policy(),T+20*M,
                                        supports_bounded_range=False)
        self.assertEqual(plan.mode, RefreshMode.RANGE_ENDPOINT_REQUIRED)
        self.assertIsNone(plan.from_utc)

    def test_empty_history_requires_authorized_bootstrap(self):
        c = snapshot(bars=())
        plan = plan_incremental_refresh(c,policy(),T+20*M,
                                        supports_bounded_range=True)
        self.assertEqual(plan.mode, RefreshMode.BOOTSTRAP_NEEDED)
        self.assertFalse(plan.may_fetch_real_data)

    def test_claimed_remote_head_identical_can_skip_history_provisionally(self):
        c=snapshot()
        head=SourceHeadClaim(c.partition.fingerprint,"synthetic-head-1",
                             T+15*M,T+18*M)
        plan=plan_incremental_refresh(c,policy(),T+20*M,
                                      supports_bounded_range=True,head=head)
        self.assertEqual(plan.mode,RefreshMode.REUSE_HEAD_CLAIM)
        self.assertIsNone(plan.from_utc)
        self.assertFalse(plan.source_claim_authenticated)
        self.assertFalse(plan.may_fetch_real_data)

    def test_untrusted_changed_head_uses_overlap_delta(self):
        c=snapshot()
        head=SourceHeadClaim(c.partition.fingerprint,"new-head",T+15*M,T+18*M)
        plan=plan_incremental_refresh(c,policy(),T+20*M,
                                      supports_bounded_range=True,head=head)
        self.assertEqual(plan.mode,RefreshMode.DELTA_WINDOW)

    def test_old_remote_head_uses_delta(self):
        c=snapshot()
        head=SourceHeadClaim(c.partition.fingerprint,"synthetic-head-1",T+15*M,T+17*M)
        plan=plan_incremental_refresh(c,policy(),T+25*M,
                                      supports_bounded_range=True,head=head)
        self.assertEqual(plan.mode, RefreshMode.DELTA_WINDOW)

    def test_wrong_pair_source_head_rejected(self):
        c=snapshot()
        head=SourceHeadClaim("not-the-same-fingerprint","synthetic-head-1",
                             T+15*M,T+18*M)
        with self.assertRaisesRegex(ValueError,"WRONG_PARTITION"):
            plan_incremental_refresh(c,policy(),T+20*M,
                                     supports_bounded_range=True,head=head)

    def test_future_remote_head_rejected(self):
        c=snapshot()
        head=SourceHeadClaim(c.partition.fingerprint,"synthetic-head-1",
                             T+21*M,T+21*M)
        with self.assertRaisesRegex(ValueError,"FUTURE_OBSERVED"):
            plan_incremental_refresh(c,policy(),T+20*M,
                                     supports_bounded_range=True,head=head)

    def test_unchanged_overlap_is_zero_recompute(self):
        c=snapshot()
        result=reconcile_closed_delta(c,(bar(1),bar(2)),T+20*M,
                                      new_source_head_claim="head-2")
        self.assertEqual(result.change,ChangeKind.NO_CHANGE)
        self.assertEqual(result.appended,0)
        self.assertEqual(result.revised,0)
        self.assertIsNone(result.first_dirty_utc)
        self.assertEqual(result.snapshot.fingerprint,c.fingerprint)

    def test_append_only_preserves_old_history(self):
        c=snapshot()
        result=reconcile_closed_delta(c,(bar(3),),T+21*M,
                                      new_source_head_claim="head-3")
        self.assertEqual(result.change,ChangeKind.APPEND)
        self.assertEqual(result.first_dirty_utc,T+15*M)
        self.assertEqual(len(result.snapshot.closed_bars),4)
        self.assertEqual(len(c.closed_bars),3)
        self.assertEqual(result.snapshot.closed_bars[:3],c.closed_bars)

    def test_revision_recomputes_from_earliest_changed_bar(self):
        c=snapshot()
        revised=bar(1,revision=2,known_minute=19,close="1.16")
        result=reconcile_closed_delta(c,(revised,),T+21*M,
                                      new_source_head_claim="head-r2")
        self.assertEqual(result.change,ChangeKind.REVISE)
        self.assertEqual(result.first_dirty_utc,T+5*M)
        self.assertNotEqual(result.snapshot.fingerprint,c.fingerprint)
        self.assertEqual(c.closed_bars[1].close,Decimal("1.14"))

    def test_append_and_revision_one_batch(self):
        result=reconcile_closed_delta(snapshot(),
                  (bar(3),bar(1,revision=2,known_minute=19,close="1.16")),
                  T+21*M,new_source_head_claim="head-r2")
        self.assertEqual(result.change,ChangeKind.APPEND_AND_REVISE)
        self.assertEqual(result.first_dirty_utc,T+5*M)

    def test_same_revision_changed_ohlc_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"SAME_REVISION"):
            reconcile_closed_delta(snapshot(),(bar(1,close="1.17"),),
                                  T+21*M,new_source_head_claim="head")

    def test_stale_revision_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"OLDER_OR_SAME"):
            reconcile_closed_delta(snapshot(),(bar(1,revision=2,known_minute=10),),
                                  T+21*M,new_source_head_claim="head")

    def test_duplicate_delta_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_DELTA"):
            reconcile_closed_delta(snapshot(),(bar(1),bar(1)),
                                  T+21*M,new_source_head_claim="head")

    def test_absent_rows_never_delete_old_history(self):
        c=snapshot()
        result=reconcile_closed_delta(c,(),T+21*M,new_source_head_claim="head-2")
        self.assertEqual(result.snapshot.closed_bars,c.closed_bars)
        self.assertEqual(result.change,ChangeKind.NO_CHANGE)

    def test_incomplete_provisional_delta_rejected(self):
        with self.assertRaisesRegex(ValueError,"PROVISIONAL"):
            reconcile_closed_delta(snapshot(),(bar(3,lifecycle=BarLifecycle.OPEN),),
                                  T+21*M,new_source_head_claim="head")

    def test_another_pair_cannot_poison_current_cache(self):
        with self.assertRaisesRegex(ValueError,"PARTITION"):
            reconcile_closed_delta(snapshot(),(bar(3,instrument="GBPUSD-synth"),),
                                  T+21*M,new_source_head_claim="head")

    def test_cannot_silently_evict_history_on_capacity(self):
        with self.assertRaisesRegex(ValueError,"CAPACITY"):
            reconcile_closed_delta(snapshot(),(bar(3),),T+21*M,
                                  new_source_head_claim="head",max_total_bars=3)

    def test_results_still_not_approved_for_persistent_market_data(self):
        result=reconcile_closed_delta(snapshot(),(bar(3),),T+21*M,
                                      new_source_head_claim="head")
        self.assertFalse(result.may_persist_real_data)
        self.assertFalse(result.source_verified_externally)
