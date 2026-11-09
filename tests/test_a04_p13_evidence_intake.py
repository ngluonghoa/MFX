"""P0.13 negative evidence-intake assertions; never authenticate vendor."""
from __future__ import annotations

from copy import deepcopy
import unittest

from tools.a04_p13_evidence_intake import (
    BASE, SCENARIOS, RIGHTS, CAPABILITIES, AUTHORITY_FLAGS,
    evaluate_attestation, scenario_payload, expected_report, read_baseline,
    verify_baseline,
)


class P13EvidenceAttestationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = expected_report()

    def rejects(self, altered: dict[str, object]) -> None:
        with self.assertRaisesRegex(ValueError, "P013_PINNED_ATTESTATION_OR_RIGHTS_TAMPERED"):
            verify_baseline(altered)

    def test_pinned_synthetic_case_matrix(self) -> None:
        result = verify_baseline(read_baseline())
        self.assertEqual(result["cases"], 46)
        self.assertFalse(result["external_evidence_received"])

    def test_structural_validity_is_not_vendor_authority(self) -> None:
        self.assertEqual(evaluate_attestation(dict(BASE)), "EXTERNAL_VENDOR_EVIDENCE_REQUIRED")

    def test_every_case_matches_exact_deny_reason(self) -> None:
        for c in SCENARIOS:
            with self.subTest(id=c["id"]):
                self.assertEqual(evaluate_attestation(scenario_payload(c)), c["expected_reason"])

    def test_every_receipt_forbids_access_cache_and_trade(self) -> None:
        for r in self.report["results"]:
            self.assertFalse(r["external_authority"])
            self.assertFalse(r["may_read_vendor"])
            self.assertFalse(r["may_write_drive_cache"])
            self.assertFalse(r["may_trade"])

    def test_rights_dimensions_are_explicit(self) -> None:
        self.assertEqual(len(RIGHTS), 7)
        for k in RIGHTS:
            self.assertEqual(BASE[k], "UNVERIFIED")
            self.assertEqual(evaluate_attestation(dict(BASE, **{k: "DENIED"})), "EXPLICIT_RIGHTS_DENIED")
            self.assertEqual(evaluate_attestation(dict(BASE, **{k: "CLAIMED_VERIFIED"})), "SELF_ATTESTED_RIGHTS_FORBIDDEN")

    def test_provider_capabilities_cannot_be_self_attested(self) -> None:
        self.assertEqual(len(CAPABILITIES), 8)
        for k in CAPABILITIES:
            self.assertEqual(evaluate_attestation(dict(BASE, **{k: "CLAIMED_VERIFIED"})),
                             "SELF_ATTESTED_CAPABILITY_FORBIDDEN")

    def test_time_effective_and_asof_checks(self) -> None:
        for key, val, expected in (
            ("license_expires_utc", "2026-11-09T08:00:00Z", "LICENSE_TERMS_NOT_EFFECTIVE_AT_REVIEW"),
            ("license_effective_utc", "2026-11-10T00:00:00Z", "LICENSE_TERMS_NOT_EFFECTIVE_AT_REVIEW"),
            ("evidence_first_known_utc", "2026-11-09T09:00:01Z", "FUTURE_KNOWN_EVIDENCE"),
            ("evidence_first_known_utc", "2026-11-09T16:00:00+07:00", "INVALID_ATTESTATION_UTC_TIMESTAMP"),
        ):
            with self.subTest(key=key, val=val):
                self.assertEqual(evaluate_attestation(dict(BASE, **{key: val})), expected)

    def test_secrets_or_real_vendor_identifiers_are_disallowed(self) -> None:
        for key, val in (("provider_id", "TWELVE_DATA"), ("account_scope", "LIVE_ACCOUNT"),
                         ("evidence_ref", "https://example.com/private")):
            with self.subTest(key=key):
                self.assertNotEqual(evaluate_attestation(dict(BASE, **{key: val})),
                                    "EXTERNAL_VENDOR_EVIDENCE_REQUIRED")

    def test_provenance_signature_cannot_self_validate(self) -> None:
        self.assertEqual(evaluate_attestation(dict(BASE, vendor_signature="CLAIMED_VERIFIED")),
                         "VENDOR_SIGNATURE_NOT_VERIFIED")
        self.assertEqual(evaluate_attestation(dict(BASE, vendor_terms_digest="a"*64)),
                         "EVIDENCE_DIGEST_UNTRUSTED")

    def test_schema_missing_or_unapproved_fields_rejected(self) -> None:
        x = dict(BASE)
        del x["rights_cloud_storage"]
        self.assertEqual(evaluate_attestation(x), "ATTESTATION_SCHEMA_FIELDS_INVALID")
        x = dict(BASE)
        x["new_live_permission"] = True
        self.assertEqual(evaluate_attestation(x), "ATTESTATION_SCHEMA_FIELDS_INVALID")

    def test_authority_denied_by_default(self) -> None:
        self.assertEqual(len(AUTHORITY_FLAGS), 14)
        for key in AUTHORITY_FLAGS:
            self.assertIs(self.report["authority_flags"][key], False)

    def test_forged_rights_or_live_grant_rejected(self) -> None:
        for key in AUTHORITY_FLAGS:
            forged = deepcopy(self.report)
            forged["authority_flags"][key] = True
            with self.subTest(key=key):
                self.rejects(forged)

    def test_altered_reference_record_or_denial_code_rejected(self) -> None:
        for key, value in (
            ("record_kind", "PROVIDER_ATTESTED"),
            ("rights_history", "CLAIMED_VERIFIED"),
            ("external_document_verified", True),
        ):
            forged = deepcopy(self.report)
            forged["base_attestation"][key] = value
            with self.subTest(key=key):
                self.rejects(forged)
        forged = deepcopy(self.report)
        forged["results"][0]["reason"] = "APPROVED"
        self.rejects(forged)

    def test_source_anchor_and_missing_external_evidence_cannot_be_dropped(self) -> None:
        forged = deepcopy(self.report)
        forged["p12_synthetic_gate_blob_sha"] = "0"*40
        self.rejects(forged)
        forged = deepcopy(self.report)
        forged["missing_external_evidence"].pop()
        self.rejects(forged)

    def test_no_broker_authority_even_if_self_claimed(self) -> None:
        for key, outcome in (
            ("runtime_enabled", "FORGED_RUNTIME_AUTHORIZATION"),
            ("broker_trades_enabled", "FORGED_BROKER_TRADING_AUTHORIZATION"),
            ("live_cache_approved", "FORGED_LIVE_CACHE_AUTHORIZATION"),
            ("source_access_enabled", "FORGED_SOURCE_ACCESS"),
        ):
            with self.subTest(key=key):
                self.assertEqual(evaluate_attestation(dict(BASE, **{key: True})), outcome)
