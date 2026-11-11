"""A04/P0.79: synthetic GitHub ref policy, fast-forward and replay QA ONLY.

NO GitHub API writes, no real witness protection, OAuth, Drive or broker.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha1
from pathlib import Path
from unittest import TestCase

from tools.mfx_native_v2_github_witness_policy import (
    NO_ACTIVE_AUTH, SCHEMA, STATUS, assess_github_ref_readback,
    plan_git_ref_witness_commit, review_witness_ruleset,
)
from test_a04_p78_fenced_cas_recovery import fixture, prepare

WITNESS_REF="refs/heads/mfx-native-v2-witness"
PARENT_GIT_SHA="a"*40
CANDIDATE_GIT_SHA="b"*40


class FakeFastForwardOnlyGitRef:
    """Fake graph demonstrating FF vs fork; not a live GitHub CAS API."""
    def __init__(self, head):
        self.ref=head
        self.parents={head:None}
    def create_commit(self, parent, payload):
        if parent not in self.parents:
            raise ValueError("UNKNOWN_PARENT")
        oid=sha1((parent+":"+payload).encode("utf-8")).hexdigest()
        self.parents[oid]=parent
        return oid
    def update_ref(self, target, *, force=False):
        if target not in self.parents:
            raise ValueError("UNKNOWN_COMMIT")
        cursor=target
        ancestry=set()
        while cursor is not None and cursor not in ancestry:
            ancestry.add(cursor)
            cursor=self.parents[cursor]
        if not force and self.ref not in ancestry:
            raise ValueError("NON_FAST_FORWARD_DENIED")
        self.ref=target


def policy(*,target=WITNESS_REF,include=("~DEFAULT_BRANCH",),
           rules=("deletion","non_fast_forward","required_status_checks",
                  "pull_request"),
           enforced=True,bypass=0,identity=True,default="main"):
    return review_witness_ruleset(
        target_ref=target,default_branch=default,
        enforced=enforced,include_patterns=include,
        rule_types=rules,bypass_actor_count=bypass,
        trusted_identity_verification_available=identity,
    )


def plan(*,tf="4h",parent=PARENT_GIT_SHA):
    f=fixture(tf)
    prepared=prepare(f)
    result=plan_git_ref_witness_commit(
        prepared,target_ref=WITNESS_REF,
        expected_parent_git_sha=parent,
    )
    return f,prepared,result


def readback(p,*,observed=CANDIDATE_GIT_SHA,
             candidate=CANDIDATE_GIT_SHA,
             parent=PARENT_GIT_SHA,payload=None):
    return assess_github_ref_readback(
        p,observed_ref_git_sha=observed,
        candidate_git_sha=candidate,candidate_parent_git_sha=parent,
        candidate_payload_sha256=(
            p.candidate_payload_sha256 if payload is None else payload
        ),
    )


class A04P079GithubWitnessPolicyTests(TestCase):
    def test_01_existing_default_branch_ruleset_matches_main_only(self):
        p=policy(target="refs/heads/main")
        self.assertTrue(p.matched_ruleset)
        self.assertTrue(p.mandatory_rules_seen)
        self.assertTrue(p.ruleset_active)
        self.assertTrue(p.required_checks_present)
        self.assertEqual(p.status,NO_ACTIVE_AUTH)
        self.assertFalse(p.safe_to_activate_v2)

    def test_02_default_only_does_not_cover_separate_witness_branch(self):
        p=policy()
        self.assertFalse(p.matched_ruleset)
        self.assertTrue(p.mandatory_rules_seen)
        self.assertFalse(p.cryptographic_external_witness_proven)

    def test_03_exact_named_witness_rule_matches_but_not_authenticated(self):
        p=policy(include=(WITNESS_REF,))
        self.assertTrue(p.matched_ruleset)
        self.assertFalse(p.identity_control_proven)
        self.assertFalse(p.cryptographic_external_witness_proven)
        self.assertFalse(p.safe_to_activate_v2)

    def test_04_missing_non_fast_forward_denied_for_review(self):
        p=policy(include=(WITNESS_REF,),
                 rules=("deletion","required_status_checks"))
        self.assertFalse(p.mandatory_rules_seen)

    def test_05_missing_deletion_denied_for_review(self):
        p=policy(include=(WITNESS_REF,),
                 rules=("non_fast_forward","required_status_checks"))
        self.assertFalse(p.mandatory_rules_seen)

    def test_06_inactive_rule_not_authoritative(self):
        p=policy(include=(WITNESS_REF,),enforced=False)
        self.assertFalse(p.ruleset_active)
        self.assertFalse(p.safe_to_activate_v2)

    def test_07_bypass_actor_count_is_an_explicit_warning(self):
        p=policy(include=(WITNESS_REF,),bypass=1)
        self.assertFalse(p.no_bypass_claimed)
        self.assertFalse(p.safe_to_activate_v2)

    def test_08_missing_required_checks_not_accepted(self):
        p=policy(include=(WITNESS_REF,),
                 rules=("deletion","non_fast_forward"))
        self.assertFalse(p.required_checks_present)

    def test_09_glob_patterns_are_not_assumed_verified(self):
        p=policy(include=("refs/heads/mfx-native-*",))
        self.assertFalse(p.matched_ruleset)

    def test_10_wrong_default_branch_name_fails_validation(self):
        with self.assertRaisesRegex(ValueError,"RULESET_INPUTS_INVALID"):
            policy(default="../main")

    def test_11_bool_bypass_actor_count_denied(self):
        with self.assertRaisesRegex(ValueError,"RULESET_INPUTS_INVALID"):
            policy(bypass=True)

    def test_12_untyped_pattern_list_denied(self):
        with self.assertRaisesRegex(ValueError,"RULESET_INPUTS_INVALID"):
            policy(include=["~DEFAULT_BRANCH"])

    def test_13_positive_h4_payload_has_no_github_oid_forgery(self):
        f,prepared,p=plan()
        self.assertEqual(p.schema,SCHEMA)
        self.assertEqual(p.status,STATUS)
        self.assertEqual(p.expected_parent_git_sha,PARENT_GIT_SHA)
        self.assertEqual(p.target_ref,WITNESS_REF)
        self.assertEqual(p.witness_generation,1)
        self.assertEqual(p.symbol,"EUR/USD")
        self.assertEqual(p.interval,"4h")
        self.assertEqual(len(p.candidate_payload_sha256),64)
        self.assertFalse(p.published_github_commit)
        self.assertFalse(p.authenticated_external_cas_verified)
        self.assertFalse(p.live_v2_enabled)
        self.assertFalse(p.private_key_or_token_used)
        self.assertEqual((p.drive_writes,p.provider_requests,p.broker_orders),
                         (0,0,0))

    def test_14_d1_sydney_source_domain_is_separate(self):
        _,_,h4=plan()
        _,_,d1=plan(tf="1day")
        self.assertEqual(d1.interval,"1day")
        self.assertNotEqual(h4.candidate_payload_sha256,
                            d1.candidate_payload_sha256)

    def test_15_mutating_main_with_witness_plan_denied(self):
        f=fixture()
        with self.assertRaisesRegex(ValueError,"WITNESS_COMMIT_INPUTS_INVALID"):
            plan_git_ref_witness_commit(
                prepare(f),target_ref="refs/heads/main",
                expected_parent_git_sha=PARENT_GIT_SHA)

    def test_16_bad_parent_git_oid_denied(self):
        with self.assertRaisesRegex(ValueError,"WITNESS_COMMIT_INPUTS_INVALID"):
            plan(parent="bad")

    def test_17_forged_next_witness_sha_denied(self):
        f=fixture()
        p=prepare(f)
        p=replace(p,next_witness_sha256="f"*64)
        with self.assertRaisesRegex(ValueError,"WITNESS_COMMIT_INPUTS_INVALID"):
            plan_git_ref_witness_commit(
                p,target_ref=WITNESS_REF,
                expected_parent_git_sha=PARENT_GIT_SHA)

    def test_18_fake_live_v2_flag_denied(self):
        f=fixture()
        p=replace(prepare(f),live_drive_writer_authorized=True)
        with self.assertRaisesRegex(ValueError,"WITNESS_COMMIT_INPUTS_INVALID"):
            plan_git_ref_witness_commit(
                p,target_ref=WITNESS_REF,
                expected_parent_git_sha=PARENT_GIT_SHA)

    def test_19_matching_caller_readback_still_not_authenticated(self):
        _,_,p=plan()
        r=readback(p)
        self.assertTrue(r.exact_candidate_sha_matched)
        self.assertFalse(r.real_git_ref_readback_verified)
        self.assertFalse(r.durable_authenticated_antirollback_verified)
        self.assertFalse(r.live_v2_enabled)

    def test_20_unchanged_ref_is_not_accepted_as_published(self):
        _,_,p=plan()
        r=readback(p,observed=PARENT_GIT_SHA)
        self.assertEqual(r.status,"NOT_PUBLISHED_OR_REF_STALE")
        self.assertFalse(r.exact_candidate_sha_matched)

    def test_21_unexpected_fork_head_denied(self):
        _,_,p=plan()
        with self.assertRaisesRegex(ValueError,"FORK_OR_UNEXPECTED_HEAD"):
            readback(p,observed="c"*40)

    def test_22_wrong_commit_parent_denied(self):
        _,_,p=plan()
        with self.assertRaisesRegex(ValueError,"PARENT_COMMIT_CHANGED"):
            readback(p,parent="c"*40)

    def test_23_wrong_payload_sha_denied(self):
        _,_,p=plan()
        with self.assertRaisesRegex(ValueError,"PAYLOAD_SHA_MISMATCH"):
            readback(p,payload="c"*64)

    def test_24_tampered_verified_flag_denied(self):
        _,_,p=plan()
        p=replace(p,authenticated_external_cas_verified=True)
        with self.assertRaisesRegex(ValueError,"READBACK_SHAPE_OR_FLAGS_INVALID"):
            readback(p)

    def test_25_synthetic_non_force_fast_forward_fork_loser_denied(self):
        store=FakeFastForwardOnlyGitRef(PARENT_GIT_SHA)
        a=store.create_commit(PARENT_GIT_SHA,"writerA")
        b=store.create_commit(PARENT_GIT_SHA,"writerB")
        store.update_ref(a,force=False)
        with self.assertRaisesRegex(ValueError,"NON_FAST_FORWARD_DENIED"):
            store.update_ref(b,force=False)
        self.assertEqual(store.ref,a)

    def test_26_force_override_defeats_synthetic_fast_forward_protection(self):
        store=FakeFastForwardOnlyGitRef(PARENT_GIT_SHA)
        a=store.create_commit(PARENT_GIT_SHA,"writerA")
        b=store.create_commit(PARENT_GIT_SHA,"writerB")
        store.update_ref(a,force=False)
        store.update_ref(b,force=True)
        self.assertEqual(store.ref,b)
        # This models why force/delete bypass restrictions matter.

    def test_27_two_independent_fake_refs_can_both_accept_forks(self):
        one=FakeFastForwardOnlyGitRef(PARENT_GIT_SHA)
        two=FakeFastForwardOnlyGitRef(PARENT_GIT_SHA)
        a=one.create_commit(PARENT_GIT_SHA,"A")
        b=two.create_commit(PARENT_GIT_SHA,"B")
        one.update_ref(a,force=False)
        two.update_ref(b,force=False)
        self.assertNotEqual(one.ref,two.ref)
        # One real independently trusted monotonic authority is required.

    def test_28_no_new_workflows_or_secrets_or_drive_activity(self):
        source=Path(".github/workflows/mfx-native-htf-incremental-commit.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn('cron: "25 * * * *"',source)
        self.assertNotIn("mfx_native_v2_github_witness_policy",source)
        audit=Path("tools/run_mfx_native_htf_cache_audit.py").read_text(
            encoding="utf-8")
        self.assertNotIn("mfx_native_v2_github_witness_policy",audit)
        _,_,p=plan()
        self.assertEqual((p.drive_writes,p.provider_requests,p.broker_orders),
                         (0,0,0))
