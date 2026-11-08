"""P2.2-B synthetic-only price/content/provenance and lineage tests."""
import ast
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
import inspect
import unittest

from forex_trading import synthetic_evidence_lineage as ev
from forex_trading.cache_core import CandleSnapshot
from forex_trading.source_stream_binding import SourceStreamBinding
from test_cache_core import M, T, bar, partition, snapshot
from test_source_stream_binding import declared


DECISION = T + 40 * M


def snapshot_at(bars=None, checked=21, head="synthetic-head-1"):
    return snapshot(
        bars=tuple(bar(i) for i in range(3)) if bars is None else tuple(bars),
        checked_at_utc=T + checked * M,
        source_head_claim=head,
    )


def revise(b, *, close=None, rev=2, known_min=23):
    ob = replace(
        b.observation, revision_id="synthetic-rev-new",
        raw_sha256="e" * 64,
        first_known_utc=T + known_min * M,
        retrieved_at_utc=T + known_min * M,
    )
    return replace(
        b, observation=ob, revision_number=rev,
        first_known_utc=T + known_min * M,
        close=b.close if close is None else Decimal(close),
    )


class ForexSyntheticEvidenceLineageTests(unittest.TestCase):
    def test_unmodified_snapshot_is_unchanged(self):
        prior = snapshot_at()
        r = ev.compare_synthetic_evidence(prior, prior, declared(prior), DECISION)
        self.assertEqual(r.change, ev.EvidenceChange.UNCHANGED)
        self.assertFalse(r.needs_indicator_recompute)
        self.assertFalse(r.propose_new_price_chunk)
        self.assertFalse(r.propose_lineage_event)
        self.assertFalse(r.may_reuse_real_cached_data)
        self.assertFalse(r.may_trade)

    def test_price_digest_stable_across_retrieval_metadata(self):
        prior = snapshot_at()
        b = prior.closed_bars[0]
        changed = replace(
            b, observation=replace(b.observation, retrieved_at_utc=T + 19*M))
        newer = snapshot_at(
            bars=(changed,) + prior.closed_bars[1:],
            checked=22, head="new-claimed-source-head")
        self.assertEqual(ev.price_content_digest(prior), ev.price_content_digest(newer))
        self.assertNotEqual(ev.provenance_digest(prior), ev.provenance_digest(newer))
        self.assertEqual(prior.fingerprint, newer.fingerprint)
        r = ev.compare_synthetic_evidence(prior, newer, declared(prior), DECISION)
        self.assertEqual(r.change, ev.EvidenceChange.LINEAGE_ONLY)
        self.assertTrue(r.propose_lineage_event)
        self.assertFalse(r.needs_indicator_recompute)
        self.assertFalse(r.propose_new_price_chunk)
        self.assertIsNone(r.first_price_dirty_utc)

    def test_content_digest_normalizes_decimal_scale(self):
        p = snapshot_at()
        b = p.closed_bars[0]
        incoming = snapshot_at(bars=(
            replace(b, close=Decimal("1.14000")),
            *p.closed_bars[1:],
        ))
        self.assertEqual(ev.price_content_digest(p), ev.price_content_digest(incoming))
        self.assertEqual(ev.provenance_digest(p), ev.provenance_digest(incoming))

    def test_head_only_change_needs_lineage_not_price_recompute(self):
        p = snapshot_at()
        new = snapshot_at(checked=25, head="reported-head-v2")
        result = ev.compare_synthetic_evidence(p, new, declared(p), DECISION)
        self.assertEqual(result.change, ev.EvidenceChange.LINEAGE_ONLY)
        self.assertFalse(result.needs_indicator_recompute)
        self.assertFalse(result.needs_causal_replay_review)
        self.assertTrue(result.propose_lineage_event)
        self.assertFalse(result.may_persist_real_data)

    def test_valid_price_revision_marks_earliest_dirty(self):
        p = snapshot_at()
        updated = revise(p.closed_bars[1], close="1.15")
        new = snapshot_at(bars=(p.closed_bars[0], updated, p.closed_bars[2]), checked=25)
        result = ev.compare_synthetic_evidence(p, new, declared(p), DECISION)
        self.assertEqual(result.change, ev.EvidenceChange.PRICE_DIRTY)
        self.assertEqual(result.first_price_dirty_utc, T + 5*M)
        self.assertTrue(result.needs_indicator_recompute)
        self.assertTrue(result.needs_causal_replay_review)
        self.assertTrue(result.propose_new_price_chunk)
        self.assertTrue(result.propose_lineage_event)
        self.assertFalse(result.may_persist_real_data)

    def test_append_marks_only_added_bar_dirty(self):
        p = snapshot_at()
        new = snapshot_at(bars=p.closed_bars + (bar(3),), checked=26)
        r = ev.compare_synthetic_evidence(p, new, declared(p), DECISION)
        self.assertEqual(r.change, ev.EvidenceChange.PRICE_DIRTY)
        self.assertEqual(r.first_price_dirty_utc, T + 15*M)

    def test_multiple_price_deltas_use_earliest_dirty_start(self):
        p = snapshot_at()
        update = (revise(p.closed_bars[2], close="1.16"),
                  revise(p.closed_bars[0], close="1.17"),
                  revise(p.closed_bars[1], close="1.18"))
        n = snapshot_at(bars=(update[1], update[2], update[0]), checked=27)
        r = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
        self.assertEqual(r.first_price_dirty_utc, T)

    def test_price_change_without_later_revision_blocks(self):
        p = snapshot_at()
        altered = replace(p.closed_bars[1], close=Decimal("1.15"))
        new = snapshot_at(bars=(p.closed_bars[0], altered, p.closed_bars[2]))
        r = ev.compare_synthetic_evidence(p, new, declared(p), DECISION)
        self.assertEqual(r.change, ev.EvidenceChange.BLOCKED)
        self.assertEqual(r.reason, "PRICE_CHANGE_WITHOUT_NEW_CAUSAL_REVISION")
        self.assertFalse(r.propose_new_price_chunk)

    def test_same_price_new_revision_requires_causal_review_not_price_dirty(self):
        p = snapshot_at()
        b = revise(p.closed_bars[1])
        n = snapshot_at(bars=(p.closed_bars[0], b, p.closed_bars[2]), checked=25)
        r = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
        self.assertEqual(r.change, ev.EvidenceChange.CAUSAL_REPLAY_REVIEW)
        self.assertTrue(r.needs_causal_replay_review)
        self.assertEqual(r.first_causal_review_utc, T + 5*M)
        self.assertFalse(r.needs_indicator_recompute)
        self.assertFalse(r.propose_new_price_chunk)
        self.assertTrue(r.propose_lineage_event)

    def test_deletion_is_blocked_even_when_remaining_bars_valid(self):
        p = snapshot_at()
        n = snapshot_at(bars=p.closed_bars[1:])
        r = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
        self.assertEqual(r.reason, "HISTORICAL_BAR_DISAPPEARED_NO_SILENT_DELETE")
        self.assertEqual(r.change, ev.EvidenceChange.BLOCKED)

    def test_cross_partition_cannot_be_classed_as_lineage_only(self):
        p = snapshot_at()
        n = replace(p, partition=partition(broker_product_ref="OTHER-PRODUCT"))
        r = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
        self.assertEqual(r.reason, "CROSS_PARTITION_EVIDENCE_CONFLICT")
        self.assertEqual(r.change, ev.EvidenceChange.BLOCKED)

    def test_mixed_stream_cannot_piggyback_on_matching_price_content(self):
        p = snapshot_at()
        b = p.closed_bars[1]
        changed = replace(
            b, observation=replace(b.observation, stream_id="ANOTHER_STREAM"))
        n = snapshot_at(bars=(p.closed_bars[0], changed, p.closed_bars[2]))
        self.assertEqual(ev.price_content_digest(p), ev.price_content_digest(n))
        r = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
        self.assertEqual(r.change, ev.EvidenceChange.BLOCKED)
        self.assertIn("DECLARED_STREAM_ID_CONFLICT", r.reason)

    def test_endpoint_or_license_claim_mismatch_blocks(self):
        p = snapshot_at()
        for field, value in (("endpoint", "OTHER_ENDPOINT"),
                             ("license_scope_claim", "EXPIRED_SOURCE_CLAIM")):
            with self.subTest(field=field):
                b = p.closed_bars[1]
                mutated = replace(
                    b, observation=replace(b.observation, **{field: value}))
                n = snapshot_at(
                    bars=(p.closed_bars[0], mutated, p.closed_bars[2]))
                r = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
                self.assertEqual(r.change, ev.EvidenceChange.BLOCKED)

    def test_clock_rollback_in_snapshot_blocks(self):
        p = snapshot_at(checked=21)
        n = snapshot_at(checked=20)
        r = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
        self.assertEqual(r.reason, "SNAPSHOT_CLOCK_ROLLBACK")

    def test_new_revised_bar_backdated_first_known_fails_closed(self):
        original = snapshot_at()
        # Both variants are valid records on their own: observation first-known
        # remains at 05:01, while the bar is claimed known at 07:00 then 06:00.
        delayed = replace(original.closed_bars[0], first_known_utc=T + 7*M)
        p = snapshot_at(bars=(delayed,) + original.closed_bars[1:])
        tampered = replace(delayed, revision_number=2,
                           first_known_utc=T + 6*M)
        n = snapshot_at(bars=(tampered,) + original.closed_bars[1:])
        r = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
        self.assertEqual(r.change, ev.EvidenceChange.BLOCKED)
        self.assertEqual(r.reason, "REVISION_OR_CAUSAL_CLOCK_ROLLBACK")

    def test_unknown_binding_blocks_even_if_ohlc_identical(self):
        p = snapshot_at()
        r = ev.compare_synthetic_evidence(p, p, None, DECISION)
        self.assertEqual(r.change, ev.EvidenceChange.BLOCKED)
        self.assertIn("SOURCE_STREAM_BINDING_MISSING", r.reason)

    def test_future_retrieval_blocks_a_synthetic_lineage_review(self):
        p = snapshot_at()
        b = p.closed_bars[0]
        altered = replace(
            b, observation=replace(
                b.observation, retrieved_at_utc=DECISION + timedelta(minutes=1)))
        n = snapshot_at(bars=(altered,) + p.closed_bars[1:])
        r = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
        self.assertEqual(r.change, ev.EvidenceChange.BLOCKED)
        self.assertIn("DECLARED_EVIDENCE_NOT_KNOWN_AT_DECISION", r.reason)

    def test_revoked_expired_and_denied_rights_cannot_reuse_even_unchanged(self):
        p = snapshot_at()
        for kind in (ev.RightsEvent.REVOKED, ev.RightsEvent.EXPIRED,
                     ev.RightsEvent.DENIED):
            with self.subTest(kind=kind):
                r = ev.compare_synthetic_evidence(
                    p, p, declared(p), DECISION, rights_event=kind)
                self.assertEqual(r.change, ev.EvidenceChange.BLOCKED)
                self.assertTrue(r.propose_lineage_event)
                self.assertFalse(r.may_reuse_real_cached_data)
                self.assertFalse(r.may_persist_real_data)
                self.assertFalse(r.may_trade)
                self.assertFalse(r.propose_new_price_chunk)

    def test_rights_state_and_input_types_are_typed(self):
        p = snapshot_at()
        with self.assertRaisesRegex(TypeError, "TYPED_RIGHTS_EVENT_REQUIRED"):
            ev.compare_synthetic_evidence(
                p, p, declared(p), DECISION, rights_event="AUTHORIZED")
        with self.assertRaisesRegex(TypeError, "TYPED_SOURCE_STREAM_BINDING"):
            ev.compare_synthetic_evidence(p, p, "trust-me", DECISION)
        with self.assertRaisesRegex(TypeError, "TYPED_CANDLE_SNAPSHOTS"):
            ev.compare_synthetic_evidence(None, p, declared(p), DECISION)
        with self.assertRaisesRegex(ValueError, "UTC"):
            ev.compare_synthetic_evidence(
                p, p, declared(p), DECISION.replace(tzinfo=None))

    def test_lineage_event_is_deterministic_and_chain_validates(self):
        p = snapshot_at()
        n1 = snapshot_at(checked=23, head="head-2")
        n2 = snapshot_at(checked=25, head="head-3")
        r1 = ev.compare_synthetic_evidence(p, n1, declared(p), DECISION)
        r2 = ev.compare_synthetic_evidence(n1, n2, declared(n1), DECISION)
        first = ev.make_synthetic_lineage_event(r1, T + 41*M)
        second = ev.make_synthetic_lineage_event(r2, T + 42*M, first)
        self.assertEqual(first.generation, 1)
        self.assertEqual(second.generation, 2)
        self.assertEqual(second.previous_event_sha256, first.event_sha256)
        self.assertTrue(ev.validate_synthetic_lineage_chain((first, second)))
        self.assertEqual(first, ev.make_synthetic_lineage_event(r1, T + 41*M))

    def test_tampered_event_chain_detected_but_not_trusted_storage(self):
        p = snapshot_at()
        n = snapshot_at(checked=23, head="head-2")
        report = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
        first = ev.make_synthetic_lineage_event(report, T + 41*M)
        fake = replace(first, reason="forged-event")
        with self.assertRaisesRegex(ValueError, "LINEAGE_EVENT_DIGEST_MISMATCH"):
            ev.validate_synthetic_lineage_chain((fake,))
        with self.assertRaisesRegex(ValueError, "LINEAGE_SEQUENCE"):
            ev.validate_synthetic_lineage_chain((replace(first, generation=2),))
        with self.assertRaisesRegex(ValueError, "LINEAGE_PARENT"):
            ev.validate_synthetic_lineage_chain(
                (replace(first, previous_event_sha256="a"*64),))

    def test_stale_or_discontinuous_lineage_append_is_blocked(self):
        p = snapshot_at()
        n = snapshot_at(checked=23, head="head-2")
        r1 = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
        first = ev.make_synthetic_lineage_event(r1, T + 43*M)
        with self.assertRaisesRegex(ValueError, "LINEAGE_EVENT_CLOCK_ROLLBACK"):
            ev.make_synthetic_lineage_event(r1, T + 42*M, first)
        with self.assertRaisesRegex(ValueError, "LINEAGE_CHAIN_SNAPSHOT_DISCONTINUITY"):
            ev.make_synthetic_lineage_event(r1, T + 44*M, first)

    def test_lineage_event_cannot_predate_asof_decision(self):
        p = snapshot_at()
        n = snapshot_at(checked=23, head="new-head")
        review = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
        with self.assertRaisesRegex(ValueError, "LINEAGE_EVENT_PREDATES_ASOF_REVIEW"):
            ev.make_synthetic_lineage_event(review, T + 39*M)

    def test_unchanged_event_not_written(self):
        p = snapshot_at()
        r = ev.compare_synthetic_evidence(p, p, declared(p), DECISION)
        with self.assertRaisesRegex(ValueError, "NO_LINEAGE_EVENT_NEEDED"):
            ev.make_synthetic_lineage_event(r, T + 41*M)

    def test_provenance_review_records_immutable(self):
        p = snapshot_at()
        n = snapshot_at(checked=23, head="newhead")
        r = ev.compare_synthetic_evidence(p, n, declared(p), DECISION)
        item = ev.make_synthetic_lineage_event(r, T + 41*M)
        with self.assertRaises(FrozenInstanceError):
            r.may_trade = True
        with self.assertRaises(FrozenInstanceError):
            item.event_sha256 = "b"*64

    def test_module_is_pure_no_transport_or_cache_write_dependencies(self):
        modules = {
            node.module
            for node in ast.walk(ast.parse(inspect.getsource(ev)))
            if isinstance(node, ast.ImportFrom) and node.level > 0
        }
        self.assertEqual(modules, {
            "cache_core", "market_data", "quotes", "source_stream_binding",
        })
        p = snapshot_at()
        prior_fingerprint = p.fingerprint
        r = ev.compare_synthetic_evidence(p, p, declared(p), DECISION)
        self.assertEqual(p.fingerprint, prior_fingerprint)
        self.assertFalse(r.may_persist_real_data)
        self.assertFalse(r.may_trade)


if __name__ == "__main__":
    unittest.main()
