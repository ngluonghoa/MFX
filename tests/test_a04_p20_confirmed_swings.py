"""P0.20: no pivot may be confirmed without known, closed right bars."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import unittest

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, SourceQuality, Timeframe,
)
from mfx_research.confirmed_swings import (
    PivotKind, SyntheticPivotParameters, detect_confirmed_swings,
    derive_swing_b2_s2_research, trend_from_confirmed_swings,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.pullback_pilot import StructuralTrend
from tools.run_a04_p20_confirmed_swing_demo import (
    case_confirmed, evaluate_case,
)
from tools.run_a04_p19_causal_context_demo import case_from_closed_bars


def eval_changed(rule: str, **changed):
    data, policy = case_confirmed(rule)
    _, zone_policy, trigger_policy = case_from_closed_bars(rule)
    for key, value in changed.items():
        if key == "policy":
            policy = value
        elif key == "zone_policy":
            zone_policy = value
        else:
            data = replace(data, **{key: value})
    return derive_swing_b2_s2_research(
        rule, data, policy, zone_policy, trigger_policy,
        data.trigger_m15[-1].first_known_utc + timedelta(seconds=1),
        origin_event_id="SIM:P020-"+rule,
    )


class ConfirmedRightBarSwingTests(unittest.TestCase):
    def test_b2_buy_only_after_actual_htf_confirmed_pivots(self):
        got = evaluate_case("B2")
        self.assertIs(got.signal.action, CandidateAction.BUY)
        self.assertIs(got.daily_trend, StructuralTrend.UP)
        self.assertIs(got.four_hour_trend, StructuralTrend.UP)
        self.assertFalse(got.source_forex_1to1_numerical_parity)

    def test_s2_sell_only_after_actual_htf_confirmed_pivots(self):
        got = evaluate_case("S2")
        self.assertIs(got.signal.action, CandidateAction.SELL)
        self.assertIs(got.daily_trend, StructuralTrend.DOWN)
        self.assertIs(got.four_hour_trend, StructuralTrend.DOWN)

    def test_every_pivot_first_known_after_candidate_close(self):
        for rule in ("B2", "S2"):
            got = evaluate_case(rule)
            for scan in (got.daily, got.four_hour):
                for p in scan.pivots:
                    self.assertGreater(p.confirmation_index, p.candidate_index)
                    self.assertGreater(p.confirmed_first_known_utc,
                                       p.candidate_bar_end_utc)
                    self.assertLessEqual(p.confirmed_first_known_utc,
                                         scan.asof_utc)

    def test_early_candidate_is_not_already_a_swing(self):
        data, policy = case_confirmed("B2")
        known = data.daily[5].first_known_utc
        scan = detect_confirmed_swings(
            data.daily[:6], Timeframe.D1, policy, known,
        )
        self.assertNotIn(5, [p.candidate_index for p in scan.pivots])

    def test_right_bar_confirmation_enters_only_after_known_clock(self):
        data, policy = case_confirmed("B2")
        known = data.daily[6].first_known_utc
        # One instant before the right bar closes, the strict CLOSED
        # source cutoff must reject it as a FUTURE PRICE BAR, regardless
        # of whether first-known/retrieval would also be too late.
        with self.assertRaisesRegex(ValueError, "FUTURE_PRICE_BAR"):
            detect_confirmed_swings(
                data.daily[:7], Timeframe.D1, policy,
                known - timedelta(seconds=1),
            )
        scan = detect_confirmed_swings(
            data.daily[:7], Timeframe.D1, policy, known,
        )
        self.assertIn(5, [p.candidate_index for p in scan.pivots])

    def test_equal_neighbor_high_not_promoted_to_pivot(self):
        data, policy = case_confirmed("B2")
        old = data.daily[0]
        equal = replace(old, high=data.daily[1].high)
        scan = detect_confirmed_swings(
            (equal,) + data.daily[1:], Timeframe.D1, policy,
            data.trigger_m15[0].key.bar_start_utc,
        )
        self.assertNotIn(1, [p.candidate_index for p in scan.pivots
                             if p.kind is PivotKind.HIGH])

    def test_all_derived_signals_remain_unverified_and_nontradeable(self):
        for rule in ("B2", "S2"):
            r = evaluate_case(rule)
            self.assertEqual(r.signal.stage.value, "UNVERIFIED")
            self.assertFalse(r.signal.may_send_confirmed_signal)
            self.assertFalse(r.signal.original_forex_numerical_parity)
            self.assertFalse(r.can_trade)
            self.assertFalse(r.may_send_confirmed_signal)
            self.assertEqual(r.market_provider_calls, 0)
            self.assertEqual(r.drive_raw_market_cache_writes, 0)
            self.assertFalse(r.daily.original_forex_numeric_policy_approved)

    def test_swing_failure_means_unknown_not_invented_buy(self):
        data, _ = case_confirmed("B2")
        got = eval_changed("B2", four_hour=data.four_hour[:4])
        self.assertIs(got.four_hour_trend, StructuralTrend.UNKNOWN)
        self.assertIs(got.signal.action, CandidateAction.NO_SIGNAL)

    def test_real_provider_even_if_one_bar_rejected(self):
        data, policy = case_confirmed("B2")
        corrupted = replace(
            data.daily[2],
            observation=replace(data.daily[2].observation, provider_id="OANDA"),
        )
        with self.assertRaisesRegex(ValueError, "REJECT_REAL_MARKET_SOURCE"):
            detect_confirmed_swings(
                data.daily[:2] + (corrupted,) + data.daily[3:],
                Timeframe.D1, policy,
                data.trigger_m15[0].key.bar_start_utc,
            )

    def test_future_retrieval_right_bar_rejected(self):
        data, policy = case_confirmed("B2")
        cutoff = data.trigger_m15[0].key.bar_start_utc
        bar = data.daily[6]
        corrupted = replace(
            bar, observation=replace(
                bar.observation, retrieved_at_utc=cutoff+timedelta(seconds=1),
            ),
        )
        with self.assertRaisesRegex(ValueError, "FUTURE_KNOWN"):
            detect_confirmed_swings(
                data.daily[:6] + (corrupted,) + data.daily[7:],
                Timeframe.D1, policy, cutoff,
            )

    def test_provisional_right_bar_rejected(self):
        data, policy = case_confirmed("B2")
        corrupted = replace(data.daily[6], lifecycle=BarLifecycle.OPEN)
        with self.assertRaisesRegex(ValueError, "OPEN_PROVISIONAL_BAR"):
            detect_confirmed_swings(
                data.daily[:6] + (corrupted,) + data.daily[7:],
                Timeframe.D1, policy, data.trigger_m15[0].key.bar_start_utc,
            )

    def test_partial_htf_right_confirmation_rejected(self):
        data, policy = case_confirmed("B2")
        corrupted = replace(data.daily[6], coverage=BarCoverage.PARTIAL)
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_COVERAGE"):
            detect_confirmed_swings(
                data.daily[:6] + (corrupted,) + data.daily[7:],
                Timeframe.D1, policy, data.trigger_m15[0].key.bar_start_utc,
            )

    def test_unverified_htf_quality_rejected(self):
        data, policy = case_confirmed("B2")
        corrupted = replace(data.daily[6], quality=SourceQuality.UNVERIFIED)
        with self.assertRaisesRegex(ValueError, "SOURCE_QUALITY_UNVERIFIED"):
            detect_confirmed_swings(
                data.daily[:6] + (corrupted,) + data.daily[7:],
                Timeframe.D1, policy, data.trigger_m15[0].key.bar_start_utc,
            )

    def test_noncontiguous_htf_rejected(self):
        data, policy = case_confirmed("B2")
        with self.assertRaisesRegex(ValueError, "MISSING_REORDERED"):
            detect_confirmed_swings(
                data.daily[:3] + data.daily[4:], Timeframe.D1, policy,
                data.trigger_m15[0].key.bar_start_utc,
            )

    def test_fake_license_rejected(self):
        data, policy = case_confirmed("B2")
        corrupted = replace(
            data.daily[3], observation=replace(
                data.daily[3].observation, license_scope_claim="APPROVED",
            ),
        )
        with self.assertRaisesRegex(ValueError, "REJECT_REAL_MARKET_SOURCE"):
            detect_confirmed_swings(
                data.daily[:3] + (corrupted,) + data.daily[4:],
                Timeframe.D1, policy, data.trigger_m15[0].key.bar_start_utc,
            )

    def test_mixed_side_rejected(self):
        data, policy = case_confirmed("B2")
        corrupted = replace(
            data.daily[3], key=replace(
                data.daily[3].key, side=BarSide.BID,
            ),
        )
        with self.assertRaisesRegex(ValueError, "CROSS_TIMEFRAME_OR_SIDE"):
            detect_confirmed_swings(
                data.daily[:3] + (corrupted,) + data.daily[4:],
                Timeframe.D1, policy, data.trigger_m15[0].key.bar_start_utc,
            )

    def test_revised_bar_denied(self):
        data, policy = case_confirmed("B2")
        corrupted = replace(data.daily[3], revision_number=2)
        with self.assertRaisesRegex(ValueError, "REJECT_REAL_MARKET_SOURCE"):
            detect_confirmed_swings(
                data.daily[:3] + (corrupted,) + data.daily[4:],
                Timeframe.D1, policy, data.trigger_m15[0].key.bar_start_utc,
            )

    def test_cross_timeframe_identity_mismatch_denied(self):
        data, _ = case_confirmed("B2")
        wrong = replace(
            data.daily[0], key=replace(
                data.daily[0].key, instrument_version="SIM:OTHER",
            ),
        )
        with self.assertRaisesRegex(ValueError, "CROSS_TIMEFRAME_IDENTITY"):
            eval_changed("B2", daily=(wrong,) + data.daily[1:])

    def test_wrong_calendar_denied(self):
        data, _ = case_confirmed("B2")
        wrong = replace(
            data.daily[0], key=replace(
                data.daily[0].key, calendar_version="SIM:WRONG",
            ),
        )
        with self.assertRaisesRegex(ValueError, "CROSS_TIMEFRAME_IDENTITY"):
            eval_changed("B2", daily=(wrong,) + data.daily[1:])

    def test_unknown_or_unapproved_pivot_parameter_denied(self):
        _, policy = case_confirmed("B2")
        with self.assertRaisesRegex(ValueError, "SIM_ONLY_UNAPPROVED"):
            replace(policy, version="APPROVED:1")
        for x in (0, 4, True, 1.5):
            with self.subTest(n=x):
                with self.assertRaisesRegex(ValueError, "INVALID_EXPLICIT"):
                    replace(policy, left_bars=x)

    def test_no_missing_or_unbounded_pivot_history(self):
        data, policy = case_confirmed("B2")
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT"):
            detect_confirmed_swings(
                data.daily[:2], Timeframe.D1, policy,
                data.trigger_m15[0].key.bar_start_utc,
            )
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT"):
            detect_confirmed_swings(
                list(data.daily), Timeframe.D1, policy,  # type: ignore[arg-type]
                data.trigger_m15[0].key.bar_start_utc,
            )

    def test_genuine_two_high_and_low_requirement(self):
        data, policy = case_confirmed("B2")
        scan = detect_confirmed_swings(
            data.daily[:4], Timeframe.D1, policy,
            data.daily[3].first_known_utc,
        )
        self.assertIs(trend_from_confirmed_swings(scan),
                      StructuralTrend.UNKNOWN)

    def test_h1_micro_seed_unchanged_and_causal(self):
        r = evaluate_case("B2")
        self.assertEqual(r.derived_context.known_micro_level,
                         Decimal("1.1015"))
        self.assertGreater(r.derived_context.known_atr, Decimal("0"))
        self.assertIs(r.signal.action, CandidateAction.BUY)

    def test_cross_rule_b2_s2_not_conflated(self):
        b2 = evaluate_case("B2")
        s2 = evaluate_case("S2")
        self.assertNotEqual(b2.signal.rule_id, s2.signal.rule_id)
        self.assertNotEqual(b2.signal.action, s2.signal.action)
