"""A03/P0.1 seeded synthetic property/metamorphic tests (no provider IO).

All draws are reproducible on GitHub Cloud for Python 3.11/3.12.
These properties cover present read-only contracts; there is NO executable
numeric zone detector, TP/SL fill simulator, licensed BID/ASK, or real trading.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from random import Random
import unittest

from forex_trading.cache_core import (
    CachePartition, CandleSnapshot, ChangeKind, IncrementalPolicy, RefreshMode,
    plan_incremental_refresh, reconcile_closed_delta,
)
from forex_trading.cache_dependency import (
    CacheArtifactFingerprint, CacheLayer, CacheNode, assess_artifact_reuse,
    dirty_dependency_closure,
)
from forex_trading.cache_indicators import ema_full, ema_recompute
from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, MarketBar, MarketBarKey, Observation,
    SourceQuality, Timeframe, evaluate_closed_bar, select_asof_revision,
)
from forex_trading.model import ActionIntent
from forex_trading.quotes import (
    PriceSide, Quote, QuoteQuality, indicative_price,
)
from forex_trading.source_calendar import resolve_local_wall_time


T = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
M = timedelta(minutes=1)
S = timedelta(seconds=1)
SEED = 0xA032026
RANGE = 96
SIDES = {
    ActionIntent.ENTRY_LONG: PriceSide.ASK,
    ActionIntent.EXIT_LONG: PriceSide.BID,
    ActionIntent.ENTRY_SHORT: PriceSide.BID,
    ActionIntent.EXIT_SHORT: PriceSide.ASK,
}


def _quote(bid: Decimal, spread: Decimal, known_at: datetime = T + M) -> Quote:
    return Quote("SYNTH-ONLY", "REV-A03", T, known_at,
                 bid, bid + spread, QuoteQuality.VERIFIED)


def _bar(
    index: int, *, revision: int = 1, known_at: datetime | None = None,
    side: BarSide = BarSide.BID, close: Decimal = Decimal("1.1200"),
) -> MarketBar:
    start = T + index * 5 * M
    end = start + 5 * M
    when = known_at or end + S
    key = MarketBarKey(
        "EURUSD-SYNTH", Timeframe.M5, start, end,
        "CAL-A03", "AGG-A03", side,
    )
    obs = Observation(
        "SYNTH-PROVIDER", "SYNTH-BID", "NO-IO", f"REV-{revision}",
        str(revision % 10) * 64, when, when, "UTC-SYNTH", "NO-REAL-RIGHTS",
    )
    return MarketBar(key, obs, revision, when, Decimal("1.1000"),
                     Decimal("1.2000"), Decimal("1.0000"), close,
                     BarLifecycle.CLOSED, BarCoverage.COMPLETE,
                     SourceQuality.VERIFIED)


def _partition() -> CachePartition:
    return CachePartition(
        "SYNTH-PROVIDER", "NO-BROKER", "EURUSD-SYNTH",
        BarSide.BID, Timeframe.M5, "CAL-A03", "AGG-A03",
        "UTC-SYNTH", "NO-REAL-RIGHTS", "SCHEMA-A03",
    )


def _snapshot(count: int) -> CandleSnapshot:
    return CandleSnapshot(
        _partition(), tuple(_bar(i) for i in range(count)),
        T + count * 5 * M + 2 * S, "HEAD-SYNTH",
    )


def _cache_chain(pairs: tuple[str, ...]) -> tuple[CacheNode, ...]:
    return tuple(
        CacheNode(f"{pair}-L{layer}", CacheLayer(layer),
                  f"PART-{pair}", "ALG-A03", "PARAM-A03",
                  () if layer == 1 else (f"{pair}-L{layer-1}",))
        for pair in pairs for layer in range(1, 6)
    )


class A03SeededReadOnlyProperties(unittest.TestCase):
    def test_quote_bid_ask_action_matrix_for_seeded_spreads(self):
        rng = Random(SEED)
        for trial in range(RANGE):
            bid = Decimal(rng.randrange(70000, 170000)) / Decimal("100000")
            spread = Decimal(rng.randrange(0, 100)) / Decimal("100000")
            quote = _quote(bid, spread)
            for intent, side in SIDES.items():
                with self.subTest(trial=trial, intent=intent.value):
                    result = indicative_price(quote, intent, T + 2 * M, 10 * M)
                    self.assertEqual(result.side, side)
                    self.assertEqual(result.value, quote.ask if side is PriceSide.ASK else quote.bid)
                    self.assertEqual(result.source_revision, "REV-A03")

    def test_quote_shift_both_sides_is_price_translation_invariant(self):
        rng = Random(SEED + 1)
        for i in range(RANGE):
            bid = Decimal(rng.randrange(95000, 105000)) / Decimal("100000")
            spread = Decimal(rng.randrange(1, 45)) / Decimal("100000")
            shift = Decimal(rng.randrange(1, 900)) / Decimal("100000")
            original = _quote(bid, spread)
            shifted = _quote(bid + shift, spread)
            for intent in ActionIntent:
                with self.subTest(i=i, intent=intent.value):
                    a = indicative_price(original, intent, T + 2 * M, 10 * M)
                    b = indicative_price(shifted, intent, T + 2 * M, 10 * M)
                    self.assertEqual(b.value - a.value, shift)
                    self.assertEqual(a.side, b.side)

    def test_widening_spread_affects_ask_only_for_fixed_bid(self):
        rng = Random(SEED + 2)
        for trial in range(RANGE):
            bid = Decimal(rng.randrange(90000, 120000)) / Decimal("100000")
            q1 = _quote(bid, Decimal("0.0001"))
            q2 = _quote(bid, Decimal("0.0009"))
            for intent in ActionIntent:
                with self.subTest(trial=trial, intent=intent.value):
                    v1 = indicative_price(q1, intent, T + 2 * M, 10 * M)
                    v2 = indicative_price(q2, intent, T + 2 * M, 10 * M)
                    self.assertEqual(v2.value - v1.value,
                                     Decimal("0.0008") if v1.side is PriceSide.ASK
                                     else Decimal("0"))

    def test_quote_known_time_boundary_is_inclusive_then_stale(self):
        rng = Random(SEED + 3)
        for i in range(RANGE):
            max_age = timedelta(seconds=rng.randrange(1, 3601))
            quote = _quote(Decimal("1.12"), Decimal("0.0002"))
            with self.subTest(i=i):
                self.assertEqual(indicative_price(
                    quote, ActionIntent.ENTRY_LONG,
                    quote.first_known_utc + max_age, max_age,
                ).side, PriceSide.ASK)
                with self.assertRaisesRegex(ValueError, "stale"):
                    indicative_price(quote, ActionIntent.ENTRY_LONG,
                                     quote.first_known_utc + max_age + S, max_age)

    def test_future_or_unverified_quote_never_approved_by_clock(self):
        for offset in range(1, 64):
            quote = _quote(Decimal("1.12"), Decimal("0.0002"),
                           T + offset * M)
            with self.subTest(offset=offset):
                with self.assertRaisesRegex(ValueError, "not yet known"):
                    indicative_price(quote, ActionIntent.ENTRY_SHORT,
                                     quote.first_known_utc - S, 90 * M)
                with self.assertRaisesRegex(ValueError, "unverified"):
                    indicative_price(replace(quote, quality=QuoteQuality.UNVERIFIED),
                                     ActionIntent.ENTRY_SHORT,
                                     quote.first_known_utc, 90 * M)

    def test_crossed_bid_ask_and_nonfinite_prices_are_rejected(self):
        for n in range(1, 50):
            with self.subTest(n=n):
                with self.assertRaises(ValueError):
                    _quote(Decimal(n) / 100, Decimal("-0.00001"))
                with self.assertRaises(ValueError):
                    _quote(Decimal(n) / 100, Decimal("NaN"))

    def test_asof_future_revisions_never_change_past_selection(self):
        rng = Random(SEED + 5)
        for i in range(RANGE):
            old = _bar(i)
            later = _bar(i, revision=2,
                         known_at=old.first_known_utc +
                         timedelta(minutes=rng.randrange(2, 150)),
                         close=Decimal("1.1300"))
            cutoff = old.first_known_utc + S
            with self.subTest(i=i):
                self.assertEqual(select_asof_revision((old,), cutoff), old)
                self.assertEqual(select_asof_revision((later, old), cutoff), old)
                self.assertEqual(select_asof_revision((old, later),
                                                      later.first_known_utc), later)

    def test_no_closed_bar_gate_grants_trade_authority(self):
        for i in range(RANGE):
            m5 = _bar(i)
            cutoff = m5.first_known_utc + M
            earlier_htf = m5.first_known_utc - S
            with self.subTest(i=i):
                blocked = evaluate_closed_bar(m5, cutoff)
                armed = evaluate_closed_bar(
                    m5, cutoff, conditional_m5_early_enabled=True,
                    htf_context_first_known_utc=earlier_htf,
                )
                self.assertFalse(blocked.permission_to_trade)
                self.assertFalse(armed.permission_to_trade)
                self.assertFalse(blocked.eligible_for_early_phase_input)
                self.assertTrue(armed.eligible_for_early_phase_input)
                self.assertFalse(armed.confirmed_phase_authorized)

    def test_m5_htf_future_context_does_not_become_causal_later(self):
        for i in range(RANGE):
            bar = _bar(i)
            context_future_to_bar = bar.first_known_utc + S
            result = evaluate_closed_bar(
                bar, bar.first_known_utc + 10 * M,
                conditional_m5_early_enabled=True,
                htf_context_first_known_utc=context_future_to_bar,
            )
            with self.subTest(i=i):
                self.assertEqual(result.reason, "M5_HTF_CONTEXT_FUTURE_KNOWN")
                self.assertFalse(result.permission_to_trade)

    def test_mid_bar_remains_non_executable_even_when_technically_usable(self):
        for i in range(RANGE):
            mid = _bar(i, side=BarSide.MID)
            gate = evaluate_closed_bar(
                mid, mid.first_known_utc + M,
                conditional_m5_early_enabled=True,
                htf_context_first_known_utc=mid.first_known_utc - S,
            )
            with self.subTest(i=i):
                self.assertTrue(gate.usable_for_technical_features)
                self.assertFalse(gate.executable_quote_basis)
                self.assertFalse(gate.permission_to_trade)

    def test_new_york_fall_dst_fold_maps_to_two_distinct_utc_instants(self):
        for minute in range(60):
            wall = datetime(2026, 11, 1, 1, minute)
            with self.subTest(minute=minute):
                with self.assertRaisesRegex(ValueError, "AMBIGUOUS_DST"):
                    resolve_local_wall_time(wall, "America/New_York")
                first = resolve_local_wall_time(wall, "America/New_York", fold=0)
                second = resolve_local_wall_time(wall, "America/New_York", fold=1)
                self.assertEqual(second - first, timedelta(hours=1))
                self.assertEqual(first.tzinfo, timezone.utc)

    def test_new_york_spring_dst_gap_rejected_for_all_missing_minutes(self):
        for minute in range(60):
            wall = datetime(2026, 3, 8, 2, minute)
            with self.subTest(minute=minute):
                with self.assertRaisesRegex(ValueError, "NONEXISTENT_DST"):
                    resolve_local_wall_time(wall, "America/New_York")
                with self.assertRaisesRegex(ValueError, "NONEXISTENT_DST"):
                    resolve_local_wall_time(wall, "America/New_York", fold=0)

    def test_dst_normal_wall_time_does_not_allow_fake_fold_one(self):
        for minute in range(60):
            wall = datetime(2026, 7, 17, 10, minute)
            with self.subTest(minute=minute):
                self.assertEqual(
                    resolve_local_wall_time(wall, "America/New_York"),
                    resolve_local_wall_time(wall, "America/New_York", fold=0),
                )
                with self.assertRaisesRegex(ValueError, "FOLD_1_NOT_APPLICABLE"):
                    resolve_local_wall_time(wall, "America/New_York", fold=1)

    def test_ema_revision_recompute_matches_full_exact_decimal(self):
        rng = Random(SEED + 13)
        for i in range(RANGE):
            n = rng.randrange(4, 40)
            period = rng.randrange(1, 25)
            closes = tuple(Decimal(rng.randrange(90000, 120000)) /
                           Decimal("100000") for _ in range(n))
            before = ema_full(closes, period)
            dirty = rng.randrange(n)
            revised = list(closes)
            revised[dirty] += Decimal("0.00001")
            revised_series = tuple(revised)
            with self.subTest(i=i, dirty=dirty, period=period):
                self.assertEqual(
                    ema_recompute(revised_series, period, before, dirty),
                    ema_full(revised_series, period),
                )

    def test_ema_append_recompute_matches_full_without_historical_refetch(self):
        rng = Random(SEED + 14)
        for i in range(RANGE):
            n = rng.randrange(1, 50)
            period = rng.randrange(1, 30)
            prefix = tuple(Decimal(rng.randrange(100, 10000)) /
                           Decimal("10000") for _ in range(n))
            incoming = Decimal(rng.randrange(100, 10000)) / Decimal("10000")
            updated = prefix + (incoming,)
            with self.subTest(i=i):
                self.assertEqual(
                    ema_recompute(updated, period, ema_full(prefix, period), n),
                    ema_full(updated, period),
                )

    def test_ema_constant_prices_are_fixed_points(self):
        rng = Random(SEED + 15)
        for i in range(RANGE):
            x = Decimal(rng.randrange(1, 10000)) / Decimal("1000")
            series = (x,) * rng.randrange(1, 45)
            with self.subTest(i=i):
                # Decimal's finite default precision (28 digits) may produce
                # +/-1E-27 rounding dust at EMA weighted-sum boundaries.
                # This tolerance is 100x that observed in the red QA run;
                # all exact full-vs-incremental tests remain unchanged.
                calculated = ema_full(series, rng.randrange(1, 35))
                self.assertEqual(len(calculated), len(series))
                self.assertTrue(all(
                    abs(y - x) <= Decimal("1e-25") for y in calculated
                ))

    def test_incremental_cache_refresh_has_exact_bounded_overlap(self):
        rng = Random(SEED + 16)
        for i in range(RANGE):
            count = rng.randrange(1, 30)
            overlap = rng.randrange(1, 40)
            snap = _snapshot(count)
            policy = IncrementalPolicy(overlap, 5 * M)
            decision = snap.checked_at_utc + S
            result = plan_incremental_refresh(
                snap, policy, decision, supports_bounded_range=True,
            )
            with self.subTest(i=i):
                self.assertEqual(result.mode, RefreshMode.DELTA_WINDOW)
                self.assertEqual(result.from_utc,
                                 snap.closed_bars[-min(overlap, count)].key.bar_start_utc)
                self.assertFalse(result.may_fetch_real_data)
                self.assertFalse(result.source_claim_authenticated)

    def test_cache_no_range_is_never_rebranded_as_safe_delta(self):
        for count in range(1, 40):
            snap = _snapshot(count)
            plan = plan_incremental_refresh(
                snap, IncrementalPolicy(3, 3 * M),
                snap.checked_at_utc + S,
                supports_bounded_range=False,
            )
            with self.subTest(count=count):
                self.assertEqual(plan.mode, RefreshMode.RANGE_ENDPOINT_REQUIRED)
                self.assertIsNone(plan.from_utc)
                self.assertFalse(plan.may_fetch_real_data)

    def test_cache_same_rows_reconcile_no_change_and_no_trade_permission(self):
        for count in range(1, 30):
            snap = _snapshot(count)
            original_fingerprint = snap.fingerprint
            result = reconcile_closed_delta(
                snap, (snap.closed_bars[-1],),
                snap.checked_at_utc + S,
                new_source_head_claim="A03-NEW-HEAD",
            )
            with self.subTest(count=count):
                self.assertEqual(result.change, ChangeKind.NO_CHANGE)
                self.assertEqual(result.appended, 0)
                self.assertEqual(result.revised, 0)
                self.assertIsNone(result.first_dirty_utc)
                self.assertFalse(result.may_persist_real_data)
                self.assertEqual(snap.fingerprint, original_fingerprint)

    def test_cache_late_revision_recomputes_earliest_dirty_bar(self):
        rng = Random(SEED + 19)
        for i in range(RANGE):
            count = rng.randrange(3, 25)
            snap = _snapshot(count)
            index = rng.randrange(count)
            decision = snap.checked_at_utc + 2 * M
            newer = _bar(index, revision=2,
                         known_at=decision - S,
                         close=Decimal("1.1300"))
            result = reconcile_closed_delta(
                snap, (newer,), decision, new_source_head_claim="NEW-A03",
            )
            with self.subTest(i=i, index=index):
                self.assertEqual(result.change, ChangeKind.REVISE)
                self.assertEqual(result.revised, 1)
                self.assertEqual(result.appended, 0)
                self.assertEqual(result.first_dirty_utc, newer.key.bar_start_utc)
                self.assertEqual(result.snapshot.closed_bars[index], newer)
                self.assertEqual(len(snap.closed_bars), count)
                self.assertFalse(result.may_persist_real_data)

    def test_same_revision_changed_cache_value_is_rejected(self):
        for count in range(1, 40):
            snap = _snapshot(count)
            old = snap.closed_bars[-1]
            altered = replace(old, close=Decimal("1.1300"))
            with self.subTest(count=count):
                with self.assertRaisesRegex(ValueError, "OLDER_OR_SAME_REVISION"):
                    reconcile_closed_delta(
                        snap, (altered,), snap.checked_at_utc + S,
                        new_source_head_claim="CHANGED-CLAIM",
                    )

    def test_cache_dirty_dag_never_invalidates_other_pairs(self):
        rng = Random(SEED + 22)
        for i in range(RANGE):
            count = rng.randrange(2, 12)
            names = tuple(f"PAIR{j:02d}" for j in range(count))
            nodes = _cache_chain(names)
            touched = names[rng.randrange(count)]
            result = dirty_dependency_closure(nodes, (f"{touched}-L1",))
            with self.subTest(i=i, pair=touched):
                self.assertEqual(set(result),
                                 {f"{touched}-L{n}" for n in range(1, 6)})
                self.assertEqual(len(result), 5)
                self.assertEqual(dirty_dependency_closure(
                    tuple(reversed(nodes)), (f"{touched}-L1",)
                ), result)

    def test_cache_dirty_closure_is_monotone_for_additional_known_changes(self):
        rng = Random(SEED + 23)
        nodes = _cache_chain(tuple(f"P{i}" for i in range(8)))
        for i in range(RANGE):
            n = rng.randrange(8)
            m = rng.randrange(8)
            initial = set(dirty_dependency_closure(nodes, (f"P{n}-L1",)))
            combined = set(dirty_dependency_closure(
                nodes, (f"P{n}-L1", f"P{m}-L1"),
            ))
            with self.subTest(i=i):
                self.assertTrue(initial <= combined)
                self.assertEqual(len(combined), 5 if n == m else 10)

    def test_cache_artifact_reuse_never_grants_production_permission(self):
        rng = Random(SEED + 24)
        nodes = _cache_chain(("PAIR",))
        node = nodes[1]
        for i in range(RANGE):
            fingerprint = str(rng.randrange(1_000_000))
            prev = CacheArtifactFingerprint(node, fingerprint, ("DEP-A03",))
            same = CacheArtifactFingerprint(node, fingerprint, ("DEP-A03",))
            drift = CacheArtifactFingerprint(node, fingerprint + "M", ("DEP-A03",))
            with self.subTest(i=i):
                good = assess_artifact_reuse(
                    prev, same, previous_complete=True,
                    source_unchanged_independently_verified=True,
                )
                changed = assess_artifact_reuse(
                    prev, drift, previous_complete=True,
                    source_unchanged_independently_verified=True,
                )
                self.assertTrue(good.value_reusable)
                self.assertFalse(changed.value_reusable)
                self.assertFalse(good.production_authorized)
                self.assertFalse(changed.production_authorized)


if __name__ == "__main__":
    unittest.main()
