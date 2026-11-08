"""RE1: release manifests and rollback checks must never authorize live actions."""
import unittest
from dataclasses import FrozenInstanceError, replace

from forex_trading.release_readiness import (
    EvidenceState, GateEvidence, ReadOnlyRollbackPreview, ReleaseCandidate,
    ReleaseGate, review_release_candidate, preview_full_profile_rollback,
)
from test_versioning import profile


SHA = "a" * 40
PKG_SHA = "b" * 64


def candidate(*, receipts=(), version="0.1.0-rc.1", code=SHA):
    return ReleaseCandidate(version, code, PKG_SHA, profile(), tuple(receipts))


def receipt(gate, state=EvidenceState.CLAIMED_PASS, sha=SHA):
    return GateEvidence(gate, state, "unverified-external-evidence-reference", sha)


class ReleaseReadinessTests(unittest.TestCase):
    def test_initial_candidate_has_all_nine_gates_missing(self):
        r = review_release_candidate(candidate())
        self.assertEqual(len(r.missing_gates), 9)
        self.assertFalse(r.ready_for_independent_evidence_review)
        self.assertFalse(r.may_publish_release)
        self.assertFalse(r.may_assign_lkg)
        self.assertFalse(r.may_trade)

    def test_all_claimed_gates_still_do_not_grant_release(self):
        all_claims = tuple(receipt(g) for g in ReleaseGate)
        r = review_release_candidate(candidate(receipts=all_claims))
        self.assertTrue(r.ready_for_independent_evidence_review)
        self.assertEqual(len(r.claimed_pass_unverified_gates), 9)
        self.assertFalse(r.has_independently_verified_evidence)
        self.assertFalse(r.release_approved)
        self.assertFalse(r.may_publish_release)
        self.assertFalse(r.may_assign_lkg)
        self.assertFalse(r.may_activate)
        self.assertFalse(r.may_trade)

    def test_blocked_external_rights_prevents_review(self):
        items = tuple(
            receipt(g, EvidenceState.BLOCKED if g is
                    ReleaseGate.SOURCE_ENTITLEMENT else EvidenceState.CLAIMED_PASS)
            for g in ReleaseGate
        )
        r = review_release_candidate(candidate(receipts=items))
        self.assertIn(ReleaseGate.SOURCE_ENTITLEMENT, r.blocked_gates)
        self.assertFalse(r.ready_for_independent_evidence_review)

    def test_missing_oos_never_default_passes(self):
        items = tuple(receipt(g) for g in ReleaseGate if
                      g is not ReleaseGate.OOS_BACKTEST)
        r = review_release_candidate(candidate(receipts=items))
        self.assertIn(ReleaseGate.OOS_BACKTEST, r.missing_gates)
        self.assertFalse(r.ready_for_independent_evidence_review)

    def test_ci_receipt_from_wrong_commit_is_rejected_at_review(self):
        items = tuple(
            receipt(g, sha="c" * 40 if g is ReleaseGate.CODE_CI else SHA)
            for g in ReleaseGate
        )
        r = review_release_candidate(candidate(receipts=items))
        self.assertEqual(r.mismatched_code_gates, (ReleaseGate.CODE_CI,))
        self.assertFalse(r.ready_for_independent_evidence_review)

    def test_blank_evidence_reference_rejected_for_pass_claim(self):
        with self.assertRaisesRegex(ValueError, "PASS_CLAIM_REQUIRES"):
            GateEvidence(ReleaseGate.CODE_CI, EvidenceState.CLAIMED_PASS, "")
        with self.assertRaisesRegex(TypeError, "TYPED_RELEASE_GATE"):
            GateEvidence("CODE_CI", EvidenceState.CLAIMED_PASS, "ref")

    def test_duplicate_receipts_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_RELEASE_GATE"):
            candidate(receipts=(receipt(ReleaseGate.CODE_CI),
                                receipt(ReleaseGate.CODE_CI)))

    def test_strict_candidate_semver_and_digests(self):
        for invalid in ("v0.1.0", "01.2.3", "1.02.3", "1.2", "release",
                        "1.2.3/evil"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "INVALID_CANDIDATE_SEMVER"):
                    candidate(version=invalid)
        with self.assertRaisesRegex(ValueError, "INVALID_CANDIDATE_CODE_SHA"):
            candidate(code="not-a-commit-sha")
        with self.assertRaisesRegex(ValueError, "INVALID_PACKAGE_SHA256"):
            replace(candidate(), package_sha256="unbuilt")
        with self.assertRaisesRegex(TypeError, "TYPED_EXECUTION_PROFILE"):
            replace(candidate(), profile="trust-me")

    def test_receipts_cannot_be_mutated_and_fingerprint_is_deterministic(self):
        initial = candidate(receipts=(receipt(ReleaseGate.CODE_CI),))
        self.assertEqual(initial.fingerprint, initial.fingerprint)
        self.assertEqual(len(initial.fingerprint), 64)
        self.assertNotEqual(initial.fingerprint, replace(initial, code_sha="c"*40).fingerprint)
        with self.assertRaises(FrozenInstanceError):
            initial.code_sha = "d"*40
        with self.assertRaises(FrozenInstanceError):
            initial.receipts[0].state = EvidenceState.BLOCKED

    def test_receipt_order_does_not_change_manifest_digest(self):
        a = receipt(ReleaseGate.CODE_CI)
        b = receipt(ReleaseGate.OOS_BACKTEST)
        self.assertEqual(
            candidate(receipts=(a, b)).fingerprint,
            candidate(receipts=(b, a)).fingerprint,
        )

    def test_empty_pass_claim_and_missing_not_confused(self):
        missing = GateEvidence(ReleaseGate.CODE_CI, EvidenceState.MISSING)
        r = review_release_candidate(candidate(receipts=(missing,)))
        self.assertIn(ReleaseGate.CODE_CI, r.missing_gates)
        self.assertFalse(r.ready_for_independent_evidence_review)

    def test_same_profile_still_requires_external_restoration_evidence(self):
        a = profile()
        r = preview_full_profile_rollback(a, a)
        self.assertTrue(r.limited_replay_compatible)
        self.assertEqual(r.changed_profile_fields, ())
        self.assertTrue(r.requires_external_review)
        self.assertFalse(r.can_restore_runtime)
        self.assertFalse(r.can_activate_lkg)
        self.assertFalse(r.can_undo_broker_fills)
        self.assertFalse(r.may_trade)

    def test_all_twelve_profile_fields_invalidate_identity_when_changed(self):
        a = profile()
        for key in a.__dataclass_fields__:
            with self.subTest(key=key):
                b = replace(a, **{key: "some-different-ref"})
                r = preview_full_profile_rollback(a, b)
                self.assertIn(key, r.changed_profile_fields)
                self.assertFalse(r.can_restore_runtime)
                self.assertFalse(r.may_trade)

    def test_incompatible_side_schema_provider_and_revision_are_flagged(self):
        a = profile()
        for field in ("persistence_schema_ref", "bid_ask_basis_ref",
                      "provider_ref", "data_revision_ref"):
            with self.subTest(field=field):
                r = preview_full_profile_rollback(
                    a, replace(a, **{field: "new-ref"}))
                self.assertIn(field, r.incompatible_fields)
                self.assertFalse(r.limited_replay_compatible)
                self.assertFalse(r.can_revert_cache_data)

    def test_noncritical_profile_difference_still_never_executes_rollback(self):
        a = profile()
        r = preview_full_profile_rollback(
            a, replace(a, rule_ref="updated-rule"))
        self.assertTrue(r.limited_replay_compatible)
        self.assertTrue(r.requires_external_review)
        self.assertIn("rule_ref", r.changed_profile_fields)
        self.assertFalse(r.can_restore_runtime)
        self.assertFalse(r.can_activate_lkg)

    def test_bad_rollback_types_fail_closed(self):
        with self.assertRaisesRegex(TypeError, "TYPED_ROLLBACK_PROFILES"):
            preview_full_profile_rollback(profile(), None)
        with self.assertRaisesRegex(TypeError, "TYPED_RELEASE_CANDIDATE"):
            review_release_candidate(None)


if __name__ == "__main__":
    unittest.main()
