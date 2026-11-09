"""P0.14 genuine public-doc audit register consistency, zero account authority."""
from __future__ import annotations

from copy import deepcopy
import unittest

from tools.a04_p14_public_vendor_evidence import (
    DOC_URLS, MANDATORY_FALSE, read_register, verify_public_register,
)


class P14PublicVendorEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reference = read_register()

    def fail_closed(self, altered: dict[str, object]) -> None:
        with self.assertRaises(ValueError):
            verify_public_register(altered)

    def test_genuine_public_doc_register_has_no_account_rights(self) -> None:
        receipt = verify_public_register(self.reference)
        self.assertEqual(receipt["public_findings"], 10)
        self.assertFalse(receipt["can_write_real_drive_cache"])

    def test_exact_ten_public_findings_and_approved_domains(self) -> None:
        self.assertEqual(len(self.reference["findings"]), 10)
        self.assertEqual(len(DOC_URLS), 7)
        self.assertTrue(all(x.startswith("https://twelvedata.com/") or
                            x.startswith("https://support.twelvedata.com/")
                            for x in DOC_URLS.values()))

    def test_seven_rights_and_eight_capabilities_not_approved(self) -> None:
        rows = self.reference["requirements"]
        self.assertEqual((len(rows), len(rows[:7]), len(rows[7:])), (15, 7, 8))
        self.assertTrue(all("APPROVED" not in x["state"] and
                            "VERIFIED" not in x["state"].replace("UNVERIFIED", "")
                            for x in rows))

    def test_six_vendor_questions_require_real_written_confirmation(self) -> None:
        self.assertEqual(len(self.reference["vendor_inquiry_questions"]), 6)
        self.assertTrue(any("Google Drive" in x["question"]
                            for x in self.reference["vendor_inquiry_questions"]))

    def test_cannot_promote_eight_no_permission_flags(self) -> None:
        for key in MANDATORY_FALSE:
            fake = deepcopy(self.reference)
            fake[key] = True
            with self.subTest(key=key):
                self.fail_closed(fake)

    def test_cannot_insert_nonofficial_url(self) -> None:
        fake = deepcopy(self.reference)
        fake["official_sources"]["terms"]["url"] = "https://random.example/path"
        self.fail_closed(fake)

    def test_cannot_remove_required_vendor_capability(self) -> None:
        fake = deepcopy(self.reference)
        fake["requirements"].pop()
        self.fail_closed(fake)

    def test_cannot_set_historical_bidask_to_verified(self) -> None:
        fake = deepcopy(self.reference)
        row = next(x for x in fake["requirements"] if x["key"] == "historical_bidask")
        row["state"] = "ACCOUNT_VERIFIED"
        self.fail_closed(fake)

    def test_cannot_drop_storage_rights_proof_requirement(self) -> None:
        fake = deepcopy(self.reference)
        row = next(x for x in fake["requirements"] if x["key"] == "rights_cloud_storage")
        row["required_written_proof"] = ""
        self.fail_closed(fake)

    def test_cannot_change_p13_static_rights_baseline(self) -> None:
        fake = deepcopy(self.reference)
        fake["p13_public_git_blob_sha"] = "0" * 40
        self.fail_closed(fake)

    def test_no_public_doc_is_account_specific_license(self) -> None:
        self.assertFalse(self.reference["evidence_provided_for_mfx_account"])
        self.assertEqual(self.reference["review_status"],
                         "PUBLIC_DOCUMENTATION_RESEARCH_ONLY")
