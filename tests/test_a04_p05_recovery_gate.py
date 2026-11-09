"""A04/P0.5 protected recovery and explicit schema selection safety QA."""
from __future__ import annotations

from dataclasses import replace
import unittest

from tools.a04_adapter_conformance import PortSchema
from tools.a04_p05_recovery_selection import (
    IntegrationFacts, RecoveryFacts, review_integration_readiness,
    review_protected_recovery, select_exact_schema_declaration,
)
from tools.check_a04_p05_recovery_gate import _seed, run_matrix

SOURCE = "7e1c1c012b1b189be5ad7b9d07756eac012a8309"


def recovery() -> RecoveryFacts:
    return RecoveryFacts(
        "ngluonghoa/MFX", "a"*40, "a"*40, "b"*40, "c"*40,
        True, True, True, True, True,
    )


class A04P05SafetyTests(unittest.TestCase):
    def test_recovery_only_allows_new_pr_review(self) -> None:
        r = review_protected_recovery(recovery())
        self.assertTrue(r.new_branch_pr_reviewable)
        self.assertFalse(r.may_write_remote_git)
        self.assertFalse(r.may_reset_or_force_main)
        self.assertFalse(r.may_redeploy_production)
        self.assertFalse(r.may_release_or_trade)

    def test_recovery_moved_main_and_competing_pr_fail_closed(self) -> None:
        for v in (
            replace(recovery(), observed_main_sha="e"*40),
            replace(recovery(), zero_competing_prs=False),
            replace(recovery(), dependency_revert_reviewed=False),
        ):
            self.assertFalse(review_protected_recovery(v).new_branch_pr_reviewable)

    def test_recovery_wrong_project_forced_or_direct_write_fail(self) -> None:
        for v in (
            replace(recovery(), project_repository="ForexTrading"),
            replace(recovery(), force_push_requested=True),
            replace(recovery(), direct_main_write_requested=True),
            replace(recovery(), production_redeploy_requested=True),
        ):
            self.assertFalse(review_protected_recovery(v).new_branch_pr_reviewable)

    def test_declared_exact_version_never_activates_plugin(self) -> None:
        prior, changed, _ = _seed()
        found = select_exact_schema_declaration(
            prior, (prior, changed), PortSchema.PROVIDER_QUERY_V1, 1, 1,
        )
        self.assertTrue(found.structural_reviewable)
        self.assertEqual(found.selected_snapshot_sha256, changed.identity_sha256)
        self.assertFalse(found.runtime_schema_applied)
        self.assertFalse(found.may_import_plugin)

    def test_declared_version_not_present_does_not_fallback(self) -> None:
        prior, _, _ = _seed()
        found = select_exact_schema_declaration(
            prior, (prior,), PortSchema.PROVIDER_QUERY_V1, 1, 1,
        )
        self.assertFalse(found.structural_reviewable)
        self.assertEqual(found.reason, "A04P5_EXACT_VERSION_NOT_DECLARED_NO_FALLBACK")

    def test_schema_minor_downgrade_no_silent_conversion(self) -> None:
        prior, changed, _ = _seed()
        found = select_exact_schema_declaration(
            prior, (changed,), PortSchema.PROVIDER_QUERY_V1, 1, 0,
        )
        self.assertFalse(found.structural_reviewable)

    def test_schema_explicit_fallback_opt_in_still_blocked(self) -> None:
        prior, _, _ = _seed()
        found = select_exact_schema_declaration(
            prior, (prior,), PortSchema.PROVIDER_QUERY_V1, 1, 0,
            allow_implicit_fallback=True,
        )
        self.assertEqual(found.reason, "A04P5_NO_IMPLICIT_SCHEMA_FALLBACK")

    def test_duplicated_schema_exact_version_is_ambiguous(self) -> None:
        prior, _, _ = _seed()
        found = select_exact_schema_declaration(
            prior, (prior, prior), PortSchema.PROVIDER_QUERY_V1, 1, 0,
        )
        self.assertEqual(found.reason, "A04P5_AMBIGUOUS_EXACT_SCHEMA_VERSION")

    def test_schema_request_is_bounded(self) -> None:
        prior, _, _ = _seed()
        with self.assertRaisesRegex(ValueError, "A04P5_INVALID_VERSION_REQUEST"):
            select_exact_schema_declaration(
                prior, (prior,), PortSchema.PROVIDER_QUERY_V1, True, 0,
            )

    def test_all_real_integration_authorities_remain_false(self) -> None:
        x = IntegrationFacts(True, True, True, True, True, True)
        r = review_integration_readiness(x)
        self.assertTrue(r.documentation_reviewable)
        self.assertFalse(r.runtime_integration_authorized)
        self.assertFalse(r.production_canary_authorized)
        self.assertFalse(r.may_fetch_real_data)
        self.assertFalse(r.may_execute_orders)

    def test_false_claims_of_approval_do_not_grant_runtime(self) -> None:
        x = IntegrationFacts(True, True, True, True, True, True)
        for p in (
            replace(x, source_delta_approved=True),
            replace(x, provider_rights_qualified=True),
            replace(x, real_execution_semantics_verified=True),
            replace(x, runtime_plugin_activation_requested=True),
            replace(x, broker_orders_requested=True),
        ):
            self.assertFalse(
                review_integration_readiness(p).documentation_reviewable,
            )

    def test_full_ci_matrix_budget_remains_structural_only(self) -> None:
        report = run_matrix()
        self.assertEqual(report["cases"], 28)
        self.assertEqual(report["review_only"], 5)
        self.assertEqual(report["blocked"], 23)
        self.assertTrue(report["no_real_git_write"])
        self.assertTrue(report["no_trades_or_release"])


if __name__ == "__main__":
    unittest.main()
