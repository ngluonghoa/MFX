"""A04/P0.32: 24 real synthetic OHLC → unverified router integration tests.

The numbers are SIM experimental research predicates, not source-approved
Forex B2/S2 rules or broker-executable BUY/SELL signals.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re
import unittest

from forex_trading.catalog import ZONES, validate_catalog
from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, SourceQuality,
)
from mfx_research.causal_multitf_context import (
    SyntheticMultiTfBars,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p032_synthetic_ohlc_bridge import (
    SUPPORTED_PILOTS, VERSION, compute_and_route_sim_b2_s2,
)
from mfx_research.p030_approved_nonentry_design import (
    read_22_zone_design_manifest,
)
from mfx_research.p031_sim_22_zone_router import route_sim_22_zone_labels
from tools.run_a04_p19_causal_context_demo import case_from_closed_bars


def case(rule: str = "B2", *, bars: SyntheticMultiTfBars | None = None,
         derivation: object = None, policy: object = None,
         decision: datetime | None = None):
    fixture, derived, params = case_from_closed_bars(rule)
    if bars is not None:
        fixture = bars
    if derivation is not None:
        derived = derivation  # type: ignore[assignment]
    if policy is not None:
        params = policy  # type: ignore[assignment]
    if decision is None:
        decision = fixture.trigger_m15[-1].first_known_utc + timedelta(seconds=1)
    return compute_and_route_sim_b2_s2(rule, fixture, derived, params, decision)


class P032CausalComputedSIMToZoneTests(unittest.TestCase):
    def test_01_frozen_original18_and_current_22(self) -> None:
        validate_catalog(ZONES)
        self.assertEqual(len(ZONES), 18)
        receipt = read_22_zone_design_manifest()
        self.assertEqual(len(receipt.zones), 22)
        self.assertEqual(len(receipt.entry_long_labels), 8)
        self.assertEqual(len(receipt.entry_short_labels), 8)

    def test_02_ohlc_computed_buy_b2_to_one_research_event(self) -> None:
        result = case("B2")
        self.assertIs(result.experimental_numeric_action, CandidateAction.BUY)
        self.assertEqual(len(result.classified_output.classified), 1)
        self.assertEqual(len(result.classified_output.events), 1)
        self.assertEqual(result.classified_output.events[0].entry_long_labels,
                         ("B2",))
        self.assertEqual(result.action, "NO_SIGNAL")

    def test_03_ohlc_computed_sell_s2_to_one_research_event(self) -> None:
        result = case("S2")
        self.assertIs(result.experimental_numeric_action, CandidateAction.SELL)
        self.assertEqual(len(result.classified_output.classified), 1)
        self.assertEqual(len(result.classified_output.events), 1)
        self.assertEqual(result.classified_output.events[0].entry_short_labels,
                         ("S2",))
        self.assertEqual(result.action, "NO_SIGNAL")

    def test_04_closed_ohlc_with_no_trigger_produces_zero_claims(self) -> None:
        b, _, _ = case_from_closed_bars("B2")
        previous, latest = b.trigger_m15
        no_break = replace(latest, close=previous.close)
        got = case("B2", bars=replace(
            b, trigger_m15=(previous, no_break)))
        self.assertIs(got.experimental_numeric_action, CandidateAction.NO_SIGNAL)
        self.assertEqual(got.classified_output.events, ())
        self.assertEqual(got.classified_output.classified, ())

    def test_05_unknown_derived_htf_trend_blocks_event(self) -> None:
        b, _, _ = case_from_closed_bars("B2")
        old = b.daily[0]
        new = replace(b.daily[-1], open=old.close, close=old.close,
                      high=old.high, low=old.low)
        got = case("B2", bars=replace(b, daily=(old, new)))
        self.assertIs(got.experimental_numeric_action, CandidateAction.NO_SIGNAL)
        self.assertEqual(len(got.classified_output.events), 0)

    def test_06_trigger_close_change_removes_previous_candidate(self) -> None:
        b, _, _ = case_from_closed_bars("S2")
        prev, last = b.trigger_m15
        altered = replace(last, close=prev.close)
        result = case("S2", bars=replace(
            b, trigger_m15=(prev, altered)))
        self.assertIs(result.experimental_numeric_action, CandidateAction.NO_SIGNAL)
        self.assertEqual(len(result.classified_output.classified), 0)

    def test_07_h1_zone_far_from_trigger_no_candidate(self) -> None:
        b, _, _ = case_from_closed_bars("S2")
        shifted = tuple(replace(x, open=x.open+Decimal("0.10"),
                                high=x.high+Decimal("0.10"),
                                low=x.low+Decimal("0.10"),
                                close=x.close+Decimal("0.10"))
                        for x in b.hourly)
        got = case("S2", bars=replace(b, hourly=shifted))
        self.assertIs(got.experimental_numeric_action, CandidateAction.NO_SIGNAL)
        self.assertEqual(got.classified_output.events, ())

    def test_08_narrow_sim_anti_chase_policy_blocks_candidate(self) -> None:
        b, d, p = case_from_closed_bars("B2")
        tiny = replace(p, max_chase_atr_multiple=Decimal("0.000001"))
        got = case("B2", bars=b, derivation=d, policy=tiny)
        self.assertIs(got.experimental_numeric_action, CandidateAction.NO_SIGNAL)
        self.assertEqual(got.classified_output.events, ())

    def test_09_ohlc_derives_positive_atr_and_known_structure(self) -> None:
        for rule in SUPPORTED_PILOTS:
            with self.subTest(rule=rule):
                r = case(rule)
                self.assertGreater(r.actual_ohlc_computation.h1_true_range_atr, 0)
                self.assertLessEqual(
                    r.actual_ohlc_computation.known_at_start_utc,
                    r.first_known_utc,
                )
                self.assertEqual(r.context_derived_from,
                                 ("D1", "H4", "H1", "M15"))

    def test_10_closed_first_known_retrieved_decision_provenance(self) -> None:
        b, d, p = case_from_closed_bars("B2")
        r = case("B2", bars=b, derivation=d, policy=p)
        bar = b.trigger_m15[-1]
        self.assertLessEqual(bar.key.bar_end_utc, bar.first_known_utc)
        self.assertLessEqual(bar.first_known_utc,
                             bar.observation.retrieved_at_utc)
        self.assertLessEqual(bar.observation.retrieved_at_utc, r.decision_utc)
        self.assertEqual(r.classified_output.classified[0].first_known_utc,
                         bar.first_known_utc)

    def test_11_mid_only_no_executable_quote_side(self) -> None:
        for rule in SUPPORTED_PILOTS:
            with self.subTest(rule=rule):
                r = case(rule)
                self.assertIs(r.source_price_side, BarSide.MID)
                self.assertFalse(r.may_send_buy_sell_or_exit_alert)
                self.assertFalse(r.release_ready)

    def test_12_all_market_numeric_promotions_denied(self) -> None:
        for rule in SUPPORTED_PILOTS:
            with self.subTest(rule=rule):
                r = case(rule)
                self.assertIs(r.research_phase.value, "UNVERIFIED")
                self.assertFalse(r.pattern_source_numeric_approved)
                self.assertFalse(r.actual_market_data_verified)
                self.assertFalse(r.verified_position)
                self.assertEqual(r.action, "NO_SIGNAL")
                self.assertEqual(r.actual_buy_sell_signals, 0)

    def test_13_experimental_hypothesis_not_frozen_source_approval(self) -> None:
        for rule in SUPPORTED_PILOTS:
            r = case(rule)
            self.assertFalse(
                r.actual_ohlc_computation.signal.original_forex_numerical_parity)
            self.assertFalse(r.actual_ohlc_computation.original_forex_source_signal_parity)
            self.assertIn("SYNTHETIC", r.research_reason)
            self.assertFalse(r.actual_ohlc_computation.may_send_confirmed_signal)

    def test_14_origin_id_deterministic_same_sim_input(self) -> None:
        a, b = case("B2"), case("B2")
        self.assertEqual(a.origin_event_id, b.origin_event_id)
        self.assertRegex(a.origin_event_id, r"^SIM:P032-[a-f0-9]{32}$")
        self.assertEqual(a.research_input_sha256, b.research_input_sha256)
        self.assertEqual(a.classified_output.events, b.classified_output.events)

    def test_15_same_trigger_window_origin_independent_of_rule(self) -> None:
        b2 = case("B2")
        s2 = case("S2")
        self.assertEqual(b2.origin_event_id, s2.origin_event_id)
        self.assertNotEqual(b2.research_input_sha256, s2.research_input_sha256)
        self.assertNotEqual(b2.experimental_numeric_action,
                            s2.experimental_numeric_action)

    def test_16_full_input_sha_changes_with_known_prior_h1_ohlc(self) -> None:
        b, _, _ = case_from_closed_bars("B2")
        old = b.hourly[0]
        changed = replace(old, close=old.close+Decimal("0.0001"))
        got = case("B2", bars=replace(b, hourly=(changed,)+b.hourly[1:]))
        self.assertNotEqual(got.research_input_sha256,
                            case("B2").research_input_sha256)
        self.assertEqual(got.origin_event_id, case("B2").origin_event_id)

    def test_17_future_known_htf_source_denied(self) -> None:
        b, _, _ = case_from_closed_bars("B2")
        late = replace(b.four_hour[-1], first_known_utc=(
            b.trigger_m15[0].key.bar_start_utc + timedelta(seconds=2)))
        with self.assertRaisesRegex(ValueError, "FUTURE_KNOWN"):
            case("B2", bars=replace(
                b, four_hour=b.four_hour[:-1]+(late,)))

    def test_18_open_and_partial_trigger_bar_denied(self) -> None:
        b, _, _ = case_from_closed_bars("B2")
        last = b.trigger_m15[-1]
        for modified, reason in (
            (replace(last, lifecycle=BarLifecycle.OPEN), "OPEN_PROVISIONAL"),
            (replace(last, coverage=BarCoverage.PARTIAL), "INCOMPLETE_COVERAGE"),
            (replace(last, quality=SourceQuality.UNVERIFIED), "QUALITY_UNVERIFIED"),
        ):
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(ValueError, reason):
                    case("B2", bars=replace(
                        b, trigger_m15=(b.trigger_m15[0], modified)))

    def test_19_real_provider_denied(self) -> None:
        b, _, _ = case_from_closed_bars("B2")
        source = replace(b.hourly[-1].observation, provider_id="OANDA")
        with self.assertRaisesRegex(ValueError, "REJECT_REAL_MARKET_SOURCE"):
            case("B2", bars=replace(
                b, hourly=b.hourly[:-1] + (
                    replace(b.hourly[-1], observation=source),)))

    def test_20_revised_bar_denied_even_if_closed(self) -> None:
        b, _, _ = case_from_closed_bars("S2")
        edited = replace(b.daily[-1], revision_number=2)
        with self.assertRaisesRegex(ValueError, "REJECT_REAL_MARKET_SOURCE"):
            case("S2", bars=replace(
                b, daily=b.daily[:-1]+(edited,)))

    def test_21_mixed_calendar_provider_stream_denied(self) -> None:
        b, _, _ = case_from_closed_bars("B2")
        other = replace(b.hourly[-1],
                        key=replace(b.hourly[-1].key,
                                    calendar_version="SIM:OTHER_CAL"))
        with self.assertRaisesRegex(ValueError, "CROSS_TIMEFRAME_IDENTITY"):
            case("B2", bars=replace(b, hourly=b.hourly[:-1]+(other,)))
        other2 = replace(b.hourly[-1], observation=replace(
            b.hourly[-1].observation, stream_id="SIM:OTHER"))
        with self.assertRaisesRegex(ValueError, "INTRA_TIMEFRAME_STREAM"):
            case("B2", bars=replace(b, hourly=b.hourly[:-1]+(other2,)))

    def test_22_invalid_pilot_or_untyped_parameter_denied(self) -> None:
        b, d, p = case_from_closed_bars("B2")
        for name in ("B1", "S1", "FX-B9", "FX-B10", "S8", "B7"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "ONLY_B2_S2"):
                    compute_and_route_sim_b2_s2(name, b, d, p, datetime(
                        2026, 11, 10, tzinfo=timezone.utc))
        with self.assertRaisesRegex(TypeError, "TYPED_SIM_OHLC"):
            compute_and_route_sim_b2_s2("B2", b, d, object(),
                                        b.trigger_m15[-1].first_known_utc)

    def test_23_source_rights_and_broker_stay_zero(self) -> None:
        r = case("B2")
        self.assertEqual(r.real_provider_calls, 0)
        self.assertEqual(r.real_drive_market_cache_writes, 0)
        self.assertEqual(r.broker_orders, 0)
        self.assertEqual(r.classified_output.numeric_entry_predicates_approved, 0)
        self.assertEqual(
            r.classified_output.original_b2_s2_source_numeric_obligations_pending,
            36,
        )
        self.assertFalse(r.classified_output.may_send_live_alerts)
        self.assertFalse(r.classified_output.may_trade)

    def test_24_separation_from_prior_22_claim_router_and_no_hidden_trade(self) -> None:
        self.assertEqual(
            VERSION, "MFX_A04_P32_CAUSAL_SIM_OHLC_TO_22_ZONE_RESEARCH_V1",
        )
        self.assertEqual(route_sim_22_zone_labels(
            (), datetime(2026, 11, 10, tzinfo=timezone.utc)).classified, ())
        for rule in SUPPORTED_PILOTS:
            r = case(rule)
            self.assertEqual(len(r.classified_output.events), 1)
            self.assertFalse(r.classified_output.events[0].may_publish_alert)
            self.assertEqual(r.classified_output.events[0].action, "NO_SIGNAL")
            self.assertEqual(r.classified_output.events[0].actual_numeric_signal_count, 0)
            self.assertFalse(r.may_send_buy_sell_or_exit_alert)


if __name__ == "__main__":
    unittest.main()
