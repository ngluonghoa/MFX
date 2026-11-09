"""A04/P0.3 inert schema upgrade and declarative rollback boundary tests."""
from __future__ import annotations

from dataclasses import replace
import json
import unittest

from tools.a04_adapter_conformance import PortSchema
from tools.a04_contract_migration import (
    ContractSnapshot, SchemaClaim, assess_transition, decode_snapshot,
    encode_snapshot, replace_schema, review_declarative_rollback,
    synthetic_baseline_contracts,
)
from tools.check_a04_schema_matrix import (
    MATRIX_BASELINE, run_matrix, verify_pinned_schema_matrix,
)

GRAPH = "fee5c25ab04139a3da502ebc372d981946c1e1e22965fb36987915220cff9ebe"
GOLDEN = "747d029192e080f88b214c76967fa9b91c8e1283f6a4464673cb2bff0b4eabb2"


def original() -> ContractSnapshot:
    return synthetic_baseline_contracts(GRAPH, GOLDEN)


def additive() -> ContractSnapshot:
    before = original()
    old = next(x for x in before.schemas
               if x.schema is PortSchema.PROVIDER_QUERY_V1)
    return replace_schema(before, replace(
        old, minor=1, optional_fields=old.optional_fields + ("synthetic_note",),
    ))


class A04P03SchemaMigrationTests(unittest.TestCase):
    def test_inert_synthetic_exact_snapshot_replay_has_stable_hash(self) -> None:
        base = original()
        decoded = decode_snapshot(encode_snapshot(base))
        # Dataclass tuple order is not canonical; compare replay bytes/hash.
        self.assertEqual(encode_snapshot(base), encode_snapshot(decoded))
        self.assertEqual(base.identity_sha256, decoded.identity_sha256)
        self.assertFalse(decoded.may_activate)

    def test_snapshot_replay_is_independent_of_contract_declaration_order(self) -> None:
        base = original()
        reversed_order = replace(base, schemas=tuple(reversed(base.schemas)))
        self.assertEqual(base.identity_sha256, reversed_order.identity_sha256)
        self.assertEqual(encode_snapshot(base), encode_snapshot(reversed_order))

    def test_additive_optional_minor_is_only_reviewable_not_approved(self) -> None:
        before, after = original(), additive()
        report = assess_transition(before, after)
        self.assertTrue(report.declaration_reviewable)
        self.assertFalse(report.exact_noop)
        self.assertEqual(report.reason, "A04P3_ADDITIVE_SHAPE_REVIEW_ONLY_NOT_APPROVED")
        self.assertFalse(report.may_activate)
        self.assertFalse(report.schema_transform_executed)
        self.assertFalse(report.may_trade)

    def test_unchanged_snapshot_is_noop_not_a_migration(self) -> None:
        base = original()
        report = assess_transition(base, decode_snapshot(encode_snapshot(base)))
        self.assertTrue(report.exact_noop)
        self.assertEqual(report.reason, "A04P3_EXACT_DECLARATION_NOOP")

    def test_major_and_semantic_drift_rejected(self) -> None:
        base = original()
        s = base.schemas[0]
        self.assertEqual(
            assess_transition(base, replace_schema(base, replace(s, major=2))).reason,
            "A04P3_SCHEMA_MAJOR_DRIFT",
        )
        self.assertEqual(
            assess_transition(base, replace_schema(
                base, replace(s, semantic_sha256_claim="f"*64),
            )).reason, "A04P3_SEMANTIC_CLAIM_DRIFT",
        )

    def test_graph_and_original_golden_drift_rejected(self) -> None:
        base = original()
        self.assertEqual(
            assess_transition(base, replace(base, graph_sha256="a"*64)).reason,
            "A04P3_PLUGIN_GRAPH_OR_ABI_DRIFT",
        )
        self.assertEqual(
            assess_transition(base, replace(base, golden_sha256="b"*64)).reason,
            "A04P3_FROZEN_GOLDEN_BASELINE_DRIFT",
        )

    def test_required_field_changes_deny_structural_review(self) -> None:
        base = original()
        s = base.schemas[0]
        moved = replace_schema(base, replace(
            s, required_fields=s.required_fields + ("z_critical",),
        ))
        report = assess_transition(base, moved)
        self.assertFalse(report.declaration_reviewable)
        self.assertEqual(report.reason, "A04P3_REQUIRED_FIELDS_CHANGED")

    def test_unversioned_or_nonadditive_minor_denied(self) -> None:
        base, proposed = original(), additive()
        field = next(s for s in proposed.schemas
                     if s.schema is PortSchema.PROVIDER_QUERY_V1)
        unversioned = replace_schema(proposed, replace(field, minor=0))
        self.assertEqual(
            assess_transition(base, unversioned).reason,
            "A04P3_UNVERSIONED_FIELD_DRIFT",
        )
        skipped = replace_schema(proposed, replace(field, minor=2))
        self.assertEqual(
            assess_transition(base, skipped).reason,
            "A04P3_NON_ADDITIVE_MINOR",
        )

    def test_backwards_minor_version_is_blocked_as_anti_rollback(self) -> None:
        prior, current = original(), additive()
        result = assess_transition(current, prior)
        self.assertFalse(result.declaration_reviewable)
        self.assertEqual(result.reason, "A04P3_SCHEMA_MINOR_ANTI_ROLLBACK")

    def test_exact_rollback_snapshot_check_is_not_git_rollback(self) -> None:
        before, proposed = original(), additive()
        good = review_declarative_rollback(
            before, proposed, decode_snapshot(encode_snapshot(before)),
        )
        self.assertTrue(good.declaration_rollback_reproducible)
        self.assertFalse(good.git_rollback_performed)
        self.assertFalse(good.runtime_reverted)
        self.assertFalse(good.may_trade)

    def test_wrong_target_and_unapproved_upgrade_reject_rollback_claim(self) -> None:
        before, proposed = original(), additive()
        self.assertFalse(review_declarative_rollback(
            before, proposed, proposed,
        ).declaration_rollback_reproducible)
        unsafe = replace(proposed, graph_sha256="b"*64)
        self.assertFalse(review_declarative_rollback(
            before, unsafe, before,
        ).declaration_rollback_reproducible)

    def test_invalid_schema_major_minor_bool_or_negative_rejected(self) -> None:
        s = original().schemas[0]
        with self.assertRaisesRegex(ValueError, "A04P3_INVALID_SCHEMA_VERSION"):
            replace(s, major=True)
        with self.assertRaisesRegex(ValueError, "A04P3_INVALID_SCHEMA_VERSION"):
            replace(s, minor=-1)

    def test_duplicate_required_and_optional_fields_rejected(self) -> None:
        s = original().schemas[0]
        with self.assertRaisesRegex(ValueError, "A04P3_INVALID_OR_DUPLICATE_FIELDS"):
            replace(s, optional_fields=(s.required_fields[0],))
        with self.assertRaisesRegex(ValueError, "A04P3_INVALID_OR_DUPLICATE_FIELDS"):
            replace(s, required_fields=())

    def test_noncanonical_field_order_rejected(self) -> None:
        s = original().schemas[0]
        with self.assertRaisesRegex(ValueError, "A04P3_FIELDS_MUST_BE_CANONICALLY_ORDERED"):
            replace(s, required_fields=tuple(reversed(s.required_fields)))

    def test_no_schema_transform_or_activation_claim(self) -> None:
        s = original().schemas[0]
        with self.assertRaisesRegex(ValueError, "A04P3_NO_EXECUTABLE_TRANSFORM"):
            replace(s, may_transform=True)
        with self.assertRaisesRegex(ValueError, "A04P3_NO_RUNTIME_ACTIVATION"):
            replace(original(), may_activate=True)

    def test_missing_schema_and_wrong_project_rejected(self) -> None:
        base = original()
        with self.assertRaisesRegex(ValueError, "A04P3_EXACT_FIVE_SCHEMAS_REQUIRED"):
            replace(base, schemas=base.schemas[:-1])
        with self.assertRaisesRegex(ValueError, "A04P3_CROSS_PROJECT_SNAPSHOT"):
            replace(base, project_id="FOREX_TRADING")

    def test_wire_replay_denies_duplicate_json_key(self) -> None:
        payload = encode_snapshot(original()).decode("utf-8")
        mangled = payload.replace('"kind":', '"kind":"duplicate","kind":', 1)
        with self.assertRaisesRegex(ValueError, "A04P3_DUPLICATE_SNAPSHOT_JSON_KEY"):
            decode_snapshot(mangled.encode("utf-8"))

    def test_wire_replay_denies_unknown_key_and_noncanonical_json(self) -> None:
        payload = json.loads(encode_snapshot(original()))
        payload["vendor_key"] = "secret-not-accepted"
        with self.assertRaisesRegex(ValueError, "A04P3_SNAPSHOT_SHAPE_OR_KIND_DRIFT"):
            decode_snapshot(json.dumps(payload, sort_keys=True).encode())
        with self.assertRaisesRegex(ValueError, "A04P3_NONCANONICAL_SNAPSHOT_REPLAY"):
            decode_snapshot(json.dumps(
                json.loads(encode_snapshot(original())), sort_keys=True,
                indent=2,
            ).encode())

    def test_snapshot_bytes_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "A04P3_INVALID_SNAPSHOT_BYTES"):
            decode_snapshot(b"x"*13000)

    def test_strict_reference_port_graph_sha_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "A04P3_FROZEN_DECLARED_GRAPH_MISMATCH"):
            synthetic_baseline_contracts("b"*64, GOLDEN)

    def test_matrix_pinned_sha_rejects_tampering(self) -> None:
        from copy import deepcopy
        report = run_matrix()
        baseline = json.loads(MATRIX_BASELINE.read_text(encoding="utf-8"))
        verify_pinned_schema_matrix(report, baseline)
        fake = deepcopy(baseline)
        fake["observed"]["case_matrix_sha256"] = "f"*64
        with self.assertRaisesRegex(ValueError, "A04P3_MATRIX_PINNED_DRIFT"):
            verify_pinned_schema_matrix(report, fake)

    def test_matrix_scope_cannot_advance_trading_or_git_rollback(self) -> None:
        baseline = json.loads(MATRIX_BASELINE.read_text(encoding="utf-8"))
        report = run_matrix()
        with self.assertRaisesRegex(ValueError, "A04P3_UNAUTHORIZED_AUTHORITY"):
            verify_pinned_schema_matrix(
                dict(report, git_rollback_performed=True), baseline,
            )
        with self.assertRaisesRegex(ValueError, "A04P3_AUTHORITY_FLAG_BASELINE_DRIFT"):
            verify_pinned_schema_matrix(
                report, dict(baseline, denied_authority_flags=[]),
            )

    def test_matrix_includes_rejected_changes_and_exact_rollback(self) -> None:
        report = run_matrix()
        self.assertEqual(report["case_count"], 14)
        self.assertTrue(report["declarative_rollback_exact_match"])
        self.assertTrue(report["declarative_rollback_wrong_target_rejected"])
        self.assertFalse(report["plugin_runtime_executed"])
        self.assertFalse(report["git_rollback_performed"])
        self.assertFalse(report["may_deploy_or_trade"])


if __name__ == "__main__":
    unittest.main()
