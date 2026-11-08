"""M2/P0.6 negative-path tests. All rights, candles and markers are synthetic."""
import unittest
from dataclasses import replace
from datetime import timedelta

from forex_trading.cache_storage_review import make_synthetic_generation
from forex_trading.synthetic_cache_failure_paths import (
    LAYERS, SyntheticRecoveryState, SyntheticRightsAction,
    evaluate_synthetic_atomic_recovery, plan_synthetic_rights_cache_transition,
)
from forex_trading.account_data_review import ReviewState
from forex_trading.source_qualification import RightDecision
from test_account_data_review import T, packet, account, notice
from test_cache_storage_review import snap

A = "a" * 64
B = "b" * 64


def plan(p=None, now=T, keys=(A, B)):
    return plan_synthetic_rights_cache_transition(
        packet() if p is None else p, now, keys,
        requested_cache_retention_days=30,
    )


def generations():
    first = make_synthetic_generation(snap(), T + timedelta(minutes=1))
    second = make_synthetic_generation(
        snap(source_head_claim="synthetic-r2"), T + timedelta(minutes=2), first
    )
    return first, second


class SyntheticRightsInvalidationTests(unittest.TestCase):
    def test_claimed_paperwork_does_not_invalidate_or_grant_live_cache(self):
        r = plan()
        self.assertEqual(r.action, SyntheticRightsAction.PAPERWORK_ONLY)
        self.assertEqual(r.partition_fingerprints, (A, B))
        self.assertEqual(r.invalidated_layers, ())
        self.assertFalse(r.may_fetch_real_data)
        self.assertFalse(r.may_reuse_real_cache)
        self.assertFalse(r.may_purge_or_restore_real_data)

    def test_expiry_invalidation_scoped_all_five_layers(self):
        r = plan(packet(account=account(expires_utc=T)))
        self.assertEqual(r.action, SyntheticRightsAction.INVALIDATE_AND_REVIEW)
        self.assertEqual(r.account_review.state, ReviewState.SUSPEND_AND_REVIEW_RETENTION)
        self.assertEqual(r.invalidated_layers, LAYERS)
        self.assertIn("PROPOSE_INVALIDATE_L1_TO_L5_PRESERVE_AUDIT", r.reasons)

    def test_seen_retroactive_revocation_not_backdated_in_audit(self):
        n = notice(when=T - timedelta(days=5), first_seen=T - timedelta(minutes=2))
        r = plan(packet(revocation=n), keys=(A,))
        self.assertEqual(r.action, SyntheticRightsAction.INVALIDATE_AND_REVIEW)
        self.assertEqual(r.observed_revocation_first_seen_utc, n.first_seen_by_us_utc)
        self.assertEqual(r.observed_revocation_effective_utc, n.effective_utc)
        self.assertEqual(r.partition_fingerprints, (A,))

    def test_future_known_notice_does_not_leak_revocation_into_past(self):
        n = notice(when=T - timedelta(minutes=1),
                   first_seen=T + timedelta(days=1))
        r = plan(packet(revocation=n))
        self.assertIsNone(r.observed_revocation_first_seen_utc)
        self.assertIsNone(r.observed_revocation_effective_utc)
        self.assertEqual(r.action, SyntheticRightsAction.BLOCK_UNVERIFIED)
        self.assertNotIn("PROPOSE_INVALIDATE_L1_TO_L5_PRESERVE_AUDIT", r.reasons)

    def test_scheduled_observed_notice_is_not_past_effective_stop(self):
        n = notice(when=T + timedelta(days=2),
                   first_seen=T - timedelta(minutes=1))
        r = plan(packet(revocation=n))
        self.assertEqual(r.action, SyntheticRightsAction.PAPERWORK_ONLY)
        self.assertEqual(r.observed_revocation_first_seen_utc, n.first_seen_by_us_utc)
        self.assertEqual(r.observed_revocation_effective_utc, n.effective_utc)

    def test_denial_does_not_allow_reuse(self):
        p = packet()
        rights = list(p.rights)
        rights[1] = replace(rights[1], decision=RightDecision.DENY)
        r = plan(replace(p, rights=tuple(rights)))
        self.assertEqual(r.action, SyntheticRightsAction.BLOCK_UNVERIFIED)
        self.assertEqual(r.invalidated_layers, LAYERS)

    def test_invalidation_scope_is_not_every_pair_by_default(self):
        r = plan(packet(account=account(expires_utc=T)), keys=(A,))
        self.assertEqual(r.partition_fingerprints, (A,))

    def test_duplicate_bad_or_empty_scope_rejected(self):
        for keys in ((), (A, A), ("EURUSD",), (A, "invalid"), (A,) * 201):
            with self.subTest(keys=keys[:2]), self.assertRaises((ValueError, TypeError)):
                plan(keys=keys)

    def test_non_utc_asof_rejected(self):
        with self.assertRaises(ValueError):
            plan(now=T.replace(tzinfo=None))

    def test_invalid_retention_rejected_upstream(self):
        with self.assertRaises(ValueError):
            plan_synthetic_rights_cache_transition(
                packet(), T, (A,), requested_cache_retention_days=0
            )


class SyntheticAtomicRecoveryTests(unittest.TestCase):
    def test_stable_committed_marker_recovers_stable_synthetic_only(self):
        stable, stage = generations()
        r = evaluate_synthetic_atomic_recovery(stable, None, stable.manifest_sha256, plan())
        self.assertEqual(r.state, SyntheticRecoveryState.STABLE_GENERATION)
        self.assertEqual(r.selected_manifest, stable)
        self.assertFalse(r.may_restore_real_data)
        self.assertFalse(r.may_write_real_data)

    def test_crash_after_stage_before_commit_keeps_stable(self):
        stable, stage = generations()
        r = evaluate_synthetic_atomic_recovery(stable, stage, stable.manifest_sha256, plan())
        self.assertEqual(r.selected_manifest, stable)
        self.assertIn("ORPHAN_STAGE_NOT_PROMOTED", r.reasons)

    def test_crash_after_committed_marker_accepts_verified_stage(self):
        stable, stage = generations()
        r = evaluate_synthetic_atomic_recovery(stable, stage, stage.manifest_sha256, plan())
        self.assertEqual(r.state, SyntheticRecoveryState.COMMITTED_NEW_GENERATION)
        self.assertEqual(r.selected_manifest, stage)

    def test_missing_torn_and_unknown_pointers_fail_closed(self):
        stable, stage = generations()
        for pointer in (None, "", "ab", "c" * 64):
            with self.subTest(pointer=pointer):
                r = evaluate_synthetic_atomic_recovery(stable, stage, pointer, plan())
                self.assertEqual(r.state, SyntheticRecoveryState.FAIL_CLOSED)
                self.assertIsNone(r.selected_manifest)

    def test_corrupted_new_generation_cannot_commit(self):
        stable, stage = generations()
        corrupt = replace(stage, cache_fingerprint="attacker-change")
        r = evaluate_synthetic_atomic_recovery(stable, corrupt,
                                               corrupt.manifest_sha256, plan())
        self.assertEqual(r.state, SyntheticRecoveryState.FAIL_CLOSED)
        self.assertIn("STAGED_MANIFEST_INVALID", r.reasons[0])

    def test_corrupt_orphan_stage_not_promoted(self):
        stable, stage = generations()
        bad = replace(stage, cache_fingerprint="uncommitted-corrupt")
        r = evaluate_synthetic_atomic_recovery(stable, bad, stable.manifest_sha256, plan())
        self.assertEqual(r.state, SyntheticRecoveryState.STABLE_GENERATION)

    def test_corrupt_stable_manifest_blocks_even_when_new_pointer_present(self):
        stable, stage = generations()
        bad = replace(stable, cache_fingerprint="attack")
        r = evaluate_synthetic_atomic_recovery(bad, stage, stage.manifest_sha256, plan())
        self.assertEqual(r.state, SyntheticRecoveryState.FAIL_CLOSED)

    def test_parent_mismatch_staged_new_marker_fails(self):
        stable, stage = generations()
        bad = replace(stage, previous_manifest_sha256="d" * 64)
        r = evaluate_synthetic_atomic_recovery(stable, bad, bad.manifest_sha256, plan())
        self.assertEqual(r.state, SyntheticRecoveryState.FAIL_CLOSED)

    def test_generation_floor_claim_detects_older_pointer(self):
        stable, stage = generations()
        r = evaluate_synthetic_atomic_recovery(
            stable, stage, stable.manifest_sha256, plan(),
            minimum_expected_generation_claim=2,
        )
        self.assertEqual(r.state, SyntheticRecoveryState.FAIL_CLOSED)
        self.assertIn("GENERATION_BELOW_CLAIMED_FLOOR", r.reasons)
        self.assertFalse(r.may_restore_real_data)

    def test_invalid_floor_rejected(self):
        stable, stage = generations()
        for floor in (0, -1, True):
            with self.subTest(floor=floor), self.assertRaises(ValueError):
                evaluate_synthetic_atomic_recovery(
                    stable, stage, stable.manifest_sha256, plan(),
                    minimum_expected_generation_claim=floor,
                )

    def test_rights_expiry_freezes_recovery_even_with_valid_committed_marker(self):
        stable, stage = generations()
        expired = plan(packet(account=account(expires_utc=T)))
        r = evaluate_synthetic_atomic_recovery(
            stable, stage, stage.manifest_sha256, expired
        )
        self.assertEqual(r.state, SyntheticRecoveryState.FAIL_CLOSED)
        self.assertIn("RIGHTS_REVIEW_BLOCKS_SYNTHETIC_REUSE", r.reasons)

    def test_denied_rights_freeze_recovery(self):
        stable, _ = generations()
        p = packet()
        rights = list(p.rights)
        rights[0] = replace(rights[0], decision=RightDecision.DENY)
        r = evaluate_synthetic_atomic_recovery(
            stable, None, stable.manifest_sha256,
            plan(replace(p, rights=tuple(rights))),
        )
        self.assertEqual(r.state, SyntheticRecoveryState.FAIL_CLOSED)

    def test_generation_two_requires_parent_or_fails_closed(self):
        stable, second = generations()
        unanchored = evaluate_synthetic_atomic_recovery(
            second, None, second.manifest_sha256, plan()
        )
        self.assertEqual(unanchored.state, SyntheticRecoveryState.FAIL_CLOSED)
        anchored = evaluate_synthetic_atomic_recovery(
            second, None, second.manifest_sha256, plan(), stable_parent=stable
        )
        self.assertEqual(anchored.state, SyntheticRecoveryState.STABLE_GENERATION)

    def test_wrong_parent_anchor_fails(self):
        stable, second = generations()
        bad = replace(stable, cache_fingerprint="changed")
        r = evaluate_synthetic_atomic_recovery(
            second, None, second.manifest_sha256, plan(), stable_parent=bad
        )
        # Parent hash chain link alone is not sufficient: verify parent
        # checksum independently before accepting the child.
        self.assertEqual(r.state, SyntheticRecoveryState.FAIL_CLOSED)
        self.assertIn("STABLE_MANIFEST_INVALID", r.reasons[0])
        self.assertFalse(r.may_restore_real_data)

    def test_no_file_io_methods_claimed(self):
        stable, _ = generations()
        result = evaluate_synthetic_atomic_recovery(
            stable, None, stable.manifest_sha256, plan()
        )
        self.assertFalse(hasattr(result, "write"))
        self.assertFalse(hasattr(result, "restore"))
        self.assertFalse(hasattr(result, "purge"))


if __name__ == "__main__":
    unittest.main()
