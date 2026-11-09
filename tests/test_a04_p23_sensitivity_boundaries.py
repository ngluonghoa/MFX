"""A04/P0.23: pre-registered synthetic B2/S2 causal sensitivity QA.

These are independent boundary oracles against existing P0.18--P0.22 research
implementations, not calibrated/approved Forex Trading numeric detectors.
No runtime source edits, feed, broker, Drive market cache, or release.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import unittest

from forex_trading.market_data import Timeframe
from mfx_research.causal_multitf_context import SyntheticDerivationParameters
from mfx_research.confirmed_swings import (
    PivotKind, SyntheticPivotParameters, detect_confirmed_swings,
    derive_swing_b2_s2_research,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p022_policy_casebook import read_casebook
from mfx_research.pullback_pilot import (
    ClaimedStructuralContext, StructuralTrend,
    UnapprovedResearchParameters, evaluate_unapproved_b2_s2,
)
from tools.run_a04_p19_causal_context_demo import case_from_closed_bars
from tools.run_a04_p20_confirmed_swing_demo import (
    case_confirmed, evaluate_case,
)

EPS = Decimal("0.000000001")


def independent_strict_pivot_oracle(
    series: tuple, left: int, right: int,
) -> tuple[tuple[int, int, str, Decimal, object], ...]:
    """Use only OHLC/first-known, not the application's pivot implementation."""
    answer: list[tuple[int, int, str, Decimal, object]] = []
    for i in range(left, len(series) - right):
        center = series[i]
        neighbors = series[i-left:i] + series[i+1:i+right+1]
        above = all(center.high > bar.high for bar in neighbors)
        below = all(center.low < bar.low for bar in neighbors)
        if above == below:
            continue
        k = max(max(b.first_known_utc, b.observation.retrieved_at_utc)
                for b in series[i-left:i+right+1])
        answer.append((
            i, i + right, "HIGH" if above else "LOW",
            center.high if above else center.low, k,
        ))
    return tuple(answer)


def evaluated(rule: str, *,
              swing: SyntheticPivotParameters | None = None,
              zone: SyntheticDerivationParameters | None = None,
              trigger: UnapprovedResearchParameters | None = None,
              origin: str = "SIM:P023-BOUNDARY") -> object:
    data, original_swing = case_confirmed(rule)
    _, original_zone, original_trigger = case_from_closed_bars(rule)
    return derive_swing_b2_s2_research(
        rule, data,
        swing if swing is not None else original_swing,
        zone if zone is not None else original_zone,
        trigger if trigger is not None else original_trigger,
        data.trigger_m15[-1].first_known_utc + timedelta(seconds=1),
        origin_event_id=origin,
    )


class P023IndependentCausalSensitivityTests(unittest.TestCase):
    def test_01_pivot_independent_strict_oracle_for_both_directions(self) -> None:
        for rule in ("B2", "S2"):
            bars, original = case_confirmed(rule)
            cutoff = bars.trigger_m15[0].key.bar_start_utc
            for left, right in ((1, 1), (1, 2), (2, 1), (2, 2), (3, 3)):
                policy = replace(original, left_bars=left, right_bars=right)
                for tf, series in ((Timeframe.D1, bars.daily),
                                   (Timeframe.H4, bars.four_hour)):
                    with self.subTest(rule=rule,tf=tf,left=left,right=right):
                        got = detect_confirmed_swings(series, tf, policy, cutoff)
                        observed = tuple(
                            (p.candidate_index, p.confirmation_index,
                             p.kind.value, p.price, p.confirmed_first_known_utc)
                            for p in got.pivots
                        )
                        self.assertEqual(
                            observed,
                            independent_strict_pivot_oracle(series,left,right),
                        )
                        for p in got.pivots:
                            self.assertGreater(p.confirmed_first_known_utc,
                                               p.candidate_bar_end_utc)
                            self.assertLessEqual(p.confirmed_first_known_utc,
                                                 cutoff)
                            self.assertFalse(p.source_verified)

    def test_02_right_bar_addition_moves_confirmation_clock(self) -> None:
        for rule in ("B2", "S2"):
            bars, base = case_confirmed(rule)
            series = bars.daily
            old = detect_confirmed_swings(
                series[:7], Timeframe.D1, base,
                series[6].first_known_utc,
            )
            newer = replace(base, right_bars=2,
                            version="SIM:P023-RIGHT2-UNAPPROVED")
            # Right2 cannot read candle #7 at candle #6's decision time.
            with self.assertRaisesRegex(ValueError, "FUTURE_PRICE_BAR"):
                detect_confirmed_swings(
                    series[:8], Timeframe.D1, newer,
                    series[6].first_known_utc,
                )
            mature = detect_confirmed_swings(
                series[:8], Timeframe.D1, newer, series[7].first_known_utc,
            )
            old_at_5 = [p for p in old.pivots if p.candidate_index == 5]
            new_at_5 = [p for p in mature.pivots if p.candidate_index == 5]
            self.assertEqual(len(old_at_5), 1)
            self.assertEqual(len(new_at_5), 1)
            self.assertEqual(new_at_5[0].confirmation_index, 7)
            self.assertEqual(old_at_5[0].confirmation_index, 6)
            self.assertGreater(new_at_5[0].confirmed_first_known_utc,
                               old_at_5[0].confirmed_first_known_utc)

    def test_03_cannot_confirm_before_right_candle_end(self) -> None:
        for rule in ("B2", "S2"):
            data, original = case_confirmed(rule)
            series = data.daily[:7]
            t = series[-1].key.bar_end_utc
            with self.assertRaisesRegex(ValueError,"FUTURE_PRICE_BAR"):
                detect_confirmed_swings(series,Timeframe.D1,original,
                                        t-timedelta(microseconds=1))
            mature = detect_confirmed_swings(
                series, Timeframe.D1, original,t,
            )
            self.assertTrue(all(p.confirmed_first_known_utc<=t
                                for p in mature.pivots))

    def test_04_no_future_retrieval_even_when_price_bar_closed(self) -> None:
        for rule in ("B2", "S2"):
            data,policy=case_confirmed(rule)
            series=data.daily[:7]
            end=series[-1].key.bar_end_utc
            bar=series[-1]
            future=replace(bar,observation=replace(
                bar.observation,retrieved_at_utc=end+timedelta(seconds=1),
            ))
            mutated=series[:-1]+(future,)
            with self.assertRaisesRegex(ValueError,"FUTURE_KNOWN"):
                detect_confirmed_swings(mutated,Timeframe.D1,policy,end)
            result=detect_confirmed_swings(
                mutated,Timeframe.D1,policy,end+timedelta(seconds=1),
            )
            for p in result.pivots:
                if p.confirmation_index == len(mutated)-1:
                    self.assertGreaterEqual(p.confirmed_first_known_utc,
                                            future.observation.retrieved_at_utc)

    def test_05_strict_tied_high_candidate_rejected(self) -> None:
        for rule in ("B2", "S2"):
            data,policy=case_confirmed(rule)
            seq=data.daily
            prior=replace(seq[4],high=seq[5].high)
            modified=seq[:4]+(prior,)+seq[5:]
            cutoff=data.trigger_m15[0].key.bar_start_utc
            receipt=detect_confirmed_swings(modified,Timeframe.D1,policy,cutoff)
            self.assertFalse(any(p.candidate_index==5
                                 and p.kind is PivotKind.HIGH
                                 for p in receipt.pivots))

    def test_06_simultaneous_high_and_low_extreme_is_ambiguous(self) -> None:
        for rule in ("B2", "S2"):
            data,policy=case_confirmed(rule)
            seq=data.daily
            extreme=replace(seq[5],high=Decimal("2"),low=Decimal("0.5"))
            modified=seq[:5]+(extreme,)+seq[6:]
            cutoff=data.trigger_m15[0].key.bar_start_utc
            receipt=detect_confirmed_swings(modified,Timeframe.D1,policy,cutoff)
            self.assertFalse(any(p.candidate_index==5 for p in receipt.pivots))

    def test_07_insufficient_and_oversized_pivot_history_denied(self) -> None:
        for rule in ("B2", "S2"):
            data,policy=case_confirmed(rule)
            cutoff=data.trigger_m15[0].key.bar_start_utc
            with self.assertRaisesRegex(ValueError,"INSUFFICIENT"):
                detect_confirmed_swings(
                    data.daily[:4],Timeframe.D1,
                    replace(policy,left_bars=3,right_bars=3),cutoff,
                )
            with self.assertRaisesRegex(ValueError,"UNBOUNDED"):
                detect_confirmed_swings(
                    data.daily*52,Timeframe.D1,policy,cutoff,
                )

    def test_08_numeric_policy_cannot_be_non_sim_or_invalid_type(self) -> None:
        _,p=case_confirmed("B2")
        for bad in (0,4,True,1.5):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError,"INVALID_EXPLICIT"):
                    replace(p,right_bars=bad)
        with self.assertRaisesRegex(ValueError,"SIM_ONLY_UNAPPROVED"):
            replace(p,version="SOURCE:APPROVED")

    def test_09_near_zone_equal_included_outside_excluded(self) -> None:
        for rule in ("B2", "S2"):
            receipt=evaluate_case(rule)
            ctx=receipt.derived_context
            bars=case_confirmed(rule)[0].trigger_m15
            _,_,parameters=case_from_closed_bars(rule)
            tolerance=ctx.known_atr*parameters.near_zone_atr_multiple
            if rule=="B2":
                edge=bars[0].low-tolerance
                at=replace(ctx,h1_zone_low=edge,h1_zone_high=edge)
                out=replace(ctx,h1_zone_low=edge-EPS,h1_zone_high=edge-EPS)
                expected=CandidateAction.BUY
            else:
                edge=bars[0].high+tolerance
                at=replace(ctx,h1_zone_low=edge,h1_zone_high=edge)
                out=replace(ctx,h1_zone_low=edge+EPS,h1_zone_high=edge+EPS)
                expected=CandidateAction.SELL
            decision=bars[-1].first_known_utc+timedelta(seconds=1)
            reached=evaluate_unapproved_b2_s2(bars,at,parameters,decision)
            missed=evaluate_unapproved_b2_s2(bars,out,parameters,decision)
            self.assertEqual(reached.action,expected)
            self.assertIs(missed.action,CandidateAction.NO_SIGNAL)
            self.assertEqual(missed.reason,"P018_PRIOR_M15_NOT_NEAR_H1_ZONE")

    def test_10_anti_chase_equal_included_just_beyond_excluded(self) -> None:
        for rule in ("B2","S2"):
            data=case_confirmed(rule)[0]
            ctx=evaluate_case(rule).derived_context
            _,_,base=case_from_closed_bars(rule)
            last=data.trigger_m15[-1].close
            displacement=(last-ctx.known_micro_level if rule=="B2"
                          else ctx.known_micro_level-last)
            self.assertGreater(displacement,Decimal("0"))
            boundary=displacement/ctx.known_atr
            # Exact decimal ratio gives <= at the equality-or-rounding
            # boundary; use tighter and looser strictly perturbed ATR costs.
            self.assertGreater(boundary,Decimal("0"))
            upper=replace(base, max_chase_atr_multiple=boundary+EPS,
                          version="SIM:P023-CHASE-UPPER")
            lower=replace(base, max_chase_atr_multiple=boundary-EPS,
                          version="SIM:P023-CHASE-LOWER")
            self.assertGreater(lower.max_chase_atr_multiple,Decimal("0"))
            decision=data.trigger_m15[-1].first_known_utc+timedelta(seconds=1)
            yes=evaluate_unapproved_b2_s2(data.trigger_m15,ctx,upper,decision)
            no=evaluate_unapproved_b2_s2(data.trigger_m15,ctx,lower,decision)
            self.assertIs(yes.action, CandidateAction.BUY
                          if rule=="B2" else CandidateAction.SELL)
            self.assertIs(no.action,CandidateAction.NO_SIGNAL)
            self.assertEqual(no.reason,"P018_SYNTHETIC_ANTI_CHASE_LIMIT")

    def test_11_latest_micro_break_is_strict_not_equal(self) -> None:
        for rule in ("B2","S2"):
            data=case_confirmed(rule)[0]
            ctx=evaluate_case(rule).derived_context
            _,_,parameters=case_from_closed_bars(rule)
            changed=replace(ctx,known_micro_level=data.trigger_m15[-1].close)
            decision=data.trigger_m15[-1].first_known_utc+timedelta(seconds=1)
            result=evaluate_unapproved_b2_s2(
                data.trigger_m15,changed,parameters,decision,
            )
            self.assertIs(result.action,CandidateAction.NO_SIGNAL)
            self.assertEqual(result.reason,"P018_NO_LATEST_MICRO_BREAK")

    def test_12_unknown_opposite_or_invalidated_trend_stops_signal(self) -> None:
        for rule in ("B2","S2"):
            data=case_confirmed(rule)[0]
            ctx=evaluate_case(rule).derived_context
            _,_,params=case_from_closed_bars(rule)
            decision=data.trigger_m15[-1].first_known_utc+timedelta(seconds=1)
            for alt in (
                replace(ctx,d1_trend=StructuralTrend.UNKNOWN),
                replace(ctx,h4_trend=StructuralTrend.UNKNOWN),
                replace(ctx,d1_trend=StructuralTrend.DOWN if rule=="B2"
                        else StructuralTrend.UP),
            ):
                result=evaluate_unapproved_b2_s2(
                    data.trigger_m15,alt,params,decision,
                )
                self.assertIs(result.action,CandidateAction.NO_SIGNAL)
                self.assertEqual(result.reason,"P018_TREND_NOT_SUPPORTED")
            inval=replace(ctx,structure_invalidated=True)
            result=evaluate_unapproved_b2_s2(
                data.trigger_m15,inval,params,decision,
            )
            self.assertIs(result.action,CandidateAction.NO_SIGNAL)
            self.assertEqual(result.reason,"P018_STRUCTURE_INVALIDATED")

    def test_13_h1_length_fail_closed_with_unapproved_period_change(self) -> None:
        for rule in ("B2","S2"):
            _,zone,_=case_from_closed_bars(rule)
            with self.assertRaisesRegex(ValueError,"INCOMPLETE_H1"):
                evaluated(rule,zone=replace(zone,atr_h1_periods=4))
            with self.assertRaisesRegex(ValueError,"INCOMPLETE_H1"):
                evaluated(rule,zone=replace(zone,h1_zone_lookback=5))

    def test_14_h1_period_change_recalculates_true_range_independently(self) -> None:
        for rule in ("B2","S2"):
            _,zone,_=case_from_closed_bars(rule)
            altered=replace(zone,atr_h1_periods=2,h1_zone_lookback=4,
                            version="SIM:P023-H1-ATR2-LOOKBACK4")
            r=evaluated(rule,zone=altered)
            data=case_confirmed(rule)[0]
            h1=data.hourly
            tr=[]
            for i in (2,3):
                bar,previous=h1[i],h1[i-1]
                tr.append(max(bar.high-bar.low,
                              abs(bar.high-previous.close),
                              abs(bar.low-previous.close)))
            independently=(tr[0]+tr[1])/Decimal(2)
            self.assertEqual(r.derived_context.known_atr,independently)
            self.assertEqual(r.signal.stage.value,"UNVERIFIED")
            self.assertFalse(r.signal.may_send_confirmed_signal)

    def test_15_revision_and_future_micro_seed_cannot_repaint(self) -> None:
        for rule in ("B2","S2"):
            data,_=case_confirmed(rule)
            seed=data.micro_seed_m15[0]
            with self.assertRaisesRegex(ValueError,"REJECT_REAL_MARKET_SOURCE"):
                shifted=replace(data,micro_seed_m15=(replace(seed,revision_number=2),))
                self._direct(rule,shifted)
            later=replace(seed,first_known_utc=data.trigger_m15[0].key.bar_start_utc
                          +timedelta(seconds=1))
            with self.assertRaisesRegex(ValueError,"FUTURE_KNOWN"):
                self._direct(rule,replace(data,micro_seed_m15=(later,)))

    def test_16_quote_side_cross_pair_and_calendar_denied(self) -> None:
        from forex_trading.market_data import BarSide
        for rule in ("B2","S2"):
            data,_=case_confirmed(rule)
            first=data.daily[0]
            changed=(
                replace(first,key=replace(first.key,side=BarSide.BID)),
                replace(first,key=replace(first.key,
                                          instrument_version="SIM:OTHER")),
                replace(first,key=replace(first.key,
                                          calendar_version="SIM:OTHER")),
            )
            for new_bar in changed:
                with self.assertRaisesRegex(ValueError,
                                            "CROSS_TIMEFRAME_OR_SIDE|CROSS_TIMEFRAME_IDENTITY"):
                    self._direct(rule,replace(
                        data,daily=(new_bar,)+data.daily[1:],
                    ))

    def test_17_original_source_numeric_obligations_remain_blocked(self) -> None:
        r,digest=read_casebook()
        self.assertEqual(r["unapproved_numeric_obligations"],36)
        self.assertEqual(r["source_rules_approved"],0)
        self.assertEqual(r["sim_example_count"],14)
        self.assertFalse(r["confirmed_signals_allowed"])
        self.assertFalse(r["release_ready"])
        self.assertEqual(len(digest),64)

    def test_18_same_event_replay_does_not_claim_idempotence(self) -> None:
        for rule in ("B2","S2"):
            a=evaluated(rule,origin="SIM:P023-SAME-EVENT")
            b=evaluated(rule,origin="SIM:P023-SAME-EVENT")
            self.assertEqual(a.signal.as_record(),b.signal.as_record())
            self.assertEqual(a.signal.origin_event_id,
                             "SIM:P023-SAME-EVENT")
            self.assertFalse(a.may_send_confirmed_signal)
            # This is NOT persistent deduplication; future runtime design gap.

    def test_19_structural_invalidation_is_not_automatically_calculated(self) -> None:
        for rule in ("B2","S2"):
            r=evaluate_case(rule)
            self.assertFalse(r.derived_context.structure_invalidated)
            self.assertFalse(r.source_forex_1to1_numerical_parity)
            # Known architectural limitation, not source/economic approval.

    def test_20_policy_versions_reproducible_and_research_only(self) -> None:
        for rule in ("B2","S2"):
            _,_,p=case_from_closed_bars(rule)
            altered=replace(p,version="SIM:P023-ALT-RESEARCH")
            a=evaluated(rule,trigger=altered)
            b=evaluated(rule,trigger=altered)
            self.assertEqual(a.signal.as_record(),b.signal.as_record())
            self.assertEqual(a.signal.parameter_version,"SIM:P023-ALT-RESEARCH")
            self.assertEqual(a.signal.stage.value,"UNVERIFIED")
            self.assertFalse(a.signal.may_send_confirmed_signal)
            self.assertFalse(a.can_trade)

    def test_21_no_real_feed_cache_orders_or_release(self) -> None:
        for rule in ("B2","S2"):
            r=evaluated(rule)
            self.assertEqual(r.market_provider_calls,0)
            self.assertEqual(r.drive_raw_market_cache_writes,0)
            self.assertFalse(r.can_trade)
            self.assertFalse(r.may_send_confirmed_signal)
            self.assertFalse(r.signal.original_forex_numerical_parity)

    def _direct(self,rule:str,data:object)->object:
        # Test the same multi-TF entrypoint with malformed derived inputs.
        from mfx_research.causal_multitf_context import SyntheticMultiTfBars
        if not isinstance(data,SyntheticMultiTfBars):
            raise TypeError("P023_TEST_TYPED_BARS_REQUIRED")
        _,swing=case_confirmed(rule)
        _,zone,trigger=case_from_closed_bars(rule)
        return derive_swing_b2_s2_research(
            rule,data,swing,zone,trigger,
            data.trigger_m15[-1].first_known_utc+timedelta(seconds=1),
            origin_event_id="SIM:P023-DENIAL",
        )
