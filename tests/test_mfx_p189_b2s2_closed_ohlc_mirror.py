"""P0.189: end-to-end price-level B2/S2 symmetry, not merely role metadata.

All input bars are invented SIM-only CLOSED OHLC. BOTH sides execute the
actual pinned P161/P160 Option-B-v2 numeric path; no actual market quotes,
approved Forex thresholds, publisher first-known, broker or Drive access.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
import json
from unittest import TestCase

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, MarketBar,
    SourceQuality, Timeframe,
)
from mfx_research.causal_multitf_context import SyntheticMultiTfBars
from mfx_research.confirmed_swings import PivotKind
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    compute_mfx_b2s2_v2_closed_candidate,
    read_mfx_confirmed_b2s2_v2,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p189_b2s2_executable_ohlc_mirror import (
    VERSION, reflect_sim_b2s2_packet, reflect_sim_closed_ohlc,
    verify_executable_b2s2_sim_mirror,
)
from tools.run_a04_p19_causal_context_demo import _make_series
from tools.run_a04_p20_confirmed_swing_demo import case_confirmed

D = Decimal
ANCHORS = (D("1.15"), D("1.20"), D("1.25"))
B2_HISTORY = (
    ("1.1008", "1.1010", "1.1002", "1.1009"),
    ("1.1009", "1.1013", "1.1003", "1.1010"),
    ("1.1010", "1.1011", "1.1004", "1.1010"),
    ("1.1010", "1.1017", "1.1007", "1.1012"),
    ("1.1012", "1.1013", "1.1006", "1.1011"),
    ("1.1011", "1.1014", "1.1007", "1.1012"),
    ("1.1010", "1.1015", "1.1009", "1.1012"),
)
S2_HISTORY = (
    ("1.2001", "1.2006", "1.1998", "1.2000"),
    ("1.2000", "1.2004", "1.1997", "1.1999"),
    ("1.1999", "1.2005", "1.1998", "1.2000"),
    ("1.2000", "1.2004", "1.1995", "1.1998"),
    ("1.1998", "1.2005", "1.1997", "1.1999"),
    ("1.1999", "1.2004", "1.1998", "1.2000"),
    ("1.1999", "1.2001", "1.1996", "1.1998"),
)


def fixture(rule: str) -> tuple:
    bars, _ = case_confirmed(rule)
    history = _make_series(
        Timeframe.M15, B2_HISTORY if rule == "B2" else S2_HISTORY,
    )
    history = history[:-1] + bars.micro_seed_m15
    assert history[-1] == bars.micro_seed_m15[-1]
    asof = bars.trigger_m15[-1].first_known_utc + timedelta(seconds=1)
    return bars, history, read_mfx_confirmed_b2s2_v2(), asof


def reflect_once(rule: str, anchor: Decimal = D("1.15")):
    bars, history, policy, asof = fixture(rule)
    return verify_executable_b2s2_sim_mirror(
        rule, bars, history, policy, asof, anchor=anchor,
    )


def translate_bar(bar: MarketBar, delta: Decimal) -> MarketBar:
    return replace(
        bar, open=bar.open+delta, high=bar.high+delta,
        low=bar.low+delta, close=bar.close+delta,
    )


def translate_case(bars: SyntheticMultiTfBars,
                   history: tuple[MarketBar, ...], delta: Decimal):
    def moving(rows):
        return tuple(translate_bar(x, delta) for x in rows)
    result = SyntheticMultiTfBars(
        daily=moving(bars.daily), four_hour=moving(bars.four_hour),
        hourly=moving(bars.hourly), micro_seed_m15=moving(bars.micro_seed_m15),
        trigger_m15=moving(bars.trigger_m15),
    )
    return result, moving(history)


class B2S2ExecutablePriceMirrorTests(TestCase):
    def test_01_actual_B2_closed_OHLC_buy_becomes_S2_sell(self):
        for anchor in ANCHORS:
            with self.subTest(anchor=anchor):
                a = reflect_once("B2", anchor)
                self.assertEqual((a.input_rule,a.mirrored_rule),("B2","S2"))
                self.assertIs(a.original.experimental_action, CandidateAction.BUY)
                self.assertIs(a.reflected.experimental_action, CandidateAction.SELL)
                self.assertEqual(a.original.routed.classified[0].label,"B2")
                self.assertEqual(a.reflected.routed.classified[0].label,"S2")

    def test_02_actual_S2_closed_OHLC_sell_becomes_B2_buy(self):
        for anchor in ANCHORS:
            with self.subTest(anchor=anchor):
                a = reflect_once("S2", anchor)
                self.assertEqual((a.input_rule,a.mirrored_rule),("S2","B2"))
                self.assertIs(a.original.experimental_action, CandidateAction.SELL)
                self.assertIs(a.reflected.experimental_action, CandidateAction.BUY)
                self.assertEqual(a.original.routed.classified[0].label,"S2")
                self.assertEqual(a.reflected.routed.classified[0].label,"B2")

    def test_03_full_OHLC_reflection_is_exact_involution(self):
        for side in ("B2","S2"):
            bars, history, _, _ = fixture(side)
            for a in ANCHORS:
                with self.subTest(side=side,anchor=a):
                    one, h1 = reflect_sim_b2s2_packet(
                        bars,history,anchor=a,
                    )
                    two, h2 = reflect_sim_b2s2_packet(
                        one,h1,anchor=a,
                    )
                    self.assertEqual(two,bars)
                    self.assertEqual(h2,history)

    def test_04_every_original_and_mirrored_candle_preserves_time_source(self):
        for side in ("B2","S2"):
            bars, history, _, _ = fixture(side)
            reflected, reflected_history = reflect_sim_b2s2_packet(
                bars,history,anchor=D("1.15"),
            )
            for name in (
                "daily","four_hour","hourly","micro_seed_m15","trigger_m15"
            ):
                for a,b in zip(getattr(bars,name),getattr(reflected,name)):
                    self.assertEqual(a.key,b.key)
                    self.assertEqual(a.observation,b.observation)
                    self.assertEqual(a.first_known_utc,b.first_known_utc)
                    self.assertEqual(a.high, D("2.30")-b.low)
                    self.assertEqual(a.low, D("2.30")-b.high)
            self.assertEqual(len(reflected_history),len(history))

    def test_05_pivots_swap_HIGH_LOW_preserving_confirmation_indices(self):
        for side in ("B2","S2"):
            x=reflect_once(side)
            for frame in ("daily","four_hour","m15_confirmed_pivots"):
                a=getattr(x.original.source,frame)
                b=getattr(x.reflected.source,frame)
                self.assertIsNotNone(a)
                self.assertIsNotNone(b)
                self.assertEqual(len(a.pivots),len(b.pivots))
                for pa,pb in zip(a.pivots,b.pivots):
                    self.assertEqual(
                        (pa.kind,pb.kind) in (
                            (PivotKind.HIGH,PivotKind.LOW),
                            (PivotKind.LOW,PivotKind.HIGH),
                        ),True)
                    self.assertEqual(pb.price,D("2.30")-pa.price)
                    self.assertEqual(pa.candidate_index,pb.candidate_index)
                    self.assertEqual(pa.confirmation_index,pb.confirmation_index)
                    self.assertEqual(
                        pa.confirmed_first_known_utc,pb.confirmed_first_known_utc,
                    )

    def test_06_H1_TR_zone_and_M15_micro_are_exact_reflections(self):
        for side in ("B2","S2"):
            x=reflect_once(side)
            a=x.original.source.derived_context
            b=x.reflected.source.derived_context
            self.assertEqual(a.known_atr,b.known_atr)
            self.assertGreater(a.known_atr,0)
            self.assertEqual(a.h1_zone_low,D("2.30")-b.h1_zone_high)
            self.assertEqual(a.h1_zone_high,D("2.30")-b.h1_zone_low)
            self.assertEqual(a.known_micro_level,D("2.30")-b.known_micro_level)
            self.assertEqual(a.context_first_known_utc,b.context_first_known_utc)

    def test_07_right_confirmed_M15_is_not_a_future_candle(self):
        for side in ("B2","S2"):
            x=reflect_once(side)
            for r in (x.original,x.reflected):
                start=r.source.signal.decision_utc
                for scan in (r.source.daily,r.source.four_hour,
                             r.source.m15_confirmed_pivots):
                    self.assertTrue(all(
                        p.candidate_index < p.confirmation_index
                        and p.confirmed_first_known_utc <= start
                        for p in scan.pivots
                    ))

    def test_08_D1_insufficient_source_mirrors_to_NO_SIGNAL(self):
        for side in ("B2","S2"):
            bars,h,p,now=fixture(side)
            b=replace(bars,daily=bars.daily[:4])
            result=verify_executable_b2s2_sim_mirror(
                side,b,h,p,now,anchor=D("1.15"),
            )
            self.assertIs(result.original.experimental_action,
                          CandidateAction.NO_SIGNAL)
            self.assertIs(result.reflected.experimental_action,
                          CandidateAction.NO_SIGNAL)
            self.assertEqual(result.original.routed.classified,())
            self.assertEqual(result.reflected.routed.classified,())

    def test_09_H4_insufficient_source_mirrors_to_NO_SIGNAL(self):
        for side in ("B2","S2"):
            bars,h,p,now=fixture(side)
            b=replace(bars,four_hour=bars.four_hour[:4])
            result=verify_executable_b2s2_sim_mirror(
                side,b,h,p,now,anchor=D("1.15"),
            )
            self.assertIs(result.original.experimental_action,
                          CandidateAction.NO_SIGNAL)
            self.assertIs(result.reflected.experimental_action,
                          CandidateAction.NO_SIGNAL)

    def test_10_price_translation_preserves_decisions_and_TR(self):
        for side in ("B2","S2"):
            bars,h,p,now=fixture(side)
            original=verify_executable_b2s2_sim_mirror(
                side,bars,h,p,now,anchor=D("1.15"),
            )
            shifted,h2=translate_case(bars,h,D("0.05"))
            translated=verify_executable_b2s2_sim_mirror(
                side,shifted,h2,p,now,anchor=D("1.20"),
            )
            self.assertEqual(original.original.experimental_action,
                             translated.original.experimental_action)
            self.assertEqual(original.reflected.experimental_action,
                             translated.reflected.experimental_action)
            self.assertEqual(original.original.source.derived_context.known_atr,
                             translated.original.source.derived_context.known_atr)

    def test_11_future_known_M15_does_not_become_a_past_mirror(self):
        bars,h,p,now=fixture("B2")
        tail=bars.trigger_m15[-1]
        corrupt=replace(tail,first_known_utc=now+timedelta(seconds=1))
        with self.assertRaises(ValueError):
            verify_executable_b2s2_sim_mirror(
                "B2",replace(bars,trigger_m15=(bars.trigger_m15[0],corrupt)),
                h,p,now,anchor=D("1.15"),
            )

    def test_12_open_or_partial_synthetic_candle_denied(self):
        bars,h,_,_=fixture("B2")
        one=bars.four_hour[0]
        for altered in (
            replace(one,lifecycle=BarLifecycle.OPEN),
            replace(one,coverage=BarCoverage.PARTIAL),
            replace(one,quality=SourceQuality.UNVERIFIED),
        ):
            with self.subTest(altered=altered.lifecycle), self.assertRaisesRegex(
                ValueError,"P189_REAL_UNVERIFIED_OR_REVISED_SOURCE_DENIED",
            ):
                reflect_sim_closed_ohlc(altered,anchor=D("1.15"))

    def test_13_real_provider_and_BID_quote_danger_denied(self):
        bars,h,_,_=fixture("B2")
        one=bars.hourly[0]
        for altered in (
            replace(one,observation=replace(
                one.observation,provider_id="TWELVE_DATA_COMPOSITE_MID",
            )),
            replace(one,key=replace(one.key,side=BarSide.BID)),
            replace(one,revision_number=2),
            replace(one,observation=replace(
                one.observation,license_scope_claim="APPROVED",
            )),
        ):
            with self.subTest(kind=altered.key.side),self.assertRaisesRegex(
                ValueError,"P189_REAL_UNVERIFIED_OR_REVISED_SOURCE_DENIED",
            ):
                reflect_sim_closed_ohlc(altered,anchor=D("1.15"))

    def test_14_anchor_must_be_finite_positive_Decimal(self):
        bar=fixture("B2")[0].hourly[0]
        for anchor in (0,"1.15",D("0"),D("-1"),D("NaN"),D("Infinity")):
            with self.subTest(anchor=str(anchor)),self.assertRaisesRegex(
                ValueError,"POSITIVE_DECIMAL_MIRROR_ANCHOR",
            ):
                reflect_sim_closed_ohlc(bar,anchor=anchor)

    def test_15_reflection_of_nonpositive_prices_is_rejected(self):
        bar=fixture("B2")[0].hourly[0]
        with self.assertRaisesRegex(ValueError,"OHLC"):
            reflect_sim_closed_ohlc(bar,anchor=D("0.10"))

    def test_16_M15_confirmed_history_must_end_with_exact_seed(self):
        bars,h,_,_=fixture("B2")
        with self.assertRaisesRegex(ValueError,"EXACT_PRETRIGGER"):
            reflect_sim_b2s2_packet(bars,h[:-1],anchor=D("1.15"))
        with self.assertRaisesRegex(ValueError,"EXACT_PRETRIGGER"):
            reflect_sim_b2s2_packet(bars,list(h),anchor=D("1.15"))

    def test_17_reject_unapproved_rule_or_wrong_input_types(self):
        bars,h,p,now=fixture("B2")
        for rule in ("B1","S3","b2",None):
            with self.subTest(rule=rule),self.assertRaisesRegex(
                ValueError,"ONLY_B2_S2",
            ):
                verify_executable_b2s2_sim_mirror(
                    rule,bars,h,p,now,anchor=D("1.15"))
        with self.assertRaises(TypeError):
            reflect_sim_b2s2_packet({},h,anchor=D("1.15"))

    def test_18_fake_owner_release_and_wrong_policy_are_denied(self):
        bars,h,p,now=fixture("B2")
        with self.assertRaisesRegex(ValueError,"DRAFT_MODIFICATION"):
            verify_executable_b2s2_sim_mirror(
                "B2",bars,h,replace(p,live_signals_allowed=True),now,
                anchor=D("1.15"),
            )
        with self.assertRaises(TypeError):
            verify_executable_b2s2_sim_mirror(
                "B2",bars,h,{},now,anchor=D("1.15"),
            )

    def test_19_public_receipt_cannot_disclose_prices_or_BUY_SELL(self):
        for rule in ("B2","S2"):
            x=reflect_once(rule)
            summary=x.as_safe_summary()
            self.assertEqual(summary["mode"],"SYNTHETIC_OFFLINE_ONLY")
            self.assertEqual(summary["action"],"NO_SIGNAL")
            self.assertEqual(summary["original_numeric_approvals"],0)
            self.assertEqual(summary["original_numeric_pending"],36)
            self.assertFalse(summary["licensed_vendor_quote_data"])
            self.assertFalse(summary["publisher_first_known_verified"])
            self.assertEqual(summary["broker_orders"],0)
            for marker in (
                "1.1017","1.1995","BUY","SELL",
                "known_micro_level","raw_sha256","original=Mfx", "reflected=Mfx",
            ):
                self.assertNotIn(marker,json.dumps(summary))
                self.assertNotIn(marker,repr(x))
            self.assertEqual(x.original.stage,"UNVERIFIED")
            self.assertEqual(x.reflected.stage,"UNVERIFIED")

    def test_20_p189_record_is_frozen_and_repeatable(self):
        for side in ("B2","S2"):
            r1=reflect_once(side)
            r2=reflect_once(side)
            self.assertEqual(r1,r2)
            self.assertEqual(r1.version,VERSION)
            self.assertEqual(r1.action,"NO_SIGNAL")
            self.assertFalse(r1.live_buy_sell_authorized)
            with self.assertRaises(FrozenInstanceError):
                r1.action="BUY"

    def test_21_no_provider_Drive_or_broker_path(self):
        for side in ("B2","S2"):
            x=reflect_once(side)
            self.assertEqual(x.broker_orders,0)
            self.assertFalse(x.source_account_license_verified)
            for result in (x.original,x.reflected):
                self.assertEqual(result.new_provider_requests,0)
                self.assertEqual(result.new_drive_market_writes,0)
                self.assertEqual(result.broker_orders,0)

    def test_22_source_candles_unchanged_after_double_path(self):
        for side in ("B2","S2"):
            bars,h,p,now=fixture(side)
            old=repr((bars,h))
            verify_executable_b2s2_sim_mirror(
                side,bars,h,p,now,anchor=D("1.15"),
            )
            self.assertEqual(repr((bars,h)),old)
