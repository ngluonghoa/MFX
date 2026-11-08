"""M2/P0.10 deterministic receipt parity with actual synthetic Drive readback."""
from dataclasses import replace
from hashlib import sha256
from json import dumps
import unittest

from forex_trading.synthetic_drive_receipt_validation import (
    ObservedDriveFile, validate_synthetic_drive_connector_smoke,
)

CHUNK_FOLDER = "1mE7Zx29kDjyN8DYfvZn4HYx-OIoYaScw"
MANIFEST_FOLDER = "1OPBHzq5sPNV9ohqlsfi_I5e35ve1qvkD"
CHUNK_FILE_ID = "1HgjhwKJW2JzuO_OL8ODl45GdsW9bGv3h"
MANIFEST_FILE_ID = "1j7yevV6EgH7fyKj5uok5iOqrF1dGBegK"

# Exact downloaded bytes from the connected Drive synthetic smoke test.
# Exported Google Docs plaintext includes a BOM and CRLF line separators.
CHUNK_BYTES = (
    b"\xef\xbb\xbfFX_SYNTHETIC_CACHE_V1\r\n"
    b"fixture_id=M2P10_DRIVE_IO_SMOKE_20261107\r\n"
    b"instrument=TESTPAIR00\r\n"
    b"no_market_data=true\r\n"
    b"scope_5_to_20_to_1_to_20=true"
)
MANIFEST_DICT = {
    "schema": "FX_SYNTHETIC_DRIVE_SMOKE_MANIFEST_V1",
    "synthetic_only": True,
    "fx_market_data_present": False,
    "pair": "TESTPAIR00",
    "kind": "CONNECTOR_IO_TEST_RECEIPT",
    "chunk_drive_file_id": CHUNK_FILE_ID,
    "chunk_sha256": "3399fba3e2dee9557bdff2f2b00f393dffd584083c2632378ee5f5864716c81d",
    "chunk_md5": "eeef04bb1095d763864a70474f21866e",
    "chunk_size_bytes": 141,
    "chapter": "M2_P0_10",
    "no_trading": True,
    "untrusted_for_rollback": True,
}


def manifest_bytes(obj=None):
    obj = MANIFEST_DICT if obj is None else obj
    return b"\xef\xbb\xbf" + dumps(
        obj, ensure_ascii=True, separators=(",", ":")
    ).encode("ascii")


def with_address(file, prefix, body):
    return replace(
        file, body=body,
        file_name=prefix + sha256(body).hexdigest()[:16] + ".txt",
    )


def inputs():
    chunk = ObservedDriveFile(
        CHUNK_FILE_ID, CHUNK_FOLDER,
        "fxsynthetic-m2p10-smoke-" + sha256(CHUNK_BYTES).hexdigest()[:16] + ".txt",
        "text/plain", CHUNK_BYTES,
    )
    manifest = ObservedDriveFile(
        MANIFEST_FILE_ID, MANIFEST_FOLDER,
        "fxsynthetic-m2p10-manifest-"
        + sha256(manifest_bytes()).hexdigest()[:16] + ".txt",
        "text/plain", manifest_bytes(),
    )
    return chunk, manifest


def verify(chunk, manifest):
    return validate_synthetic_drive_connector_smoke(
        chunk, manifest, expected_chunk_folder=CHUNK_FOLDER,
        expected_manifest_folder=MANIFEST_FOLDER,
    )


class RealConnectorSmokeReceiptTests(unittest.TestCase):
    def test_fixture_bytes_match_real_drive_connector_readback_hashes(self):
        self.assertEqual(len(CHUNK_BYTES), 141)
        self.assertEqual(sha256(CHUNK_BYTES).hexdigest(),
                         MANIFEST_DICT["chunk_sha256"])
        self.assertEqual(len(manifest_bytes()), 439)
        self.assertEqual(
            sha256(manifest_bytes()).hexdigest(),
            "fccca2450f150bc1839ef6e266190200526e74a6d22c6365ab48d7533a9e7b9a",
        )

    def test_valid_actual_two_object_reference_passes_offline(self):
        chunk, manifest = inputs()
        verdict = verify(chunk, manifest)
        self.assertTrue(verdict.byte_integrity_passed)
        self.assertEqual(verdict.chunk_sha256, MANIFEST_DICT["chunk_sha256"])
        self.assertEqual(verdict.chunk_bytes, 141)
        self.assertEqual(verdict.fixture_symbol, "TESTPAIR00")
        self.assertEqual(verdict.actual_drive_requests_by_validator, 0)
        self.assertEqual(verdict.actual_vendor_requests_by_validator, 0)
        self.assertFalse(verdict.may_cache_real_fx)
        self.assertFalse(verdict.may_trade)
        self.assertFalse(verdict.may_claim_atomic_commit)
        self.assertFalse(verdict.may_claim_external_rollback_witness)

    def test_content_address_name_detects_changed_chunk(self):
        chunk, manifest = inputs()
        with self.assertRaisesRegex(ValueError, "CHUNK_CONTENT_ADDRESS"):
            verify(replace(chunk, body=chunk.body + b"x"), manifest)

    def test_content_address_name_detects_changed_manifest(self):
        chunk, manifest = inputs()
        with self.assertRaisesRegex(ValueError, "MANIFEST_CONTENT_ADDRESS"):
            verify(chunk, replace(manifest, body=manifest.body + b" "))

    def test_changed_chunk_payload_even_with_matching_filename_fails_closed(self):
        chunk, manifest = inputs()
        altered = with_address(
            chunk, "fxsynthetic-m2p10-smoke-", chunk.body[:-1] + b"X"
        )
        with self.assertRaisesRegex(ValueError, "SYNTHETIC_FIXTURE_CONTENT"):
            verify(altered, manifest)

    def test_wrong_chunk_parent_fails_closed(self):
        chunk, manifest = inputs()
        with self.assertRaisesRegex(ValueError, "CHUNK_PARENT_FOLDER"):
            verify(replace(chunk, folder_id=MANIFEST_FOLDER), manifest)

    def test_wrong_manifest_parent_fails_closed(self):
        chunk, manifest = inputs()
        with self.assertRaisesRegex(ValueError, "MANIFEST_PARENT_FOLDER"):
            verify(chunk, replace(manifest, folder_id=CHUNK_FOLDER))

    def test_wrong_mime_type_fails(self):
        chunk, manifest = inputs()
        with self.assertRaisesRegex(ValueError, "CHUNK_MIME_MISMATCH"):
            verify(replace(chunk, mime_type="application/json"), manifest)

    def test_wrong_chunk_file_id_in_manifest_fails(self):
        chunk, manifest = inputs()
        m = dict(MANIFEST_DICT)
        m["chunk_drive_file_id"] = "FAKE_ANOTHER_FILE_ID"
        bad = with_address(manifest, "fxsynthetic-m2p10-manifest-", manifest_bytes(m))
        with self.assertRaisesRegex(ValueError, "MANIFEST_CHUNK_REFERENCE"):
            verify(chunk, bad)

    def test_wrong_chunk_sha_in_manifest_fails(self):
        chunk, manifest = inputs()
        m = dict(MANIFEST_DICT)
        m["chunk_sha256"] = "0" * 64
        bad = with_address(manifest, "fxsynthetic-m2p10-manifest-", manifest_bytes(m))
        with self.assertRaisesRegex(ValueError, "MANIFEST_CHUNK_REFERENCE"):
            verify(chunk, bad)

    def test_wrong_md5_or_size_in_manifest_fails(self):
        chunk, manifest = inputs()
        for changed in ({"chunk_md5": "0" * 32},
                        {"chunk_size_bytes": 140},
                        {"chunk_size_bytes": True}):
            with self.subTest(changed=changed):
                m = {**MANIFEST_DICT, **changed}
                bad = with_address(
                    manifest, "fxsynthetic-m2p10-manifest-", manifest_bytes(m)
                )
                with self.assertRaisesRegex(ValueError, "MANIFEST_CHUNK_REFERENCE"):
                    verify(chunk, bad)

    def test_attempt_to_assert_real_data_rights_is_rejected(self):
        chunk, manifest = inputs()
        for changed in ({"synthetic_only": False},
                        {"fx_market_data_present": True},
                        {"no_trading": False},
                        {"untrusted_for_rollback": False},
                        {"pair": "EURUSD"}):
            with self.subTest(changed=changed):
                m = {**MANIFEST_DICT, **changed}
                bad = with_address(
                    manifest, "fxsynthetic-m2p10-manifest-", manifest_bytes(m)
                )
                with self.assertRaisesRegex(ValueError, "NOT_APPROVED_SYNTHETIC"):
                    verify(chunk, bad)

    def test_extra_field_fails_closed(self):
        chunk, manifest = inputs()
        m = {**MANIFEST_DICT, "unknown_provider_claim": "AUTHORIZED"}
        bad = with_address(manifest, "fxsynthetic-m2p10-manifest-", manifest_bytes(m))
        with self.assertRaisesRegex(ValueError, "FIELDS_UNEXPECTED"):
            verify(chunk, bad)

    def test_duplicate_json_key_fails(self):
        chunk, manifest = inputs()
        malicious = manifest_bytes()[:-1] + b',\"pair\":\"EURUSD\"}'
        bad = with_address(manifest, "fxsynthetic-m2p10-manifest-", malicious)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_FIELD"):
            verify(chunk, bad)

    def test_missing_bom_fails_closed(self):
        chunk, manifest = inputs()
        bad = with_address(
            chunk, "fxsynthetic-m2p10-smoke-", chunk.body[3:],
        )
        with self.assertRaisesRegex(ValueError, "UNEXPECTED_SYNTHETIC_EXPORT_ENCODING"):
            verify(bad, manifest)

    def test_wrong_file_id_or_same_id_fails_closed(self):
        chunk, manifest = inputs()
        with self.assertRaisesRegex(ValueError, "INVALID_CHUNK_FILE_ID"):
            verify(replace(chunk, file_id="???"), manifest)
        with self.assertRaisesRegex(ValueError, "FILE_IDS_MUST_DIFFER"):
            verify(chunk, replace(manifest, file_id=chunk.file_id))

    def test_manifest_and_chunk_folders_must_be_distinct(self):
        chunk, manifest = inputs()
        with self.assertRaisesRegex(ValueError, "FOLDERS_MUST_BE_DISTINCT"):
            validate_synthetic_drive_connector_smoke(
                chunk, manifest, expected_chunk_folder=CHUNK_FOLDER,
                expected_manifest_folder=CHUNK_FOLDER,
            )

    def test_unexpected_fixture_lines_and_oversize_rejected(self):
        chunk, manifest = inputs()
        new = chunk.body.replace(b"TESTPAIR00", b"EURUSD")
        with self.assertRaisesRegex(ValueError, "SYNTHETIC_FIXTURE_CONTENT"):
            verify(with_address(chunk, "fxsynthetic-m2p10-smoke-", new), manifest)
        large = b"\xef\xbb\xbf" + b"X" * (128 * 1024)
        with self.assertRaisesRegex(ValueError, "CHUNK_INVALID_BOUNDED_BYTES"):
            verify(with_address(chunk, "fxsynthetic-m2p10-smoke-", large), manifest)


if __name__ == "__main__":
    unittest.main()
