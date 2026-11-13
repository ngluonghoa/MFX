"""Cloud-only hermetic B2/S2 SIM closed OHLC -> net R:R composition.

No market provider, archival mutation, real source approval, public BUY/SELL,
broker trading, or licensed economic performance inferred from SIM fixtures.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from forex_trading.model import ActionIntent
from forex_trading.quotes import PriceSide, Quote, QuoteQuality
from mfx_research.bidask_cost_aware_sim_risk import (
    SimExitLevels, SimPerUnitCosts,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p152_sim_signal_risk_vertical_slice import (
    VERSION, review_sim_b2_s2_with_net_risk,
)
from tools.run_a04_p19_causal_context_demo import case_from_closed_bars


def inputs(rule="B2"):
    bars, derivation, parameters = case_from_closed_bars(rule)
    last = bars.trigger_m15[-1]
    close = last.close
    long = rule == "B2"
    quote = Quote(
        provider=last.observation.provider_id,
        source_revision="SIM:IN_MEMORY_QUOTE_REV1",
        event_time_utc=last.key.bar_end_utc,
        first_known_utc=last.first_known_utc,
        bid=close - D("0.0001"), ask=close + D("0.0001"),
        quality=QuoteQuality.VERIFIED,
    )
    exits = SimExitLevels(
        version="SIM:IN_MEMORY_EXIT_PLAN",
        stop_price=(close - D("0.0020") if long
                    else close + D("0.0020")),
        target_price=(close + D("0.0040") if long
                      else close - D("0.0040")),
        exit_side=PriceSide.BID if long else PriceSide.ASK,
    )
    costs = SimPerUnitCosts(
        version="SIM:EXPLICIT_UNIT_COSTS",
        entry_slippage=D("0.00005"),
        exit_slippage=D("0.00005"),
        entry_fee=D("0.00002"),exit_fee=D("0.00003"),
    )
    return {
        "rule_id": rule, "bars": bars, "derivation": derivation,
        "parameters": parameters,
        "decision_utc": last.first_known_utc + timedelta(seconds=1),
        "quote": quote, "exits": exits, "costs": costs,
        "max_quote_age": timedelta(seconds=3),
    }


def run(rule="B2", **kwargs):
    data = inputs(rule)
    data.update(kwargs)
    return review_sim_b2_s2_with_net_risk(**data)


class P152SimB2S2RiskVerticalSliceTests(TestCase):
    def test_01_buy_pattern_then_long_ask_bid_economics(self):
        r=run("B2")
        self.assertIs(r.experimental_pattern,CandidateAction.BUY)
        self.assertEqual(r.pattern.pilot_rule_id,"B2")
        self.assertEqual(r.pattern.classified_output.events[0].entry_long_labels,("B2",))
        self.assertIsNotNone(r.economics)
        self.assertIs(r.economics.intent,ActionIntent.ENTRY_LONG)
        self.assertEqual((r.economics.entry_side,r.economics.exit_side),
                         (PriceSide.ASK,PriceSide.BID))
        self.assertGreater(r.economics.net_risk_quote_currency_per_base_unit,D(0))
        self.assertGreater(r.economics.net_reward_quote_currency_per_base_unit,D(0))
        self.assertEqual(r.cost_evidence_status,"SIM_NET_R_CALCULATED_NOT_EXECUTABLE")

    def test_02_sell_pattern_then_short_bid_ask_economics(self):
        r=run("S2")
        self.assertIs(r.experimental_pattern,CandidateAction.SELL)
        self.assertEqual(r.pattern.classified_output.events[0].entry_short_labels,("S2",))
        self.assertIs(r.economics.intent,ActionIntent.ENTRY_SHORT)
        self.assertEqual((r.economics.entry_side,r.economics.exit_side),
                         (PriceSide.BID,PriceSide.ASK))
        self.assertGreater(r.economics.net_risk_quote_currency_per_base_unit,D(0))
        self.assertGreater(r.economics.net_reward_quote_currency_per_base_unit,D(0))

    def test_03_both_computed_patterns_public_action_never_buy_sell(self):
        for direction in ("B2","S2"):
            with self.subTest(direction=direction):
                r=run(direction)
                self.assertEqual((r.action,r.stage),("NO_SIGNAL","UNVERIFIED"))
                self.assertEqual(r.pattern.action,"NO_SIGNAL")
                self.assertEqual(r.economics.action,"NO_SIGNAL")
                self.assertFalse(r.may_publish_buy_sell)
                self.assertFalse(r.may_trade)
                self.assertEqual(r.broker_orders,0)

    def test_04_frozen_source_and_vendor_gates_remain_unverified(self):
        r=run()
        for flag in ("original_forex_numeric_policy_approved",
                     "live_data_rights_verified","publisher_first_known_attested",
                     "real_bidask_execution_costs_verified","causal_oos_qualified"):
            self.assertFalse(getattr(r,flag),flag)
        self.assertEqual(r.pattern.classified_output.numeric_entry_predicates_approved,0)
        self.assertEqual(
            r.pattern.classified_output.original_b2_s2_source_numeric_obligations_pending,
            36,
        )

    def test_05_pattern_only_without_any_quote_is_valid_but_no_economics(self):
        args=inputs("S2")
        for f in ("quote","exits","costs","max_quote_age"):
            args[f]=None
        r=review_sim_b2_s2_with_net_risk(**args)
        self.assertIs(r.experimental_pattern,CandidateAction.SELL)
        self.assertIsNone(r.economics)
        self.assertEqual(r.cost_evidence_status,
                         "PATTERN_RESEARCH_ONLY_NO_SIM_RISK_BUNDLE")
        self.assertEqual(r.action,"NO_SIGNAL")

    def test_06_partial_bundle_not_permitted(self):
        for missing in ("quote","exits","costs","max_quote_age"):
            data=inputs()
            data[missing]=None
            with self.subTest(missing=missing),self.assertRaisesRegex(
                    ValueError,"EXACT_COMPLETE_SIM_RISK_BUNDLE"):
                review_sim_b2_s2_with_net_risk(**data)

    def test_07_no_pattern_never_generates_hypothetical_trade(self):
        data=inputs()
        old,last=data["bars"].trigger_m15
        data["bars"]=replace(data["bars"],trigger_m15=(
            old,replace(last,close=old.close)))
        r=review_sim_b2_s2_with_net_risk(**data)
        self.assertIs(r.experimental_pattern,CandidateAction.NO_SIGNAL)
        self.assertIsNone(r.economics)
        self.assertEqual(r.cost_evidence_status,"NO_CLOSED_SIM_PATTERN")
        self.assertEqual(r.pattern.classified_output.classified,())
        self.assertEqual(r.pattern.classified_output.events,())
        self.assertEqual(r.action,"NO_SIGNAL")

    def test_08_quote_synthetically_joined_to_exact_trigger(self):
        d=inputs()
        r=run(**{})  # independently reconstruct same synthetic snapshot
        self.assertEqual(r.economics.source_quote_provider_claim,
                         d["bars"].trigger_m15[-1].observation.provider_id)
        self.assertEqual(r.pattern.first_known_utc,
                         d["bars"].trigger_m15[-1].first_known_utc)
        self.assertLessEqual(d["quote"].first_known_utc,d["decision_utc"])

    def test_09_vendor_named_quote_claim_is_never_source_approved(self):
        d=inputs()
        d["quote"]=replace(d["quote"],provider="OANDA")
        with self.assertRaisesRegex(ValueError,"SIM_CLAIMED_QUOTE_ONLY"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_10_foreign_sim_provider_is_rejected(self):
        d=inputs()
        d["quote"]=replace(d["quote"],provider="SIM:OTHER_FEED")
        with self.assertRaisesRegex(ValueError,"QUOTE_PROVIDER_MISMATCH"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_11_non_SIM_revision_is_rejected(self):
        d=inputs()
        d["quote"]=replace(d["quote"],source_revision="LIVE:V9")
        with self.assertRaisesRegex(ValueError,"SIM_CLAIMED_QUOTE_ONLY"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_12_future_first_known_quote_rejected(self):
        d=inputs()
        d["quote"]=replace(d["quote"],
                           first_known_utc=d["decision_utc"]+timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError,"NONCAUSAL_JOIN"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_13_quote_event_before_last_M15_close_rejected(self):
        d=inputs()
        d["quote"]=replace(d["quote"],
                           event_time_utc=d["quote"].event_time_utc-
                           timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError,"NONCAUSAL_JOIN"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_14_quote_cannot_be_known_before_closed_pattern(self):
        d=inputs()
        old=d["quote"]
        d["quote"]=replace(old,first_known_utc=old.event_time_utc)
        with self.assertRaisesRegex(ValueError,"NONCAUSAL_JOIN"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_15_mid_close_must_be_bracketed_by_same_sim_quote(self):
        d=inputs()
        d["quote"]=replace(d["quote"],
                           bid=d["quote"].ask,
                           ask=d["quote"].ask+D("0.0001"))
        with self.assertRaisesRegex(ValueError,"MID_OUTSIDE"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_16_unverified_quote_quality_rejected(self):
        d=inputs()
        d["quote"]=replace(d["quote"],quality=QuoteQuality.UNVERIFIED)
        with self.assertRaisesRegex(ValueError,"SIM_CLAIMED_QUOTE_ONLY"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_17_wrong_s2_exit_side_rejected_by_existing_risk(self):
        d=inputs("S2")
        d["exits"]=replace(d["exits"],exit_side=PriceSide.BID)
        with self.assertRaisesRegex(ValueError,"EXIT_PRICE_SIDE"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_18_wrong_b2_exit_side_rejected_by_existing_risk(self):
        d=inputs("B2")
        d["exits"]=replace(d["exits"],exit_side=PriceSide.ASK)
        with self.assertRaisesRegex(ValueError,"EXIT_PRICE_SIDE"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_19_stale_sim_quote_causes_hard_rejection(self):
        d=inputs()
        d["max_quote_age"]=timedelta(microseconds=1)
        with self.assertRaisesRegex(ValueError,"stale"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_20_unsigned_future_source_cannot_enter_via_M15(self):
        d=inputs()
        old,last=d["bars"].trigger_m15
        fake=replace(last,first_known_utc=d["decision_utc"]+timedelta(seconds=10))
        d["bars"]=replace(d["bars"],trigger_m15=(old,fake))
        with self.assertRaises(ValueError):
            review_sim_b2_s2_with_net_risk(**d)

    def test_21_real_data_injection_into_synthetic_bars_rejected(self):
        d=inputs()
        bars=d["bars"]
        updated=replace(bars.hourly[-1],observation=replace(
            bars.hourly[-1].observation, provider_id="Twelve Data"))
        d["bars"]=replace(bars,hourly=bars.hourly[:-1]+(updated,))
        with self.assertRaisesRegex(ValueError,"REJECT_REAL_MARKET_SOURCE"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_22_quote_spread_widening_degrades_net_rr(self):
        d=inputs()
        base=review_sim_b2_s2_with_net_risk(**d)
        quote=d["quote"]
        d["quote"]=replace(quote,ask=quote.ask+D("0.00015"))
        wide=review_sim_b2_s2_with_net_risk(**d)
        self.assertLess(wide.economics.experimental_net_risk_reward,
                        base.economics.experimental_net_risk_reward)

    def test_23_cost_increase_degrades_both_directions(self):
        for rule in ("B2","S2"):
            d=inputs(rule)
            base=review_sim_b2_s2_with_net_risk(**d)
            cost=d["costs"]
            d["costs"]=replace(cost,entry_fee=cost.entry_fee+D("0.0001"))
            expensive=review_sim_b2_s2_with_net_risk(**d)
            self.assertLess(expensive.economics.experimental_net_risk_reward,
                            base.economics.experimental_net_risk_reward)

    def test_24_research_digest_deterministic_and_price_sensitive(self):
        d=inputs()
        a=review_sim_b2_s2_with_net_risk(**d)
        b=review_sim_b2_s2_with_net_risk(**d)
        self.assertEqual(a.research_fingerprint_sha256,b.research_fingerprint_sha256)
        self.assertEqual(len(a.research_fingerprint_sha256),64)
        q=d["quote"]
        d["quote"]=replace(q,ask=q.ask+D("0.00001"))
        changed=review_sim_b2_s2_with_net_risk(**d)
        self.assertNotEqual(a.research_fingerprint_sha256,
                            changed.research_fingerprint_sha256)

    def test_25_no_pattern_vs_pattern_distinct_digests(self):
        d=inputs()
        a=review_sim_b2_s2_with_net_risk(**d)
        old,last=d["bars"].trigger_m15
        d["bars"]=replace(d["bars"],trigger_m15=(
            old,replace(last,close=old.close)))
        b=review_sim_b2_s2_with_net_risk(**d)
        self.assertNotEqual(a.research_fingerprint_sha256,
                            b.research_fingerprint_sha256)

    def test_26_absent_costs_never_invent_default_risk(self):
        d=inputs()
        for k in ("quote","exits","costs","max_quote_age"):
            d[k]=None
        r=review_sim_b2_s2_with_net_risk(**d)
        self.assertIsNone(r.economics)
        self.assertEqual(r.action,"NO_SIGNAL")

    def test_27_explicit_negative_reward_does_not_emit_alert(self):
        d=inputs()
        close=d["bars"].trigger_m15[-1].close
        d["exits"]=replace(d["exits"],target_price=close+D("0.00005"))
        r=review_sim_b2_s2_with_net_risk(**d)
        self.assertLess(r.economics.net_reward_quote_currency_per_base_unit,D(0))
        self.assertEqual(r.action,"NO_SIGNAL")
        self.assertFalse(r.may_publish_buy_sell)

    def test_28_negative_unsupported_pilot_ids(self):
        for rule in ("B1","S1","FX-B9","B7",None,1):
            d=inputs()
            d["rule_id"]=rule
            with self.subTest(rule=rule),self.assertRaisesRegex(
                    ValueError,"ONLY_B2_S2"):
                review_sim_b2_s2_with_net_risk(**d)

    def test_29_utc_decision_required(self):
        d=inputs()
        d["decision_utc"]=d["decision_utc"].replace(tzinfo=None)
        with self.assertRaisesRegex(ValueError,"UTC"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_30_bad_complete_bundle_rejected(self):
        d=inputs()
        d["quote"]={}
        with self.assertRaisesRegex(TypeError,"TYPED_SIM_RISK_BUNDLE"):
            review_sim_b2_s2_with_net_risk(**d)
        d=inputs()
        d["costs"]={}
        with self.assertRaisesRegex(TypeError,"TYPED_SIM_RISK_BUNDLE"):
            review_sim_b2_s2_with_net_risk(**d)

    def test_31_immutable_but_nested_economics_remain_hypothetical(self):
        r=run()
        self.assertEqual(r.version,VERSION)
        self.assertTrue(r.economics.hypothetical_exit_only)
        with self.assertRaises(FrozenInstanceError):
            r.action="BUY"

    def test_32_zero_external_calls_and_no_broker(self):
        r=run("B2")
        self.assertEqual((r.provider_requests,r.drive_market_cache_writes,
                          r.broker_orders),(0,0,0))
        self.assertEqual((r.economics.provider_requests,
                          r.economics.drive_market_cache_writes,
                          r.economics.broker_orders),(0,0,0))
        self.assertFalse(r.pattern.may_send_buy_sell_or_exit_alert)
