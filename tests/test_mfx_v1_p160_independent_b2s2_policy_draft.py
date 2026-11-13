"""Option B numeric prototype: exact MFX draft, not Forex original parity.

Only existing synthetic fixtures are used. No quote provider, real cache,
live BUY/SELL, real historical OOS or broker capability is introduced.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from mfx_research.mfx_b2s2_independent_policy_draft import (
    CONFIG_PATH, LINEAGE, SCHEMA, VERSION,
    calculate_independent_mfx_b2s2_offline_candidate,
    read_independent_mfx_policy_draft,
    verify_independent_mfx_policy_draft,
)
from mfx_research.offline_ema_signals import CandidateAction
from tools.run_a04_p19_causal_context_demo import case_from_closed_bars


def inputs(rule="B2"):
    bars, _, _ = case_from_closed_bars(rule)
    return {
        "rule_id": rule,
        "bars": bars,
        "draft": read_independent_mfx_policy_draft(),
        "decision_utc": bars.trigger_m15[-1].first_known_utc + timedelta(seconds=1),
    }


def run(rule="B2"):
    return calculate_independent_mfx_b2s2_offline_candidate(**inputs(rule))


def source_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


class MfxOptionBPolicyDraftTests(TestCase):
    def test_01_exact_versioned_scope_is_option_b_not_forex_1to1(self):
        r = read_independent_mfx_policy_draft()
        self.assertEqual((r.version, r.strategy_lineage), (VERSION, LINEAGE))
        self.assertTrue(r.user_option_b_development_scope_approved)
        self.assertFalse(r.specific_numeric_policy_approved)
        self.assertFalse(r.original_forex_numerical_parity_verified)
        self.assertEqual(len(r.canonical_sha256), 64)

    def test_02_actual_closed_sim_b2_computes_internal_buy(self):
        a = run("B2")
        self.assertIs(a.experimental_action, CandidateAction.BUY)
        self.assertEqual(a.technical.pilot_rule_id, "B2")
        self.assertEqual(a.technical.classified_output.classified[0].label, "B2")

    def test_03_actual_closed_sim_s2_computes_internal_sell(self):
        a = run("S2")
        self.assertIs(a.experimental_action, CandidateAction.SELL)
        self.assertEqual(a.technical.pilot_rule_id, "S2")
        self.assertEqual(a.technical.classified_output.classified[0].label, "S2")

    def test_04_public_action_no_signal_even_real_internal_buy_and_sell(self):
        for rule in ("B2", "S2"):
            with self.subTest(rule=rule):
                a = run(rule)
                self.assertEqual((a.action, a.stage), ("NO_SIGNAL", "UNVERIFIED"))
                self.assertFalse(a.may_publish_buy_sell)
                self.assertFalse(a.may_trade)
                self.assertEqual(a.broker_orders, 0)
                self.assertEqual(a.technical.action, "NO_SIGNAL")

    def test_05_public_record_never_contains_event_or_price_or_experimental_action(self):
        for rule in ("B2", "S2"):
            a = run(rule)
            record = json.dumps(a.as_safe_record(), sort_keys=True)
            self.assertNotIn("BUY", record)
            self.assertNotIn("SELL", record)
            self.assertNotIn("origin_event_id", record)
            self.assertNotIn("experimental_action", record)
            self.assertNotIn("1.101", record)
            self.assertNotIn("canonical_sha256", record)
            self.assertEqual(a.as_safe_record()["action"], "NO_SIGNAL")

    def test_06_no_cross_yields_no_internal_candidate_or_zone_event(self):
        d = inputs("B2")
        first, last = d["bars"].trigger_m15
        d["bars"] = replace(d["bars"], trigger_m15=(
            first, replace(last, close=first.close),
        ))
        a = calculate_independent_mfx_b2s2_offline_candidate(**d)
        self.assertIs(a.experimental_action, CandidateAction.NO_SIGNAL)
        self.assertEqual(a.technical.classified_output.events, ())

    def test_07_explicit_versioned_numeric_profile_value(self):
        a = read_independent_mfx_policy_draft()
        self.assertEqual(a.h1_tr_mean_period, 3)
        self.assertEqual(a.h1_zone_lookback, 3)
        self.assertEqual(a.h1_width_multiple, Decimal("0.3"))
        self.assertEqual(a.h1_near_multiple, Decimal("0.5"))
        self.assertEqual(a.max_chase_multiple, Decimal("0.5"))

    def test_08_unauthorized_numeric_override_fails_before_pattern(self):
        d=inputs()
        d["draft"]=replace(d["draft"],max_chase_multiple=Decimal("4"))
        with self.assertRaisesRegex(ValueError, "DRAFT_DIFFERS"):
            calculate_independent_mfx_b2s2_offline_candidate(**d)

    def test_09_fake_signed_policy_fails_closed(self):
        d=inputs()
        d["draft"]=replace(d["draft"],specific_numeric_policy_approved=True)
        with self.assertRaisesRegex(ValueError,"FORGED_NUMERIC"):
            calculate_independent_mfx_b2s2_offline_candidate(**d)

    def test_10_fake_original_forex_numeric_parity_fails_closed(self):
        d=inputs()
        d["draft"]=replace(d["draft"],original_forex_numerical_parity_verified=True)
        with self.assertRaisesRegex(ValueError,"FORGED_NUMERIC"):
            calculate_independent_mfx_b2s2_offline_candidate(**d)

    def test_11_fake_vendor_rights_fails_closed(self):
        d=inputs()
        d["draft"]=replace(d["draft"],source_license_verified=True)
        with self.assertRaisesRegex(ValueError,"FORGED_NUMERIC"):
            calculate_independent_mfx_b2s2_offline_candidate(**d)

    def test_12_real_vendor_bars_injection_fails_closed(self):
        d=inputs()
        b=d["bars"]
        h1=b.hourly[-1]
        d["bars"]=replace(b,hourly=b.hourly[:-1]+(
            replace(h1,observation=replace(
                h1.observation,provider_id="Twelve Data")),
        ))
        with self.assertRaisesRegex(ValueError,"REJECT_REAL_MARKET_SOURCE"):
            calculate_independent_mfx_b2s2_offline_candidate(**d)

    def test_13_future_first_known_m15_fails_closed(self):
        d=inputs()
        b=d["bars"]
        first,last=b.trigger_m15
        d["bars"]=replace(b,trigger_m15=(first,replace(
            last,first_known_utc=d["decision_utc"]+timedelta(seconds=2),
        )))
        with self.assertRaises(ValueError):
            calculate_independent_mfx_b2s2_offline_candidate(**d)

    def test_14_source_config_rejects_self_signoff(self):
        cfg=source_config()
        cfg["permission_flags"]["may_publish_buy_sell"]=True
        with self.assertRaisesRegex(ValueError,"PERMISSION_DRIFT"):
            verify_independent_mfx_policy_draft(cfg)

    def test_15_source_config_rejects_false_forex_lineage(self):
        cfg=source_config()
        cfg["strategy_lineage"]="ORIGINAL_FOREX_NUMERIC_1TO1"
        with self.assertRaisesRegex(ValueError,"PERMISSION_DRIFT"):
            verify_independent_mfx_policy_draft(cfg)

    def test_16_schema_rejects_extra_unknown_licensing_keys(self):
        cfg=source_config()
        cfg["production_licence_claim"]="YES"
        with self.assertRaisesRegex(ValueError,"EXACT_MFX_DRAFT_SCHEMA"):
            verify_independent_mfx_policy_draft(cfg)

    def test_17_bad_numeric_near_zone_and_zero_rejected(self):
        for value in ("0", "-1", "NaN", "Infinity", "0.0000000001", 0.5):
            with self.subTest(value=value):
                cfg=source_config()
                cfg["numeric_candidate"]["h1_near_zone_tr_multiple"]=value
                with self.assertRaises(ValueError):
                    verify_independent_mfx_policy_draft(cfg)

    def test_18_bad_period_bool_or_oversize_rejected(self):
        for n in (0, 1, 25, True, 1.5, "3"):
            with self.subTest(n=n):
                cfg=source_config()
                cfg["numeric_candidate"]["h1_zone_lookback"]=n
                with self.assertRaises(ValueError):
                    verify_independent_mfx_policy_draft(cfg)

    def test_19_duplicate_keys_in_draft_json_denied(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"draft.json"
            p.write_text('{"schema":"first","schema":"second"}',encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"DUPLICATE_DRAFT_JSON_KEY"):
                read_independent_mfx_policy_draft(p)

    def test_20_reject_unbounded_and_invalid_paths(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"draft.json"
            p.write_bytes(b"x"*8193)
            with self.assertRaisesRegex(ValueError,"EMPTY_OR_OVERSIZED"):
                read_independent_mfx_policy_draft(p)
        with self.assertRaisesRegex(TypeError,"TYPED_DRAFT_PATH"):
            read_independent_mfx_policy_draft("docs/file")

    def test_21_reject_non_B2S2_and_wrong_typed_policy(self):
        for rule in ("B5", "S7", "FX-B9", "", None):
            d=inputs()
            d["rule_id"]=rule
            with self.subTest(rule=rule), self.assertRaisesRegex(
                    ValueError,"ONLY_MFX_INDEPENDENT"):
                calculate_independent_mfx_b2s2_offline_candidate(**d)
        d=inputs()
        d["draft"]={}
        with self.assertRaisesRegex(TypeError,"TYPED_INDEPENDENT"):
            calculate_independent_mfx_b2s2_offline_candidate(**d)

    def test_22_deterministic_policy_and_same_source_outputs(self):
        self.assertEqual(
            read_independent_mfx_policy_draft(),
            read_independent_mfx_policy_draft(),
        )
        self.assertEqual(run("B2"), run("B2"))
        self.assertEqual(run("S2"), run("S2"))

    def test_23_immutable_policy_and_receipt(self):
        d=read_independent_mfx_policy_draft()
        with self.assertRaises(FrozenInstanceError):
            d.may_publish_buy_sell=True
        r=run()
        with self.assertRaises(FrozenInstanceError):
            r.action="BUY"

    def test_24_no_live_provider_drive_broker_or_OOS_claim(self):
        for rule in ("B2", "S2"):
            a=run(rule)
            self.assertEqual((a.provider_requests,
                              a.drive_market_cache_writes,a.broker_orders),
                             (0,0,0))
            self.assertFalse(a.live_quote_rights_verified)
            self.assertFalse(a.historical_oos_qualified)
            self.assertFalse(a.parameter_rule_approved)
            self.assertEqual(a.strategy_lineage,LINEAGE)
