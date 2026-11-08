"""P2.2-A: synthetic-only stream/product binding fail-closed negative tests."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
import ast
import inspect
import unittest

from forex_trading.cache_core import CandleSnapshot
from forex_trading.market_data import BarSide, Timeframe
from forex_trading import source_stream_binding as contract
from test_cache_core import T, M, bar, partition, snapshot


DECISION = T + 20 * M


def declared(snapshot_value=None, **changes):
    instance = snapshot() if snapshot_value is None else snapshot_value
    p = instance.partition
    obs = instance.closed_bars[0].observation if instance.closed_bars else bar(0).observation
    values = dict(
        provider_id=p.provider_id,
        broker_product_ref=p.broker_product_ref,
        instrument_version=p.instrument_version,
        side=p.side,
        timeframe=p.timeframe,
        calendar_version=p.calendar_version,
        aggregation_version=p.aggregation_version,
        source_timezone_policy=p.source_timezone_policy,
        rights_policy_ref=p.rights_policy_ref,
        schema_version=p.schema_version,
        stream_id=obs.stream_id,
        endpoint=obs.endpoint,
        license_scope_claim=obs.license_scope_claim,
        product_mapping_claim_ref="SYNTHETIC-NO-REAL-MAPPING-CLAIM",
    )
    values.update(changes)
    return contract.SourceStreamBinding(**values)


class ForexSourceStreamBindingTests(unittest.TestCase):
    def test_homogeneous_metadata_consistent_but_never_authorized(self):
        snap = snapshot()
        binding = declared(snap)
        prior_fingerprint = snap.fingerprint
        result = contract.qualify_snapshot_binding(snap, binding, DECISION)
        self.assertTrue(result.declared_metadata_consistent)
        self.assertEqual(result.examined_bars, 3)
        self.assertEqual(result.partition_fingerprint, snap.partition.fingerprint)
        self.assertEqual(result.reason, "DECLARED_SYNTHETIC_METADATA_CONSISTENT_NOT_AUTHORIZED")
        self.assertFalse(result.mapping_independently_verified)
        self.assertFalse(result.vendor_entitlement_independently_verified)
        self.assertFalse(result.may_ingest_real_data)
        self.assertFalse(result.may_persist_real_data)
        self.assertFalse(result.may_trade)
        self.assertEqual(snap.fingerprint, prior_fingerprint)

    def test_missing_binding_is_blocked_without_exceptional_fallback(self):
        report = contract.qualify_snapshot_binding(snapshot(), None, DECISION)
        self.assertFalse(report.declared_metadata_consistent)
        self.assertEqual(report.reason, "SOURCE_STREAM_BINDING_MISSING")
        self.assertFalse(report.may_ingest_real_data)

    def test_empty_history_cannot_claim_stream_consistency(self):
        snap = snapshot(bars=())
        report = contract.qualify_snapshot_binding(snap, declared(snap), DECISION)
        self.assertFalse(report.declared_metadata_consistent)
        self.assertEqual(report.reason, "NO_OBSERVED_BARS_TO_QUALIFY")

    def test_broker_product_and_provider_conflict_fail_closed(self):
        for field, value in (
            ("provider_id", "ANOTHER_SYNTHETIC_PROVIDER"),
            ("broker_product_ref", "ANOTHER_FAKE_PRODUCT"),
            ("instrument_version", "DIFFERENT_INSTRUMENT"),
            ("rights_policy_ref", "DIFFERENT_UNVERIFIED_RIGHTS"),
            ("schema_version", "schema-v2"),
            ("source_timezone_policy", "tz-policy-v2"),
        ):
            with self.subTest(field=field):
                result = contract.qualify_snapshot_binding(
                    snapshot(), declared(**{field: value}), DECISION)
                self.assertFalse(result.declared_metadata_consistent)
                self.assertEqual(result.reason, "DECLARED_PARTITION_OR_BROKER_PRODUCT_CONFLICT")
                self.assertFalse(result.may_persist_real_data)

    def test_side_timeframe_calendar_and_aggregation_fail_closed(self):
        for field, value in (
            ("side", BarSide.ASK),
            ("timeframe", Timeframe.M15),
            ("calendar_version", "other-calendar"),
            ("aggregation_version", "other-aggregation"),
        ):
            with self.subTest(field=field):
                result = contract.qualify_snapshot_binding(
                    snapshot(), declared(**{field: value}), DECISION)
                self.assertEqual(result.reason, "DECLARED_PARTITION_OR_BROKER_PRODUCT_CONFLICT")

    def test_differing_stream_id_inside_snapshot_rejected(self):
        clean = snapshot()
        changed = replace(
            clean.closed_bars[1],
            observation=replace(clean.closed_bars[1].observation, stream_id="STREAM-B"),
        )
        mixed = replace(clean, closed_bars=(clean.closed_bars[0], changed, clean.closed_bars[2]))
        self.assertNotEqual(clean.fingerprint, mixed.fingerprint)
        result = contract.qualify_snapshot_binding(mixed, declared(clean), DECISION)
        self.assertEqual(result.reason, "DECLARED_STREAM_ID_CONFLICT")
        self.assertFalse(result.declared_metadata_consistent)

    def test_changed_endpoint_rejected_even_when_price_digest_unchanged(self):
        clean = snapshot()
        changed = replace(
            clean.closed_bars[1],
            observation=replace(clean.closed_bars[1].observation, endpoint="OTHER_SYNTHETIC_ENDPOINT"),
        )
        mixed = replace(clean, closed_bars=(clean.closed_bars[0], changed, clean.closed_bars[2]))
        # Existing candle-content digest does not contain every provenance field.
        self.assertEqual(clean.fingerprint, mixed.fingerprint)
        result = contract.qualify_snapshot_binding(mixed, declared(clean), DECISION)
        self.assertEqual(result.reason, "DECLARED_SOURCE_ENDPOINT_CONFLICT")
        self.assertFalse(result.may_persist_real_data)

    def test_changed_license_claim_rejected_without_granting_rights(self):
        clean = snapshot()
        changed = replace(
            clean.closed_bars[2],
            observation=replace(clean.closed_bars[2].observation, license_scope_claim="DIFFERENT_CLAIM"),
        )
        mixed = replace(clean, closed_bars=(clean.closed_bars[0], clean.closed_bars[1], changed))
        result = contract.qualify_snapshot_binding(mixed, declared(clean), DECISION)
        self.assertEqual(result.reason, "DECLARED_LICENSE_SCOPE_CLAIM_CONFLICT")
        self.assertFalse(result.vendor_entitlement_independently_verified)

    def test_future_checked_snapshot_rejected(self):
        result = contract.qualify_snapshot_binding(
            snapshot(), declared(), T + 15 * M)
        self.assertEqual(result.reason, "SNAPSHOT_NOT_KNOWN_AT_DECISION")

    def test_evidence_retrieved_after_decision_cannot_be_backdated(self):
        clean = snapshot()
        moved = replace(
            clean.closed_bars[0],
            observation=replace(
                clean.closed_bars[0].observation, retrieved_at_utc=T + 30 * M),
        )
        future = replace(clean, closed_bars=(moved,) + clean.closed_bars[1:])
        result = contract.qualify_snapshot_binding(future, declared(clean), DECISION)
        self.assertEqual(result.reason, "DECLARED_EVIDENCE_NOT_KNOWN_AT_DECISION")

    def test_wrong_input_types_are_rejected(self):
        with self.assertRaisesRegex(TypeError, "TYPED_CANDLE_SNAPSHOT"):
            contract.qualify_snapshot_binding(None, declared(), DECISION)
        with self.assertRaisesRegex(TypeError, "TYPED_SOURCE_STREAM"):
            contract.qualify_snapshot_binding(snapshot(), "trust-me", DECISION)
        with self.assertRaisesRegex(ValueError, "UTC"):
            contract.qualify_snapshot_binding(snapshot(), declared(), DECISION.replace(tzinfo=None))
        with self.assertRaisesRegex(TypeError, "TYPED_SOURCE_SIDE"):
            declared(side="BID")

    def test_empty_and_credential_like_mapping_reference_rejected(self):
        with self.assertRaisesRegex(ValueError, "product_mapping_claim_ref"):
            declared(product_mapping_claim_ref="")
        for reference in ("https://vendor.example/secret", "user@host"):
            with self.subTest(reference=reference):
                with self.assertRaisesRegex(ValueError, "NONSECRET_PRODUCT_MAPPING"):
                    declared(product_mapping_claim_ref=reference)

    def test_binding_and_review_records_are_immutable(self):
        b = declared()
        r = contract.qualify_snapshot_binding(snapshot(), b, DECISION)
        with self.assertRaises(FrozenInstanceError):
            b.broker_product_ref = "new-product"
        with self.assertRaises(FrozenInstanceError):
            r.may_trade = True

    def test_source_binding_has_no_io_or_orchestrator_dependencies(self):
        tree = ast.parse(inspect.getsource(contract))
        relative_imports = {
            node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level > 0
        }
        self.assertEqual(relative_imports, {"cache_core", "market_data", "quotes"})
        self.assertFalse(any(
            isinstance(node, (ast.AsyncFunctionDef, ast.Await))
            for node in ast.walk(tree)
        ))

    def test_legacy_cache_contract_and_mixed_scope_fixture_untouched(self):
        clean = snapshot()
        before = clean.fingerprint
        result = contract.qualify_snapshot_binding(clean, declared(clean), DECISION)
        self.assertTrue(result.declared_metadata_consistent)
        self.assertEqual(clean.fingerprint, before)
        self.assertEqual(clean.partition, partition())
        self.assertIsInstance(clean, CandleSnapshot)


if __name__ == "__main__":
    unittest.main()
