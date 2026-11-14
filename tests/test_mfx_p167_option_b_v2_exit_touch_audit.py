"""P0.167: closed M5 SIM BID/ASK stop vs target *touch* and ambiguity."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal as D
import json
from unittest import TestCase

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, MarketBar, MarketBarKey, Observation,
    SourceQuality, Timeframe,
)
from mfx_research.option_b_v2_exit_touch_audit import (
    AMBIGUOUS, NO_PATH, NO_TOUCH, OPEN_STOP, OPEN_TARGET, STOP, TARGET,
    MAX_M5_BARS_PER_WINDOW, audit_option_b_v2_sim_exit_touches,
    verify_option_b_v2_sim_exit_touch_audit,
)
from test_mfx_p165_option_b_v2_chronological_replay import snapshot, future
from test_mfx_p166_option_b_v2_bidask_replay_bridge import bundle, price


def case(rule="B2"):
    s = snapshot(rule)
    return s, price((s,), (bundle(s),))


def make_bar(s, outcome="none", *, offset=0):
    """Only closed and later-than-entry simulated M5; no vendor quote/fill."""
    anchor = s.bars.trigger_m15[-1]
    start = anchor.key.bar_end_utc + timedelta(minutes=5 * (offset + 1))
    end = start + timedelta(minutes=5)
    q = bundle(s).quote
    entry_side = BarSide.BID if s.rule_id == "B2" else BarSide.ASK
    price_ref = q.bid if s.rule_id == "B2" else q.ask
    if outcome == "none":
        low, high = price_ref - D("0.0001"), price_ref + D("0.0001")
    elif outcome == "stop":
        low, high = (price_ref - D("0.0021"), price_ref + D("0.0001")
                     ) if s.rule_id == "B2" else (
                         price_ref - D("0.0001"), price_ref + D("0.0021"))
    elif outcome == "target":
        low, high = (price_ref - D("0.0001"), price_ref + D("0.0042")
                     ) if s.rule_id == "B2" else (
                         price_ref - D("0.0042"), price_ref + D("0.0001"))
    elif outcome == "both":
        low, high = (price_ref - D("0.0021"), price_ref + D("0.0042")
                     ) if s.rule_id == "B2" else (
                         price_ref - D("0.0042"), price_ref + D("0.0021"))
    else:
        raise ValueError("invalid local fixture")
    published = end + timedelta(seconds=1)
    obs = Observation(
        provider_id=anchor.observation.provider_id,
        stream_id=anchor.observation.stream_id,
        endpoint="SIM:M5_TEST_ONLY",
        revision_id="SIM:EXIT_PATH_1",
        raw_sha256="a" * 64,
        first_known_utc=published,
        retrieved_at_utc=published,
        source_timezone_policy="SIM:UTC",
        license_scope_claim="SIM:EXPLICIT_NO_VENDOR_RIGHTS",
    )
    return MarketBar(
        key=MarketBarKey(
            instrument_version=anchor.key.instrument_version,
            timeframe=Timeframe.M5,
            bar_start_utc=start, bar_end_utc=end,
            calendar_version=anchor.key.calendar_version,
            aggregation_version=anchor.key.aggregation_version,
            side=entry_side,
        ),
        observation=obs, revision_number=1,
        first_known_utc=published,
        open=price_ref, high=high, low=low, close=price_ref,
        lifecycle=BarLifecycle.CLOSED,
        coverage=BarCoverage.COMPLETE,
        quality=SourceQuality.VERIFIED,
    )


def audit(s, prior, path):
    return audit_option_b_v2_sim_exit_touches(
        prior, (tuple(path),),
        evaluation_utc=s.decision_utc + timedelta(hours=2),
    )


class P167BidAskExitTouchTests(TestCase):
    def test_01_b2_long_bid_stop_only(self):
        s,r = case()
        x=audit(s,r,(make_bar(s,"stop"),))
        self.assertEqual(x.steps[0].status,STOP)
        self.assertEqual(x.stop_only,1)
        self.assertFalse(x.actual_fill_or_order_known)
        self.assertEqual(x.action,"NO_SIGNAL")

    def test_02_s2_short_ask_stop_only(self):
        s,r = case("S2")
        x=audit(s,r,(make_bar(s,"stop"),))
        self.assertEqual(x.steps[0].status,STOP)
        self.assertEqual(x.stop_only,1)

    def test_03_b2_target_only_is_not_a_real_fill(self):
        s,r=case()
        x=audit(s,r,(make_bar(s,"target"),))
        self.assertEqual(x.steps[0].status,TARGET)
        self.assertEqual(x.target_only,1)
        self.assertFalse(x.realized_profit_verified)

    def test_04_s2_target_only_is_not_a_real_fill(self):
        s,r=case("S2")
        x=audit(s,r,(make_bar(s,"target"),))
        self.assertEqual(x.steps[0].status,TARGET)
        self.assertEqual(x.target_only,1)

    def test_05_both_levels_same_m5_long_is_ambiguous(self):
        s,r=case()
        x=audit(s,r,(make_bar(s,"both"),))
        self.assertEqual(x.steps[0].status,AMBIGUOUS)
        self.assertEqual(x.same_bar_ambiguous,1)
        self.assertEqual(x.target_only,0)
        self.assertEqual(x.stop_only,0)

    def test_06_both_levels_same_m5_short_is_ambiguous(self):
        s,r=case("S2")
        x=audit(s,r,(make_bar(s,"both"),))
        self.assertEqual(x.steps[0].status,AMBIGUOUS)
        self.assertEqual(x.same_bar_ambiguous,1)

    def test_07_no_touch_does_not_claim_closed_trade(self):
        s,r=case()
        x=audit(s,r,(make_bar(s),))
        self.assertEqual(x.steps[0].status,NO_TOUCH)
        self.assertEqual(x.no_touch,1)
        self.assertFalse(x.actual_fill_or_order_known)

    def test_08_empty_supplied_path_is_not_no_hit(self):
        s,r=case()
        x=audit(s,r,())
        self.assertEqual(x.steps[0].status,NO_PATH)
        self.assertEqual(x.missing_future_path,1)
        self.assertEqual(x.no_touch,0)

    def test_09_path_detects_first_touch_and_keeps_trailing_bars(self):
        s,r=case()
        x=audit(s,r,(
            make_bar(s,"none",offset=0),
            make_bar(s,"stop",offset=1),
            make_bar(s,"target",offset=2),
        ))
        self.assertEqual(x.steps[0].first_touch_m5_bar_index,1)
        self.assertEqual(x.steps[0].status,STOP)
        self.assertEqual(x.steps[0].inspected_closed_m5_bars,3)

    def test_10_no_gap_in_future_m5_series(self):
        s,r=case()
        with self.assertRaisesRegex(ValueError,"NONCAUSAL"):
            audit(s,r,(make_bar(s,offset=0),make_bar(s,offset=2)))

    def test_11_wrong_bidask_exit_side_denied(self):
        for side in ("B2","S2"):
            s,r=case(side)
            b=make_bar(s)
            other=BarSide.ASK if side=="B2" else BarSide.BID
            with self.subTest(side=side),self.assertRaisesRegex(
                ValueError,"NONCAUSAL"):
                audit(s,r,(replace(b,key=replace(
                    b.key,side=other)),))

    def test_12_incomplete_or_unverified_bar_denied(self):
        s,r=case()
        b=make_bar(s)
        for bad in (
            replace(b,lifecycle=BarLifecycle.OPEN),
            replace(b,coverage=BarCoverage.PARTIAL),
            replace(b,quality=SourceQuality.UNVERIFIED),
        ):
            with self.subTest(bad=str(bad.quality)),self.assertRaisesRegex(
                ValueError,"NONCAUSAL"):
                audit(s,r,(bad,))

    def test_13_real_provider_cannot_be_laundered_as_sim(self):
        s,r=case()
        b=make_bar(s)
        injected=replace(b,observation=replace(
            b.observation,provider_id="REAL:PROVIDER"))
        with self.assertRaisesRegex(ValueError,"NONCAUSAL"):
            audit(s,r,(injected,))

    def test_14_future_first_known_unavailable_at_audit_time(self):
        s,r=case()
        b=make_bar(s)
        late=replace(b,
            observation=replace(
                b.observation,
                first_known_utc=s.decision_utc+timedelta(days=1),
                retrieved_at_utc=s.decision_utc+timedelta(days=1)),
            first_known_utc=s.decision_utc+timedelta(days=1),
        )
        with self.assertRaisesRegex(ValueError,"NONCAUSAL"):
            audit(s,r,(late,))

    def test_15_future_retrieval_unavailable_at_audit_time(self):
        s,r=case()
        b=make_bar(s)
        changed=replace(b,observation=replace(
            b.observation,retrieved_at_utc=s.decision_utc+timedelta(days=1)))
        with self.assertRaisesRegex(ValueError,"NONCAUSAL"):
            audit(s,r,(changed,))

    def test_16_wrong_m5_start_before_entry_rejected(self):
        s,r=case()
        b=make_bar(s)
        earlier=b.key.bar_start_utc-timedelta(minutes=15)
        changed=replace(b,key=replace(b.key,
            bar_start_utc=earlier,
            bar_end_utc=earlier+timedelta(minutes=5)))
        with self.assertRaisesRegex(ValueError,"NONCAUSAL"):
            audit(s,r,(changed,))

    def test_17_wrong_tf_denied(self):
        s,r=case()
        b=make_bar(s)
        changed=replace(b,key=replace(b.key,timeframe=Timeframe.M15))
        with self.assertRaisesRegex(ValueError,"NONCAUSAL"):
            audit(s,r,(changed,))

    def test_18_typed_bounded_path_and_count_required(self):
        s,r=case()
        b=make_bar(s)
        for p in ([], ((b,), (b,)), ((object(),),),
                  ((b,)*(MAX_M5_BARS_PER_WINDOW+1),)):
            with self.subTest(k=type(p)),self.assertRaisesRegex(
                ValueError,"BOUNDED_TYPED"):
                audit_option_b_v2_sim_exit_touches(
                    r,p,evaluation_utc=s.decision_utc+timedelta(hours=2))

    def test_19_exact_utc_and_later_audit_clock(self):
        s,r=case()
        b=make_bar(s)
        for now in (s.decision_utc.replace(tzinfo=None),):
            with self.assertRaisesRegex(ValueError,"EXACT_UTC"):
                audit_option_b_v2_sim_exit_touches(
                    r,((b,),),evaluation_utc=now)
        with self.assertRaisesRegex(ValueError,"MUST_FOLLOW_ENTRY"):
            audit_option_b_v2_sim_exit_touches(
                r,((b,),),evaluation_utc=s.decision_utc)

    def test_20_report_reproducible_and_tampering_denied(self):
        s,r=case()
        a=audit(s,r,(make_bar(s,"both"),))
        b=audit(s,r,(make_bar(s,"both"),))
        self.assertEqual(a,b)
        self.assertTrue(verify_option_b_v2_sim_exit_touch_audit(a))
        for kw in (
            {"chain_sha256":"0"*64},
            {"same_bar_ambiguous":0},
            {"may_trade":True},
            {"source_license_verified":True},
            {"action":"SELL"},
            {"realized_profit_verified":True},
        ):
            with self.subTest(kw=kw),self.assertRaisesRegex(
                ValueError,"CHAIN_OR_RIGHTS_DRIFT"):
                verify_option_b_v2_sim_exit_touch_audit(replace(a,**kw))

    def test_21_source_price_tampering_denied_during_reverification(self):
        s,r=case()
        a=audit(s,r,(make_bar(s,"none"),))
        b=make_bar(s,"target")
        with self.assertRaisesRegex(ValueError,"CHAIN_OR_RIGHTS_DRIFT"):
            verify_option_b_v2_sim_exit_touch_audit(replace(a,paths=((b,),)))

    def test_22_public_record_no_price_direction_or_hash(self):
        s,r=case()
        a=audit(s,r,(make_bar(s,"both"),))
        public=json.dumps(a.as_safe_record(),sort_keys=True)
        for forbidden in (
            '"BUY"', '"SELL"', '"B2"', '"S2"', "1.100", "1.200",
            "stop_price", "target_price", "event_sha256",
            "chain_sha256", "private_path_sha256",
        ):
            with self.subTest(f=forbidden):
                self.assertNotIn(forbidden,public)
        self.assertEqual((a.broker_orders,a.provider_requests,
                          a.drive_market_writes),(0,0,0))

    def test_23_no_economic_bundle_skips_outcome_without_path(self):
        s=snapshot()
        r=price((s,),(None,))
        x=audit(s,r,())
        self.assertEqual(x.skipped_not_qualified,1)
        with self.assertRaisesRegex(ValueError,"NO_EXIT_PATH"):
            audit(s,r,(make_bar(s),))

    def test_24_no_duplicate_event_double_outcome(self):
        s=snapshot()
        later=replace(s,decision_utc=s.decision_utc+timedelta(seconds=1))
        q=bundle(s)
        r=price((s,later),(q,q))
        b=make_bar(s,"stop")
        x=audit_option_b_v2_sim_exit_touches(
            r,((b,),()),
            evaluation_utc=s.decision_utc+timedelta(hours=2),
        )
        self.assertEqual(x.stop_only,1)
        self.assertEqual(x.skipped_not_qualified,1)

    def test_25_old_source_identity_mismatch_denied(self):
        s,r=case()
        b=make_bar(s)
        invalid=replace(b,observation=replace(
            b.observation,stream_id="SIM:DIFFERENT_STREAM"))
        with self.assertRaisesRegex(ValueError,"NONCAUSAL"):
            audit(s,r,(invalid,))

    def test_26_immutable_audit_and_no_real_oos(self):
        s,r=case()
        a=audit(s,r,(make_bar(s),))
        with self.assertRaises(FrozenInstanceError):
            a.action="BUY"
        self.assertFalse(a.true_oos_qualified)
        self.assertFalse(a.real_bidask_or_tick_data_verified)
        self.assertFalse(a.may_publish_buy_sell)
