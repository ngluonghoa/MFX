"""Actual research BUY/SELL detection and fail-closed offline negative paths."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta, timezone
import unittest

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, SourceQuality, Timeframe,
)
from forex_trading.model import SignalStage
from mfx_research.offline_ema_signals import (
    CandidateAction, research_only_ema_signal,
)
from tools.run_a04_p16_signal_demo import (
    BUY_CLOSES, FLAT_CLOSES, SELL_CLOSES, synthetic_m15_bars,
)


class OfflineEmaResearchSignalTests(unittest.TestCase):
    def evaluate(self, closes=BUY_CLOSES, **changes):
        bars = synthetic_m15_bars(closes)
        return research_only_ema_signal(
            bars, bars[-1].first_known_utc + timedelta(seconds=1), **changes,
        )

    def test_actual_buy_cross_from_closed_m15_ema(self):
        value = self.evaluate()
        self.assertIs(value.action, CandidateAction.BUY)
        self.assertEqual(value.direction, "LONG")
        self.assertIs(value.stage, SignalStage.UNVERIFIED)

    def test_actual_sell_cross_from_closed_m15_ema(self):
        value = self.evaluate(SELL_CLOSES)
        self.assertIs(value.action, CandidateAction.SELL)
        self.assertEqual(value.direction, "SHORT")

    def test_flat_has_no_buy_or_sell(self):
        value = self.evaluate(FLAT_CLOSES)
        self.assertIs(value.action, CandidateAction.NO_SIGNAL)
        self.assertEqual(value.direction, "NONE")

    def test_all_actions_are_unverified_and_no_trade(self):
        for sample in (BUY_CLOSES, SELL_CLOSES, FLAT_CLOSES):
            row = self.evaluate(sample).as_record()
            with self.subTest(sample=sample):
                self.assertEqual(row["stage"], "UNVERIFIED")
                self.assertFalse(row["source_verified"])
                self.assertFalse(row["economic_parity_proven"])
                self.assertFalse(row["can_trade"])
                self.assertEqual(row["provider_requests"], 0)
                self.assertEqual(row["drive_market_cache_writes"], 0)
                self.assertEqual(row["strategy"],
                                 "EXPERIMENTAL_EMA_CROSS_NOT_FOREX_1_TO_1")

    def test_future_first_known_blocks_candidate(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        invalid = replace(bars[-1], first_known_utc=bars[-1].first_known_utc +
                          timedelta(seconds=30))
        with self.assertRaisesRegex(ValueError, "CLOSED_BAR_GATE"):
            research_only_ema_signal(
                bars[:-1] + (invalid,), bars[-1].first_known_utc +
                timedelta(seconds=1),
            )

    def test_future_retrieval_blocks_candidate(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        obs = replace(bars[-1].observation, retrieved_at_utc=
                      bars[-1].first_known_utc + timedelta(minutes=5))
        with self.assertRaisesRegex(ValueError, "FUTURE_BAR_OR_RETRIEVAL"):
            research_only_ema_signal(
                bars[:-1] + (replace(bars[-1], observation=obs),),
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_unclosed_bar_denied(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        invalid = replace(bars[-1], lifecycle=BarLifecycle.OPEN)
        with self.assertRaisesRegex(ValueError, "OPEN_PROVISIONAL_BAR"):
            research_only_ema_signal(
                bars[:-1] + (invalid,), bars[-1].first_known_utc +
                timedelta(seconds=1),
            )

    def test_partial_coverage_denied(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        invalid = replace(bars[-1], coverage=BarCoverage.PARTIAL)
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_COVERAGE"):
            research_only_ema_signal(
                bars[:-1] + (invalid,), bars[-1].first_known_utc +
                timedelta(seconds=1),
            )

    def test_unverified_source_quality_denied(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        invalid = replace(bars[-1], quality=SourceQuality.UNVERIFIED)
        with self.assertRaisesRegex(ValueError, "SOURCE_QUALITY_UNVERIFIED"):
            research_only_ema_signal(
                bars[:-1] + (invalid,), bars[-1].first_known_utc +
                timedelta(seconds=1),
            )

    def test_missing_or_reordered_bars_denied(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        decision = bars[-1].first_known_utc + timedelta(seconds=1)
        for bad in (bars[:2] + bars[3:], tuple(reversed(bars)),
                    bars[:3] + bars[2:]):
            with self.subTest(length=len(bad)):
                with self.assertRaises(ValueError):
                    research_only_ema_signal(bad, decision)

    def test_mixed_instruments_denied(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        other = synthetic_m15_bars(BUY_CLOSES, instrument="SIM:OTHER")[3]
        with self.assertRaisesRegex(ValueError, "MIXED_INSTRUMENT"):
            research_only_ema_signal(
                bars[:3] + (other,) + bars[4:],
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_mixed_provider_denied(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        obs = replace(bars[-1].observation, provider_id="SIM:ANOTHER")
        with self.assertRaisesRegex(ValueError, "MIXED_INSTRUMENT"):
            research_only_ema_signal(
                bars[:-1] + (replace(bars[-1], observation=obs),),
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_not_licensed_real_provider_input(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        obs = replace(bars[0].observation, provider_id="TWELVE_DATA")
        with self.assertRaisesRegex(ValueError, "NO_LIVE_PROVIDER"):
            research_only_ema_signal(
                (replace(bars[0], observation=obs),) + bars[1:],
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_refuses_fake_live_entitlement(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        obs = replace(bars[-1].observation, license_scope_claim="LIVE_APPROVED")
        with self.assertRaisesRegex(ValueError, "NOT_SYNTHETIC"):
            research_only_ema_signal(
                bars[:-1] + (replace(bars[-1], observation=obs),),
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_mid_is_technical_reference_not_bidask_execution(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        bid = replace(bars[0].key, side=BarSide.BID)
        with self.assertRaisesRegex(ValueError, "MID_TECHNICAL_REFERENCE"):
            research_only_ema_signal(
                (replace(bars[0], key=bid),) + bars[1:],
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_m15_only_not_guessed_htf_calendar(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        m30key = replace(bars[0].key, timeframe=Timeframe.M30,
                         bar_start_utc=bars[0].key.bar_end_utc -
                         timedelta(minutes=30))
        with self.assertRaisesRegex(ValueError, "CLOSED_M15"):
            research_only_ema_signal(
                (replace(bars[0], key=m30key),) + bars[1:],
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_revisions_not_silently_reused(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        revised = replace(bars[-1], revision_number=2)
        with self.assertRaisesRegex(ValueError, "FIRST_REVISION"):
            research_only_ema_signal(
                bars[:-1] + (revised,),
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_bad_periods_denied(self):
        for fast, slow in ((1, 3), (3, 3), (4, 3), (True, 3), (2, 201)):
            with self.subTest(fast=fast, slow=slow):
                with self.assertRaisesRegex(ValueError, "EMA_PERIOD"):
                    self.evaluate(fast_period=fast, slow_period=slow)

    def test_unbounded_or_insufficient_data_denied(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT"):
            research_only_ema_signal(bars[:4], bars[-1].first_known_utc)
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT"):
            research_only_ema_signal((), bars[-1].first_known_utc)

    def test_naive_datetime_denied(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        with self.assertRaises(ValueError):
            research_only_ema_signal(
                bars, bars[-1].first_known_utc.replace(tzinfo=None),
            )

    def test_asof_is_utc_and_stamped(self):
        bars = synthetic_m15_bars(BUY_CLOSES)
        at = bars[-1].first_known_utc.astimezone(timezone.utc) + timedelta(seconds=1)
        value = research_only_ema_signal(bars, at)
        self.assertEqual(value.latest_bar_end_utc, bars[-1].key.bar_end_utc)
        self.assertEqual(value.first_known_utc, bars[-1].first_known_utc)
        self.assertEqual(value.decision_utc, at)
