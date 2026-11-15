"""P0.177 Option B v2 real-source private gap diagnostics (never live BUY/SELL)."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from unittest import TestCase
from unittest.mock import patch

from mfx_research.p177_real_source_b2s2_readiness import (
    VERSION, PrivateB2S2Readiness,
    compute_private_option_b2s2_requirements,
)
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    read_mfx_confirmed_b2s2_v2,
)
from mfx_research.sealed_private_pivot_sensitivity import (
    scan_private_sealed_pivot_sensitivity,
)
from mfx_research.sealed_private_m15_microbreak import (
    compute_private_sealed_m15_microbreak,
)
from test_mfx_v1_six_tf_sealed_archive_consumer import consume
from test_mfx_p174_active_d1_six_tf_readonly import (
    reviewed_inputs, consume_offline, make_epoch, archived_tip,
)


def inputs():
    r=consume()
    return (r.private_multibar,r.technical,
            r.private_pivot_sensitivity,r.private_m15_microbreak)


def run(*, source_mode="LEGACY_D1_V1", source=None):
    a=inputs() if source is None else source
    return compute_private_option_b2s2_requirements(
        *a,active_d1_source_epoch=source_mode)


class B2S2RealPrivateReadinessTests(TestCase):
    def test_01_actual_consumer_contains_private_B2S2_gap_diagnosis(self):
        r=consume()
        x=r.private_b2s2_source_readiness
        self.assertIsInstance(x,PrivateB2S2Readiness)
        self.assertEqual(x.version,VERSION)
        self.assertEqual(tuple(g.rule_id for g in x.gates),("B2","S2"))
        self.assertEqual(x.public_action,"NO_SIGNAL")
        self.assertEqual(x.stage,"UNVERIFIED")

    def test_02_exact_draft_policy_is_reused_not_approved(self):
        x=run()
        p=read_mfx_confirmed_b2s2_v2()
        self.assertEqual(x.policy_fingerprint_sha256,p.fingerprint_sha256)
        self.assertFalse(p.numeric_rules_approved)
        self.assertFalse(x.numeric_policy_approved)
        self.assertFalse(x.original_forex_numeric_1to1)

    def test_03_each_side_has_source_and_risk_gaps(self):
        x=run()
        for g in x.gates:
            self.assertEqual(g.readiness,"RESEARCH_GAPS_NO_SIGNAL")
            self.assertIn("D1_NATIVE_SESSION_CALENDAR_AND_FIRST_KNOWN_UNVERIFIED",
                          g.missing_preconditions)
            self.assertIn("D1_TWO_RIGHT_CONFIRMED_HIGH_LOWS_UNQUALIFIED",
                          g.missing_preconditions)
            self.assertIn("MFX_OPTION_B_V2_NUMERIC_OWNER_REVIEW_PENDING",
                          g.missing_preconditions)
            self.assertIn("TRUE_HISTORICAL_OOS_PENDING",
                          g.missing_preconditions)
            self.assertIn("REAL_BIDASK_SL_TP_NET_RR_UNVERIFIED",
                          g.missing_preconditions)
            self.assertFalse(g.can_publish_buy_sell)
            self.assertFalse(g.can_trade)

    def test_04_B2_requires_confirmed_M15_high_before_break(self):
        g=run().gates[0]
        self.assertIn("M15_PRETRIGGER_CONFIRMED_LEVEL_MISSING",
                      g.missing_preconditions)
        self.assertIn("M15_CLOSED_MICROBREAK_NOT_OBSERVED",
                      g.missing_preconditions)

    def test_05_S2_requires_confirmed_M15_low_before_break(self):
        g=run().gates[1]
        self.assertIn("M15_PRETRIGGER_CONFIRMED_LEVEL_MISSING",
                      g.missing_preconditions)
        self.assertIn("M15_CLOSED_MICROBREAK_NOT_OBSERVED",
                      g.missing_preconditions)

    def test_06_full_H4_swing_structure_not_invented(self):
        x=run()
        for g in x.gates:
            self.assertEqual((g.h4_confirmed_high_pivots,
                              g.h4_confirmed_low_pivots),(0,0))
            self.assertIn("H4_TWO_CONFIRMED_HIGHS_AND_LOWS_MISSING",
                          g.missing_preconditions)

    def test_07_H1_draft_TR3_requires_more_than_three_closed_H1(self):
        g=run().gates[0]
        self.assertEqual(g.h1_closed_bars_available,2)
        self.assertIn("H1_DRAFT_TR_PERIOD_NOT_CLOSED",
                      g.missing_preconditions)

    def test_08_D1_history_not_source_session_qualified(self):
        g=run().gates[0]
        self.assertEqual(g.d1_observed_native_rows,1)
        self.assertIn("D1_NOT_ENOUGH_OBSERVED_CLOSED_ROWS",
                      g.missing_preconditions)

    def test_09_all_rights_rejected_and_zero_side_effects(self):
        x=run()
        self.assertFalse(x.d1_calendar_qualified)
        self.assertFalse(x.publisher_first_known_verified)
        self.assertFalse(x.source_data_license_verified)
        self.assertFalse(x.bidask_net_rr_qualified)
        self.assertFalse(x.real_oos_qualified)
        self.assertFalse(x.may_publish_buy_sell)
        self.assertFalse(x.may_trade)
        self.assertEqual((x.market_price_requests,x.drive_gets_added,
                          x.drive_writes,x.broker_orders),(0,0,0,0))

    def test_10_new_P171_source_epoch_only_private_research(self):
        m,h,d,p=reviewed_inputs()
        x=consume_offline(
            m,h,d,p,active=make_epoch(origin=archived_tip(d)))
        r=x.private_b2s2_source_readiness
        self.assertEqual(r.source_technical_mode,"P171_D1_FRESH_20261111")
        self.assertFalse(r.may_publish_buy_sell)
        self.assertIn(
            "D1_NATIVE_SESSION_CALENDAR_AND_FIRST_KNOWN_UNVERIFIED",
            r.gates[0].missing_preconditions)

    def test_11_legacy_D1_only_fixture_path_keeps_same_no_signal(self):
        x=consume()
        self.assertEqual(x.private_b2s2_source_readiness.source_technical_mode,
                         "LEGACY_D1_V1")
        self.assertEqual(x.private_b2s2_source_readiness.public_action,
                         "NO_SIGNAL")

    def test_12_forced_original_source_policy_approval_denied(self):
        multi,tech,pivots,micro=inputs()
        bad=replace(multi,original_forex_numeric_source_approved=True)
        with self.assertRaises(ValueError):
            compute_private_option_b2s2_requirements(
                bad,tech,pivots,micro,active_d1_source_epoch="LEGACY_D1_V1")

    def test_13_tampered_pivot_studies_fail_recheck(self):
        multi,tech,pivots,micro=inputs()
        bad=replace(pivots,studied=())
        with self.assertRaisesRegex(ValueError,"SOURCE_PIVOT_OR_CROSS_DRIFT"):
            compute_private_option_b2s2_requirements(
                multi,tech,bad,micro,active_d1_source_epoch="LEGACY_D1_V1")

    def test_14_tampered_M15_cross_fails_recheck(self):
        multi,tech,pivots,micro=inputs()
        prof=replace(micro.profiles[0],
                     experimental_cross="EXPERIMENTAL_UP_CROSS")
        bad=replace(micro,profiles=(prof,)+micro.profiles[1:])
        with self.assertRaisesRegex(ValueError,"SOURCE_PIVOT_OR_CROSS_DRIFT"):
            compute_private_option_b2s2_requirements(
                multi,tech,pivots,bad,active_d1_source_epoch="LEGACY_D1_V1")

    def test_15_unknown_source_generation_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_SOURCE_EPOCH"):
            run(source_mode="FAKE_D1_FOREX_SOURCE")

    def test_16_policy_must_remain_pending(self):
        policy=replace(read_mfx_confirmed_b2s2_v2(),
                       numeric_rules_approved=True)
        with patch("mfx_research.p177_real_source_b2s2_readiness."
                   "read_mfx_confirmed_b2s2_v2",return_value=policy):
            with self.assertRaisesRegex(ValueError,"UNAPPROVED_POLICY"):
                run()

    def test_17_typed_not_untrusted_dict(self):
        x=list(inputs())
        for i in range(4):
            altered=x.copy()
            altered[i]={}
            with self.subTest(i=i),self.assertRaisesRegex(
                TypeError,"SEALED_TYPED_SOURCE_REQUIRED"):
                run(source=tuple(altered))

    def test_18_repr_hides_private_direction_and_price(self):
        x=run()
        self.assertNotIn("experimental_cross",repr(x.gates[0]))
        self.assertNotIn("candidate_mid_price",repr(x))
        self.assertNotIn("PRIVATE_RESEARCH",repr(x))
        self.assertNotIn("1.1",repr(x))

    def test_19_log_projection_contains_no_private_source_feature(self):
        x=run()
        encoded=json.dumps(x.as_safe_summary(),sort_keys=True)
        for token in ("experimental_cross","candidate_mid_price",
                      "h4_confirmed_high_pivots","observed_low",
                      "private_input_digest_sha256","1.100"):
            self.assertNotIn(token,encoded)
        self.assertIn("NO_SIGNAL",encoded)
        self.assertIn("RESEARCH_GAPS_NO_SIGNAL",encoded)

    def test_20_gate_projection_owner_rights_are_false(self):
        payload=run().as_safe_summary()
        self.assertFalse(payload["approved_numeric_rules"])
        self.assertEqual(payload["provider_requests"],0)
        self.assertEqual(payload["drive_writes"],0)
        self.assertEqual(payload["broker_orders"],0)

    def test_21_results_are_repeatable(self):
        x=run()
        y=run()
        self.assertEqual(x,y)
        self.assertEqual(x.private_input_digest_sha256,
                         inputs()[0].private_input_digest_sha256)

    def test_22_frozen_receipts_cannot_promote_authority(self):
        x=run()
        with self.assertRaises(FrozenInstanceError):
            x.may_trade=True
        with self.assertRaises(FrozenInstanceError):
            x.gates[0].can_publish_buy_sell=True

    def test_23_no_trading_source_or_schedule_added(self):
        from pathlib import Path
        s=Path("mfx_research/p177_real_source_b2s2_readiness.py").read_text()
        for forbidden in ("requests.post(","requests.get(",
                          "googleapiclient","workflow_dispatch",
                          "order_send(","broker.submit("):
            self.assertNotIn(forbidden,s)

    def test_24_private_gate_never_relabelled_live_BUY_SELL(self):
        r=consume()
        x=r.private_b2s2_source_readiness
        self.assertEqual(r.technical.action,"NO_SIGNAL")
        self.assertFalse(r.may_publish_buy_sell)
        self.assertEqual(x.public_action,"NO_SIGNAL")
        self.assertEqual(x.source_technical_mode,"LEGACY_D1_V1")
