"""P0.19: derive rather than trust D1/H4/H1 synthetic input metadata."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import unittest

from forex_trading.market_data import BarCoverage, BarLifecycle, BarSide, SourceQuality
from mfx_research.causal_multitf_context import (
    SyntheticDerivationParameters, derive_and_evaluate_b2_s2,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.pullback_pilot import StructuralTrend
from tools.run_a04_p19_causal_context_demo import case_from_closed_bars, evaluate_case


def evaluate(rule: str, **change):
    bars, derive, trigger = case_from_closed_bars(rule)
    if "daily" in change:
        bars = replace(bars, daily=change["daily"])
    if "four_hour" in change:
        bars = replace(bars, four_hour=change["four_hour"])
    if "hourly" in change:
        bars = replace(bars, hourly=change["hourly"])
    if "micro_seed_m15" in change:
        bars=replace(bars,micro_seed_m15=change["micro_seed_m15"])
    if "trigger_m15" in change:
        bars = replace(bars, trigger_m15=change["trigger_m15"])
    if "derivation" in change:
        derive = change["derivation"]
    return derive_and_evaluate_b2_s2(
        rule,bars,derive,trigger,
        bars.trigger_m15[-1].first_known_utc+timedelta(seconds=1),
        origin_event_id="SIM:P019-"+rule,
    )


class CausalSyntheticMultitfTests(unittest.TestCase):
    def test_real_computation_b2_buy_from_ohlc(self):
        receipt=evaluate_case("B2")
        self.assertIs(receipt.signal.action,CandidateAction.BUY)
        self.assertIs(receipt.derived_context.d1_trend,StructuralTrend.UP)
        self.assertIs(receipt.derived_context.h4_trend,StructuralTrend.UP)
        self.assertEqual(receipt.derived_context.known_micro_level,Decimal("1.1015"))
        self.assertGreater(receipt.h1_true_range_atr,0)

    def test_real_computation_s2_sell_from_ohlc(self):
        receipt=evaluate_case("S2")
        self.assertIs(receipt.signal.action,CandidateAction.SELL)
        self.assertIs(receipt.derived_context.d1_trend,StructuralTrend.DOWN)
        self.assertIs(receipt.derived_context.h4_trend,StructuralTrend.DOWN)
        self.assertEqual(receipt.derived_context.known_micro_level,Decimal("1.1996"))

    def test_unverified_even_if_all_fixture_quality_claims_are_verified(self):
        for rule in ("B2","S2"):
            r=evaluate_case(rule)
            self.assertFalse(r.structural_calibration_approved)
            self.assertFalse(r.original_forex_source_signal_parity)
            self.assertFalse(r.source_verified_for_market)
            self.assertFalse(r.may_send_confirmed_signal)
            self.assertFalse(r.can_trade)
            self.assertFalse(r.signal.may_send_confirmed_signal)
            self.assertEqual(r.provider_requests,0)
            self.assertEqual(r.drive_market_cache_writes,0)

    def test_no_trend_when_h4_extrema_proxy_conflicts(self):
        b,_,_=case_from_closed_bars("B2")
        new=replace(b.four_hour[-1],
                    high=b.four_hour[0].high-Decimal("0.001"),
                    low=b.four_hour[0].low+Decimal("0.001"))
        # Need OHLC physically consistent with edited high/low.
        new=replace(new,open=Decimal("1.094"),close=Decimal("1.094"))
        r=evaluate("B2",four_hour=b.four_hour[:-1]+(new,))
        self.assertIs(r.signal.action,CandidateAction.NO_SIGNAL)
        self.assertIs(r.derived_context.h4_trend,StructuralTrend.UNKNOWN)

    def test_reject_future_known_h4_context(self):
        b,_,_=case_from_closed_bars("B2")
        future=replace(b.four_hour[-1],first_known_utc=
                       b.trigger_m15[0].key.bar_start_utc+timedelta(seconds=2))
        with self.assertRaisesRegex(ValueError,"FUTURE_KNOWN"):
            evaluate("B2",four_hour=b.four_hour[:-1]+(future,))

    def test_reject_future_retrieved_hourly_even_if_first_known_old(self):
        b,_,_=case_from_closed_bars("B2")
        o=replace(b.hourly[-1].observation,retrieved_at_utc=
                  b.trigger_m15[0].key.bar_start_utc+timedelta(seconds=2))
        with self.assertRaisesRegex(ValueError,"FUTURE_KNOWN"):
            evaluate("B2",hourly=b.hourly[:-1]+
                     (replace(b.hourly[-1],observation=o),))

    def test_reject_open_d1(self):
        b,_,_=case_from_closed_bars("B2")
        with self.assertRaisesRegex(ValueError,"OPEN_PROVISIONAL_BAR"):
            evaluate("B2",daily=b.daily[:-1]+
                     (replace(b.daily[-1],lifecycle=BarLifecycle.OPEN),))

    def test_reject_partial_h1(self):
        b,_,_=case_from_closed_bars("B2")
        with self.assertRaisesRegex(ValueError,"INCOMPLETE_COVERAGE"):
            evaluate("B2",hourly=b.hourly[:-1]+
                     (replace(b.hourly[-1],coverage=BarCoverage.PARTIAL),))

    def test_reject_unverified_d1_quality(self):
        b,_,_=case_from_closed_bars("B2")
        with self.assertRaisesRegex(ValueError,"SOURCE_QUALITY_UNVERIFIED"):
            evaluate("B2",daily=b.daily[:-1]+
                     (replace(b.daily[-1],quality=SourceQuality.UNVERIFIED),))

    def test_reject_one_hour_history_missing(self):
        b,_,_=case_from_closed_bars("B2")
        with self.assertRaisesRegex(ValueError,"COMPLETE_H1"):
            evaluate("B2",hourly=b.hourly[1:])

    def test_reject_h1_gap_or_reordering(self):
        b,_,_=case_from_closed_bars("B2")
        with self.assertRaisesRegex(ValueError,"MISSING_REORDERED"):
            evaluate("B2",hourly=(b.hourly[0],b.hourly[2],
                                  b.hourly[1],b.hourly[3]))

    def test_reject_htf_bar_after_m15_start(self):
        b,_,_=case_from_closed_bars("B2")
        h=replace(b.four_hour[-1],key=replace(
            b.four_hour[-1].key,
            bar_start_utc=b.four_hour[-1].key.bar_start_utc+timedelta(hours=1),
            bar_end_utc=b.four_hour[-1].key.bar_end_utc+timedelta(hours=1),
        ),first_known_utc=b.four_hour[-1].first_known_utc+timedelta(hours=1),
        observation=replace(b.four_hour[-1].observation,
            first_known_utc=b.four_hour[-1].observation.first_known_utc+timedelta(hours=1),
            retrieved_at_utc=b.four_hour[-1].observation.retrieved_at_utc+timedelta(hours=1)))
        with self.assertRaisesRegex(ValueError,"FUTURE_PRICE_BAR"):
            evaluate("B2",four_hour=b.four_hour[:-1]+(h,))

    def test_reject_real_provider_in_hourly(self):
        b,_,_=case_from_closed_bars("B2")
        new=replace(b.hourly[2],observation=replace(
            b.hourly[2].observation,provider_id="OANDA"))
        with self.assertRaisesRegex(ValueError,"REJECT_REAL_MARKET_SOURCE"):
            evaluate("B2",hourly=b.hourly[:2]+(new,)+b.hourly[3:])

    def test_reject_cross_pair_htf(self):
        b,_,_=case_from_closed_bars("B2")
        new=replace(b.daily[0],key=replace(
            b.daily[0].key,instrument_version="SIM:OTHER"))
        with self.assertRaisesRegex(ValueError,"CROSS_TIMEFRAME_IDENTITY"):
            evaluate("B2",daily=(new,b.daily[1]))

    def test_reject_mixed_price_side(self):
        b,_,_=case_from_closed_bars("B2")
        new=replace(b.hourly[-1],key=replace(
            b.hourly[-1].key,side=BarSide.BID))
        with self.assertRaisesRegex(ValueError,"CROSS_TIMEFRAME_OR_SIDE"):
            evaluate("B2",hourly=b.hourly[:-1]+(new,))

    def test_reject_hidden_h4_revision(self):
        b,_,_=case_from_closed_bars("B2")
        new=replace(b.four_hour[1],revision_number=2)
        with self.assertRaisesRegex(ValueError,"REJECT_REAL_MARKET_SOURCE"):
            evaluate("B2",four_hour=(b.four_hour[0],new))

    def test_reject_micro_seed_after_context_cutoff(self):
        b,_,_=case_from_closed_bars("B2")
        new=replace(b.micro_seed_m15[0],first_known_utc=
                    b.trigger_m15[0].key.bar_start_utc+timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError,"FUTURE_KNOWN"):
            evaluate("B2",micro_seed_m15=(new,))

    def test_reject_m15_seed_gap(self):
        b,_,_=case_from_closed_bars("B2")
        new=replace(b.micro_seed_m15[0],key=replace(
            b.micro_seed_m15[0].key,
            bar_start_utc=b.micro_seed_m15[0].key.bar_start_utc-timedelta(minutes=15),
            bar_end_utc=b.micro_seed_m15[0].key.bar_end_utc-timedelta(minutes=15),
        ),first_known_utc=b.micro_seed_m15[0].first_known_utc-timedelta(minutes=15),
        observation=replace(b.micro_seed_m15[0].observation,
            first_known_utc=b.micro_seed_m15[0].observation.first_known_utc-timedelta(minutes=15),
            retrieved_at_utc=b.micro_seed_m15[0].observation.retrieved_at_utc-timedelta(minutes=15)))
        with self.assertRaisesRegex(ValueError,"MICRO_PIVOT_NOT_CAUSALLY"):
            evaluate("B2",micro_seed_m15=(new,))

    def test_reject_source_calendar_conflict(self):
        b,_,_=case_from_closed_bars("B2")
        new=replace(b.daily[-1],key=replace(
            b.daily[-1].key,calendar_version="SIM:DIFFERENT-CALENDAR"))
        with self.assertRaisesRegex(ValueError,"CROSS_TIMEFRAME_IDENTITY"):
            evaluate("B2",daily=b.daily[:-1]+(new,))

    def test_reject_invalid_sim_h1_duration(self):
        b,_,_=case_from_closed_bars("B2")
        new=replace(b.hourly[0],key=replace(
            b.hourly[0].key,
            bar_start_utc=b.hourly[0].key.bar_start_utc+timedelta(minutes=1)))
        with self.assertRaisesRegex(ValueError,"TIMEFRAME_DURATION"):
            evaluate("B2",hourly=(new,)+b.hourly[1:])

    def test_reject_unapproved_numeric_policy_defaults(self):
        b,d,_=case_from_closed_bars("B2")
        for bad in (0,25,True,1.5):
            with self.subTest(n=bad):
                with self.assertRaisesRegex(ValueError,"H1_PERIOD_BOUNDS"):
                    replace(d,atr_h1_periods=bad)
        with self.assertRaisesRegex(ValueError,"SIM_ONLY_PARAMETER"):
            replace(d,version="APPROVED-1")
        for v in (Decimal("NaN"),Decimal("0"),Decimal("21")):
            with self.subTest(v=v):
                with self.assertRaisesRegex(ValueError,"UNAPPROVED_ZONE_WIDTH"):
                    replace(d,zone_width_atr_multiple=v)

    def test_no_real_broker_d1_data_allowed(self):
        b,_,_=case_from_closed_bars("B2")
        new=replace(b.daily[0],observation=replace(
            b.daily[0].observation,license_scope_claim="REAL_DATA_LICENSED"))
        with self.assertRaisesRegex(ValueError,"REJECT_REAL_MARKET_SOURCE"):
            evaluate("B2",daily=(new,b.daily[1]))

    def test_no_zone_if_trend_unknown_on_daily(self):
        b,_,_=case_from_closed_bars("B2")
        old=b.daily[0]
        new=replace(b.daily[-1],high=old.high,low=old.low,
                    open=old.close,close=old.close)
        r=evaluate("B2",daily=(old,new))
        self.assertIs(r.signal.action,CandidateAction.NO_SIGNAL)
        self.assertIs(r.derived_context.d1_trend,StructuralTrend.UNKNOWN)

    def test_prior_h1_close_changes_true_range_atr(self):
        r=evaluate_case("B2")
        b,_,_=case_from_closed_bars("B2")
        old=b.hourly[0]
        # A synthetic gap relative to the NEXT candle changes true range,
        # unlike merely changing the previous close inside its old range.
        moved=replace(old, high=Decimal("1.1080"),
                      close=Decimal("1.1080"))
        changed=evaluate("B2",hourly=(moved,)+b.hourly[1:])
        self.assertNotEqual(r.h1_true_range_atr,changed.h1_true_range_atr)

    def test_no_missing_or_mutable_input(self):
        b,_,_=case_from_closed_bars("B2")
        with self.assertRaisesRegex(ValueError,"MISSING_OR_MUTABLE"):
            evaluate("B2",hourly=list(b.hourly))  # type: ignore[arg-type]

    def test_different_h1_policy_lookback_changes_support_zone(self):
        b,d,_=case_from_closed_bars("B2")
        new=replace(d, h1_zone_lookback=2)
        r=evaluate("B2",derivation=new)
        self.assertGreaterEqual(r.derived_context.h1_zone_low,
                                evaluate_case("B2").derived_context.h1_zone_low)

    def test_noncausal_first_known_order_denied(self):
        b,_,_=case_from_closed_bars("B2")
        # Delay the older bar's first known time *past* the next bar's
        # first-known, without violating its own CLOSED cutoff or as-of.
        prior=b.hourly[1]
        late_known=b.hourly[2].first_known_utc+timedelta(minutes=1)
        late_obs=replace(prior.observation,first_known_utc=late_known,
                         retrieved_at_utc=late_known)
        delayed=replace(prior,first_known_utc=late_known,
                        observation=late_obs)
        with self.assertRaisesRegex(ValueError,"NONCAUSAL_OBSERVATION_ORDER"):
            evaluate("B2",hourly=b.hourly[:1]+(delayed,)+b.hourly[2:])

    def test_s2_no_signal_when_h1_zone_is_far(self):
        b,d,_=case_from_closed_bars("S2")
        # Valid synthetic H1 highs far above M15 location; trend unchanged.
        shifted=tuple(replace(
            x, open=x.open+Decimal("0.10"),high=x.high+Decimal("0.10"),
            low=x.low+Decimal("0.10"),close=x.close+Decimal("0.10"),
        ) for x in b.hourly)
        r=evaluate("S2",hourly=shifted)
        self.assertIs(r.signal.action,CandidateAction.NO_SIGNAL)
