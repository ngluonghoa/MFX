"""MFX 1.0 SIM-only cost-aware LONG/SHORT math; NO signals or live IO."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest import TestCase

from forex_trading.model import ActionIntent
from forex_trading.quotes import PriceSide, Quote, QuoteQuality
from mfx_research.bidask_cost_aware_sim_risk import (
    VERSION, SimExitLevels, SimPerUnitCosts, evaluate_cost_aware_sim_risk,
)

D = Decimal
NOW = datetime(2026, 11, 13, 9, 1, tzinfo=timezone.utc)
FIRST_KNOWN = NOW - timedelta(minutes=1)
ONE = timedelta(minutes=3)


def quote(**kwargs):
    q=Quote(
        provider="SIM:CALLER_CLAIM_ONLY",
        source_revision="SIM:REV1",
        event_time_utc=NOW-timedelta(minutes=2),
        first_known_utc=FIRST_KNOWN,
        bid=D("1.1000"),ask=D("1.1002"),
        quality=QuoteQuality.VERIFIED,
    )
    return replace(q,**kwargs)


def costs(**kwargs):
    c=SimPerUnitCosts(
        version="SIM:COSTS1",
        entry_slippage=D("0.00005"), exit_slippage=D("0.00005"),
        entry_fee=D("0.00002"), exit_fee=D("0.00003"),
    )
    return replace(c,**kwargs)


def exits(long=True,**kwargs):
    p=SimExitLevels(
        version="SIM:EXIT1",
        stop_price=D("1.0990") if long else D("1.1010"),
        target_price=D("1.1022") if long else D("1.0980"),
        exit_side=PriceSide.BID if long else PriceSide.ASK,
    )
    return replace(p,**kwargs)


def compute(long=True,**kwargs):
    args={
        "quote":quote(),
        "intent":ActionIntent.ENTRY_LONG if long else ActionIntent.ENTRY_SHORT,
        "decision_utc":NOW,"max_quote_age":ONE,
        "exits":exits(long),"costs":costs(),"instrument":"EUR/USD",
    }
    args.update(kwargs)
    return evaluate_cost_aware_sim_risk(**args)


class BidAskCostAwareSimRiskTests(TestCase):
    def test_01_long_ask_entry_bid_exit_with_separate_costs(self):
        r=compute()
        self.assertEqual((r.entry_side,r.exit_side),
                         (PriceSide.ASK,PriceSide.BID))
        self.assertEqual(r.entry_reference_price,D("1.1002"))
        self.assertEqual(r.effective_entry_price,D("1.10025"))
        self.assertEqual(r.effective_stop_exit_price,D("1.09895"))
        self.assertEqual(r.effective_target_exit_price,D("1.10215"))
        self.assertEqual(r.explicit_roundtrip_fee_per_base_unit,D("0.00005"))
        self.assertEqual(r.net_risk_quote_currency_per_base_unit,D("0.00135"))
        self.assertEqual(r.net_reward_quote_currency_per_base_unit,D("0.00185"))
        self.assertEqual(r.experimental_net_risk_reward,
                         D("0.00185")/D("0.00135"))

    def test_02_short_bid_entry_ask_exit_with_separate_costs(self):
        r=compute(False)
        self.assertEqual((r.entry_side,r.exit_side),
                         (PriceSide.BID,PriceSide.ASK))
        self.assertEqual(r.entry_reference_price,D("1.1000"))
        self.assertEqual(r.effective_entry_price,D("1.09995"))
        self.assertEqual(r.effective_stop_exit_price,D("1.10105"))
        self.assertEqual(r.effective_target_exit_price,D("1.09805"))
        self.assertEqual(r.net_risk_quote_currency_per_base_unit,D("0.00115"))
        self.assertEqual(r.net_reward_quote_currency_per_base_unit,D("0.00185"))
        self.assertEqual(r.experimental_net_risk_reward,
                         D("0.00185")/D("0.00115"))

    def test_03_long_spread_widening_increases_risk_decreases_reward(self):
        base=compute()
        wider=compute(quote=quote(ask=D("1.1004")))
        self.assertEqual(wider.reference_spread,D("0.0004"))
        self.assertEqual(wider.net_risk_quote_currency_per_base_unit-
                         base.net_risk_quote_currency_per_base_unit,D("0.0002"))
        self.assertEqual(base.net_reward_quote_currency_per_base_unit-
                         wider.net_reward_quote_currency_per_base_unit,D("0.0002"))

    def test_04_short_spread_widening_bid_down_increases_risk(self):
        base=compute(False)
        wide=compute(False,quote=quote(bid=D("1.0998")))
        self.assertEqual(wide.net_risk_quote_currency_per_base_unit-
                         base.net_risk_quote_currency_per_base_unit,D("0.0002"))
        self.assertEqual(base.net_reward_quote_currency_per_base_unit-
                         wide.net_reward_quote_currency_per_base_unit,D("0.0002"))

    def test_05_increasing_slippage_and_fees_worsens_both_sides(self):
        high=costs(entry_slippage=D("0.00015"),exit_slippage=D("0.00015"),
                   entry_fee=D("0.00004"),exit_fee=D("0.00006"))
        for side in (True,False):
            with self.subTest(side=side):
                a=compute(side)
                b=compute(side,costs=high)
                self.assertGreater(b.net_risk_quote_currency_per_base_unit,
                                   a.net_risk_quote_currency_per_base_unit)
                self.assertLess(b.net_reward_quote_currency_per_base_unit,
                                a.net_reward_quote_currency_per_base_unit)
                self.assertLess(b.experimental_net_risk_reward,
                                a.experimental_net_risk_reward)

    def test_06_negative_reward_remains_unverified_not_fake_trade(self):
        e=exits(True,target_price=D("1.1001"))
        r=compute(exits=e)
        self.assertLess(r.net_reward_quote_currency_per_base_unit,0)
        self.assertLess(r.experimental_net_risk_reward,0)
        self.assertEqual(r.action,"NO_SIGNAL")
        self.assertFalse(r.may_trade)

    def test_07_zero_fee_and_slippage_are_assumptions_not_rights(self):
        c=costs(entry_slippage=D(0),exit_slippage=D(0),
                entry_fee=D(0),exit_fee=D(0))
        r=compute(costs=c)
        self.assertEqual(r.explicit_roundtrip_fee_per_base_unit,D(0))
        self.assertFalse(r.real_execution_costs_approved)
        self.assertFalse(r.independently_verified_data_rights)

    def test_08_market_source_and_original_rules_never_claimed(self):
        for side in (True,False):
            r=compute(side)
            self.assertEqual((r.version,r.action,r.stage),
                             (VERSION,"NO_SIGNAL","UNVERIFIED"))
            for name in ("original_forex_numeric_rules_approved",
                         "independently_verified_data_rights",
                         "publisher_first_known_attested",
                         "real_execution_costs_approved",
                         "historical_oos_qualified",
                         "may_publish_buy_sell","may_trade"):
                self.assertFalse(getattr(r,name),name)

    def test_09_all_side_effects_zero_no_broker(self):
        r=compute()
        self.assertEqual((r.provider_requests,r.drive_market_cache_writes,
                          r.broker_orders),(0,0,0))
        self.assertTrue(r.hypothetical_exit_only)
        self.assertEqual(r.instrument,"EUR/USD")

    def test_10_reject_short_stop_and_target_with_bid_basis(self):
        with self.assertRaisesRegex(ValueError,"EXIT_PRICE_SIDE"):
            compute(False,exits=exits(False,exit_side=PriceSide.BID))

    def test_11_reject_long_stop_and_target_with_ask_basis(self):
        with self.assertRaisesRegex(ValueError,"EXIT_PRICE_SIDE"):
            compute(True,exits=exits(True,exit_side=PriceSide.ASK))

    def test_12_reject_long_stop_at_or_above_bid(self):
        for level in ("1.1000","1.1001"):
            with self.subTest(level=level),self.assertRaisesRegex(
                    ValueError,"LONG_STOP_TARGET"):
                compute(exits=exits(True,stop_price=D(level)))

    def test_13_reject_long_target_at_or_below_bid(self):
        for level in ("1.1000","1.0999"):
            with self.subTest(level=level),self.assertRaisesRegex(
                    ValueError,"LONG_STOP_TARGET"):
                compute(exits=exits(True,target_price=D(level)))

    def test_14_reject_short_stop_at_or_below_ask(self):
        for level in ("1.1002","1.1001"):
            with self.subTest(level=level),self.assertRaisesRegex(
                    ValueError,"SHORT_STOP_TARGET"):
                compute(False,exits=exits(False,stop_price=D(level)))

    def test_15_reject_short_target_at_or_above_ask(self):
        for level in ("1.1002","1.1003"):
            with self.subTest(level=level),self.assertRaisesRegex(
                    ValueError,"SHORT_STOP_TARGET"):
                compute(False,exits=exits(False,target_price=D(level)))

    def test_16_reject_exit_and_cost_versions_not_sim(self):
        for input_ in ("OWNER_APPROVED","LIVE:EXITS","SIM:","SIM:X Y"):
            with self.subTest(v=input_),self.assertRaisesRegex(
                    ValueError,"ONLY_SIM_VERSION"):
                SimExitLevels(input_,D("1.0"),D("1.2"),PriceSide.BID)
            with self.subTest(v=input_),self.assertRaisesRegex(
                    ValueError,"ONLY_SIM_VERSION"):
                SimPerUnitCosts(input_,D(0),D(0),D(0),D(0))

    def test_17_reject_negative_nan_infinite_costs(self):
        for bad in (D("-0.1"),D("NaN"),D("Infinity")):
            for field in ("entry_slippage","exit_slippage","entry_fee","exit_fee"):
                with self.subTest(bad=str(bad),field=field),self.assertRaisesRegex(
                        ValueError,"INVALID_DECIMAL"):
                    costs(**{field:bad})

    def test_18_reject_nonpositive_or_nonfinite_exits(self):
        for bad in (D("0"),D("-1"),D("NaN"),D("Infinity")):
            for field in ("stop_price","target_price"):
                with self.subTest(bad=str(bad),field=field),self.assertRaisesRegex(
                        ValueError,"INVALID_DECIMAL"):
                    exits(**{field:bad})

    def test_19_reject_float_integer_or_string_costs_and_exits(self):
        for bad in (0.0,0,"0.0",None):
            with self.subTest(bad=bad),self.assertRaisesRegex(
                    ValueError,"INVALID_DECIMAL"):
                costs(entry_fee=bad)
            with self.subTest(bad=bad),self.assertRaisesRegex(
                    ValueError,"INVALID_DECIMAL"):
                exits(stop_price=bad)

    def test_20_reject_invalid_quote_side_in_original_model(self):
        with self.assertRaisesRegex(ValueError,"positive non-crossed"):
            quote(bid=D("1.1003"))

    def test_21_reject_unverified_or_blocked_source_quote(self):
        for quality in (QuoteQuality.UNVERIFIED,QuoteQuality.BLOCKED):
            with self.subTest(quality=quality),self.assertRaisesRegex(
                    ValueError,"unverified quote source"):
                compute(quote=quote(quality=quality))

    def test_22_quote_not_first_known_at_decision_rejected(self):
        q=quote(first_known_utc=NOW+timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError,"not yet known"):
            compute(quote=q)

    def test_23_quote_age_is_explicit_and_stale_rejected(self):
        with self.assertRaisesRegex(ValueError,"stale"):
            compute(max_quote_age=timedelta(seconds=20))
        with self.assertRaisesRegex(ValueError,"age policy"):
            compute(max_quote_age=timedelta(0))

    def test_24_non_utc_decision_rejected(self):
        for clock in (NOW.replace(tzinfo=None),NOW.astimezone(
                timezone(timedelta(hours=7)))):
            with self.subTest(clock=clock),self.assertRaisesRegex(
                    ValueError,"UTC"):
                compute(decision_utc=clock)

    def test_25_reject_exit_intents_and_untyped_action(self):
        for action in (ActionIntent.EXIT_LONG,ActionIntent.EXIT_SHORT,"BUY",None):
            with self.subTest(action=action),self.assertRaisesRegex(
                    ValueError,"ENTRY_LONG_OR_SHORT_ONLY"):
                compute(intent=action)

    def test_26_reject_other_pair_or_untyped_quote(self):
        for instrument in ("GBP/USD","EURUSD",""):
            with self.subTest(i=instrument),self.assertRaisesRegex(
                    ValueError,"EXACT_EURUSD_ONLY"):
                compute(instrument=instrument)
        with self.assertRaisesRegex(TypeError,"TYPED_QUOTE"):
            compute(quote={})

    def test_27_reject_inverted_type_for_exit_side_or_plan(self):
        with self.assertRaisesRegex(TypeError,"TYPED_EXIT_SIDE"):
            exits(exit_side="BID")
        with self.assertRaisesRegex(TypeError,"TYPED_SIM_ASSUMPTIONS"):
            compute(exits={})
        with self.assertRaisesRegex(TypeError,"TYPED_SIM_ASSUMPTIONS"):
            compute(costs={})

    def test_28_reject_effective_nonpositive_short_entry_and_long_exit(self):
        with self.assertRaisesRegex(ValueError,"EFFECTIVE_PRICE"):
            compute(False,costs=costs(entry_slippage=D("1.2")))
        with self.assertRaisesRegex(ValueError,"EFFECTIVE_PRICE"):
            compute(True,costs=costs(exit_slippage=D("1.2")))

    def test_29_spread_positive_and_price_units_not_pips_or_lots(self):
        r=compute()
        self.assertEqual(r.reference_spread,D("0.0002"))
        self.assertEqual(r.reference_bid,D("1.1000"))
        self.assertEqual(r.reference_ask,D("1.1002"))
        self.assertEqual(r.risk_plan_version,"SIM:EXIT1")
        self.assertEqual(r.cost_version,"SIM:COSTS1")
        self.assertEqual(r.quote_first_known_claim_utc,FIRST_KNOWN.isoformat())

    def test_30_immutable_receipt_and_deterministic_decimal(self):
        a,b=compute(),compute()
        self.assertEqual(a,b)
        with self.assertRaises(FrozenInstanceError):
            a.action="BUY"

    def test_31_extreme_fee_cannot_be_mistaken_for_profitable_signal(self):
        high_fee=costs(entry_fee=D("2.0"))
        r=compute(costs=high_fee)
        self.assertLess(r.experimental_net_risk_reward,0)
        self.assertEqual(r.action,"NO_SIGNAL")
        self.assertFalse(r.may_publish_buy_sell)
