"""A04/P0.80 hermetic GitHub witness read-only branch rules/ref preflight.

No GitHub API writes; synthetic branch-rules responses DO NOT prove real
ruleset coverage or independent signing/trust. All prices and broker OFF.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest import TestCase

from tools.mfx_native_v2_github_witness_readonly_preflight import (
    GITHUB_BRANCH_RULES_ENDPOINT, SCHEMA, TARGET,
    GitBranchRulesObservation, GitCommitObservation, GitRefObservation,
    assess_github_witness_sandbox_readonly,
)
from test_a04_p79_github_witness_policy import plan

PARENT="a"*40
CANDIDATE="b"*40
RULES=((980012,"deletion"),(980012,"non_fast_forward"),
       (980012,"required_status_checks"))


def branch_rules(*,types=RULES, code=200,
                 endpoint=GITHUB_BRANCH_RULES_ENDPOINT,branch=TARGET):
    return GitBranchRulesObservation(
        branch_ref=branch,endpoint=endpoint,http_status=code,
        active_rules=types,
    )


def ref(sha=PARENT, *,status=200, branch=TARGET, object_type="commit"):
    return GitRefObservation(
        ref=branch,http_status=status,git_sha=sha,
        object_type=object_type,
    )


def candidate(commit_sha=CANDIDATE, *,
              parent=PARENT,payload=None,signature=True):
    _,_,p=plan()
    return GitCommitObservation(
        git_sha=commit_sha,parents=(parent,),
        witness_payload_sha256=(
            p.candidate_payload_sha256 if payload is None else payload
        ),
        github_signature_verified=signature,
    )


AUTO = object()


def assess(*,strategy="4h",before_rules=None,after_rules=None,
           before_ref=None,after_ref=None,commit=AUTO):
    _,_,p=plan(tf=strategy)
    return assess_github_witness_sandbox_readonly(
        p,
        rules_before=(
            branch_rules() if before_rules is None else before_rules
        ),
        rules_after=(
            branch_rules() if after_rules is None else after_rules
        ),
        ref_before=(
            ref() if before_ref is None else before_ref
        ),
        ref_after=(
            ref(CANDIDATE) if after_ref is None else after_ref
        ),
        candidate=candidate(payload=p.candidate_payload_sha256)
                  if commit is AUTO else commit,
    )


class A04P080GithubWitnessReadOnlyPreflightTests(TestCase):
    def test_01_exhaustive_offline_positive_is_still_not_real_trust(self):
        r=assess()
        self.assertEqual(r.status,
                         "CALLER_READBACK_CONSISTENT_NOT_EXTERNAL_AUTHORITY")
        self.assertTrue(r.head_matches_candidate)
        self.assertTrue(r.required_branch_rules_reported)
        self.assertTrue(r.caller_observation_consistent)
        self.assertFalse(r.independently_authenticated_head)
        self.assertFalse(r.real_exact_head_atomic_cas_verified)
        self.assertFalse(r.durable_monotonic_antirollback_verified)
        self.assertFalse(r.ruleset_bypass_protection_verified)
        self.assertFalse(r.live_v2_authorized)
        self.assertEqual((r.github_mutations,r.drive_writes,
                          r.provider_requests,r.broker_orders),(0,0,0))

    def test_02_absent_branch_cannot_be_treated_as_activated(self):
        r=assess(before_ref=ref(None,status=404,object_type=None),
                 after_ref=ref(None,status=404,object_type=None),
                 commit=None)
        self.assertEqual(r.status,"NO_WITNESS_REF_READONLY_RESEARCH_ONLY")
        self.assertFalse(r.head_matches_candidate)
        self.assertIsNone(r.observed_head_sha)

    def test_03_existing_branch_without_candidate_unpublished(self):
        _,_,p=plan()
        r=assess_github_witness_sandbox_readonly(
            p, rules_before=branch_rules(),
            rules_after=branch_rules(), ref_before=ref(),
            ref_after=ref(), candidate=None)
        self.assertEqual(r.status,"NO_CANDIDATE_NO_PUBLICATION")
        self.assertFalse(r.head_matches_candidate)

    def test_04_candidate_is_not_yet_published(self):
        r=assess(after_ref=ref(PARENT))
        self.assertEqual(r.status,"CANDIDATE_NOT_PUBLISHED_OR_STALE_HEAD")
        self.assertFalse(r.head_matches_candidate)

    def test_05_wrong_signer_verification_cannot_publish(self):
        with self.assertRaisesRegex(ValueError,
                                    "CANDIDATE_SIGNATURE_NOT_VERIFIED"):
            assess(commit=candidate(signature=False))

    def test_06_wrong_initial_ref_rejected(self):
        with self.assertRaisesRegex(ValueError,
                                    "INITIAL_REF_HEAD_NOT_EXPECTED_PARENT"):
            assess(before_ref=ref("c"*40))

    def test_07_wrong_candidate_parent_rejected(self):
        with self.assertRaisesRegex(ValueError,"PARENT_COMMIT_CHANGED"):
            assess(commit=candidate(parent="c"*40))

    def test_08_wrong_candidate_payload_rejected(self):
        with self.assertRaisesRegex(ValueError,"PAYLOAD_SHA_MISMATCH"):
            assess(commit=candidate(payload="c"*64))

    def test_09_unexpected_ref_head_after_read_rejected(self):
        with self.assertRaisesRegex(ValueError,
                                    "GITHUB_REF_FORK_OR_UNEXPECTED_HEAD"):
            assess(after_ref=ref("c"*40))

    def test_10_branch_disappeared_during_readback_rejected(self):
        with self.assertRaisesRegex(ValueError,
                                    "WITNESS_REF_APPEARED_OR_DISAPPEARED"):
            assess(after_ref=ref(None,status=404,object_type=None))

    def test_11_branch_created_during_readback_rejected(self):
        with self.assertRaisesRegex(ValueError,
                                    "WITNESS_REF_APPEARED_OR_DISAPPEARED"):
            assess(before_ref=ref(None,status=404,object_type=None))

    def test_12_branch_rules_changed_between_reads(self):
        mutated=branch_rules(types=RULES+((980012,"required_linear_history"),))
        with self.assertRaisesRegex(ValueError,"BRANCH_RULES_CHANGED"):
            assess(after_rules=mutated)

    def test_13_branch_ruleset_issuer_changed_between_reads(self):
        changed=branch_rules(types=((980013,"deletion"),
                                    (980013,"non_fast_forward"),
                                    (980013,"required_status_checks")))
        with self.assertRaisesRegex(ValueError,"BRANCH_RULES_CHANGED"):
            assess(after_rules=changed)

    def test_14_missing_deletion_rule_denied(self):
        rs=branch_rules(types=((980012,"non_fast_forward"),))
        with self.assertRaisesRegex(ValueError,
                                    "BRANCH_REF_NOT_PROTECTED"):
            assess(before_rules=rs,after_rules=rs)

    def test_15_missing_non_fast_forward_rule_denied(self):
        rs=branch_rules(types=((980012,"deletion"),))
        with self.assertRaisesRegex(ValueError,
                                    "BRANCH_REF_NOT_PROTECTED"):
            assess(before_rules=rs,after_rules=rs)

    def test_16_default_only_ruleset_is_not_branch_scoped_evidence(self):
        rs=branch_rules(types=())
        with self.assertRaisesRegex(ValueError,
                                    "BRANCH_REF_NOT_PROTECTED"):
            assess(before_rules=rs,after_rules=rs)

    def test_17_wrong_api_route_denied(self):
        rs=branch_rules(endpoint="GET /repos/ngluonghoa/MFX/rulesets")
        with self.assertRaisesRegex(ValueError,
                                    "RULES_OBSERVATION_INVALID"):
            assess(before_rules=rs)

    def test_18_wrong_branch_ref_denied(self):
        rs=branch_rules(branch="refs/heads/main")
        with self.assertRaisesRegex(ValueError,
                                    "RULES_OBSERVATION_INVALID"):
            assess(before_rules=rs)

    def test_19_403_or_404_for_branch_rules_not_silently_passed(self):
        for code in (403,404,500):
            with self.subTest(code=code):
                rs=branch_rules(code=code)
                with self.assertRaisesRegex(ValueError,
                                            "RULES_OBSERVATION_INVALID"):
                    assess(before_rules=rs)

    def test_20_oversized_rule_list_rejected(self):
        rs=branch_rules(types=tuple((9876,"deletion") for _ in range(65)))
        with self.assertRaisesRegex(ValueError,
                                    "RULES_OBSERVATION_INVALID"):
            assess(before_rules=rs)

    def test_21_malformed_rule_id_bool_rejected(self):
        rs=branch_rules(types=((True,"deletion"),
                               (980012,"non_fast_forward")))
        with self.assertRaisesRegex(ValueError,
                                    "RULES_OBSERVATION_INVALID"):
            assess(before_rules=rs)

    def test_22_claimed_verified_bypass_info_denied(self):
        rs=replace(branch_rules(),bypass_visibility_verified=True)
        with self.assertRaisesRegex(ValueError,
                                    "RULES_OBSERVATION_INVALID"):
            assess(before_rules=rs)

    def test_23_wrong_git_ref_object_type_denied(self):
        with self.assertRaisesRegex(ValueError,
                                    "GIT_REF_OBSERVATION_INVALID"):
            assess(after_ref=ref(CANDIDATE,object_type="tag"))

    def test_24_bad_git_ref_sha_denied(self):
        with self.assertRaisesRegex(ValueError,
                                    "GIT_REF_OBSERVATION_INVALID"):
            assess(after_ref=ref("x"*40))

    def test_25_no_commit_merge_parent_allowed(self):
        c=replace(candidate(),parents=(PARENT,"c"*40))
        with self.assertRaisesRegex(ValueError,
                                    "CANDIDATE_GIT_COMMIT_INVALID"):
            assess(commit=c)

    def test_26_commit_signature_type_has_to_be_bool(self):
        c=replace(candidate(),github_signature_verified=1)
        with self.assertRaisesRegex(ValueError,
                                    "CANDIDATE_GIT_COMMIT_INVALID"):
            assess(commit=c)

    def test_27_signed_commit_is_not_independent_witness_proof(self):
        r=assess()
        self.assertFalse(r.independently_authenticated_head)
        self.assertFalse(r.ruleset_bypass_protection_verified)
        self.assertFalse(r.durable_monotonic_antirollback_verified)

    def test_28_d1_sydney_witness_is_separate(self):
        _,_,d1=plan(tf="1day")
        r=assess_github_witness_sandbox_readonly(
            d1,rules_before=branch_rules(),
            rules_after=branch_rules(),ref_before=ref(),
            ref_after=ref(CANDIDATE),
            candidate=candidate(
                payload=d1.candidate_payload_sha256))
        self.assertTrue(r.caller_observation_consistent)
        self.assertFalse(r.live_v2_authorized)

    def test_29_forged_live_flags_in_parent_plan_denied(self):
        _,_,p=plan()
        p=replace(p,live_v2_enabled=True)
        with self.assertRaisesRegex(ValueError,"GIT_WITNESS_PLAN_UNSAFE"):
            assess_github_witness_sandbox_readonly(
                p,rules_before=branch_rules(),
                rules_after=branch_rules(),
                ref_before=ref(),ref_after=ref(CANDIDATE),
                candidate=candidate(payload=p.candidate_payload_sha256))

    def test_30_witness_module_not_wired_to_production_actions(self):
        source=Path(".github/workflows/mfx-native-htf-incremental-commit.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn('cron: "25 * * * *"',source)
        self.assertNotIn("mfx_native_v2_github_witness_readonly_preflight",
                         source)
        audit=Path("tools/run_mfx_native_htf_cache_audit.py").read_text(
            encoding="utf-8")
        self.assertNotIn("mfx_native_v2_github_witness_readonly_preflight",
                         audit)
        self.assertEqual(SCHEMA,"MFX_A04_P80_WITNESS_REF_READONLY_PREFLIGHT_V1")
