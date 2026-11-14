"""P0.166 real P0.161/P0.165 SIM candidates + existing bid/ask net R."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal as D
import json
from unittest import TestCase
from unittest.mock import patch

from forex_trading.model import ActionIntent
from forex_trading.quotes import PriceSide, Quote, QuoteQuality
from mfx_research.bidask_cost_aware_sim_risk import SimExitLevels, SimPerUnitCosts
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    read_mfx_confirmed_b2s2_v2,
)
from mfx_research.option_b_v2_bidask_replay_bridge import (
    SimRiskBundle, price_option_b_v2_replay, verify_option_b_v2_risk_replay,
)
from test_mfx_p165_option_b_v2_chronological_replay import (
    snapshot, future,
)


def bundle(s, **kwargs):
    last = s.bars.trigger_m15[-1]
    mid = last.close
    long = s.rule_id == "B2"
    raw = {
        "quote": Quote(
            provider=last.observation.provider_id,
            source_revision="SIM:READONLY_RISK_REV1",
            event_time_utc=last.key.bar_end_utc,
            first_known_utc=last.first_known_utc,
            bid=mid-D("0.0001"), ask=mid+D("0.0001"),
            quality=QuoteQuality.VERIFIED,
        ),
        "exits": SimExitLevels(
            version="SIM:MANUAL_HYPOTHETICAL_EXITS",
            stop_price=(mid-D("0.002") if long else mid+D("0.002")),
            target_price=(mid+D("0.004") if long else mid-D("0.004")),
            exit_side=PriceSide.BID if long else PriceSide.ASK,
        ),
        "costs": SimPerUnitCosts(
            version="SIM:EXPLICIT_PRICE_UNITS",
            entry_slippage=D("0.00005"), exit_slippage=D("0.00005"),
            entry_fee=D("0.00002"), exit_fee=D("0.00003"),
        ),
        "max_quote_age": timedelta(seconds=5),
    }
    raw.update(kwargs)
    return SimRiskBundle(**raw)


def price(snaps, bundles):
    return price_option_b_v2_replay(
        snaps, bundles, read_mfx_confirmed_b2s2_v2(),
    )


class OptionBV2BidAskReplayBridgeTests(TestCase):
    def test_01_B2_right_confirmed_to_ask_entry_bid_exit(self):
        s=snapshot("B2")
        out=price((s,), (bundle(s),))
        r=out.steps[0].economics
        self.assertIsNotNone(r)
        self.assertIs(r.intent, ActionIntent.ENTRY_LONG)
        self.assertIs(r.entry_side, PriceSide.ASK)
        self.assertIs(r.exit_side, PriceSide.BID)
        self.assertGreater(r.experimental_net_risk_reward, D(0))
        self.assertEqual(out.simulated_economic_evaluations, 1)
        self.assertEqual((out.action,out.stage),("NO_SIGNAL","UNVERIFIED"))

    def test_02_S2_right_confirmed_to_bid_entry_ask_exit(self):
        s=snapshot("S2")
        out=price((s,), (bundle(s),))
        r=out.steps[0].economics
        self.assertIs(r.intent, ActionIntent.ENTRY_SHORT)
        self.assertIs(r.entry_side, PriceSide.BID)
        self.assertIs(r.exit_side, PriceSide.ASK)
        self.assertGreater(r.experimental_net_risk_reward,D(0))

    def test_03_two_separate_events_price_both_replay_directions(self):
        a=snapshot("B2")
        b=future(snapshot("S2"))
        report=price((a,b),(bundle(a),bundle(b)))
        self.assertEqual(report.simulated_economic_evaluations,2)
        self.assertEqual(report.replay.distinct_event_windows,2)
        self.assertTrue(verify_option_b_v2_risk_replay(report))
        self.assertNotEqual(report.steps[0].risk_input_sha256,
                            report.steps[1].risk_input_sha256)

    def test_04_exact_duplicate_price_bundle_reuses_first_risk(self):
        s=snapshot()
        repeat=replace(s,decision_utc=s.decision_utc+timedelta(seconds=1))
        b=bundle(s)
        out=price((s,repeat),(b,b))
        self.assertEqual(out.simulated_economic_evaluations,1)
        self.assertEqual(out.duplicate_economic_evaluations_suppressed,1)
        self.assertEqual(out.steps[1].status,
                         "DUPLICATE_SIM_EVENT_NOT_REPRICED")
        self.assertIs(out.steps[0].economics,out.steps[1].economics)

    def test_05_same_event_changed_spread_refused(self):
        s=snapshot()
        repeat=replace(s,decision_utc=s.decision_utc+timedelta(seconds=1))
        b=bundle(s)
        q=replace(b.quote,ask=b.quote.ask+D("0.0001"))
        with self.assertRaisesRegex(ValueError,"REPRICE_OR_COST_REVISION"):
            price((s,repeat),(b,replace(b,quote=q)))

    def test_06_same_event_changed_fee_refused(self):
        s=snapshot()
        repeat=replace(s,decision_utc=s.decision_utc+timedelta(seconds=1))
        b=bundle(s)
        changed=replace(b,costs=replace(
            b.costs,entry_fee=b.costs.entry_fee+D("0.00001")))
        with self.assertRaisesRegex(ValueError,"REPRICE_OR_COST_REVISION"):
            price((s,repeat),(b,changed))

    def test_07_missing_risk_bundle_still_no_signal(self):
        s=snapshot("B2")
        out=price((s,),(None,))
        self.assertEqual(out.simulated_economic_evaluations,0)
        self.assertEqual(out.no_economic_bundle_snapshots,1)
        self.assertIsNone(out.steps[0].economics)
        self.assertFalse(out.may_publish_buy_sell)

    def test_08_no_pattern_cannot_generate_hypothetical_risk(self):
        s=snapshot("B2")
        s=replace(s,bars=replace(s.bars,daily=s.bars.daily[:4]))
        no_r=price((s,),(None,))
        self.assertEqual(no_r.no_pattern_snapshots,1)
        self.assertIsNone(no_r.steps[0].economics)
        with self.assertRaisesRegex(ValueError,"NO_COMPUTED_PATTERN"):
            price((s,),(bundle(s),))

    def test_09_unlicensed_named_real_provider_quote_denied(self):
        s=snapshot()
        b=bundle(s)
        with self.assertRaisesRegex(ValueError,"SIM_CLAIMED_QUOTE_ONLY"):
            price((s,),(replace(b,quote=replace(
                b.quote,provider="REAL:MARKET")),))

    def test_10_different_sim_provider_quote_denied(self):
        s=snapshot()
        b=bundle(s)
        with self.assertRaisesRegex(ValueError,"QUOTE_PROVIDER_MISMATCH"):
            price((s,),(replace(b,quote=replace(
                b.quote,provider="SIM:OTHER")),))

    def test_11_future_first_known_quote_denied(self):
        s=snapshot()
        b=bundle(s)
        q=replace(b.quote,first_known_utc=s.decision_utc+timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError,"NONCAUSAL_JOIN"):
            price((s,),(replace(b,quote=q),))

    def test_12_quote_before_closed_M15_denied(self):
        s=snapshot()
        b=bundle(s)
        q=replace(b.quote,event_time_utc=b.quote.event_time_utc-
                  timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError,"NONCAUSAL_JOIN"):
            price((s,),(replace(b,quote=q),))

    def test_13_sim_mid_must_stay_inside_same_quote_spread(self):
        s=snapshot()
        b=bundle(s)
        q=replace(b.quote,bid=b.quote.ask,
                  ask=b.quote.ask+D("0.0001"))
        with self.assertRaisesRegex(ValueError,"MID_OUTSIDE"):
            price((s,),(replace(b,quote=q),))

    def test_14_stale_quote_requires_explicit_fresh_age_budget(self):
        s=snapshot()
        b=bundle(s)
        with self.assertRaisesRegex(ValueError,"stale"):
            price((s,),(replace(b,max_quote_age=timedelta(
                microseconds=1)),))

    def test_15_exit_side_long_short_must_be_correct(self):
        for rule in ("B2","S2"):
            s=snapshot(rule)
            b=bundle(s)
            other=PriceSide.ASK if rule=="B2" else PriceSide.BID
            with self.subTest(rule=rule), self.assertRaisesRegex(
                ValueError,"EXIT_PRICE_SIDE_MISMATCH"):
                price((s,),(replace(b,exits=replace(
                    b.exits,exit_side=other)),))

    def test_16_more_slippage_and_fee_reduces_net_rr_both_sides(self):
        for rule in ("B2","S2"):
            s=snapshot(rule)
            normal=bundle(s)
            bad=replace(normal,costs=replace(
                normal.costs,entry_fee=D("0.0004"),
                exit_slippage=D("0.0004")))
            a=price((s,),(normal,)).steps[0].economics
            b=price((s,),(bad,)).steps[0].economics
            with self.subTest(rule=rule):
                self.assertGreater(
                    b.net_risk_quote_currency_per_base_unit,
                    a.net_risk_quote_currency_per_base_unit)
                self.assertLess(b.experimental_net_risk_reward,
                                a.experimental_net_risk_reward)

    def test_17_wrong_bundle_alignment_rejected(self):
        s=snapshot()
        for k in ((),(bundle(s),None),[bundle(s)]):
            with self.subTest(k=str(type(k))),self.assertRaisesRegex(
                ValueError,"ONE_RISK_BUNDLE"):
                price_option_b_v2_replay(
                    (s,),k,read_mfx_confirmed_b2s2_v2())

    def test_18_wrong_bundle_type_rejected(self):
        s=snapshot()
        with self.assertRaisesRegex(TypeError,"SIM_RISK_BUNDLE_OR_NONE"):
            price((s,),({"quote": "fake"},))

    def test_19_no_approval_forged_policy_rejected_by_p165(self):
        s=snapshot()
        fake=replace(read_mfx_confirmed_b2s2_v2(),live_signals_allowed=True)
        with self.assertRaisesRegex(ValueError,"EXACT_UNAPPROVED"):
            price_option_b_v2_replay((s,),(bundle(s),),fake)

    def test_20_tampered_replay_counts_risk_values_or_rights_denied(self):
        s=snapshot()
        r=price((s,),(bundle(s),))
        for name,value in (
            ("risk_chain_sha256","0"*64),
            ("simulated_economic_evaluations",2),
            ("may_trade",True),("licensed_source_verified",True),
            ("action","BUY"),("real_out_of_sample_qualified",True),
        ):
            with self.subTest(name=name),self.assertRaisesRegex(
                ValueError,"CHAIN_OR_RIGHTS_DRIFT"):
                verify_option_b_v2_risk_replay(replace(r,**{name:value}))
        damaged=replace(r.steps[0],economics=replace(
            r.steps[0].economics,experimental_net_risk_reward=D(99)))
        with self.assertRaisesRegex(ValueError,"CHAIN_OR_RIGHTS_DRIFT"):
            verify_option_b_v2_risk_replay(replace(r,steps=(damaged,)))

    def test_21_public_record_redacts_all_price_strategy_and_hash(self):
        a=snapshot("B2"); b=future(snapshot("S2"))
        r=price((a,b),(bundle(a),bundle(b)))
        public=json.dumps(r.as_safe_record(),sort_keys=True)
        for forbidden in (
            "BUY","SELL","B2","S2","1.1017","1.1995",
            '"bid":', '"ask":', "net_risk", "net_reward","risk_chain_sha256",
            "risk_input_sha256","source_revision","event_identity"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,public)
        self.assertFalse(r.may_publish_buy_sell)
        self.assertFalse(r.may_trade)
        self.assertEqual((r.provider_requests,r.drive_market_writes,
                          r.broker_orders),(0,0,0))

    def test_22_deterministic_repeat_and_verification(self):
        s=snapshot()
        a=price((s,),(bundle(s),))
        b=price((s,),(bundle(s),))
        self.assertEqual(a,b)
        self.assertEqual(a.risk_chain_sha256,b.risk_chain_sha256)
        self.assertTrue(verify_option_b_v2_risk_replay(a))

    def test_23_no_vendor_cloud_broker_io_called(self):
        s=snapshot()
        with patch(
            "mfx_research.option_b_v2_bidask_replay_bridge."
            "evaluate_cost_aware_sim_risk",
            wraps=__import__(
                "mfx_research.bidask_cost_aware_sim_risk",
                fromlist=["evaluate_cost_aware_sim_risk"],
            ).evaluate_cost_aware_sim_risk,
        ) as evaluate:
            result=price((s,),(bundle(s),))
            self.assertEqual(evaluate.call_count,1)
        self.assertEqual((result.provider_requests,result.drive_market_writes,
                          result.broker_orders),(0,0,0))

    def test_24_invalid_bundle_constructor_denied(self):
        s=snapshot()
        b=bundle(s)
        for kw in (
            {"quote":{}},{"exits":{}},{"costs":{}},
            {"max_quote_age":timedelta(0)},
            {"max_quote_age":"5 seconds"},
        ):
            with self.subTest(kw=list(kw)),self.assertRaisesRegex(
                TypeError,"EXACT_TYPED_POSITIVE"):
                replace(b,**kw)

    def test_25_private_risk_not_in_repr_or_mutable(self):
        s=snapshot()
        r=price((s,),(bundle(s),))
        self.assertNotIn("1.101",repr(r))
        self.assertNotIn("experimental_net_risk_reward",repr(r.steps[0]))
        with self.assertRaises(FrozenInstanceError):
            r.action="BUY"

    def test_26_real_source_restated_snapshot_rejected_by_existing_p165(self):
        s=snapshot()
        b=bundle(s)
        revised=replace(s,
            decision_utc=s.decision_utc+timedelta(seconds=1),
            bars=replace(s.bars,daily=(
                replace(s.bars.daily[0],
                        open=s.bars.daily[0].open+D("0.00001")),
            )+s.bars.daily[1:]))
        with self.assertRaisesRegex(ValueError,"RESTATED_OR_DIRECTION_CONFLICT"):
            price((s,revised),(b,b))
