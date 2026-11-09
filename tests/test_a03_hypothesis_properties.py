"""A03/P0.4 — reproducible shrinkable Hypothesis properties, synthetic only.

Hypothesis examples are generated and deterministically shrunk on CI failures.
No broker, provider request, market data, scheduler, real order or production
cache is accessed. This is PROPERTY-BASED fuzz, not an automated coverage-guided
fuzzer or economic backtest.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import unittest

from hypothesis import given, settings, strategies as st

from forex_trading.cache_core import ChangeKind, reconcile_closed_delta
from forex_trading.cache_dependency import (
    CacheLayer, CacheNode, dirty_dependency_closure,
)
from forex_trading.cache_indicators import ema_full, ema_recompute
from forex_trading.model import ActionIntent
from forex_trading.quotes import PriceSide, Quote, QuoteQuality, indicative_price

from test_a03_seeded_properties import M, S, T, _bar, _snapshot

CONF = settings(max_examples=80, derandomize=True, deadline=None, database=None)
P = Decimal("0.00001")
ACTION_SIDE = {
    ActionIntent.ENTRY_LONG: PriceSide.ASK,
    ActionIntent.EXIT_LONG: PriceSide.BID,
    ActionIntent.ENTRY_SHORT: PriceSide.BID,
    ActionIntent.EXIT_SHORT: PriceSide.ASK,
}


class A03HypothesisShrinkableProperties(unittest.TestCase):
    @CONF
    @given(
        bid_ticks=st.integers(min_value=50000, max_value=200000),
        spread_ticks=st.integers(min_value=0, max_value=200),
        shift_ticks=st.integers(min_value=0, max_value=200),
        intent=st.sampled_from(tuple(ActionIntent)),
    )
    def test_price_side_translation_independent_oracle(
        self, bid_ticks: int, spread_ticks: int,
        shift_ticks: int, intent: ActionIntent,
    ) -> None:
        bid = Decimal(bid_ticks) * P
        spread = Decimal(spread_ticks) * P
        quote = Quote(
            "SYNTH-A03", "NO-REAL-FEED", T, T + M,
            bid, bid + spread, QuoteQuality.VERIFIED,
        )
        shift = Decimal(shift_ticks) * P
        shifted = Quote(
            "SYNTH-A03", "NO-REAL-FEED", T, T + M,
            bid + shift, bid + shift + spread, QuoteQuality.VERIFIED,
        )
        a = indicative_price(quote, intent, T + 2 * M, 10 * M)
        b = indicative_price(shifted, intent, T + 2 * M, 10 * M)
        expected_side = ACTION_SIDE[intent]
        self.assertEqual(a.side, expected_side)
        self.assertEqual(b.side, expected_side)
        self.assertEqual(a.value, quote.ask if expected_side is PriceSide.ASK
                         else quote.bid)
        self.assertEqual(b.value - a.value, shift)
        self.assertFalse(hasattr(a, "permission_to_trade"))

    @CONF
    @given(
        age_seconds=st.integers(min_value=0, max_value=3600),
        max_seconds=st.integers(min_value=1, max_value=3600),
        future_seconds=st.integers(min_value=0, max_value=30),
    )
    def test_quote_causal_cutoff_model(
        self, age_seconds: int, max_seconds: int, future_seconds: int,
    ) -> None:
        known = T + M
        quote = Quote(
            "SYNTH", "REV-1", T, known, Decimal("1.1200"),
            Decimal("1.1202"), QuoteQuality.VERIFIED,
        )
        decision = known + timedelta(seconds=age_seconds)
        max_age = timedelta(seconds=max_seconds)
        if age_seconds > max_seconds:
            with self.assertRaisesRegex(ValueError, "stale"):
                indicative_price(quote, ActionIntent.ENTRY_LONG,
                                 decision, max_age)
        else:
            measured = indicative_price(
                quote, ActionIntent.ENTRY_LONG, decision, max_age
            )
            self.assertEqual(measured.value, Decimal("1.1202"))
        with self.assertRaisesRegex(ValueError, "not yet known"):
            indicative_price(
                quote, ActionIntent.ENTRY_LONG,
                known - timedelta(seconds=future_seconds + 1), max_age,
            )

    @CONF
    @given(
        values=st.lists(
            st.integers(min_value=1000, max_value=300000),
            min_size=2, max_size=32,
        ),
        period=st.integers(min_value=1, max_value=30),
        dirty_index=st.integers(min_value=0, max_value=100),
        delta_ticks=st.integers(min_value=1, max_value=1000),
    )
    def test_ema_any_dirty_revision_matches_full_replay(
        self, values: list[int], period: int,
        dirty_index: int, delta_ticks: int,
    ) -> None:
        close = tuple(Decimal(x) * P for x in values)
        old = ema_full(close, period)
        dirty = dirty_index % len(close)
        revised = list(close)
        revised[dirty] += Decimal(delta_ticks) * P
        revised_series = tuple(revised)
        self.assertEqual(
            ema_recompute(revised_series, period, old, dirty),
            ema_full(revised_series, period),
        )
        self.assertEqual(len(old), len(close))

    @CONF
    @given(
        count=st.integers(min_value=2, max_value=14),
        revise_index=st.integers(min_value=0, max_value=100),
        close_ticks=st.integers(min_value=112001, max_value=119999),
    )
    def test_cache_revision_mutates_one_slot_without_reordering(
        self, count: int, revise_index: int, close_ticks: int,
    ) -> None:
        prior = _snapshot(count)
        target = revise_index % count
        newer = _bar(
            target, revision=2,
            known_at=prior.checked_at_utc + M,
            close=Decimal(close_ticks) * P,
        )
        result = reconcile_closed_delta(
            prior, (newer,), newer.first_known_utc + S,
            new_source_head_claim="A03-P04-CLAIM-ONLY",
        )
        expected = list(prior.closed_bars)
        expected[target] = newer
        self.assertEqual(result.change, ChangeKind.REVISE)
        self.assertEqual(result.revised, 1)
        self.assertEqual(result.appended, 0)
        self.assertEqual(result.snapshot.closed_bars, tuple(expected))
        self.assertEqual(result.first_dirty_utc, newer.key.bar_start_utc)
        self.assertEqual(prior.closed_bars[target].revision_number, 1)
        self.assertFalse(result.may_persist_real_data)

    @CONF
    @given(
        pair_count=st.integers(min_value=2, max_value=10),
        first_pair=st.integers(min_value=0, max_value=200),
        second_pair=st.integers(min_value=0, max_value=200),
    )
    def test_pair_partition_dag_union_and_nonleakage(
        self, pair_count: int, first_pair: int, second_pair: int,
    ) -> None:
        nodes = tuple(
            CacheNode(
                f"P{p}-L{layer}", CacheLayer(layer), f"PART-{p}",
                "ALG-P04", "PARAM-P04",
                () if layer == 1 else (f"P{p}-L{layer-1}",),
            )
            for p in range(pair_count) for layer in range(1, 6)
        )
        a, b = first_pair % pair_count, second_pair % pair_count
        result = dirty_dependency_closure(
            nodes, (f"P{a}-L1", f"P{b}-L1"),
        )
        expected = {
            f"P{p}-L{layer}" for p in {a, b} for layer in range(1, 6)
        }
        self.assertEqual(set(result), expected)
        self.assertEqual(len(result), len(expected))
        self.assertEqual(
            dirty_dependency_closure(
                tuple(reversed(nodes)), (f"P{b}-L1", f"P{a}-L1")
            ), result,
        )


if __name__ == "__main__":
    unittest.main()
