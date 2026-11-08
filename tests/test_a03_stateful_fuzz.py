"""A03/P0.3 deterministic stateful fuzz replay, synthetic contracts only.

No provider, broker, external data, or scheduler IO. Eight immutable seeds
and 16 steps per seed allow exact GitHub Cloud Python 3.11/3.12 replay.
This is systematic bounded scenario exploration, NOT coverage-guided fuzzing.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from random import Random
import unittest

from forex_trading.cache_core import (
    CachePartition, CandleSnapshot, ChangeKind, reconcile_closed_delta,
)
from forex_trading.cache_dependency import (
    CacheLayer, CacheNode, dirty_dependency_closure,
)
from forex_trading.market_data import BarSide, select_asof_revision
from forex_trading.model import ActionIntent
from forex_trading.quotes import Quote, QuoteQuality, indicative_price

from test_a03_seeded_properties import M, S, T, _bar, _snapshot

SEEDS = (
    0xA032026, 0xA032027, 0xA0320A3, 0xA0320B4,
    0xA0320C5, 0xA0320D6, 0xA0320E7, 0xA0320F8,
)
STEPS_PER_SEED = 16
SYNTHETIC_ONLY = True


def model_descendants(
    nodes: tuple[CacheNode, ...], changed: tuple[str, ...],
) -> tuple[str, ...]:
    """Independent iterative transitive closure, no production DAG call."""
    marked = set(changed)
    while True:
        next_set = marked | {
            node.node_id for node in nodes
            if any(parent in marked for parent in node.parents)
        }
        if next_set == marked:
            break
        marked = next_set
    return tuple(node.node_id for node in
                 sorted(nodes, key=lambda n: (n.layer, n.node_id))
                 if node.node_id in marked)


def minimize_changed_nodes(
    nodes: tuple[CacheNode, ...], changed: tuple[str, ...],
    broken,
) -> tuple[str, ...]:
    """Deterministically reduce a failing changed-ID set without extra IO."""
    current = tuple(dict.fromkeys(changed))
    if not broken(current):
        return ()
    for item in tuple(current):
        trial = tuple(x for x in current if x != item)
        if broken(trial):
            current = trial
    return current


class A03StatefulSyntheticFuzz(unittest.TestCase):
    def test_asof_revision_model_and_future_injection(self):
        for seed in SEEDS:
            rng = Random(seed)
            for case in range(STEPS_PER_SEED):
                index = rng.randrange(0, 12)
                first = _bar(index)
                history = [first]
                known = first.first_known_utc
                for version in range(2, 2 + rng.randrange(1, 6)):
                    known += timedelta(seconds=rng.randrange(1, 90))
                    history.append(_bar(
                        index, revision=version, known_at=known,
                        close=Decimal("1.1200") +
                              Decimal(version) / Decimal("100000"),
                    ))
                shuffled = list(history)
                rng.shuffle(shuffled)
                for k, expected in enumerate(history):
                    decision = expected.first_known_utc
                    with self.subTest(seed=seed, case=case, known_rev=k + 1):
                        # Future revisions are included in the input but never
                        # influence an earlier as-of value.
                        self.assertEqual(
                            select_asof_revision(shuffled, decision), expected
                        )
                        self.assertEqual(
                            select_asof_revision(tuple(reversed(shuffled)),
                                                 decision), expected
                        )
                with self.subTest(seed=seed, case=case, before_first=True):
                    self.assertIsNone(select_asof_revision(
                        shuffled, first.first_known_utc - S
                    ))

    def test_cache_stateful_append_revision_and_idempotence_model(self):
        for seed in SEEDS:
            rng = Random(seed)
            current = _snapshot(2)
            model = {b.key.bar_start_utc: b for b in current.closed_bars}
            next_index = 2
            for step in range(STEPS_PER_SEED):
                operation = step % 3
                if operation == 0:
                    incoming = _bar(next_index)
                    next_index += 1
                    expected_kind = ChangeKind.APPEND
                    expected_dirty = incoming.key.bar_start_utc
                else:
                    key = rng.choice(tuple(sorted(model)))
                    previous = model[key]
                    if operation == 1:
                        incoming = _bar(
                            int((key - T) // (5 * M)),
                            revision=previous.revision_number + 1,
                            known_at=max(current.checked_at_utc + M,
                                         previous.first_known_utc + M),
                            close=Decimal("1.1300") +
                                  Decimal(step) / Decimal("100000"),
                        )
                        expected_kind = ChangeKind.REVISE
                        expected_dirty = key
                    else:
                        incoming = previous
                        expected_kind = ChangeKind.NO_CHANGE
                        expected_dirty = None
                decision = max(current.checked_at_utc + M,
                               incoming.first_known_utc + S,
                               incoming.key.bar_end_utc + S)
                old_rows = current.closed_bars
                old_digest = current.fingerprint
                receipt = reconcile_closed_delta(
                    current, (incoming,), decision,
                    new_source_head_claim=f"SYNTH-STATE-{seed}-{step}",
                )
                if operation != 2:
                    model[incoming.key.bar_start_utc] = incoming
                expected_bars = tuple(model[k] for k in sorted(model))
                with self.subTest(seed=seed, step=step, op=operation):
                    self.assertEqual(receipt.snapshot.closed_bars,
                                     expected_bars)
                    self.assertEqual(receipt.change, expected_kind)
                    self.assertEqual(receipt.appended,
                                     1 if operation == 0 else 0)
                    self.assertEqual(receipt.revised,
                                     1 if operation == 1 else 0)
                    self.assertEqual(receipt.first_dirty_utc, expected_dirty)
                    self.assertFalse(receipt.may_persist_real_data)
                    self.assertFalse(receipt.source_verified_externally)
                    self.assertEqual(current.closed_bars, old_rows)
                    self.assertEqual(current.fingerprint, old_digest)
                current = receipt.snapshot

    def test_mixed_batch_append_revision_commutes(self):
        for seed in SEEDS:
            rng = Random(seed)
            for case in range(STEPS_PER_SEED):
                original = _snapshot(5)
                position = rng.randrange(5)
                replaced = _bar(
                    position, revision=2,
                    known_at=original.checked_at_utc + M,
                    close=Decimal("1.1300") +
                          Decimal(case) / Decimal("100000"),
                )
                appended = _bar(5)
                decision = appended.first_known_utc + M
                left = reconcile_closed_delta(
                    original, (appended, replaced), decision,
                    new_source_head_claim="SYNTH-HEAD",
                )
                right = reconcile_closed_delta(
                    original, (replaced, appended), decision,
                    new_source_head_claim="SYNTH-HEAD",
                )
                with self.subTest(seed=seed, case=case):
                    self.assertEqual(left, right)
                    self.assertEqual(left.change,
                                     ChangeKind.APPEND_AND_REVISE)
                    self.assertEqual(left.appended, 1)
                    self.assertEqual(left.revised, 1)
                    self.assertEqual(
                        left.first_dirty_utc,
                        min(appended.key.bar_start_utc,
                            replaced.key.bar_start_utc),
                    )
                    self.assertEqual(len(original.closed_bars), 5)

    def test_random_dag_matches_independent_fixed_point_oracle(self):
        for seed in SEEDS:
            rng = Random(seed)
            for case in range(STEPS_PER_SEED):
                pair_count = rng.randrange(2, 7)
                nodes = []
                for pair in range(pair_count):
                    for layer in range(1, 6):
                        parents = ()
                        if layer > 1:
                            earlier = [f"PAIR{pair}-L{i}"
                                       for i in range(1, layer)]
                            parents = tuple(sorted(rng.sample(
                                earlier, rng.randrange(
                                    1, min(3, len(earlier)) + 1
                                ),
                            )))
                        nodes.append(CacheNode(
                            f"PAIR{pair}-L{layer}", CacheLayer(layer),
                            f"SYNTH-PARTITION-{pair}", "ALG-FUZZ",
                            "PARAM-FUZZ", parents,
                        ))
                rng.shuffle(nodes)
                frozen = tuple(nodes)
                all_ids = tuple(n.node_id for n in nodes)
                changed = tuple(rng.sample(
                    all_ids, rng.randrange(1, min(5, len(all_ids)) + 1)
                ))
                expect = model_descendants(frozen, changed)
                actual = dirty_dependency_closure(frozen, changed)
                with self.subTest(seed=seed, case=case):
                    self.assertEqual(actual, expect)
                    self.assertEqual(dirty_dependency_closure(
                        tuple(reversed(frozen)), tuple(reversed(changed))
                    ), expect)
                    self.assertTrue(set(changed) <= set(actual))
                    self.assertEqual(len(actual), len(set(actual)))

    def test_quote_time_translation_preserves_bid_ask_without_io(self):
        for seed in SEEDS:
            rng = Random(seed)
            for case in range(STEPS_PER_SEED):
                shift = timedelta(minutes=rng.randrange(2, 720))
                known = T + timedelta(minutes=rng.randrange(1, 80))
                bid = Decimal(rng.randrange(80000, 120000)) / 100000
                ask = bid + Decimal(rng.randrange(1, 100)) / 100000
                quote = Quote(
                    "SYNTH", "R-FUZZ", known - M, known,
                    bid, ask, QuoteQuality.VERIFIED,
                )
                translated = replace(
                    quote, event_time_utc=quote.event_time_utc + shift,
                    first_known_utc=quote.first_known_utc + shift,
                )
                for intent in ActionIntent:
                    a = indicative_price(quote, intent, known + M, 2 * M)
                    b = indicative_price(translated, intent,
                                         known + M + shift, 2 * M)
                    with self.subTest(seed=seed, case=case,
                                      intent=intent.value):
                        self.assertEqual(a.value, b.value)
                        self.assertEqual(a.side, b.side)
                        self.assertEqual(b.first_known_utc -
                                         a.first_known_utc, shift)

    def test_cache_partition_fingerprint_and_source_isolation(self):
        for seed in SEEDS:
            rng = Random(seed)
            for case in range(STEPS_PER_SEED):
                base = _snapshot(rng.randrange(1, 8))
                partition = base.partition
                alt = replace(
                    partition,
                    rights_policy_ref=f"OTHER-NOT-LICENSED-{seed}-{case}",
                )
                changed_rights = CandleSnapshot(
                    alt, base.closed_bars, base.checked_at_utc,
                    base.source_head_claim,
                )
                with self.subTest(seed=seed, case=case):
                    self.assertNotEqual(partition.fingerprint,
                                        alt.fingerprint)
                    self.assertNotEqual(base.fingerprint,
                                        changed_rights.fingerprint)
                    self.assertEqual(base.closed_bars,
                                     changed_rights.closed_bars)
                    with self.assertRaisesRegex(
                        ValueError, "CACHE_PARTITION_SOURCE_IDENTITY_CONFLICT"
                    ):
                        CandleSnapshot(
                            replace(partition, side=BarSide.ASK),
                            base.closed_bars, base.checked_at_utc,
                            base.source_head_claim,
                        )
                    with self.assertRaisesRegex(
                        ValueError, "CACHE_PARTITION_SOURCE_IDENTITY_CONFLICT"
                    ):
                        CandleSnapshot(
                            replace(partition, provider_id="OTHER-PROVIDER"),
                            base.closed_bars, base.checked_at_utc,
                            base.source_head_claim,
                        )

    def test_counterexample_reducer_is_deterministic_and_minimal(self):
        nodes = (
            CacheNode("A", CacheLayer.L1_MARKET, "P", "ALG", "PARAM", ()),
            CacheNode("B", CacheLayer.L2_INDICATORS, "P", "ALG", "PARAM",
                      ("A",)),
        )
        # Hypothetical failing predicate used only to exercise the reducer;
        # it never changes the application code or data permissions.
        def failure(changed):
            return "A" in changed and "B" in changed
        original = ("X", "B", "A", "Y", "Z")
        one = minimize_changed_nodes(nodes, original, failure)
        two = minimize_changed_nodes(nodes, original, failure)
        self.assertEqual(one, ("B", "A"))
        self.assertEqual(one, two)
        self.assertTrue(failure(one))
        self.assertTrue(all(
            not failure(tuple(x for x in one if x != item)) for item in one
        ))


if __name__ == "__main__":
    unittest.main()
