"""P0.161: actually compute *independent* B2/S2 SIM from confirmed pivots.

D1/H4 needs TWO right-confirmed highs + lows per TF; M15 break must use
one right-confirmed high or low known before trigger open. No live signals.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from forex_trading.market_data import Timeframe
from mfx_research.confirmed_swings import (
    PivotKind, SyntheticPivotParameters, detect_confirmed_swings,
)
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    CONFIG_PATH, LINEAGE, VERSION,
    compute_mfx_b2s2_v2_closed_candidate,
    read_mfx_confirmed_b2s2_v2, verify_mfx_confirmed_b2s2_v2,
)
from mfx_research.offline_ema_signals import CandidateAction
from tools.run_a04_p19_causal_context_demo import _make_series
from tools.run_a04_p20_confirmed_swing_demo import case_confirmed


_B2_M15 = (
    ("1.1008", "1.1010", "1.1002", "1.1009"),
    ("1.1009", "1.1013", "1.1003", "1.1010"),
    ("1.1010", "1.1011", "1.1004", "1.1010"),
    ("1.1010", "1.1017", "1.1007", "1.1012"),
    ("1.1012", "1.1013", "1.1006", "1.1011"),
    ("1.1011", "1.1014", "1.1007", "1.1012"),
    ("1.1010", "1.1015", "1.1009", "1.1012"),
)
_S2_M15 = (
    ("1.2001", "1.2006", "1.1998", "1.2000"),
    ("1.2000", "1.2004", "1.1997", "1.1999"),
    ("1.1999", "1.2005", "1.1998", "1.2000"),
    ("1.2000", "1.2004", "1.1995", "1.1998"),
    ("1.1998", "1.2005", "1.1997", "1.1999"),
    ("1.1999", "1.2004", "1.1998", "1.2000"),
    ("1.1999", "1.2001", "1.1996", "1.1998"),
)


def inputs(rule="B2"):
    bars, _ = case_confirmed(rule)
    raws = _B2_M15 if rule == "B2" else _S2_M15
    history = _make_series(Timeframe.M15, raws)
    # Use EXACT existing seed, not an adjusted/fabricated pivot level.
    history = history[:-1] + bars.micro_seed_m15
    return {
        "rule_id": rule,
        "bars": bars,
        "confirmed_m15_history": history,
        "policy": read_mfx_confirmed_b2s2_v2(),
        "decision_utc": bars.trigger_m15[-1].first_known_utc + timedelta(seconds=1),
    }


def run(rule="B2"):
    return compute_mfx_b2s2_v2_closed_candidate(**inputs(rule))


def cfg():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


class OptionBConfirmedV2Tests(TestCase):
    def test_01_B2_computes_right_confirmed_buy_internal_only(self):
        result = run("B2")
        self.assertIs(result.experimental_action, CandidateAction.BUY)
        self.assertEqual(result.source.daily_trend.value, "UP")
        self.assertEqual(result.source.four_hour_trend.value, "UP")
        self.assertEqual(result.source.derived_context.known_micro_level,
                         Decimal("1.1017"))
        self.assertEqual(len(result.routed.classified), 1)
        self.assertEqual(result.routed.classified[0].label, "B2")

    def test_02_S2_computes_right_confirmed_sell_internal_only(self):
        result = run("S2")
        self.assertIs(result.experimental_action, CandidateAction.SELL)
        self.assertEqual(result.source.daily_trend.value, "DOWN")
        self.assertEqual(result.source.four_hour_trend.value, "DOWN")
        self.assertEqual(result.source.derived_context.known_micro_level,
                         Decimal("1.1995"))
        self.assertEqual(result.routed.classified[0].label, "S2")

    def test_03_genuine_D1_H4_highs_lows_and_no_future(self):
        for rule in ("B2", "S2"):
            r = run(rule)
            for receipt in (r.source.daily, r.source.four_hour):
                for kind in (PivotKind.HIGH, PivotKind.LOW):
                    self.assertGreaterEqual(
                        len([x for x in receipt.pivots if x.kind is kind]), 2)
                for swing in receipt.pivots:
                    self.assertGreater(swing.confirmation_index,
                                       swing.candidate_index)
                    self.assertLessEqual(swing.confirmed_first_known_utc,
                                         receipt.asof_utc)

    def test_04_M15_confirmed_pivot_precedes_trigger_open(self):
        for rule, expected_kind in (
            ("B2", PivotKind.HIGH), ("S2", PivotKind.LOW),
        ):
            d=inputs(rule)
            receipt=compute_mfx_b2s2_v2_closed_candidate(**d)
            m15=receipt.source.m15_confirmed_pivots
            self.assertIsNotNone(m15)
            cutoff=d["bars"].trigger_m15[0].key.bar_start_utc
            self.assertEqual(m15.asof_utc,cutoff)
            pivots=[p for p in m15.pivots if p.kind is expected_kind]
            self.assertTrue(pivots)
            for p in pivots:
                self.assertLessEqual(p.confirmed_first_known_utc,cutoff)
                self.assertGreater(p.confirmation_index,p.candidate_index)
                self.assertLessEqual(
                    d["confirmed_m15_history"][p.confirmation_index].key.bar_end_utc,
                    cutoff)

    def test_05_same_timestamp_cannot_make_unclosed_right_pivot(self):
        d=inputs("B2")
        first=d["bars"].trigger_m15[0]
        with self.assertRaisesRegex(ValueError,"FUTURE_PRICE_BAR"):
            detect_confirmed_swings(
                d["confirmed_m15_history"],Timeframe.M15,
                SyntheticPivotParameters(
                    version="SIM:P161-RIGHT1",left_bars=1,right_bars=1),
                first.key.bar_start_utc-timedelta(seconds=1),
            )

    def test_06_no_high_pivot_is_hard_fail_not_fallback_seed(self):
        d=inputs("B2")
        original=d["confirmed_m15_history"]
        altered=[]
        for i,bar in enumerate(original[:-1]):
            high=Decimal("1.1001")+Decimal(i)*Decimal("0.00015")
            low=Decimal("1.0990")+Decimal(i)*Decimal("0.00010")
            altered.append(replace(
                bar,open=low+Decimal("0.00001"),low=low,
                high=high,close=low+Decimal("0.00002"),
            ))
        d["confirmed_m15_history"]=tuple(altered)+(original[-1],)
        with self.assertRaisesRegex(ValueError,"NO_PRIOR_RIGHT_CONFIRMED_M15"):
            compute_mfx_b2s2_v2_closed_candidate(**d)

    def test_07_no_low_pivot_is_hard_fail_not_fallback_seed(self):
        d=inputs("S2")
        original=d["confirmed_m15_history"]
        altered=[]
        for i,bar in enumerate(original[:-1]):
            low=Decimal("1.1990")-Decimal(i)*Decimal("0.00015")
            high=Decimal("1.2020")-Decimal(i)*Decimal("0.00010")
            altered.append(replace(
                bar,open=low+Decimal("0.00002"),low=low,
                high=high,close=low+Decimal("0.00001"),
            ))
        d["confirmed_m15_history"]=tuple(altered)+(original[-1],)
        with self.assertRaisesRegex(ValueError,"NO_PRIOR_RIGHT_CONFIRMED_M15"):
            compute_mfx_b2s2_v2_closed_candidate(**d)

    def test_08_missing_D1_confirmed_structure_yields_no_buy(self):
        d=inputs("B2")
        d["bars"]=replace(d["bars"],daily=d["bars"].daily[:4])
        r=compute_mfx_b2s2_v2_closed_candidate(**d)
        self.assertIs(r.experimental_action,CandidateAction.NO_SIGNAL)
        self.assertEqual(r.routed.classified,())
        self.assertEqual(r.source.daily_trend.value,"UNKNOWN")

    def test_09_missing_H4_confirmed_structure_yields_no_sell(self):
        d=inputs("S2")
        d["bars"]=replace(d["bars"],four_hour=d["bars"].four_hour[:4])
        r=compute_mfx_b2s2_v2_closed_candidate(**d)
        self.assertIs(r.experimental_action,CandidateAction.NO_SIGNAL)
        self.assertEqual(r.routed.events,())

    def test_10_M15_trigger_not_closed_hard_fail(self):
        d=inputs("B2")
        first,last=d["bars"].trigger_m15
        d["bars"]=replace(d["bars"],trigger_m15=(first,replace(
            last,first_known_utc=d["decision_utc"]+timedelta(seconds=1),
        )))
        with self.assertRaises(ValueError):
            compute_mfx_b2s2_v2_closed_candidate(**d)

    def test_11_M15_history_must_end_at_real_exact_seed(self):
        d=inputs()
        d["confirmed_m15_history"]=d["confirmed_m15_history"][:-1]
        with self.assertRaisesRegex(ValueError,"EXACT_PRETRIGGER_SEED"):
            compute_mfx_b2s2_v2_closed_candidate(**d)

    def test_12_M15_history_cross_provider_rejected(self):
        d=inputs()
        x=d["confirmed_m15_history"][2]
        d["confirmed_m15_history"]=(
            d["confirmed_m15_history"][:2]+(
                replace(x,observation=replace(x.observation,provider_id="SIM:DIFF")),)+
            d["confirmed_m15_history"][3:])
        with self.assertRaisesRegex(ValueError,"ORIGIN_STREAM_IDENTITY"):
            compute_mfx_b2s2_v2_closed_candidate(**d)

    def test_13_M15_history_real_provider_rejected(self):
        d=inputs()
        x=d["confirmed_m15_history"][2]
        d["confirmed_m15_history"]=(
            d["confirmed_m15_history"][:2]+(
                replace(x,observation=replace(x.observation,provider_id="OANDA")),)+
            d["confirmed_m15_history"][3:])
        with self.assertRaises(ValueError):
            compute_mfx_b2s2_v2_closed_candidate(**d)

    def test_14_trigger_mismatched_M15_stream_rejected(self):
        d=inputs()
        x,y=d["bars"].trigger_m15
        y=replace(y,observation=replace(y.observation,stream_id="SIM:OTHER"))
        d["bars"]=replace(d["bars"],trigger_m15=(x,y))
        with self.assertRaisesRegex(ValueError,"TRIGGER_STREAM_DRIFT"):
            compute_mfx_b2s2_v2_closed_candidate(**d)

    def test_15_public_output_redacts_price_direction_and_origin(self):
        for rule in ("B2","S2"):
            r=run(rule)
            record=json.dumps(r.as_safe_record())
            self.assertEqual(r.as_safe_record()["public_action"],"NO_SIGNAL")
            for secret in ("experimental_action","BUY","SELL","1.1017",
                           "1.1995","origin_event_id","source_raw_sha256"):
                self.assertNotIn(secret,record)
            self.assertNotIn("experimental_action",repr(r))
            self.assertNotIn("known_micro_level",repr(r))

    def test_16_no_real_market_rights_or_orders(self):
        for rule in ("B2","S2"):
            r=run(rule)
            self.assertEqual((r.public_action,r.stage),("NO_SIGNAL","UNVERIFIED"))
            self.assertFalse(r.independent_numeric_rule_approved)
            self.assertFalse(r.original_forex_numeric_1to1)
            self.assertFalse(r.live_buy_sell_allowed)
            self.assertFalse(r.source_market_rights_verified)
            self.assertFalse(r.may_trade)
            self.assertFalse(r.true_historical_oos_qualified)
            self.assertEqual((r.new_provider_requests,r.new_drive_market_writes,
                              r.broker_orders),(0,0,0))

    def test_17_versioned_v2_is_separate_from_v1(self):
        p=read_mfx_confirmed_b2s2_v2()
        self.assertEqual(p.version,VERSION)
        self.assertEqual(p.lineage,LINEAGE)
        self.assertEqual((p.htf_left,p.htf_right,p.micro_left,p.micro_right),
                         (1,1,1,1))
        self.assertEqual(len(p.fingerprint_sha256),64)

    def test_18_reject_forged_numeric_approval_in_json(self):
        d=cfg()
        d["permissions"]["numeric_policy_approved"]=True
        with self.assertRaisesRegex(ValueError,"RIGHTS_DRIFT"):
            verify_mfx_confirmed_b2s2_v2(d)

    def test_19_reject_forged_released_policy_object(self):
        d=inputs()
        d["policy"]=replace(d["policy"],live_signals_allowed=True)
        with self.assertRaisesRegex(ValueError,"DRAFT_MODIFICATION"):
            compute_mfx_b2s2_v2_closed_candidate(**d)

    def test_20_wrong_parent_git_blob_rejected(self):
        d=cfg()
        d["parent_numeric_config_git_blob"]="0"*40
        with self.assertRaisesRegex(ValueError,"RIGHTS_DRIFT"):
            verify_mfx_confirmed_b2s2_v2(d)

    def test_21_sha_lock_rejects_tampered_parent_bytes(self):
        with TemporaryDirectory() as tmp:
            fake=Path(tmp)/"p160.json"
            fake.write_text("{}",encoding="utf-8")
            d=inputs()
            with patch(
                "mfx_research.mfx_b2s2_confirmed_policy_v2.P160_PATH",fake,
            ), self.assertRaisesRegex(ValueError,"PARENT_P160"):
                compute_mfx_b2s2_v2_closed_candidate(**d)

    def test_22_reject_unknown_param_or_malformed_pivot_width(self):
        for bad in (0,4,True,"2",1.5):
            d=cfg()
            d["experimental_params"]["m15_confirmed_micro_right_bars"]=bad
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                verify_mfx_confirmed_b2s2_v2(d)

    def test_23_reject_unknown_json_flags_or_false_causal_invariant(self):
        d=cfg()
        d["permissions"]["new_unreviewed_flag"]=False
        with self.assertRaisesRegex(ValueError,"EXACT_DRAFT_SCHEMA"):
            verify_mfx_confirmed_b2s2_v2(d)
        d=cfg()
        d["experimental_params"]["requires_source_closed_at_asof"]=False
        with self.assertRaisesRegex(ValueError,"RIGHTS_DRIFT"):
            verify_mfx_confirmed_b2s2_v2(d)

    def test_24_reject_duplicate_config_keys(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"malformed.json"
            p.write_text('{"version":"a","version":"b"}',encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"DUPLICATE_DRAFT_JSON_KEY"):
                read_mfx_confirmed_b2s2_v2(p)

    def test_25_reject_bad_pivot_history_type_and_missing_pair(self):
        d=inputs()
        d["confirmed_m15_history"]=list(d["confirmed_m15_history"])
        with self.assertRaisesRegex(ValueError,"EXACT_PRETRIGGER_SEED"):
            compute_mfx_b2s2_v2_closed_candidate(**d)
        d=inputs()
        d["confirmed_m15_history"]=()
        with self.assertRaisesRegex(ValueError,"EXACT_PRETRIGGER_SEED"):
            compute_mfx_b2s2_v2_closed_candidate(**d)

    def test_26_reject_wrong_rule_and_wrong_draft_type(self):
        d=inputs()
        d["rule_id"]="B7"
        with self.assertRaisesRegex(ValueError,"ONLY_OPTION_B_B2_S2"):
            compute_mfx_b2s2_v2_closed_candidate(**d)
        d=inputs()
        d["policy"]={}
        with self.assertRaisesRegex(TypeError,"TYPED_EXACT_DRAFT"):
            compute_mfx_b2s2_v2_closed_candidate(**d)

    def test_27_zero_new_cloud_io_and_idempotent_repeat(self):
        for rule in ("B2","S2"):
            a=run(rule)
            b=run(rule)
            self.assertEqual(a,b)
            self.assertEqual(a.broker_orders,0)
            self.assertEqual(a.new_provider_requests,0)
            self.assertEqual(a.new_drive_market_writes,0)

    def test_28_immutable_research_policy_and_output(self):
        p=read_mfx_confirmed_b2s2_v2()
        with self.assertRaises(FrozenInstanceError):
            p.numeric_rules_approved=True
        r=run()
        with self.assertRaises(FrozenInstanceError):
            r.public_action="BUY"
