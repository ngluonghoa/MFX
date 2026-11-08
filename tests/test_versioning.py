import unittest
from dataclasses import replace
from forex_trading.versioning import ExecutionProfile, assess_rollback


def profile():
    return ExecutionProfile(
        "synthetic-code", "stdlib", "rules-design-18", "uncalibrated",
        "provider-unqualified", "source-snapshot-unknown",
        "calendar-unqualified", "BID-ASK-required", "simulator-not-implemented",
        "risk-unverified", "schema-v0", "report-v0",
    )


class VersionTests(unittest.TestCase):
    def test_deterministic_profile_fingerprint(self):
        self.assertEqual(profile().fingerprint, profile().fingerprint)
        self.assertEqual(len(profile().fingerprint), 64)

    def test_data_revision_changes_identity(self):
        p = profile()
        self.assertNotEqual(p.fingerprint,
                            replace(p, data_revision_ref="other").fingerprint)

    def test_cost_model_changes_identity(self):
        p = profile()
        self.assertNotEqual(p.fingerprint,
                            replace(p, cost_fill_ref="cost-v2").fingerprint)

    def test_empty_component_fails(self):
        with self.assertRaises(ValueError):
            replace(profile(), provider_ref="")

    def test_same_profile_synthetic_rollback_preview(self):
        a = profile()
        candidate = replace(a, rule_ref="candidate-2")
        self.assertNotEqual(a.fingerprint, candidate.fingerprint)
        check = assess_rollback(candidate, a)
        self.assertTrue(check.compatible_in_read_only_replay)
        self.assertTrue(check.requires_external_review)

    def test_schema_migration_not_silent_rollback(self):
        a = profile()
        b = replace(a, persistence_schema_ref="schema-v1")
        check = assess_rollback(b, a)
        self.assertFalse(check.compatible_in_read_only_replay)
        self.assertIn("PERSISTENCE_SCHEMA_MISMATCH", check.reasons)

    def test_source_basis_mismatch_blocks_preview(self):
        a = profile()
        b = replace(a, bid_ask_basis_ref="MID")
        check = assess_rollback(b, a)
        self.assertFalse(check.compatible_in_read_only_replay)

    def test_revised_data_needs_reconciliation(self):
        a = profile()
        b = replace(a, data_revision_ref="source-r2")
        check = assess_rollback(b, a)
        self.assertFalse(check.compatible_in_read_only_replay)
