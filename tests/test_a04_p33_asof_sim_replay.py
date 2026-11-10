"""P0.33: 24 preregistered strictly chronological SIM OHLC replay tests.

Only experimental B2/S2 computed patterns; no full-zone source numeric
approval, historical P&L, true OOS evidence or market execution rights.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from forex_trading.catalog import ZONES, validate_catalog
from forex_trading.market_data import BarCoverage, BarLifecycle
from mfx_research.causal_multitf_context import SyntheticMultiTfBars
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p030_approved_nonentry_design import read_22_zone_design_manifest
from mfx_research.p031_sim_22_zone_router import VERSION as P031_VERSION
from mfx_research.p032_synthetic_ohlc_bridge import VERSION as P032_VERSION
from mfx_research.p033_asof_sim_replay import (
    GENESIS_SHA256, MAX_WINDOWS, VERSION,
    ResearchReplayReport, SyntheticReplayWindow, run_asof_sim_ohlc_replay,
    verify_sim_replay_chain,
)
from tools.run_a04_p19_causal_context_demo import case_from_closed_bars

DAY = timedelta(days=1)
ONE_SECOND = timedelta(seconds=1)


def shift_bar(bar: object, delay: timedelta):
    key = replace(bar.key,
                  bar_start_utc=bar.key.bar_start_utc + delay,
                  bar_end_utc=bar.key.bar_end_utc + delay)
    observation = replace(
        bar.observation,
        first_known_utc=bar.observation.first_known_utc + delay,
        retrieved_at_utc=bar.observation.retrieved_at_utc + delay,
    )
    return replace(bar, key=key, observation=observation,
                   first_known_utc=bar.first_known_utc + delay)


def shift_bars(bars: SyntheticMultiTfBars,
               delay: timedelta) -> SyntheticMultiTfBars:
    return SyntheticMultiTfBars(
        daily=tuple(shift_bar(x, delay) for x in bars.daily),
        four_hour=tuple(shift_bar(x, delay) for x in bars.four_hour),
        hourly=tuple(shift_bar(x, delay) for x in bars.hourly),
        micro_seed_m15=tuple(shift_bar(x, delay) for x in bars.micro_seed_m15),
        trigger_m15=tuple(shift_bar(x, delay) for x in bars.trigger_m15),
    )


def w(rule: str = "B2", day: int = 0) -> SyntheticReplayWindow:
    bars, derivation, params = case_from_closed_bars(rule)
    shifted = shift_bars(bars, DAY * day)
    return SyntheticReplayWindow(
        rule_id=rule, bars=shifted, derivation=derivation,
        parameters=params,
        decision_utc=shifted.trigger_m15[-1].first_known_utc + ONE_SECOND,
    )


def report(*cases: SyntheticReplayWindow) -> ResearchReplayReport:
    asof = max((x.decision_utc for x in cases), default=datetime(
        2026, 11, 10, tzinfo=timezone.utc))
    return run_asof_sim_ohlc_replay(tuple(cases), asof)


def shifted_changed(window: SyntheticReplayWindow) -> SyntheticReplayWindow:
    prior = window.bars.hourly[0]
    changed = replace(prior, close=prior.close + Decimal("0.00001"))
    return replace(window, bars=replace(
        window.bars,
        hourly=(changed,)+window.bars.hourly[1:],
    ))


class P033AsOfSyntheticReplayTests(unittest.TestCase):
    def test_01_frozen_forex18_and_approved_mfx22(self) -> None:
        validate_catalog(ZONES)
        self.assertEqual(len(ZONES), 18)
        r = read_22_zone_design_manifest()
        self.assertEqual(len(r.zones), 22)
        self.assertEqual(len(r.entry_long_labels), 8)
        self.assertEqual(len(r.entry_short_labels), 8)

    def test_02_b2_computed_buy_unverified_replay(self) -> None:
        r = report(w("B2"))
        self.assertEqual(r.executed_sim_snapshots, 1)
        self.assertEqual(r.experimental_pattern_observations, 1)
        self.assertIs(r.entries[0].experimental_pattern, CandidateAction.BUY)
        self.assertEqual(r.entries[0].linked_research_labels, ("B2",))
        self.assertEqual(r.entries[0].action, "NO_SIGNAL")
        self.assertTrue(verify_sim_replay_chain(r))

    def test_03_s2_computed_sell_later(self) -> None:
        r = report(w("B2"), w("S2", 1))
        self.assertEqual(r.executed_sim_snapshots, 2)
        self.assertEqual(r.experimental_pattern_observations, 2)
        self.assertIs(r.entries[1].experimental_pattern, CandidateAction.SELL)
        self.assertEqual(r.entries[1].linked_research_labels, ("S2",))

    def test_04_valid_no_pattern_snapshot_stays_in_ledger(self) -> None:
        base = w("B2")
        old, latest = base.bars.trigger_m15
        last = replace(latest, close=old.close)
        no_pattern = replace(base, bars=replace(
            base.bars, trigger_m15=(old, last)))
        r = report(no_pattern)
        self.assertEqual(r.no_pattern_snapshots, 1)
        self.assertEqual(r.experimental_pattern_observations, 0)
        self.assertEqual(r.entries[0].linked_research_labels, ())
        self.assertEqual(r.entries[0].computed_receipt.classified_output.events, ())
        self.assertTrue(verify_sim_replay_chain(r))

    def test_05_chronological_asof_after_source_first_known(self) -> None:
        r = report(w("B2"), w("S2", 1))
        self.assertLess(r.entries[0].decision_utc, r.entries[1].decision_utc)
        for entry in r.entries:
            self.assertLessEqual(entry.computed_receipt.first_known_utc,
                                 entry.decision_utc)
        self.assertEqual(r.replay_asof_utc, r.entries[-1].decision_utc)

    def test_06_identical_replay_yields_stable_hash_chain(self) -> None:
        a, b = report(w("B2"), w("S2", 1)), report(w("B2"), w("S2", 1))
        self.assertEqual(a, b)
        self.assertRegex(a.chain_tip_sha256, "^[a-f0-9]{64}$")
        self.assertNotEqual(a.chain_tip_sha256, GENESIS_SHA256)

    def test_07_future_appended_window_cannot_modify_prefix(self) -> None:
        one = report(w("B2"))
        two = report(w("B2"), w("S2", 1))
        self.assertEqual(one.entries, two.entries[:1])
        self.assertEqual(one.chain_tip_sha256,
                         two.entries[0].chain_sha256)
        self.assertNotEqual(one.chain_tip_sha256, two.chain_tip_sha256)

    def test_08_change_only_later_input_changes_only_later_link(self) -> None:
        early, late = w("B2"), w("S2", 1)
        a, b = report(early, late), report(early, shifted_changed(late))
        self.assertEqual(a.entries[0], b.entries[0])
        self.assertNotEqual(a.entries[1].research_input_sha256,
                            b.entries[1].research_input_sha256)
        self.assertNotEqual(a.entries[1].chain_sha256,
                            b.entries[1].chain_sha256)
        self.assertTrue(verify_sim_replay_chain(b))

    def test_09_tampered_link_or_tip_fails_verification(self) -> None:
        r = report(w("B2"), w("S2", 1))
        tampered = replace(r, entries=(
            r.entries[0], replace(r.entries[1],
                                  payload_sha256="0" * 64)))
        with self.assertRaisesRegex(ValueError, "HASH_CHAIN_TAMPER"):
            verify_sim_replay_chain(tampered)
        with self.assertRaisesRegex(ValueError, "TIP_OR_PATTERN"):
            verify_sim_replay_chain(replace(r, chain_tip_sha256="0" * 64))

    def test_10_first_snapshot_price_fingerprint_is_frozen_in_prefix(self) -> None:
        first, second = report(w("B2")), report(w("B2"), w("S2", 1))
        self.assertEqual(first.entries[0].research_input_sha256,
                         second.entries[0].research_input_sha256)
        self.assertEqual(first.entries[0].payload_sha256,
                         second.entries[0].payload_sha256)

    def test_11_duplicate_identical_source_event_fails_closed(self) -> None:
        original = w("B2")
        duplicate = replace(
            original, decision_utc=original.decision_utc + ONE_SECOND)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_REVISED"):
            report(original, duplicate)

    def test_12_duplicate_source_event_with_changed_price_fails(self) -> None:
        original = w("B2")
        revised = shifted_changed(replace(
            original, decision_utc=original.decision_utc + ONE_SECOND))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_REVISED"):
            report(original, revised)

    def test_13_same_origin_with_different_pilot_fails(self) -> None:
        first = w("B2")
        second = replace(first, rule_id="S2",
                         decision_utc=first.decision_utc + ONE_SECOND)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_REVISED"):
            report(first, second)

    def test_14_out_of_order_decision_clocks_denied(self) -> None:
        with self.assertRaisesRegex(ValueError, "NONINCREASING_REPLAY"):
            report(w("S2", 1), w("B2"))

    def test_15_equal_decision_clocks_denied(self) -> None:
        a, b = w("B2"), w("S2", 1)
        with self.assertRaisesRegex(ValueError, "NONINCREASING_REPLAY"):
            report(a, replace(b, decision_utc=a.decision_utc))

    def test_16_global_asof_cutoff_before_window_denied(self) -> None:
        a = w("B2")
        with self.assertRaisesRegex(ValueError, "FUTURE_REPLAY_WINDOW"):
            run_asof_sim_ohlc_replay((a,),
                                     a.decision_utc - ONE_SECOND)

    def test_17_future_known_h4_denied_before_research_event(self) -> None:
        a = w("B2")
        h4 = a.bars.four_hour[-1]
        late = replace(h4, first_known_utc=(
            a.bars.trigger_m15[0].key.bar_start_utc + ONE_SECOND))
        with self.assertRaisesRegex(ValueError, "FUTURE_KNOWN"):
            report(replace(a, bars=replace(
                a.bars, four_hour=a.bars.four_hour[:-1] + (late,))))

    def test_18_open_or_partial_m15_denied(self) -> None:
        a = w("B2")
        last = a.bars.trigger_m15[-1]
        for bad, marker in (
            (replace(last, lifecycle=BarLifecycle.OPEN), "OPEN_PROVISIONAL"),
            (replace(last, coverage=BarCoverage.PARTIAL),
             "INCOMPLETE_COVERAGE"),
        ):
            with self.subTest(marker=marker), self.assertRaisesRegex(
                ValueError, marker
            ):
                report(replace(a, bars=replace(
                    a.bars, trigger_m15=(a.bars.trigger_m15[0], bad))))

    def test_19_real_vendor_provenance_denied(self) -> None:
        a = w("B2")
        h1 = a.bars.hourly[0]
        changed = replace(h1, observation=replace(
            h1.observation, provider_id="OANDA"))
        with self.assertRaisesRegex(ValueError, "REJECT_REAL_MARKET_SOURCE"):
            report(replace(a, bars=replace(
                a.bars, hourly=(changed,) + a.bars.hourly[1:])))

    def test_20_revised_old_history_denied(self) -> None:
        a = w("B2")
        old = a.bars.daily[0]
        changed = replace(old, revision_number=2)
        with self.assertRaisesRegex(ValueError, "REJECT_REAL_MARKET_SOURCE"):
            report(replace(a, bars=replace(
                a.bars, daily=(changed,) + a.bars.daily[1:])))

    def test_21_mutable_too_many_or_wrong_typed_input_denied(self) -> None:
        a = w("B2")
        with self.assertRaisesRegex(ValueError, "BOUNDED_IMMUTABLE"):
            run_asof_sim_ohlc_replay([a], a.decision_utc)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "BOUNDED_IMMUTABLE"):
            run_asof_sim_ohlc_replay(
                tuple(a for _ in range(MAX_WINDOWS + 1)), a.decision_utc)
        with self.assertRaisesRegex(TypeError, "TYPED_SYNTHETIC_REPLAY"):
            run_asof_sim_ohlc_replay((object(),), a.decision_utc)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "EXACT_UTC"):
            run_asof_sim_ohlc_replay(
                (a,), datetime(2026, 11, 10, 4))
        self.assertEqual(report().chain_tip_sha256, GENESIS_SHA256)

    def test_22_no_research_snapshot_can_publish_or_exit(self) -> None:
        r = report(w("B2"), w("S2", 1))
        self.assertTrue(all(e.action == "NO_SIGNAL" for e in r.entries))
        self.assertTrue(all(
            row.action == "NO_SIGNAL"
            for entry in r.entries
            for row in entry.computed_receipt.classified_output.classified
        ))
        self.assertTrue(all(
            not entry.computed_receipt.may_send_buy_sell_or_exit_alert
            for entry in r.entries
        ))
        self.assertFalse(r.publish_alerts)

    def test_23_original_36_and_zero_market_actions(self) -> None:
        r = report(w("B2"), w("S2", 1))
        self.assertEqual(r.owner_signed_entry_numeric_rules, 0)
        self.assertEqual(r.original_b2_s2_owner_numeric_obligations_pending,
                         36)
        self.assertEqual(r.actual_confirmed_buy_sell_signals, 0)
        self.assertEqual(r.real_market_backtest_trades, 0)
        self.assertEqual(r.actual_out_of_sample_performance_metrics, 0)
        self.assertEqual(r.provider_calls, 0)
        self.assertEqual(r.real_drive_market_cache_writes, 0)
        self.assertEqual(r.broker_orders, 0)
        self.assertFalse(r.release_ready)
        self.assertFalse(r.may_trade)

    def test_24_version_isolated_from_prior_p031_p032_and_source(self) -> None:
        self.assertEqual(
            VERSION, "MFX_A04_P33_CHRONOLOGICAL_SIM_REPLAY_CHAIN_V1")
        self.assertEqual(
            P031_VERSION, "MFX_A04_P31_22_ZONE_SIM_RESEARCH_PRESENTATION_V1")
        self.assertEqual(
            P032_VERSION, "MFX_A04_P32_CAUSAL_SIM_OHLC_TO_22_ZONE_RESEARCH_V1")
        self.assertEqual(len(ZONES), 18)
        self.assertEqual(len(read_22_zone_design_manifest().zones), 22)
        self.assertTrue(verify_sim_replay_chain(report(w("B2"))))


if __name__ == "__main__":
    unittest.main()
