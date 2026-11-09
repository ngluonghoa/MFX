"""MFX A03/P0.5 — negative boundary probes for measured uncovered branches.

Synthetic, read-only inputs only; no vendor transport, cache persistence,
release authority, broker execution, or changes to frozen source modules.
The intention is to improve measured branch coverage, not assert market fitness.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import unittest

from forex_trading.cache_core import (
    RefreshMode, RefreshPlan, SourceHeadClaim, plan_incremental_refresh,
    reconcile_closed_delta,
)
from forex_trading.cache_dependency import (
    CacheArtifactFingerprint, CacheLayer, CacheNode, assess_artifact_reuse,
    dirty_dependency_closure, validate_cache_dag,
)
from forex_trading.cache_storage_review import (
    make_synthetic_generation, validate_synthetic_generation_chain,
)
from forex_trading.market_data import BarSide
from forex_trading.provider_delta_contract import (
    StagedQuoteBar, parse_oanda_utc, plan_synthetic_oanda_delta,
    parse_synthetic_oanda_candles, diff_synthetic_delta,
)
from forex_trading.synthetic_evidence_lineage import (
    compare_synthetic_evidence, validate_synthetic_lineage_chain,
)

from test_provider_delta_contract import T, M, part, req, row, payload, parse
from test_cache_core import snapshot, policy
from test_cache_storage_review import snap, proposal


class P05MeasuredGapSafetyTests(unittest.TestCase):
    def test_wire_timestamp_requires_string_without_coercion(self):
        with self.assertRaises(TypeError):
            parse_oanda_utc(123)

    def test_request_instrument_and_window_are_explicit(self):
        with self.assertRaisesRegex(ValueError, "INVALID_WIRE_INSTRUMENT"):
            req(wire_instrument="EURUSD")
        with self.assertRaisesRegex(ValueError, "EMPTY_OR_REVERSED_DELTA_RANGE"):
            req(from_utc=T + 15 * M)

    def test_response_candle_rows_must_be_mappings(self):
        with self.assertRaisesRegex(TypeError, "mapping"):
            parse_synthetic_oanda_candles(
                payload("not-a-record"), req(), T + 16 * M,
            )

    def test_complete_flag_must_be_real_bool(self):
        for invalid in (None, 1, "true"):
            record = row()
            record["complete"] = invalid
            with self.subTest(value=invalid), self.assertRaisesRegex(
                ValueError, "CANDLE_COMPLETE_FLAG_REQUIRED"
            ):
                parse(record)

    def test_wire_price_rejects_nonpositive_and_nonstrings(self):
        for invalid in ("0", "-1.2", 1.10, "nan"):
            record = row()
            record["bid"]["o"] = invalid
            with self.subTest(value=invalid), self.assertRaisesRegex(
                ValueError, "INVALID_BID_O_PRICE"
            ):
                parse(record)

    def test_volume_count_rejects_boolean_or_negative(self):
        for invalid in (False, -1, None):
            with self.subTest(value=invalid), self.assertRaisesRegex(
                ValueError, "INVALID_CANDLE_PRICE_COUNT"
            ):
                parse(row(volume=invalid))

    def test_bounded_page_and_observation_cutoff_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_CANDLE_PAGE_SIZE"):
            parse_synthetic_oanda_candles(payload(row()), req(), T + 16 * M,
                                          max_rows=0)
        with self.assertRaisesRegex(ValueError, "OBSERVED_BEFORE_REQUEST_CUTOFF"):
            parse_synthetic_oanda_candles(payload(row()), req(), T + 14 * M)

    def test_staged_quote_ohlc_and_mid_basis_never_accepted(self):
        valid = (T, T + 5 * M, Decimal("1.10"), Decimal("1.11"),
                 Decimal("1.09"), Decimal("1.10"), "synthetic-only")
        with self.assertRaisesRegex(ValueError, "NEEDS_NATIVE_BID_ASK"):
            StagedQuoteBar(BarSide.MID, *valid)
        invalid_high = (T, T + 5 * M, Decimal("1.10"), Decimal("1.05"),
                        Decimal("1.09"), Decimal("1.10"), "synthetic-only")
        with self.assertRaisesRegex(ValueError, "INCONSISTENT_NATIVE_SIDE_OHLC"):
            StagedQuoteBar(BarSide.BID, *invalid_high)

    def test_delta_planner_requires_typed_input_and_closed_range(self):
        with self.assertRaisesRegex(TypeError, "Typed cache plan"):
            plan_synthetic_oanda_delta("unknown", part(), "EUR_USD", T + 15 * M)
        plan = RefreshPlan(
            RefreshMode.DELTA_WINDOW, None, "synthetic-hash",
            False, False, "no-bounds",
        )
        review = plan_synthetic_oanda_delta(plan, part(), "EUR_USD", T + 15 * M)
        self.assertIsNone(review.request)
        self.assertFalse(review.may_issue_network_call)

    def test_delta_diff_rejects_duplicate_previous_windows(self):
        staged = parse(row(0))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_PREVIOUS_CANDLES"):
            diff_synthetic_delta(staged.pairs + staged.pairs, staged)

    def test_cache_dag_rejects_mutable_or_untyped_nodes(self):
        with self.assertRaisesRegex(TypeError, "Immutable typed nodes"):
            validate_cache_dag([])
        with self.assertRaisesRegex(TypeError, "Immutable typed nodes"):
            validate_cache_dag(("not-a-node",))
        a = CacheNode("L1", CacheLayer.L1_MARKET,
                      "SYNTH", "ALG", "PARAM", ())
        with self.assertRaisesRegex(TypeError, "Changed node IDs"):
            dirty_dependency_closure((a,), ["L1"])
        with self.assertRaisesRegex(TypeError, "Changed node IDs"):
            dirty_dependency_closure((a,), (123,))

    def test_cache_node_denies_invalid_layer_and_parent_shape(self):
        with self.assertRaisesRegex(TypeError, "Explicit L1"):
            CacheNode("a", 1, "SYNTH", "ALG", "PARAM", ())
        with self.assertRaisesRegex(TypeError, "Parents must be immutable"):
            CacheNode("b", CacheLayer.L2_INDICATORS,
                      "SYNTH", "ALG", "PARAM", ["a"])
        with self.assertRaisesRegex(ValueError, "Self/duplicate"):
            CacheNode("c", CacheLayer.L2_INDICATORS,
                      "SYNTH", "ALG", "PARAM", ("c",))

    def test_reuse_flags_must_be_explicit_not_truthy(self):
        n = CacheNode("L1", CacheLayer.L1_MARKET,
                      "SYNTH", "ALG", "PARAM", ())
        digest = CacheArtifactFingerprint(n, "SYNTHETIC-INPUT", ())
        with self.assertRaisesRegex(TypeError, "Explicit quality flags"):
            assess_artifact_reuse(
                digest, digest, previous_complete=1,
                source_unchanged_independently_verified=True,
            )
        with self.assertRaisesRegex(TypeError, "Explicit quality flags"):
            assess_artifact_reuse(
                digest, digest, previous_complete=True,
                source_unchanged_independently_verified=1,
            )

    def test_refresh_does_not_accept_wrong_claim_partition(self):
        prior = snapshot()
        head = SourceHeadClaim(
            "ANOTHER-PARTITION", "HEAD-SYNTH",
            T + 15 * M, T + 18 * M,
        )
        with self.assertRaisesRegex(ValueError, "SOURCE_HEAD_WRONG_PARTITION"):
            plan_incremental_refresh(
                prior, policy(), T + 22 * M,
                supports_bounded_range=True, head=head,
            )

    def test_reconciliation_enforces_capacity_without_eviction(self):
        prior = snapshot()
        with self.assertRaisesRegex(ValueError, "CACHE_CAPACITY_EXCEEDED"):
            reconcile_closed_delta(
                prior, (), T + 20 * M,
                new_source_head_claim="CLAIM-ONLY",
                max_total_bars=2,
            )

    def test_synthetic_manifest_rejects_forged_parent_type(self):
        first = make_synthetic_generation(snap(), T + M)
        with self.assertRaisesRegex(TypeError, "SyntheticGenerationManifest"):
            make_synthetic_generation(snap(), T + 2 * M, "fake-parent")
        with self.assertRaisesRegex(TypeError, "Previous generation manifest required"):
            validate_synthetic_generation_chain(first, "fake-parent")
        with self.assertRaisesRegex(ValueError, "INVALID_MANIFEST_DIGEST"):
            replace(first, manifest_sha256="fake-hash")

    def test_lineage_rejects_untyped_rights_or_mutable_chain(self):
        prior = snapshot()
        with self.assertRaisesRegex(TypeError, "TYPED_RIGHTS_EVENT"):
            compare_synthetic_evidence(
                prior, prior, None, T + 20 * M, rights_event="REVOKED",
            )
        with self.assertRaisesRegex(ValueError, "INVALID_SYNTHETIC_LINEAGE_HISTORY"):
            validate_synthetic_lineage_chain([])


if __name__ == "__main__":
    unittest.main()
