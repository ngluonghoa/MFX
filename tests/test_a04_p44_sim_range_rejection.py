"""A04/P0.44 27 independent offline SIM-OHLC B3/S4 research cases."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, MarketBar, MarketBarKey,
    Observation, SourceQuality, Timeframe,
)
from forex_trading.model import SignalStage
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p030_approved_nonentry_design import (
    read_22_zone_design_manifest,
)
from mfx_research.p044_sim_range_rejection import (
    VERSION, SimRangeResearchBars, SimRangeResearchParameters,
    compute_sim_b3_s4_range_rejection,
)

D = Decimal
UTC = timezone.utc
T = datetime(2026, 11, 10, 8, tzinfo=UTC)


def bar(
    tf: Timeframe, end: datetime,
    o: str, h: str, low_value: str, c: str,
) -> MarketBar:
    span = timedelta(hours=1) if tf is Timeframe.H1 else timedelta(minutes=15)
    key = MarketBarKey(
        instrument_version="SIM:EURUSD",
        timeframe=tf, bar_start_utc=end - span, bar_end_utc=end,
        calendar_version="SIM:UTC_CLOCK",
        aggregation_version="SIM:AGG",
        side=BarSide.MID,
    )
    obs = Observation(
        provider_id="SIM:OFFLINE",
        stream_id="SIM:H1_CLOSED" if tf is Timeframe.H1 else "SIM:M15_CLOSED",
        endpoint="SIM:IN_MEMORY", revision_id="SIM:REV1",
        raw_sha256="a" * 64,
        first_known_utc=end, retrieved_at_utc=end,
        source_timezone_policy="SIM:UTC",
        license_scope_claim="SYNTHETIC_ONLY",
    )
    return MarketBar(
        key=key, observation=obs,
        revision_number=1, first_known_utc=end,
        open=D(o), high=D(h), low=D(low_value), close=D(c),
        lifecycle=BarLifecycle.CLOSED, coverage=BarCoverage.COMPLETE,
        quality=SourceQuality.VERIFIED,
    )


def fixture(rule: str = "B3") -> tuple[SimRangeResearchBars, SimRangeResearchParameters, datetime]:
    hourly = tuple(
        bar(Timeframe.H1, T - timedelta(hours=4-i),
            "1.105", "1.110", "1.100", "1.105")
        for i in range(5)
    )
    if rule == "B3":
        prior = bar(Timeframe.M15, T + timedelta(minutes=15),
                    "1.100", "1.101", "1.098", "1.099")
        latest = bar(Timeframe.M15, T + timedelta(minutes=30),
                     "1.099", "1.105", "1.0988", "1.103")
    else:
        prior = bar(Timeframe.M15, T + timedelta(minutes=15),
                    "1.110", "1.112", "1.109", "1.111")
        latest = bar(Timeframe.M15, T + timedelta(minutes=30),
                     "1.111", "1.112", "1.106", "1.107")
    params = SimRangeResearchParameters(
        version="SIM:P044_TEST_V1", h1_lookback=4,
        min_edge_touches=2,
        touch_tolerance_true_range_multiple=D("0.10"),
        max_sweep_true_range_multiple=D("0.50"),
        reclaim_margin_true_range_multiple=D("0.10"),
    )
    return SimRangeResearchBars(hourly, (prior, latest)), params, T + timedelta(minutes=31)


def run(rule: str = "B3", *,
        data: SimRangeResearchBars | None = None,
        policy: SimRangeResearchParameters | None = None,
        decision: datetime | None = None):
    bars, params, t = fixture(rule)
    return compute_sim_b3_s4_range_rejection(
        rule, bars if data is None else data,
        params if policy is None else policy,
        t if decision is None else decision,
    )


class P044RangeResearchTests(unittest.TestCase):
    def test_01_b3_computed_buy_h1_m15(self) -> None:
        r = run("B3")
        self.assertIs(r.experimental_pattern, CandidateAction.BUY)
        self.assertEqual(r.research_reason, "SIM_P044_B3_LOWER_RANGE_SWEEP_AND_CLOSED_RECLAIM")
        self.assertEqual(r.classified_output.events[0].entry_long_labels, ("B3",))

    def test_02_s4_computed_sell_h1_m15(self) -> None:
        r = run("S4")
        self.assertIs(r.experimental_pattern, CandidateAction.SELL)
        self.assertEqual(r.research_reason, "SIM_P044_S4_UPPER_RANGE_SWEEP_AND_CLOSED_REJECTION")
        self.assertEqual(r.classified_output.events[0].entry_short_labels, ("S4",))

    def test_03_known_range_and_volatility_proxy(self) -> None:
        for rule in ("B3", "S4"):
            r = run(rule)
            self.assertEqual((r.observed_h1_range_low, r.observed_h1_range_high),
                             (D("1.100"), D("1.110")))
            self.assertEqual(r.h1_mean_true_range, D("0.010"))
            self.assertEqual((r.lower_boundary_touches, r.upper_boundary_touches),
                             (4, 4))

    def test_04_experimental_only_no_live_actions(self) -> None:
        for rule in ("B3", "S4"):
            r = run(rule)
            self.assertIs(r.stage, SignalStage.UNVERIFIED)
            self.assertEqual(r.action, "NO_SIGNAL")
            self.assertFalse(r.source_numeric_approved)
            self.assertFalse(r.original_forex_numeric_parity)
            self.assertFalse(r.original_h4_range_validation_proven)
            self.assertFalse(r.publish_alerts)
            self.assertFalse(r.release_ready)
            self.assertEqual((r.actual_confirmed_signals, r.real_provider_calls,
                              r.drive_real_quote_cache_writes, r.broker_orders),
                             (0, 0, 0, 0))
            self.assertEqual(r.classified_output.numeric_entry_predicates_approved, 0)

    def test_05_exact_taxonomy_preserved(self) -> None:
        m = read_22_zone_design_manifest()
        self.assertEqual((len(m.zones), len(m.entry_long_labels),
                          len(m.entry_short_labels)), (22, 8, 8))
        self.assertEqual(run("B3").classified_output.mfx_design_labels, 22)

    def test_06_b3_closes_inside_without_sweep_no_pattern(self) -> None:
        bars, params, now = fixture("B3")
        a, b = bars.trigger_m15
        changed = replace(a, low=D("1.100"), close=D("1.1005"))
        r = run("B3", data=replace(bars, trigger_m15=(changed, b)))
        self.assertIs(r.experimental_pattern, CandidateAction.NO_SIGNAL)
        self.assertEqual(r.classified_output.events, ())

    def test_07_s4_no_close_above_upper_no_pattern(self) -> None:
        bars, _, _ = fixture("S4")
        a, b = bars.trigger_m15
        changed = replace(a, high=D("1.110"), close=D("1.1095"))
        r = run("S4", data=replace(bars, trigger_m15=(changed, b)))
        self.assertIs(r.experimental_pattern, CandidateAction.NO_SIGNAL)
        self.assertEqual(r.classified_output.events, ())

    def test_08_b3_deep_sweep_exceeds_limit_no_pattern(self) -> None:
        bars, _, _ = fixture("B3")
        a, b = bars.trigger_m15
        r = run("B3", data=replace(bars, trigger_m15=(
            replace(a, low=D("1.090")), b)))
        self.assertIs(r.experimental_pattern, CandidateAction.NO_SIGNAL)

    def test_09_s4_deep_sweep_exceeds_limit_no_pattern(self) -> None:
        bars, _, _ = fixture("S4")
        a, b = bars.trigger_m15
        r = run("S4", data=replace(bars, trigger_m15=(
            replace(a, high=D("1.121")), b)))
        self.assertIs(r.experimental_pattern, CandidateAction.NO_SIGNAL)

    def test_10_b3_reclaim_not_deep_enough_no_pattern(self) -> None:
        bars, _, _ = fixture("B3")
        a, b = bars.trigger_m15
        changed = replace(b, close=D("1.1005"))
        self.assertIs(run("B3", data=replace(
            bars, trigger_m15=(a, changed))).experimental_pattern,
            CandidateAction.NO_SIGNAL)

    def test_11_s4_rejection_not_deep_enough_no_pattern(self) -> None:
        bars, _, _ = fixture("S4")
        a, b = bars.trigger_m15
        changed = replace(b, close=D("1.1095"))
        self.assertIs(run("S4", data=replace(
            bars, trigger_m15=(a, changed))).experimental_pattern,
            CandidateAction.NO_SIGNAL)

    def test_12_b3_no_micro_high_break_no_pattern(self) -> None:
        bars, _, _ = fixture("B3")
        a, b = bars.trigger_m15
        changed = replace(a, high=D("1.105"))
        r = run("B3", data=replace(bars, trigger_m15=(changed, b)))
        self.assertIs(r.experimental_pattern, CandidateAction.NO_SIGNAL)

    def test_13_s4_no_micro_low_break_no_pattern(self) -> None:
        bars, _, _ = fixture("S4")
        a, b = bars.trigger_m15
        changed = replace(a, low=D("1.106"))
        r = run("S4", data=replace(bars, trigger_m15=(changed, b)))
        self.assertIs(r.experimental_pattern, CandidateAction.NO_SIGNAL)

    def test_14_missing_boundary_touches_no_pattern(self) -> None:
        bars, policy, _ = fixture("B3")
        changed = replace(bars.hourly[1], high=D("1.109"), low=D("1.101"))
        r = run("B3", data=replace(
            bars, hourly=(bars.hourly[0], changed, *bars.hourly[2:])),
            policy=replace(policy, min_edge_touches=4))
        self.assertEqual(r.research_reason,
                         "SIM_P044_PRIOR_H1_RANGE_TOUCH_COUNT_NOT_MET")
        self.assertIs(r.experimental_pattern, CandidateAction.NO_SIGNAL)

    def test_15_future_h1_retrieval_rejected(self) -> None:
        bars, _, _ = fixture("B3")
        h = bars.hourly[-1]
        future = replace(h, observation=replace(
            h.observation, retrieved_at_utc=T+timedelta(seconds=1)))
        with self.assertRaisesRegex(ValueError, "P019_FUTURE_KNOWN"):
            run("B3", data=replace(
                bars, hourly=bars.hourly[:-1] + (future,)))

    def test_16_open_m15_rejected(self) -> None:
        bars, _, _ = fixture("S4")
        a, b = bars.trigger_m15
        with self.assertRaisesRegex(ValueError, "OPEN_PROVISIONAL_BAR"):
            run("S4", data=replace(
                bars, trigger_m15=(a, replace(b, lifecycle=BarLifecycle.OPEN))))

    def test_17_partial_coverage_rejected(self) -> None:
        bars, _, _ = fixture("B3")
        a, b = bars.trigger_m15
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_COVERAGE"):
            run("B3", data=replace(
                bars, trigger_m15=(a, replace(b, coverage=BarCoverage.PARTIAL))))

    def test_18_unverified_h1_rejected(self) -> None:
        bars, _, _ = fixture("S4")
        with self.assertRaisesRegex(ValueError, "SOURCE_QUALITY_UNVERIFIED"):
            run("S4", data=replace(bars, hourly=(
                replace(bars.hourly[0], quality=SourceQuality.UNVERIFIED),
                *bars.hourly[1:])))

    def test_19_real_source_rejected_before_pattern(self) -> None:
        bars, _, _ = fixture("B3")
        h = bars.hourly[-1]
        real = replace(h, observation=replace(
            h.observation, provider_id="TWELVE_DATA"))
        with self.assertRaisesRegex(ValueError, "P019_REJECT_REAL_MARKET_SOURCE"):
            run("B3", data=replace(bars, hourly=bars.hourly[:-1]+(real,)))

    def test_20_historical_revision_denied(self) -> None:
        bars, _, _ = fixture("S4")
        h = bars.hourly[-1]
        with self.assertRaisesRegex(ValueError, "P019_REJECT_REAL_MARKET_SOURCE"):
            run("S4", data=replace(
                bars, hourly=bars.hourly[:-1]+(replace(h, revision_number=2),)))

    def test_21_missing_h1_bar_denied(self) -> None:
        bars, _, _ = fixture("B3")
        with self.assertRaisesRegex(ValueError, "P044_EXACT_H1_LOOKBACK"):
            run("B3", data=replace(bars, hourly=bars.hourly[1:]))

    def test_22_gap_between_h1_or_m15_denied(self) -> None:
        bars, _, _ = fixture("B3")
        old = bars.hourly[2]
        skipped = replace(old, key=replace(
            old.key, bar_start_utc=old.key.bar_start_utc+timedelta(minutes=1)))
        with self.assertRaisesRegex(ValueError, "P019_SIM_UTC_TIMEFRAME_DURATION"):
            run("B3", data=replace(bars, hourly=(
                *bars.hourly[:2], skipped, *bars.hourly[3:])))

    def test_23_mixed_calendar_and_price_side_denied(self) -> None:
        bars, _, _ = fixture("B3")
        a, b = bars.trigger_m15
        other_cal = replace(b, key=replace(b.key, calendar_version="SIM:OTHER"))
        with self.assertRaisesRegex(ValueError, "CROSS_TIMEFRAME_IDENTITY_CONFLICT"):
            run("B3", data=replace(bars, trigger_m15=(a, other_cal)))
        other_side = replace(b, key=replace(b.key, side=BarSide.ASK))
        with self.assertRaisesRegex(ValueError, "CROSS_TIMEFRAME_OR_SIDE_MISMATCH"):
            run("B3", data=replace(bars, trigger_m15=(a, other_side)))

    def test_24_parameter_types_bounds_fail_closed(self) -> None:
        _, p, _ = fixture("B3")
        for field, val in (
            ("h1_lookback", True),
            ("h1_lookback", 1),
            ("min_edge_touches", 1),
            ("min_edge_touches", 10),
            ("touch_tolerance_true_range_multiple", D("NaN")),
            ("max_sweep_true_range_multiple", D("0")),
            ("reclaim_margin_true_range_multiple", D("21")),
            ("max_sweep_true_range_multiple", 0.5),
            ("version", "PRODUCTION:P044"),
        ):
            with self.subTest(field=field, val=val), self.assertRaises(ValueError):
                replace(p, **{field: val})

    def test_25_no_unapproved_zone_or_untyped_inputs(self) -> None:
        bars, p, decision = fixture("B3")
        for rule in ("B1", "S6", "FX-B9", "B7", "S3", "FX-B10"):
            with self.subTest(rule=rule), self.assertRaisesRegex(
                ValueError, "P044_ONLY_B3_S4"):
                compute_sim_b3_s4_range_rejection(rule, bars, p, decision)
        with self.assertRaisesRegex(TypeError, "P044_TYPED_SIM_RANGE_POLICY"):
            compute_sim_b3_s4_range_rejection("B3", bars, object(), decision)

    def test_26_unchanged_fixture_deterministic_fingerprint_and_origin(self) -> None:
        a, b = run("B3"), run("B3")
        self.assertEqual(a, b)
        self.assertEqual(a.version, VERSION)
        self.assertEqual(len(a.input_fingerprint_sha256), 64)
        self.assertTrue(a.origin_event_id.startswith("SIM:P044-"))

    def test_27_provenance_changes_with_prior_H1_price_no_hindsight_signal(self) -> None:
        bars, _, _ = fixture("B3")
        old = bars.hourly[0]
        revised = replace(old, close=D("1.106"))
        r = run("B3", data=replace(
            bars, hourly=(revised, *bars.hourly[1:])))
        self.assertNotEqual(r.input_fingerprint_sha256,
                            run("B3").input_fingerprint_sha256)
        self.assertEqual(r.origin_event_id, run("B3").origin_event_id)
        self.assertEqual(r.action, "NO_SIGNAL")


if __name__ == "__main__":
    unittest.main()
