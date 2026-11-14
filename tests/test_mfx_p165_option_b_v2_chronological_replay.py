"""P0.165: real P0.161 Option B v2 computation across causal SIM snapshots."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
from decimal import Decimal
import json
from unittest import TestCase

from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    read_mfx_confirmed_b2s2_v2,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.option_b_v2_chronological_replay import (
    MAX_SNAPSHOTS, OptionBReplaySnapshot, replay_option_b_v2,
    verify_option_b_v2_replay,
)
from test_mfx_v1_p161_option_b_confirmed_b2s2_v2 import inputs


def snapshot(rule="B2", *, extra_seconds=0):
    x = inputs(rule)
    return OptionBReplaySnapshot(
        rule_id=rule, bars=x["bars"],
        confirmed_m15_history=x["confirmed_m15_history"],
        decision_utc=x["decision_utc"]+timedelta(seconds=extra_seconds),
    )


def shift_bar(bar, delta):
    return replace(
        bar,
        key=replace(
            bar.key,
            bar_start_utc=bar.key.bar_start_utc+delta,
            bar_end_utc=bar.key.bar_end_utc+delta,
        ),
        observation=replace(
            bar.observation,
            first_known_utc=bar.observation.first_known_utc+delta,
            retrieved_at_utc=bar.observation.retrieved_at_utc+delta,
        ),
        first_known_utc=bar.first_known_utc+delta,
    )


def future(snap, *, days=1):
    delta=timedelta(days=days)
    b=snap.bars
    fresh=replace(
        b,
        daily=tuple(shift_bar(x,delta) for x in b.daily),
        four_hour=tuple(shift_bar(x,delta) for x in b.four_hour),
        hourly=tuple(shift_bar(x,delta) for x in b.hourly),
        micro_seed_m15=tuple(shift_bar(x,delta) for x in b.micro_seed_m15),
        trigger_m15=tuple(shift_bar(x,delta) for x in b.trigger_m15),
    )
    return replace(
        snap, bars=fresh,
        confirmed_m15_history=tuple(
            shift_bar(x,delta) for x in snap.confirmed_m15_history),
        decision_utc=snap.decision_utc+delta,
    )


def change_bars(snap, *, field="open"):
    b=snap.bars
    old=b.daily[0]
    adjusted=replace(old, **{field:getattr(old,field)+Decimal("0.00001")})
    return replace(snap,bars=replace(b,daily=(adjusted,)+b.daily[1:]))


def replay(*snapshots):
    return replay_option_b_v2(tuple(snapshots),
                              read_mfx_confirmed_b2s2_v2())


class OptionBV2ChronologicalReplayTests(TestCase):
    def test_01_real_p161_B2_private_buy_only(self):
        out=replay(snapshot("B2"))
        self.assertIs(out.steps[0].computed.experimental_action,
                      CandidateAction.BUY)
        self.assertEqual(out.action,"NO_SIGNAL")
        self.assertEqual(out.stage,"UNVERIFIED")
        self.assertFalse(out.may_publish_buy_sell)

    def test_02_real_p161_S2_private_sell_only(self):
        out=replay(snapshot("S2"))
        self.assertIs(out.steps[0].computed.experimental_action,
                      CandidateAction.SELL)
        self.assertFalse(out.may_trade)

    def test_03_two_separate_chronological_source_windows(self):
        first=snapshot("B2")
        later=future(snapshot("S2"))
        out=replay(first,later)
        self.assertEqual(out.snapshots_checked,2)
        self.assertEqual(out.distinct_event_windows,2)
        self.assertEqual(out.repeated_windows_suppressed,0)
        self.assertNotEqual(out.steps[0].event_identity_sha256,
                            out.steps[1].event_identity_sha256)
        self.assertTrue(verify_option_b_v2_replay(out))

    def test_04_identical_event_replay_suppressed_once(self):
        initial=snapshot()
        repeated=replace(initial,decision_utc=initial.decision_utc+
                         timedelta(seconds=1))
        out=replay(initial,repeated)
        self.assertEqual((out.snapshots_checked,out.distinct_event_windows,
                          out.repeated_windows_suppressed),(2,1,1))
        self.assertFalse(out.steps[0].duplicate_suppressed)
        self.assertTrue(out.steps[1].duplicate_suppressed)
        self.assertEqual(out.steps[0].source_content_sha256,
                         out.steps[1].source_content_sha256)

    def test_05_price_changed_for_same_event_cannot_replace_prior(self):
        initial=snapshot()
        replayed=change_bars(replace(
            initial,decision_utc=initial.decision_utc+timedelta(seconds=1)))
        with self.assertRaisesRegex(ValueError,"RESTATED_OR_DIRECTION_CONFLICT"):
            replay(initial,replayed)

    def test_06_opposite_rule_on_same_source_event_conflicts(self):
        b2=snapshot("B2")
        s2=snapshot("S2",extra_seconds=1)
        with self.assertRaisesRegex(ValueError,"RESTATED_OR_DIRECTION_CONFLICT"):
            replay(b2,s2)

    def test_07_replay_decision_out_of_order_denied(self):
        first=snapshot()
        later=future(snapshot("S2"))
        with self.assertRaisesRegex(ValueError,"STRICT_CHRONOLOGICAL"):
            replay(later,first)

    def test_08_duplicate_decision_timestamp_denied(self):
        first=snapshot()
        with self.assertRaisesRegex(ValueError,"STRICT_CHRONOLOGICAL"):
            replay(first,first)

    def test_09_later_decision_cannot_rollback_trigger_window(self):
        first=future(snapshot("B2"))
        old=snapshot("S2")
        old=replace(old,decision_utc=first.decision_utc+timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError,"TRIGGER_WINDOW_REPLAY_ROLLBACK"):
            replay(first,old)

    def test_10_future_known_data_is_rejected_by_existing_p161(self):
        snap=snapshot()
        trigger=snap.bars.trigger_m15
        latest=replace(trigger[-1],
                       first_known_utc=snap.decision_utc+timedelta(seconds=1))
        corrupted=replace(snap,bars=replace(
            snap.bars,trigger_m15=(trigger[0],latest)))
        with self.assertRaises(ValueError):
            replay(corrupted)

    def test_11_unapproved_policy_forgery_rejected(self):
        fake=replace(read_mfx_confirmed_b2s2_v2(),live_signals_allowed=True)
        with self.assertRaisesRegex(ValueError,"EXACT_UNAPPROVED"):
            replay_option_b_v2((snapshot(),),fake)

    def test_12_non_UTC_and_naive_decision_rejected(self):
        initial=snapshot()
        for utc in (
            initial.decision_utc.replace(tzinfo=None),
            initial.decision_utc.astimezone(timezone(timedelta(hours=7))),
        ):
            with self.subTest(utc=utc), self.assertRaisesRegex(
                ValueError,"EXACT_UTC"):
                replay(replace(initial,decision_utc=utc))

    def test_13_wrong_snapshot_container_and_nonempty_bound(self):
        for value in ([],(),(snapshot(),)*(MAX_SNAPSHOTS+1),
                      (snapshot(),object())):
            with self.subTest(k=type(value)),self.assertRaisesRegex(
                ValueError,"TYPED_BOUNDED"):
                replay_option_b_v2(value,read_mfx_confirmed_b2s2_v2())

    def test_14_read_only_replay_does_not_accept_real_provider(self):
        snap=snapshot()
        a=snap.bars.daily
        replaced=replace(a[0],
            observation=replace(a[0].observation,provider_id="REAL:SOURCE"))
        corrupt=replace(snap,bars=replace(snap.bars,daily=(replaced,)+a[1:]))
        with self.assertRaises(ValueError):
            replay(corrupt)

    def test_15_M15_history_gap_fails_existing_p161_causal_guard(self):
        snap=snapshot()
        history=list(snap.confirmed_m15_history)
        sample=history[2]
        history[2]=replace(
            sample,key=replace(
                sample.key,
                bar_start_utc=sample.key.bar_start_utc+timedelta(minutes=1),
                bar_end_utc=sample.key.bar_end_utc+timedelta(minutes=1),
            ))
        with self.assertRaises(ValueError):
            replay(replace(snap,confirmed_m15_history=tuple(history)))

    def test_16_repeat_deterministic_chain_and_reverification(self):
        a=replay(snapshot(),future(snapshot("S2")))
        b=replay(snapshot(),future(snapshot("S2")))
        self.assertEqual(a,b)
        self.assertEqual(a.chain_sha256,b.chain_sha256)
        self.assertEqual(len(a.chain_sha256),64)
        self.assertTrue(verify_option_b_v2_replay(a))

    def test_17_mutated_chain_counts_and_authority_denied(self):
        out=replay(snapshot())
        for kw in (
            {"chain_sha256":"0"*64},
            {"snapshots_checked":99},
            {"distinct_event_windows":0},
            {"numeric_policy_owner_approved":True},
            {"action":"BUY"},
            {"may_trade":True},
        ):
            with self.subTest(kw=kw),self.assertRaisesRegex(
                ValueError,"REPLAY_CHAIN_OR_AUTHORITY_DRIFT"):
                verify_option_b_v2_replay(replace(out,**kw))

    def test_18_public_record_has_no_internal_direction_price_or_digest(self):
        out=replay(snapshot("B2"),future(snapshot("S2")))
        safe=json.dumps(out.as_safe_record(),sort_keys=True)
        for hidden in ("BUY","SELL","B2","S2","1.1017","1.1995",
                       "event_identity_sha256","chain_sha256",
                       "experimental_action","known_micro_level"):
            self.assertNotIn(hidden,safe)
        self.assertFalse(out.as_safe_record()["real_oos_qualified"])
        self.assertFalse(out.as_safe_record()["source_license_verified"])

    def test_19_do_not_report_trades_licensed_quotes_or_source_rights(self):
        out=replay(snapshot("B2"),future(snapshot("S2")))
        self.assertEqual((out.broker_orders,out.provider_calls,
                          out.drive_market_writes),(0,0,0))
        self.assertTrue(out.simulated_only)
        self.assertFalse(out.numeric_policy_owner_approved)
        self.assertFalse(out.publisher_first_known_verified)
        self.assertFalse(out.native_d1_revision_qualified)

    def test_20_mixed_source_stream_across_windows_rejected(self):
        first=snapshot()
        second=future(snapshot("S2"))
        # Source identity is different even when each local row is valid.
        def replace_provider(bar):
            return replace(bar,observation=replace(
                bar.observation,provider_id="SIM:ALTERNATE_PROVIDER"))
        b=second.bars
        altered=replace(
            b,
            daily=tuple(map(replace_provider,b.daily)),
            four_hour=tuple(map(replace_provider,b.four_hour)),
            hourly=tuple(map(replace_provider,b.hourly)),
            micro_seed_m15=tuple(map(replace_provider,b.micro_seed_m15)),
            trigger_m15=tuple(map(replace_provider,b.trigger_m15)),
        )
        changed=replace(second,bars=altered,
            confirmed_m15_history=tuple(
                map(replace_provider,second.confirmed_m15_history)))
        with self.assertRaisesRegex(ValueError,"CROSS_SOURCE_STREAM_DRIFT"):
            replay(first,changed)

    def test_21_private_fields_not_in_repr_or_mutable(self):
        out=replay(snapshot())
        self.assertNotIn("experimental_action",repr(out))
        self.assertNotIn("1.1017",repr(out))
        with self.assertRaises(FrozenInstanceError):
            out.action="BUY"
        with self.assertRaises(FrozenInstanceError):
            out.steps[0].chain_sha256="fake"

    def test_22_only_typed_nonempty_replay_can_be_verified(self):
        for r in (None,{},[]):
            with self.subTest(r=r),self.assertRaises(TypeError):
                verify_option_b_v2_replay(r)
