import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, MarketBar, MarketBarKey,
    Observation, SourceQuality, Timeframe, evaluate_closed_bar, select_asof_revision,
)


T = datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc)


def observation(**changes):
    base = dict(provider_id="synthetic", stream_id="sample-stream", endpoint="fixture-only",
                revision_id="rev-1", raw_sha256="a"*64,
                first_known_utc=T + timedelta(minutes=15),
                retrieved_at_utc=T + timedelta(minutes=16),
                source_timezone_policy="UTC-v1", license_scope_claim="UNVERIFIED_TEST_FIXTURE")
    base.update(changes)
    return Observation(**base)


def bar(tf=Timeframe.M15, side=BarSide.BID, **changes):
    dur = {Timeframe.M5:5, Timeframe.M15:15, Timeframe.M1:1, Timeframe.M30:30}.get(tf, 15)
    key = MarketBarKey("EURUSD-synthetic", tf, T, T + timedelta(minutes=dur),
                       "UTC-calendar-test", "raw-provider-v1", side)
    values = dict(key=key, observation=observation(),
                  revision_number=1, first_known_utc=T + timedelta(minutes=16),
                  open=Decimal("1.1"), high=Decimal("1.2"),
                  low=Decimal("1.0"), close=Decimal("1.15"),
                  lifecycle=BarLifecycle.CLOSED, coverage=BarCoverage.COMPLETE,
                  quality=SourceQuality.VERIFIED)
    values.update(changes)
    return MarketBar(**values)


class MarketDataContractTests(unittest.TestCase):
    def test_closed_verified_m15_causal_only_not_tradable(self):
        gate = evaluate_closed_bar(bar(), T + timedelta(minutes=16))
        self.assertTrue(gate.usable_for_technical_features)
        self.assertTrue(gate.eligible_for_early_phase_input)
        self.assertFalse(gate.confirmed_phase_authorized)
        self.assertFalse(gate.permission_to_trade)

    def test_mid_only_technical_nonexecutable(self):
        gate = evaluate_closed_bar(bar(side=BarSide.MID), T + timedelta(minutes=20))
        self.assertTrue(gate.usable_for_technical_features)
        self.assertFalse(gate.executable_quote_basis)
        self.assertFalse(gate.permission_to_trade)

    def test_bid_quote_basis_not_license(self):
        gate = evaluate_closed_bar(bar(side=BarSide.ASK), T + timedelta(minutes=20))
        self.assertTrue(gate.executable_quote_basis)
        self.assertFalse(gate.permission_to_trade)

    def test_future_first_known_blocked(self):
        gate = evaluate_closed_bar(bar(), T + timedelta(minutes=15))
        self.assertEqual(gate.reason, "FUTURE_REVISION_NOT_KNOWN")

    def test_open_candle_cannot_pass(self):
        gate = evaluate_closed_bar(bar(lifecycle=BarLifecycle.OPEN), T + timedelta(minutes=20))
        self.assertEqual(gate.reason, "OPEN_PROVISIONAL_BAR")

    def test_partial_or_unknown_coverage_blocked(self):
        for c in (BarCoverage.PARTIAL, BarCoverage.SPARSE_UNVERIFIED,
                  BarCoverage.UNKNOWN, BarCoverage.INVALID):
            with self.subTest(c=c):
                self.assertEqual(evaluate_closed_bar(bar(coverage=c),
                                 T + timedelta(minutes=20)).reason, "INCOMPLETE_COVERAGE")

    def test_unverified_warn_blocked_quality(self):
        for q in (SourceQuality.WARN, SourceQuality.UNVERIFIED, SourceQuality.BLOCKED):
            with self.subTest(q=q):
                self.assertEqual(evaluate_closed_bar(bar(quality=q),
                                 T + timedelta(minutes=20)).reason, "SOURCE_QUALITY_UNVERIFIED")

    def test_missing_bar_does_not_mean_zero_market_volume(self):
        self.assertEqual(evaluate_closed_bar(None, T).reason, "MISSING_BAR_NOT_ZERO_VOLUME")

    def test_m5_arm_default_blocked(self):
        self.assertEqual(evaluate_closed_bar(bar(Timeframe.M5), T+timedelta(minutes=17)).reason,
                         "M5_CONDITIONAL_ARM_DISABLED")

    def test_m5_requires_preexisting_htf_context(self):
        result = evaluate_closed_bar(bar(Timeframe.M5), T+timedelta(minutes=20),
                                     conditional_m5_early_enabled=True)
        self.assertEqual(result.reason, "M5_REQUIRES_PRIOR_HTF_CONTEXT")

    def test_m5_prior_htf_context_allows_early_input_not_confirmation(self):
        result = evaluate_closed_bar(bar(Timeframe.M5), T+timedelta(minutes=20),
                                     conditional_m5_early_enabled=True,
                                     htf_context_first_known_utc=T+timedelta(minutes=4))
        self.assertTrue(result.eligible_for_early_phase_input)
        self.assertFalse(result.confirmed_phase_authorized)

    def test_m5_future_htf_context_rejected(self):
        result = evaluate_closed_bar(bar(Timeframe.M5), T+timedelta(minutes=20),
                                     conditional_m5_early_enabled=True,
                                     htf_context_first_known_utc=T+timedelta(minutes=17))
        self.assertEqual(result.reason, "M5_HTF_CONTEXT_FUTURE_KNOWN")

    def test_m15_cannot_use_m5_flag(self):
        result = evaluate_closed_bar(bar(), T+timedelta(minutes=20),
                                     conditional_m5_early_enabled=True)
        self.assertEqual(result.reason, "M5_ARM_USED_WITH_WRONG_TIMEFRAME")

    def test_known_revision_selected_without_future_correction(self):
        first = bar()
        second = bar(revision_number=2, first_known_utc=T+timedelta(minutes=22),
                     observation=observation(revision_id="rev-2",
                         first_known_utc=T+timedelta(minutes=21),
                         retrieved_at_utc=T+timedelta(minutes=22)))
        self.assertEqual(select_asof_revision((first,second), T+timedelta(minutes=20)), first)
        self.assertEqual(select_asof_revision((first,second), T+timedelta(minutes=30)), second)

    def test_only_future_revision_yields_none(self):
        self.assertIsNone(select_asof_revision((bar(),), T))

    def test_duplicate_revision_number_rejected_when_known(self):
        first = bar()
        second = bar(first_known_utc=T+timedelta(minutes=18))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            select_asof_revision((first,second), T+timedelta(minutes=25))

    def test_out_of_order_revision_rejected_when_known(self):
        newer = bar(revision_number=2)
        older = bar(revision_number=1, first_known_utc=T+timedelta(minutes=17))
        with self.assertRaisesRegex(ValueError, "causal order"):
            select_asof_revision((older,newer), T+timedelta(minutes=25))

    def test_mixed_side_never_merged_as_same_bar(self):
        with self.assertRaisesRegex(ValueError, "mixed identity"):
            select_asof_revision((bar(),bar(side=BarSide.ASK,revision_number=2,
                                      first_known_utc=T+timedelta(minutes=20))),
                                  T+timedelta(minutes=25))

    def test_bad_digest_rejected(self):
        with self.assertRaises(ValueError):
            observation(raw_sha256="UNVERIFIED")

    def test_bad_clock_rejected(self):
        with self.assertRaises(ValueError):
            observation(first_known_utc=datetime(2026,11,7))

    def test_retrieval_before_first_known_rejected(self):
        with self.assertRaises(ValueError):
            observation(retrieved_at_utc=T)

    def test_closed_bar_before_cutoff_rejected(self):
        with self.assertRaises(ValueError):
            bar(first_known_utc=T+timedelta(minutes=14),
                observation=observation(first_known_utc=T+timedelta(minutes=13),
                                        retrieved_at_utc=T+timedelta(minutes=14)))

    def test_bad_ohlc_rejected(self):
        with self.assertRaises(ValueError):
            bar(high=Decimal("1.0"))
        with self.assertRaises(ValueError):
            bar(open=Decimal("NaN"))

    def test_short_intraday_bar_rejected(self):
        with self.assertRaises(ValueError):
            MarketBarKey("EURUSD", Timeframe.M15, T, T+timedelta(minutes=5),
                         "test-calendar","version-1",BarSide.BID)

    def test_revision_boolean_not_a_valid_sequence(self):
        with self.assertRaises(ValueError):
            bar(revision_number=True)

    def test_first_known_before_provenance_rejected(self):
        with self.assertRaises(ValueError):
            bar(first_known_utc=T+timedelta(minutes=14))

    def test_open_bar_never_confirmed_even_if_verification_flag_true(self):
        g = evaluate_closed_bar(bar(lifecycle=BarLifecycle.OPEN,
                                    quality=SourceQuality.VERIFIED),
                                T+timedelta(minutes=30))
        self.assertFalse(g.confirmed_phase_authorized)
        self.assertFalse(g.permission_to_trade)
