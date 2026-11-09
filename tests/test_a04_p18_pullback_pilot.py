"""P0.18 B2/S2 actual numeric synthetic research, plus negative causality."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import unittest

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, SourceQuality, Timeframe,
)
from forex_trading.model import SignalStage
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.pullback_pilot import (
    ClaimedStructuralContext, StructuralTrend, UnapprovedResearchParameters,
    evaluate_unapproved_b2_s2,
)
from tools.run_a04_p18_pullback_demo import case


def evaluate(rule: str = "B2"):
    bars, ctx, params = case(rule)
    return evaluate_unapproved_b2_s2(
        bars, ctx, params, bars[-1].first_known_utc + timedelta(seconds=1),
    )


class UnapprovedPullbackResearchTests(unittest.TestCase):
    def test_actual_b2_buy_research_numeric_predicate(self) -> None:
        result = evaluate("B2")
        self.assertIs(result.action, CandidateAction.BUY)
        self.assertEqual(result.rule_id, "B2")
        self.assertIs(result.stage, SignalStage.UNVERIFIED)

    def test_actual_s2_sell_research_numeric_predicate(self) -> None:
        result = evaluate("S2")
        self.assertIs(result.action, CandidateAction.SELL)
        self.assertEqual(result.rule_id, "S2")
        self.assertIs(result.stage, SignalStage.UNVERIFIED)

    def test_no_source_parity_no_confirmed_signal_no_trade(self) -> None:
        for rule in ("B2", "S2"):
            with self.subTest(rule=rule):
                row = evaluate(rule).as_record()
                self.assertFalse(row["original_forex_numerical_parity"])
                self.assertFalse(row["source_verified_for_market"])
                self.assertFalse(row["may_send_confirmed_signal"])
                self.assertFalse(row["can_trade"])
                self.assertEqual(row["provider_requests"], 0)
                self.assertEqual(row["drive_market_cache_writes"], 0)
                self.assertTrue(str(row["parameter_version"]).startswith("SIM:"))

    def test_countertrend_blocks_both_sides(self) -> None:
        for rule in ("B2", "S2"):
            bars, ctx, p = case(rule)
            mismatch = replace(
                ctx, h4_trend=StructuralTrend.DOWN if rule == "B2" else StructuralTrend.UP,
            )
            got = evaluate_unapproved_b2_s2(
                bars, mismatch, p, bars[-1].first_known_utc + timedelta(seconds=1),
            )
            self.assertIs(got.action, CandidateAction.NO_SIGNAL)
            self.assertEqual(got.reason, "P018_TREND_NOT_SUPPORTED")

    def test_unknown_context_is_not_implicitly_up_or_down(self) -> None:
        bars, ctx, p = case("B2")
        r = evaluate_unapproved_b2_s2(
            bars, replace(ctx, d1_trend=StructuralTrend.UNKNOWN), p,
            bars[-1].first_known_utc + timedelta(seconds=1),
        )
        self.assertIs(r.action, CandidateAction.NO_SIGNAL)

    def test_prior_structure_invalidation_blocks(self) -> None:
        bars, ctx, p = case("S2")
        r = evaluate_unapproved_b2_s2(
            bars, replace(ctx, structure_invalidated=True), p,
            bars[-1].first_known_utc + timedelta(seconds=1),
        )
        self.assertEqual(r.reason, "P018_STRUCTURE_INVALIDATED")

    def test_b2_no_latest_micro_high_break(self) -> None:
        bars, ctx, p = case("B2")
        last = replace(
            bars[-1], open=Decimal("1.1010"), high=Decimal("1.1014"),
            close=Decimal("1.1014"),
        )
        r = evaluate_unapproved_b2_s2(
            (bars[0], last), ctx, p,
            bars[-1].first_known_utc + timedelta(seconds=1),
        )
        self.assertEqual(r.reason, "P018_NO_LATEST_MICRO_BREAK")

    def test_s2_no_latest_micro_low_break(self) -> None:
        bars, ctx, p = case("S2")
        last = replace(
            bars[-1], open=Decimal("1.1999"), low=Decimal("1.1997"),
            close=Decimal("1.1998"),
        )
        r = evaluate_unapproved_b2_s2(
            (bars[0], last), ctx, p,
            bars[-1].first_known_utc + timedelta(seconds=1),
        )
        self.assertEqual(r.reason, "P018_NO_LATEST_MICRO_BREAK")

    def test_b2_far_from_support_denied(self) -> None:
        bars, ctx, p = case("B2")
        r = evaluate_unapproved_b2_s2(
            bars, replace(ctx, h1_zone_low=Decimal("1.0900"),
                          h1_zone_high=Decimal("1.0910")), p,
            bars[-1].first_known_utc + timedelta(seconds=1),
        )
        self.assertEqual(r.reason, "P018_PRIOR_M15_NOT_NEAR_H1_ZONE")

    def test_s2_far_from_resistance_denied(self) -> None:
        bars, ctx, p = case("S2")
        r = evaluate_unapproved_b2_s2(
            bars, replace(ctx, h1_zone_low=Decimal("1.2200"),
                          h1_zone_high=Decimal("1.2210")), p,
            bars[-1].first_known_utc + timedelta(seconds=1),
        )
        self.assertEqual(r.reason, "P018_PRIOR_M15_NOT_NEAR_H1_ZONE")

    def test_research_anti_chase_denies_overshoot(self) -> None:
        for rule in ("B2", "S2"):
            bars, ctx, p = case(rule)
            tiny = replace(p, max_chase_atr_multiple=Decimal("0.01"))
            result = evaluate_unapproved_b2_s2(
                bars, ctx, tiny,
                bars[-1].first_known_utc + timedelta(seconds=1),
            )
            self.assertEqual(result.reason, "P018_SYNTHETIC_ANTI_CHASE_LIMIT")

    def test_context_known_after_window_start_denied(self) -> None:
        bars, ctx, p = case("B2")
        with self.assertRaisesRegex(ValueError, "CONTEXT_WAS_NOT_KNOWN"):
            evaluate_unapproved_b2_s2(
                bars, replace(ctx, context_first_known_utc=
                              bars[0].key.bar_start_utc + timedelta(seconds=1)),
                p, bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_future_market_revision_first_known_denied(self) -> None:
        bars, ctx, p = case("B2")
        future = replace(bars[-1], first_known_utc=
                         bars[-1].first_known_utc + timedelta(minutes=1))
        with self.assertRaisesRegex(ValueError, "CLOSED_BAR_SOURCE_GATE"):
            evaluate_unapproved_b2_s2(
                (bars[0], future), ctx, p,
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_future_retrieval_denied(self) -> None:
        bars, ctx, p = case("B2")
        o = replace(bars[-1].observation, retrieved_at_utc=
                    bars[-1].first_known_utc + timedelta(minutes=1))
        with self.assertRaisesRegex(ValueError, "FUTURE_BAR_OR_RETRIEVAL"):
            evaluate_unapproved_b2_s2(
                (bars[0], replace(bars[-1], observation=o)),
                ctx, p, bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_open_bar_denied(self) -> None:
        bars, ctx, p = case("B2")
        with self.assertRaisesRegex(ValueError, "OPEN_PROVISIONAL_BAR"):
            evaluate_unapproved_b2_s2(
                (bars[0], replace(bars[-1], lifecycle=BarLifecycle.OPEN)),
                ctx, p, bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_partial_coverage_denied(self) -> None:
        bars, ctx, p = case("B2")
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_COVERAGE"):
            evaluate_unapproved_b2_s2(
                (bars[0], replace(bars[-1], coverage=BarCoverage.PARTIAL)),
                ctx, p, bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_unverified_source_denied(self) -> None:
        bars, ctx, p = case("B2")
        with self.assertRaisesRegex(ValueError, "SOURCE_QUALITY_UNVERIFIED"):
            evaluate_unapproved_b2_s2(
                (bars[0], replace(bars[-1], quality=SourceQuality.UNVERIFIED)),
                ctx, p, bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_wrong_price_side_denied(self) -> None:
        bars, ctx, p = case("B2")
        wrong = replace(bars[0], key=replace(bars[0].key, side=BarSide.BID))
        with self.assertRaisesRegex(ValueError, "M15_MID_TECHNICAL_ONLY"):
            evaluate_unapproved_b2_s2(
                (wrong, bars[1]), ctx, p,
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_wrong_timeframe_denied(self) -> None:
        bars, ctx, p = case("B2")
        key=replace(
            bars[0].key, timeframe=Timeframe.M30,
            bar_start_utc=bars[0].key.bar_end_utc - timedelta(minutes=30),
        )
        with self.assertRaisesRegex(ValueError, "M15_MID_TECHNICAL_ONLY"):
            evaluate_unapproved_b2_s2(
                (replace(bars[0], key=key), bars[1]), ctx, p,
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_gapped_or_reordered_denied(self) -> None:
        bars, ctx, p = case("B2")
        with self.assertRaisesRegex(ValueError, "NONCONTIGUOUS"):
            evaluate_unapproved_b2_s2(
                (bars[-1], bars[0]), ctx, p,
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_cross_instrument_stream_denied(self) -> None:
        bars, ctx, p = case("B2")
        bad = replace(
            bars[1], key=replace(bars[1].key, instrument_version="SIM:OTHER"),
        )
        with self.assertRaisesRegex(ValueError, "MIXED_INSTRUMENT"):
            evaluate_unapproved_b2_s2(
                (bars[0], bad), ctx, p,
                bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_revised_market_bar_denied(self) -> None:
        bars, ctx, p = case("B2")
        with self.assertRaisesRegex(ValueError, "REJECT_REAL_SOURCE_OR_REVISED"):
            evaluate_unapproved_b2_s2(
                (bars[0], replace(bars[1], revision_number=2)),
                ctx, p, bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_real_provider_denied(self) -> None:
        bars, ctx, p = case("B2")
        provider = replace(bars[1].observation, provider_id="OANDA")
        with self.assertRaisesRegex(ValueError, "REJECT_REAL_SOURCE_OR_REVISED"):
            evaluate_unapproved_b2_s2(
                (bars[0], replace(bars[1], observation=provider)),
                ctx, p, bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_fake_license_denied(self) -> None:
        bars, ctx, p = case("B2")
        obs = replace(bars[1].observation, license_scope_claim="APPROVED")
        with self.assertRaisesRegex(ValueError, "REJECT_REAL_SOURCE_OR_REVISED"):
            evaluate_unapproved_b2_s2(
                (bars[0], replace(bars[1], observation=obs)),
                ctx, p, bars[-1].first_known_utc + timedelta(seconds=1),
            )

    def test_unknown_rule_denied(self) -> None:
        bars, ctx, _ = case("B2")
        with self.assertRaisesRegex(ValueError, "ONLY_B2_S2"):
            replace(ctx, rule_id="B5")

    def test_negative_nan_and_float_parameters_denied(self) -> None:
        _, _, p = case("B2")
        for invalid in (Decimal("-1"), Decimal("NaN"), Decimal("0"),
                        Decimal("21"), 1.5):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "INVALID_"):
                    replace(p, near_zone_atr_multiple=invalid)

    def test_unapproved_version_must_be_sim(self) -> None:
        _, _, p = case("B2")
        with self.assertRaisesRegex(ValueError, "ONLY_SYNTHETIC"):
            replace(p, version="APPROVED-V1")

    def test_invalid_context_trend_and_zone_denied(self) -> None:
        _, ctx, _ = case("B2")
        with self.assertRaises(TypeError):
            replace(ctx, d1_trend="UP")
        with self.assertRaisesRegex(ValueError, "INVERTED_KNOWN_H1_ZONE"):
            replace(ctx, h1_zone_low=Decimal("2.0"))
        with self.assertRaisesRegex(ValueError, "INVALID_"):
            replace(ctx, known_atr=Decimal("NaN"))

    def test_naive_decision_clock_denied(self) -> None:
        bars, ctx, p = case("B2")
        with self.assertRaises(ValueError):
            evaluate_unapproved_b2_s2(
                bars, ctx, p,
                bars[-1].first_known_utc.replace(tzinfo=None),
            )

    def test_no_implicit_default_parameters(self) -> None:
        _, ctx, _ = case("B2")
        bars, _, _ = case("B2")
        with self.assertRaises(TypeError):
            evaluate_unapproved_b2_s2(
                bars, ctx, None, bars[-1].first_known_utc,  # type: ignore[arg-type]
            )
