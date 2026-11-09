"""A04/P0.4 negative policy checks; disposable Git drill only in CI step."""
from __future__ import annotations

from dataclasses import replace
import json
import os
from unittest import TestCase
from unittest.mock import patch

from tools.a04_canary_contract import (
    CanaryEvidence, SyntheticCanaryStage, assess_synthetic_canary,
)
from tools.check_a04_schema_matrix import MATRIX_BASELINE
from tools.run_a04_canary_git_drill import (
    PIN, _observed_inputs, run_canary_matrix,
    run_disposable_git_revert, verify_pinned_a04_p04_receipt,
)

G = "fee5c25ab04139a3da502ebc372d981946c1e1e22965fb36987915220cff9ebe"
F = "747d029192e080f88b214c76967fa9b91c8e1283f6a4464673cb2bff0b4eabb2"
M = "85e285640914e55a700417b88a6586052c214835a9d087235569312fabe33443"
SOURCE = "7e1c1c012b1b189be5ad7b9d07756eac012a8309"


def sample() -> CanaryEvidence:
    return CanaryEvidence(
        "MFX", SOURCE, G, F, M, True, True, True, True, True, True,
    )


def review(evidence: CanaryEvidence, src: SyntheticCanaryStage,
           dst: SyntheticCanaryStage):
    return assess_synthetic_canary(
        src, dst, evidence, expected_graph_sha256=G,
        expected_golden_sha256=F, expected_schema_matrix_sha256=M,
    )


class A04P04CanaryTests(TestCase):
    def test_four_explicit_declaration_only_stages(self):
        self.assertEqual(len(SyntheticCanaryStage), 4)
        self.assertEqual(SyntheticCanaryStage.BASELINE.value, 0)

    def test_allowed_adjacent_review_never_grants_deploy(self):
        states = tuple(SyntheticCanaryStage)
        for a, b in zip(states, states[1:]):
            with self.subTest(a=a.name, b=b.name):
                result = review(sample(), a, b)
                self.assertTrue(result.structural_reviewable)
                self.assertFalse(result.may_deploy_or_trade)
                self.assertFalse(result.may_activate_runtime)
                self.assertFalse(result.may_change_protected_main)

    def test_skip_repeat_reverse_are_denied(self):
        s = SyntheticCanaryStage
        for before, after in (
            (s.BASELINE, s.SYNTHETIC_REPLAY_EXTENDED),
            (s.DECLARATION_SHADOW, s.DECLARATION_SHADOW),
            (s.SYNTHETIC_REPLAY_EXTENDED, s.BASELINE),
        ):
            result = review(sample(), before, after)
            self.assertFalse(result.structural_reviewable)
            self.assertEqual(result.reason, "A04P4_STAGE_SKIP_REPLAY_OR_REVERSE")

    def test_wrong_project_or_original_sha_blocked(self):
        s = SyntheticCanaryStage
        for changed in (replace(sample(), project_id="FOREX"),
                        replace(sample(), frozen_forex_sha="0"*40)):
            self.assertEqual(
                review(changed, s.BASELINE, s.DECLARATION_SHADOW).reason,
                "A04P4_FROZEN_SOURCE_OR_PROJECT_MISMATCH",
            )

    def test_wrong_graph_or_golden_or_matrix_blocked(self):
        s = SyntheticCanaryStage
        for field in ("graph_sha256", "golden_sha256", "schema_matrix_sha256"):
            with self.subTest(field=field):
                e = replace(sample(), **{field: "a"*64})
                self.assertEqual(
                    review(e, s.BASELINE, s.DECLARATION_SHADOW).reason,
                    "A04P4_GOLDEN_GRAPH_OR_MATRIX_DRIFT",
                )

    def test_required_qa_flags_fail_closed(self):
        s = SyntheticCanaryStage
        for field in (
            "snapshot_restored_exact", "git_drill_restored_exact",
            "original_source_parity_passed", "golden_50_passed",
            "matrix_14_passed", "security_gates_passed",
        ):
            with self.subTest(field=field):
                e = replace(sample(), **{field: False})
                self.assertEqual(
                    review(e, s.BASELINE, s.DECLARATION_SHADOW).reason,
                    "A04P4_MISSING_REQUIRED_GATE",
                )

    def test_integer_budget_drift_cannot_mask_bool(self):
        s = SyntheticCanaryStage
        for changed in (replace(sample(), replay_budget_cases=49),
                        replace(sample(), blocked_migration_cases=10),
                        replace(sample(), replay_budget_cases=True)):
            self.assertEqual(
                review(changed, s.BASELINE, s.DECLARATION_SHADOW).reason,
                "A04P4_SYNTHETIC_EVIDENCE_BUDGET_DRIFT",
            )

    def test_runtime_data_failover_order_proposals_denied(self):
        s = SyntheticCanaryStage
        for field in (
            "runtime_activation_requested", "real_data_requested",
            "automatic_provider_failover", "broker_order_requested",
        ):
            with self.subTest(field=field):
                e = replace(sample(), **{field: True})
                self.assertEqual(
                    review(e, s.BASELINE, s.DECLARATION_SHADOW).reason,
                    "A04P4_FORBIDDEN_REAL_OPERATION",
                )

    def test_typed_evidence_and_stage_enforced(self):
        s = SyntheticCanaryStage
        with self.assertRaisesRegex(TypeError, "A04P4_TYPED_EVIDENCE_REQUIRED"):
            review("bad", s.BASELINE, s.DECLARATION_SHADOW)  # type: ignore[arg-type]
        with self.assertRaisesRegex(TypeError, "A04P4_TYPED_STAGES_REQUIRED"):
            review(sample(), 0, s.DECLARATION_SHADOW)  # type: ignore[arg-type]

    def test_missing_or_invalid_pinned_sha_raises(self):
        s = SyntheticCanaryStage
        with self.assertRaisesRegex(ValueError, "A04P4_UNTYPED_PINNED_SHA"):
            assess_synthetic_canary(
                s.BASELINE, s.DECLARATION_SHADOW, sample(),
                expected_graph_sha256="garbage",
                expected_golden_sha256=F, expected_schema_matrix_sha256=M,
            )

    def test_real_p03_and_p02_pinned_data_reused_not_derived_from_live_source(self):
        before, after, hashes = _observed_inputs()
        self.assertNotEqual(before.identity_sha256, after.identity_sha256)
        self.assertEqual(hashes["graph_sha256"], G)
        self.assertEqual(hashes["golden_sha256"], F)
        self.assertEqual(hashes["matrix_sha256"], M)
        self.assertEqual(
            json.loads(MATRIX_BASELINE.read_text())["observed"]["case_count"], 14,
        )

    def test_canonical_policy_matrix_repeats_identically(self):
        _, _, pins = _observed_inputs()
        first = run_canary_matrix(pins)
        second = run_canary_matrix(pins)
        self.assertEqual(first, second)
        self.assertEqual(first["case_count"], 19)
        self.assertEqual(first["blocked_count"], 16)
        self.assertEqual(first["structural_review_only_count"], 3)

    def test_local_runner_must_fail_before_any_git_or_network_mutation(self):
        before, proposed, _ = _observed_inputs()
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(ValueError, "A04P4_GITHUB_HOSTED_ONLY"):
                run_disposable_git_revert(before, proposed)

    def test_wrong_connected_repository_rejected(self):
        before, proposed, _ = _observed_inputs()
        with patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "ngluonghoa/forex-trading-1-0",
        }):
            with self.assertRaisesRegex(ValueError, "A04P4_GITHUB_HOSTED_ONLY"):
                run_disposable_git_revert(before, proposed)

    def test_pinned_receipt_missing_on_bootstrap_documented(self):
        # The first PR execution only measures. Exact SHA is pinned by the
        # next reviewed commit, not fabricated in the initial patch.
        if PIN.is_file():
            self.assertEqual(
                json.loads(PIN.read_text())["schema_version"], 1,
            )

    def test_invalid_receipt_kind_rejected(self):
        with self.assertRaisesRegex(ValueError, "A04P4_UNRECOGNIZED_PINNED_BASELINE"):
            verify_pinned_a04_p04_receipt({}, {"schema_version": 0})
