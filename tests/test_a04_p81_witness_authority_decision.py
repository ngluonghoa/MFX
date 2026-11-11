"""A04/P0.81: research-only GitHub witness authority decision cases."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest import TestCase

from tools.mfx_native_v2_witness_authority_decision import (
    EXISTING_REF, MISSING_REF, REPO, REF, RULES_BLOCKED,
    RULES_HTTP_200, RULES_NOT_READ, SCHEMA,
    WitnessAuthorityResearch, assess_witness_authority_decision,
)


def sample(**changes: object) -> WitnessAuthorityResearch:
    base = WitnessAuthorityResearch(
        repository=REPO, candidate_ref=REF,
        main_ruleset_includes=("~DEFAULT_BRANCH",),
        witness_ref_result=MISSING_REF,
        witness_rules_result=RULES_BLOCKED,
        effective_branch_rules=(),
    )
    return replace(base, **changes)


class A04P081WitnessAuthorityDecisionTests(TestCase):
    def test_01_current_real_blockers_are_fully_visible(self):
        result = assess_witness_authority_decision(sample())
        self.assertEqual(result.status, "BLOCKED_RESEARCH_ONLY")
        self.assertIn("REAL_WITNESS_REF_READBACK", result.missing_evidence)
        self.assertIn("EFFECTIVE_EXACT_BRANCH_RULES_GET",
                      result.missing_evidence)
        self.assertIn("MAIN_RULESET_DOES_NOT_COVER_WITNESS",
                      result.missing_evidence)
        self.assertIn("SERVER_SIDE_EXACT_HEAD_CAS_NOT_PROVED",
                      result.missing_evidence)
        self.assertFalse(result.rules_readback_available)

    def test_02_not_approved_to_touch_git_or_drive(self):
        r = assess_witness_authority_decision(sample())
        self.assertEqual((r.github_mutations, r.drive_reads,
                          r.drive_writes, r.vendor_calls, r.broker_orders),
                         (0, 0, 0, 0, 0))
        self.assertFalse(r.production_witness_branch_created)

    def test_03_never_authorize_live_v2(self):
        r = assess_witness_authority_decision(sample())
        self.assertFalse(r.native_v2_read_authorized)
        self.assertFalse(r.native_v2_write_authorized)
        self.assertFalse(r.independently_authenticated)
        self.assertFalse(r.durable_antirollback_verified)
        self.assertFalse(r.exact_head_cas_verified)

    def test_04_owner_acceptance_alone_not_enough(self):
        r = assess_witness_authority_decision(sample(
            owner_selected_github_metadata_witness=True,
            owner_authorized_sandbox_mutation=True))
        self.assertFalse(r.research_reviewable)
        self.assertFalse(r.native_v2_write_authorized)

    def test_05_real_ref_alone_not_enough(self):
        r = assess_witness_authority_decision(sample(
            witness_ref_result=EXISTING_REF))
        self.assertFalse(r.research_reviewable)
        self.assertIn("EFFECTIVE_EXACT_BRANCH_RULES_GET",
                      r.missing_evidence)

    def test_06_main_ruleset_is_not_witness_ruleset(self):
        r = assess_witness_authority_decision(sample(
            main_ruleset_includes=("~DEFAULT_BRANCH",)))
        self.assertIn("MAIN_RULESET_DOES_NOT_COVER_WITNESS",
                      r.missing_evidence)

    def test_07_connector_block_not_github_http_400(self):
        r = assess_witness_authority_decision(sample())
        self.assertFalse(r.rules_readback_available)

    def test_08_missing_rule_api_returns_gap(self):
        r = assess_witness_authority_decision(sample(
            witness_rules_result=RULES_NOT_READ))
        self.assertIn("EFFECTIVE_EXACT_BRANCH_RULES_GET",
                      r.missing_evidence)

    def test_09_missing_deletion_protection(self):
        r = assess_witness_authority_decision(sample(
            witness_rules_result=RULES_HTTP_200,
            effective_branch_rules=("non_fast_forward",)))
        self.assertIn("EFFECTIVE_EXACT_BRANCH_RULES_GET",
                      r.missing_evidence)

    def test_10_missing_non_fast_forward_protection(self):
        r = assess_witness_authority_decision(sample(
            witness_rules_result=RULES_HTTP_200,
            effective_branch_rules=("deletion",)))
        self.assertIn("EFFECTIVE_EXACT_BRANCH_RULES_GET",
                      r.missing_evidence)

    def test_11_both_rules_still_not_sufficient(self):
        r = assess_witness_authority_decision(sample(
            witness_rules_result=RULES_HTTP_200,
            effective_branch_rules=("deletion", "non_fast_forward")))
        self.assertTrue(r.rules_readback_available)
        self.assertIn("SERVER_SIDE_EXACT_HEAD_CAS_NOT_PROVED",
                      r.missing_evidence)
        self.assertFalse(r.native_v2_write_authorized)

    def test_12_all_caller_flags_still_not_authentication(self):
        r = assess_witness_authority_decision(sample(
            owner_selected_github_metadata_witness=True,
            owner_authorized_sandbox_mutation=True,
            witness_ref_result=EXISTING_REF,
            witness_rules_result=RULES_HTTP_200,
            effective_branch_rules=("deletion", "non_fast_forward"),
            independently_verified_signer=True,
            bypass_and_admin_threat_accepted=True,
            independent_append_only_backup_verified=True,
            genuine_cloud_concurrent_ff_probe_verified=True,
            independently_authenticated_monotonic_head_verified=True))
        self.assertTrue(r.research_reviewable)
        self.assertEqual(r.missing_evidence,
                         ("SERVER_SIDE_EXACT_HEAD_CAS_NOT_PROVED",))
        self.assertFalse(r.independently_authenticated)
        self.assertFalse(r.native_v2_write_authorized)

    def test_13_forged_cas_flag_rejected(self):
        with self.assertRaisesRegex(ValueError, "NOT_EXACT_HEAD_CAS"):
            assess_witness_authority_decision(sample(
                externally_atomic_exact_head_cas_verified=True))

    def test_14_missing_owner_selection(self):
        r = assess_witness_authority_decision(sample())
        self.assertIn("OWNER_TRUST_BOUNDARY_CHOICE", r.missing_evidence)

    def test_15_missing_sandbox_approval(self):
        r = assess_witness_authority_decision(sample())
        self.assertIn("OWNER_TEST_ONLY_MUTATION_APPROVAL",
                      r.missing_evidence)

    def test_16_wrong_repo_denied(self):
        with self.assertRaisesRegex(ValueError, "SCHEMA_INVALID"):
            assess_witness_authority_decision(sample(
                repository="ngluonghoa/forex-trading-1-0"))

    def test_17_wrong_ref_denied(self):
        with self.assertRaisesRegex(ValueError, "SCHEMA_INVALID"):
            assess_witness_authority_decision(sample(
                candidate_ref="refs/heads/main"))

    def test_18_invalid_rule_list_denied(self):
        with self.assertRaisesRegex(ValueError, "SCHEMA_INVALID"):
            assess_witness_authority_decision(sample(
                effective_branch_rules=("deletion", 3),
                witness_rules_result=RULES_HTTP_200))

    def test_19_duplicate_rules_denied(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATED_RULE_TYPE"):
            assess_witness_authority_decision(sample(
                witness_rules_result=RULES_HTTP_200,
                effective_branch_rules=("deletion", "deletion")))

    def test_20_fake_rules_without_get_rejected(self):
        with self.assertRaisesRegex(ValueError, "RULES_FABRICATED"):
            assess_witness_authority_decision(sample(
                effective_branch_rules=("deletion", "non_fast_forward")))

    def test_21_boolean_type_not_coerced(self):
        with self.assertRaisesRegex(ValueError, "SCHEMA_INVALID"):
            assess_witness_authority_decision(sample(
                owner_selected_github_metadata_witness=1))

    def test_22_ref_readback_enum_required(self):
        with self.assertRaisesRegex(ValueError, "SCHEMA_INVALID"):
            assess_witness_authority_decision(sample(
                witness_ref_result="HTTP_404"))

    def test_23_rules_enum_required(self):
        with self.assertRaisesRegex(ValueError, "SCHEMA_INVALID"):
            assess_witness_authority_decision(sample(
                witness_rules_result="GITHUB_HTTP_400"))

    def test_24_no_production_workflow_change(self):
        workflow = Path(
            ".github/workflows/mfx-native-htf-incremental-commit.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('cron: "25 * * * *"', workflow)
        self.assertNotIn("mfx_native_v2_witness_authority_decision",
                         workflow)
        self.assertEqual(SCHEMA,
                         "MFX_A04_P81_WITNESS_AUTHORITY_DECISION_V1")
