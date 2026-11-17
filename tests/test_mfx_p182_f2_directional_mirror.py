"""P0.182 offline counterfactual F2 mirror tests, no vendor/Drive/broker."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from mfx_research.p182_f2_directional_mirror import (
    F2DesignEvidence, F2Phase, PAIR,
    VERSION, evaluate_f2_design, reflect_f2_design,
)

UTC = timezone.utc
BASE = datetime(2026, 11, 17, 8, 0, tzinfo=UTC)
D = Decimal


def sample(**overrides):
    args = dict(
        rule_id="B2", event_id="SIM:F2-EVENT.1",
        asof_utc=BASE,
        m15_start_utc=BASE-timedelta(minutes=20),
        m15_closed_utc=BASE-timedelta(minutes=5),
        m15_first_known_utc=BASE-timedelta(minutes=4),
        micro_first_known_utc=BASE-timedelta(minutes=30),
        regime="HH_HL", zone_side="SUPPORT", pivot="HL",
        internal_bos="BOS_UP", zone_reentry=True, source_complete=True,
        micro_level=D("105"), trigger_close=D("108"),
        invalidation_level=D("90"), h1_close=D("95"),
        mirror_anchor=D("100"),
    )
    args.update(overrides)
    return F2DesignEvidence(**args)


class P182DirectionalMirrorTests(TestCase):
    def check_mirror(self, e, expected):
        mirrored=reflect_f2_design(e)
        self.assertEqual(reflect_f2_design(mirrored),e)
        a,b=evaluate_f2_design(e),evaluate_f2_design(mirrored)
        self.assertEqual(a.phase,expected)
        self.assertEqual(b.phase,expected)
        self.assertEqual(a.event_id,b.event_id)
        self.assertEqual(a.public_action,"NO_SIGNAL")
        self.assertEqual(b.public_action,"NO_SIGNAL")
        self.assertEqual(a.source_numeric_approvals,0)
        self.assertEqual(b.remaining_owner_decisions,36)
        self.assertFalse(a.may_publish_buy_sell)
        self.assertFalse(b.may_execute_broker_order)
        self.assertEqual((a.hypothetical_entry_side,a.hypothetical_exit_side),
                         ("ASK","BID"))
        self.assertEqual((b.hypothetical_entry_side,b.hypothetical_exit_side),
                         ("BID","ASK"))

    def test_01_symmetric_confirmed_design_never_live_signal(self):
        self.check_mirror(sample(),F2Phase.CONFIRMED_DESIGN_ONLY)

    def test_02_watch_when_no_early_event_even_if_micro_crossed(self):
        self.check_mirror(sample(pivot="NONE",internal_bos="NONE",
                                 zone_reentry=False),F2Phase.WATCH)

    def test_03_early_on_HL_LH_without_confirmed_micro_cross(self):
        self.check_mirror(sample(trigger_close=D("104"),zone_reentry=False,
                                 internal_bos="NONE"),F2Phase.EARLY)

    def test_04_early_zone_reentry_symmetric_without_pivot(self):
        self.check_mirror(sample(trigger_close=D("105"),pivot="NONE",
                                 internal_bos="NONE"),F2Phase.EARLY)

    def test_05_internal_bos_up_and_down_pair_early_only(self):
        self.check_mirror(sample(trigger_close=D("103"),pivot="NONE",
                                 zone_reentry=False),F2Phase.EARLY)

    def test_06_micro_level_strict_tie_does_not_confirm(self):
        self.check_mirror(sample(trigger_close=D("105")),F2Phase.EARLY)

    def test_07_confirm_precedence_prevents_duplicate_early_event(self):
        e=sample()
        p=evaluate_f2_design(e)
        self.assertEqual(p.phase,F2Phase.CONFIRMED_DESIGN_ONLY)
        self.assertTrue(p.no_double_counted_confirmation)
        self.assertEqual(evaluate_f2_design(e),p)

    def test_08_invalidation_takes_precedence_to_prevent_false_action(self):
        self.check_mirror(sample(h1_close=D("89")),F2Phase.INVALIDATED)

    def test_09_wrong_regime_does_not_inherit_opposite_setup(self):
        self.check_mirror(sample(regime="LH_LL"),F2Phase.NO_SETUP)

    def test_10_wrong_zone_does_not_inherit_opposite_setup(self):
        self.check_mirror(sample(zone_side="RESISTANCE"),F2Phase.NO_SETUP)

    def test_11_incomplete_source_cannot_be_not_detected_or_confirmed(self):
        self.check_mirror(sample(source_complete=False),F2Phase.UNVERIFIED)

    def test_12_micro_level_must_exist_before_candle_open(self):
        with self.assertRaisesRegex(ValueError,"FIRST_KNOWN_CAUSALITY"):
            sample(micro_first_known_utc=BASE)

    def test_13_closed_candle_and_first_known_must_precede_asof(self):
        for overrides in (
            {"m15_first_known_utc":BASE+timedelta(seconds=1)},
            {"m15_closed_utc":BASE+timedelta(seconds=1)},
            {"m15_start_utc":BASE},
        ):
            with self.assertRaisesRegex(ValueError,"CAUSALITY"):
                sample(**overrides)

    def test_14_utc_timestamp_required(self):
        with self.assertRaisesRegex(ValueError,"EXPLICIT_UTC"):
            sample(asof_utc=BASE.replace(tzinfo=None))

    def test_15_invalid_prices_nan_infinite_negative_and_reflection(self):
        for x in (D("NaN"),D("Infinity"),D("-1"),D("0")):
            with self.assertRaisesRegex(ValueError,"POSITIVE_FINITE"):
                sample(micro_level=x)
        with self.assertRaisesRegex(ValueError,"POSITIVE_FINITE"):
            reflect_f2_design(sample(mirror_anchor=D("1")))

    def test_16_unrecognized_rules_and_directional_labels_rejected(self):
        for k,v in (
            ("rule_id","B1"),("pivot","HL_UNVERIFIED"),
            ("regime","SYNTHETIC"),("internal_bos","BOS_NEUTRAL"),
            ("zone_side","OTHER"),
        ):
            with self.assertRaises(ValueError):
                sample(**{k:v})

    def test_17_strict_event_identity_boolean_and_immutable_record(self):
        for val in ("", "SIM EVENT", "x"*97, "test@example.com"):
            with self.assertRaises(ValueError):
                sample(event_id=val)
        with self.assertRaisesRegex(ValueError,"TYPED_BOOLEAN"):
            sample(zone_reentry=1)
        with self.assertRaisesRegex(FrozenInstanceError,"cannot assign"):
            e=sample()
            e.event_id="OTHER"

    def test_18_symmetry_is_involution_and_mapping_is_exact(self):
        a=sample()
        self.assertEqual(set(PAIR),{"B2","S2"})
        self.assertEqual(reflect_f2_design(reflect_f2_design(a)),a)
        self.assertEqual(
            reflect_f2_design(reflect_f2_design(reflect_f2_design(a))),
            reflect_f2_design(a),
        )

    def test_19_public_rights_and_numeric_source_are_always_denied(self):
        for e in (sample(),reflect_f2_design(sample())):
            a=evaluate_f2_design(e)
            self.assertEqual(a.version,VERSION)
            self.assertEqual(a.source_numeric_approvals,0)
            self.assertEqual(a.remaining_owner_decisions,36)
            for k in ("original_forex_numerical_parity_verified",
                      "publisher_first_known_verified",
                      "provider_market_rights_verified",
                      "real_bidask_cost_verified","historical_oos_verified",
                      "may_publish_buy_sell","may_execute_broker_order"):
                self.assertIs(getattr(a,k),False)

    def test_20_contract_cannot_mutate_original_frozen_source_or_schedule(self):
        src=Path("mfx_research/p182_f2_directional_mirror.py").read_text()
        for forbidden in (
            "googleapiclient", "requests.post", "urllib.request",
            "time_series(", "broker.submit", "DriveFileStore",
            "os.environ", "MFX_V1_SIX_TF_MANUAL_READONLY_APPROVED",
        ):
            self.assertNotIn(forbidden,src)
        spec=Path("docs/MFX_P182_F2_B2_S2_MIRROR_CONTRACT.md").read_text()
        self.assertIn("Original owner numeric approvals: **0/36**",spec)
        self.assertIn("NO_SIGNAL",spec)
