import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, MarketBar, MarketBarKey,
    Observation, SourceQuality, Timeframe,
)
from forex_trading.side_pair import BidAskSourceManifest, assess_bid_ask_side_pair


UTC = timezone.utc
T = datetime(2026, 11, 7, tzinfo=UTC)
ASOF = T + timedelta(minutes=20)


def bar(side: BarSide, **changes):
    key = MarketBarKey("EURUSD-synthetic", Timeframe.M15, T, T + timedelta(minutes=15),
                       "syn-cal-v1", "syn-agg-v1", side)
    obs = Observation("synthetic-provider", side.value.lower() + "-stream",
                      "synthetic-fixture", "bid-r1" if side is BarSide.BID else "ask-r1",
                      "1" * 64, T + timedelta(minutes=15), T + timedelta(minutes=16),
                      "synthetic-timezone", "NO_EXTERNAL_RIGHTS")
    payload = dict(key=key, observation=obs, revision_number=1,
                   first_known_utc=T + timedelta(minutes=16),
                   open=Decimal("1.10"), high=Decimal("1.20"),
                   low=Decimal("1.00"), close=Decimal("1.15"),
                   lifecycle=BarLifecycle.CLOSED, coverage=BarCoverage.COMPLETE,
                   quality=SourceQuality.VERIFIED)
    payload.update(changes)
    return MarketBar(**payload)


def manifest(**changes):
    payload = dict(
        provider_id="synthetic-provider", dataset_version="snapshot-v1",
        instrument_version="EURUSD-synthetic", calendar_version="syn-cal-v1",
        aggregation_version="syn-agg-v1", source_timezone_policy="synthetic-timezone",
        bid_stream_id="bid-stream", ask_stream_id="ask-stream",
        bid_revision_id="bid-r1", ask_revision_id="ask-r1",
        dataset_digest_claim="a"*64, first_known_utc=T + timedelta(minutes=17),
    )
    payload.update(changes)
    return BidAskSourceManifest(**payload)


class SidePairTests(unittest.TestCase):
    def test_correct_pair_is_only_internal_metadata_pass(self):
        g = assess_bid_ask_side_pair(bar(BarSide.BID), bar(BarSide.ASK), manifest(), ASOF)
        self.assertTrue(g.coherent_internal_metadata)
        self.assertFalse(g.trade_permission)

    def test_missing_side_fails_closed(self):
        self.assertEqual(assess_bid_ask_side_pair(bar(BarSide.BID), None, manifest(), ASOF).reason,
                         "REQUIRES_BOTH_BID_ASK_AND_MANIFEST")

    def test_mid_never_substitutes_ask(self):
        got = assess_bid_ask_side_pair(bar(BarSide.BID), bar(BarSide.MID), manifest(), ASOF)
        self.assertEqual(got.reason, "BID_ASK_SIDE_MISMATCH")

    def test_reversed_side_never_accepted(self):
        g = assess_bid_ask_side_pair(bar(BarSide.ASK), bar(BarSide.BID), manifest(), ASOF)
        self.assertEqual(g.reason, "BID_ASK_SIDE_MISMATCH")

    def test_future_manifest_rejected(self):
        g = assess_bid_ask_side_pair(bar(BarSide.BID), bar(BarSide.ASK),
                                     manifest(first_known_utc=ASOF+timedelta(seconds=1)), ASOF)
        self.assertEqual(g.reason, "SOURCE_REVISION_FUTURE_AS_OF")

    def test_future_ask_revision_rejected(self):
        ask = bar(BarSide.ASK, first_known_utc=ASOF+timedelta(seconds=1),
                  observation=replace(bar(BarSide.ASK).observation,
                                      first_known_utc=ASOF, retrieved_at_utc=ASOF))
        g = assess_bid_ask_side_pair(bar(BarSide.BID), ask, manifest(), ASOF)
        self.assertEqual(g.reason, "SOURCE_REVISION_FUTURE_AS_OF")

    def test_provider_disagreement_never_merge(self):
        bid = bar(BarSide.BID)
        ask = bar(BarSide.ASK, observation=replace(bar(BarSide.ASK).observation,
                                                   provider_id="other-provider"))
        g = assess_bid_ask_side_pair(bid, ask, manifest(), ASOF)
        self.assertEqual(g.reason, "PROVIDER_STREAM_REVISION_OR_ZONE_POLICY_MISMATCH")

    def test_ask_revision_mismatch_rejected(self):
        m = manifest(ask_revision_id="ask-other")
        g = assess_bid_ask_side_pair(bar(BarSide.BID), bar(BarSide.ASK), m, ASOF)
        self.assertEqual(g.reason, "PROVIDER_STREAM_REVISION_OR_ZONE_POLICY_MISMATCH")

    def test_source_timezone_policy_mismatch_rejected(self):
        m = manifest(source_timezone_policy="other-zone-policy")
        self.assertFalse(assess_bid_ask_side_pair(
            bar(BarSide.BID), bar(BarSide.ASK), m, ASOF).coherent_internal_metadata)

    def test_mismatched_bar_interval_rejected(self):
        source = bar(BarSide.ASK)
        ask = replace(source, key=replace(source.key, bar_start_utc=T + timedelta(minutes=15),
                                          bar_end_utc=T + timedelta(minutes=30)),
                      first_known_utc=T+timedelta(minutes=31),
                      observation=replace(source.observation,
                                          first_known_utc=T+timedelta(minutes=30),
                                          retrieved_at_utc=T+timedelta(minutes=31)))
        g = assess_bid_ask_side_pair(bar(BarSide.BID), ask, manifest(), T+timedelta(minutes=35))
        self.assertEqual(g.reason, "BAR_IDENTITY_OR_INTERVAL_MISMATCH")

    def test_aggregation_mismatch_rejected(self):
        old = bar(BarSide.ASK)
        ask = replace(old, key=replace(old.key, aggregation_version="other-aggregator"))
        g = assess_bid_ask_side_pair(bar(BarSide.BID), ask, manifest(), ASOF)
        self.assertEqual(g.reason, "BAR_IDENTITY_OR_INTERVAL_MISMATCH")

    def test_manifest_instrument_mismatch_rejected(self):
        g = assess_bid_ask_side_pair(bar(BarSide.BID), bar(BarSide.ASK),
                                     manifest(instrument_version="EURUSD-real"), ASOF)
        self.assertEqual(g.reason, "MANIFEST_DATASET_IDENTITY_MISMATCH")

    def test_open_bar_rejected(self):
        bid = bar(BarSide.BID, lifecycle=BarLifecycle.OPEN)
        g = assess_bid_ask_side_pair(bid, bar(BarSide.ASK), manifest(), ASOF)
        self.assertEqual(g.reason, "BID_OPEN_PROVISIONAL_BAR")

    def test_incomplete_ask_coverage_rejected(self):
        ask = bar(BarSide.ASK, coverage=BarCoverage.PARTIAL)
        g = assess_bid_ask_side_pair(bar(BarSide.BID), ask, manifest(), ASOF)
        self.assertEqual(g.reason, "ASK_INCOMPLETE_COVERAGE")

    def test_unverified_quality_rejected(self):
        bid = bar(BarSide.BID, quality=SourceQuality.UNVERIFIED)
        g = assess_bid_ask_side_pair(bid, bar(BarSide.ASK), manifest(), ASOF)
        self.assertEqual(g.reason, "BID_SOURCE_QUALITY_UNVERIFIED")

    def test_bad_digest_claim_shape_rejected(self):
        with self.assertRaisesRegex(ValueError, "DIGEST"):
            manifest(dataset_digest_claim="NOT_A_DIGEST")

    def test_bad_source_clock_rejected(self):
        with self.assertRaises(ValueError):
            manifest(first_known_utc=datetime(2026, 11, 7))

    def test_mid_data_still_not_usable_even_with_manifest_revision(self):
        with self.assertRaisesRegex(ValueError, "DIGEST"):
            manifest(dataset_digest_claim="")
