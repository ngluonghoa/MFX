"""M2/P0.10: offline verification of a real Drive CONNECTOR synthetic-only readback.

Two raw files were uploaded/downloaded through the connected Google Drive
service as an independent staging smoke test. This validator does not invoke
Google APIs, perform encryption, establish vendor entitlements, provide
independent authenticity, verify a distributed lease, or enable trading.

All metadata arguments are UNTRUSTED caller observations. A pass proves only
internal byte/hash/reference consistency, not live data freshness, rights,
storage residency, authenticated source provenance or anti-rollback safety.
"""
from dataclasses import dataclass
from hashlib import md5, sha256
from json import loads
from re import fullmatch

MAX_SMOKE_BYTES = 128 * 1024
SCHEMA = "FX_SYNTHETIC_DRIVE_SMOKE_MANIFEST_V1"
PREFIX = "FX_SYNTHETIC_CACHE_V1"


@dataclass(frozen=True, slots=True)
class ObservedDriveFile:
    """Copy of downloaded bytes and the metadata returned by Drive connector."""
    file_id: str
    folder_id: str
    file_name: str
    mime_type: str
    body: bytes


@dataclass(frozen=True, slots=True)
class SyntheticDriveSmokeReceipt:
    manifest_sha256: str
    chunk_sha256: str
    chunk_bytes: int
    fixture_symbol: str
    # A verified byte equality is NOT proof of production release readiness.
    byte_integrity_passed: bool = True
    actual_vendor_requests_by_validator: int = 0
    actual_drive_requests_by_validator: int = 0
    may_cache_real_fx: bool = False
    may_trade: bool = False
    may_claim_atomic_commit: bool = False
    may_claim_external_rollback_witness: bool = False


def _reject(message: str) -> None:
    raise ValueError(message)


def _id(value: str, label: str) -> None:
    if not isinstance(value, str) or not fullmatch(r"[A-Za-z0-9_-]{10,128}", value):
        _reject("INVALID_" + label)


def _load_json_no_duplicate_keys(payload: bytes) -> dict:
    def on_pairs(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                _reject("DUPLICATE_JSON_FIELD")
            out[key] = value
        return out
    try:
        parsed = loads(payload.decode("utf-8-sig"), object_pairs_hook=on_pairs)
    except (ValueError, UnicodeError) as exc:
        _reject("INVALID_SYNTHETIC_MANIFEST_JSON:" + str(exc))
    if not isinstance(parsed, dict):
        _reject("SYNTHETIC_MANIFEST_NOT_OBJECT")
    return parsed


def _check_file(
    file: ObservedDriveFile, expected_folder: str, label: str,
) -> None:
    if not isinstance(file, ObservedDriveFile):
        raise TypeError("TYPED_OBSERVED_DRIVE_FILE_REQUIRED")
    _id(expected_folder, "EXPECTED_FOLDER")
    _id(file.file_id, label + "_FILE_ID")
    if file.folder_id != expected_folder:
        _reject(label + "_PARENT_FOLDER_MISMATCH")
    if file.mime_type != "text/plain":
        _reject(label + "_MIME_MISMATCH")
    if not isinstance(file.body, bytes) or not 0 < len(file.body) <= MAX_SMOKE_BYTES:
        _reject(label + "_INVALID_BOUNDED_BYTES")
    if not isinstance(file.file_name, str):
        _reject(label + "_NAME_INVALID")


def validate_synthetic_drive_connector_smoke(
    chunk: ObservedDriveFile, manifest: ObservedDriveFile,
    *,
    expected_chunk_folder: str,
    expected_manifest_folder: str,
) -> SyntheticDriveSmokeReceipt:
    """Fail closed unless the manifest and chunk match their downloaded bytes.

    The function makes no network calls and never infers rights or rollback
    safety. It accepts exactly one harmless synthetic fixture, not OHLC.
    """
    if expected_chunk_folder == expected_manifest_folder:
        _reject("CHUNK_MANIFEST_FOLDERS_MUST_BE_DISTINCT")
    _check_file(chunk, expected_chunk_folder, "CHUNK")
    _check_file(manifest, expected_manifest_folder, "MANIFEST")
    if chunk.file_id == manifest.file_id:
        _reject("CHUNK_AND_MANIFEST_FILE_IDS_MUST_DIFFER")

    chunk_sha = sha256(chunk.body).hexdigest()
    manifest_sha = sha256(manifest.body).hexdigest()
    if chunk.file_name != "fxsynthetic-m2p10-smoke-" + chunk_sha[:16] + ".txt":
        _reject("CHUNK_CONTENT_ADDRESS_NAME_MISMATCH")
    if manifest.file_name != "fxsynthetic-m2p10-manifest-" + manifest_sha[:16] + ".txt":
        _reject("MANIFEST_CONTENT_ADDRESS_NAME_MISMATCH")

    # Exporting a Google Doc as text/plain produced UTF-8 BOM + CRLF, not the
    # exact UTF-8 bytes inserted into the editor. This is a smoke-only format.
    if not chunk.body.startswith(b"\xef\xbb\xbf" + PREFIX.encode("ascii") + b"\r\n"):
        _reject("UNEXPECTED_SYNTHETIC_EXPORT_ENCODING")
    try:
        lines = chunk.body.decode("utf-8-sig").split("\r\n")
    except UnicodeError as exc:
        _reject("INVALID_SYNTHETIC_FIXTURE_UTF8:" + str(exc))
    if len(lines) != 5 or lines[0] != PREFIX:
        _reject("INVALID_SYNTHETIC_FIXTURE_STRUCTURE")
    expected_lines = (
        "fixture_id=M2P10_DRIVE_IO_SMOKE_20261107",
        "instrument=TESTPAIR00",
        "no_market_data=true",
        "scope_5_to_20_to_1_to_20=true",
    )
    if tuple(lines[1:]) != expected_lines:
        _reject("SYNTHETIC_FIXTURE_CONTENT_NOT_APPROVED")

    data = _load_json_no_duplicate_keys(manifest.body)
    required = {
        "schema", "synthetic_only", "fx_market_data_present",
        "pair", "kind", "chunk_drive_file_id", "chunk_sha256",
        "chunk_md5", "chunk_size_bytes", "chapter", "no_trading",
        "untrusted_for_rollback",
    }
    if set(data) != required:
        _reject("SYNTHETIC_MANIFEST_FIELDS_UNEXPECTED")
    if (data["schema"] != SCHEMA or data["synthetic_only"] is not True
        or data["fx_market_data_present"] is not False
        or data["no_trading"] is not True
        or data["untrusted_for_rollback"] is not True
        or data["kind"] != "CONNECTOR_IO_TEST_RECEIPT"
        or data["chapter"] != "M2_P0_10"
        or data["pair"] != "TESTPAIR00"):
        _reject("NOT_APPROVED_SYNTHETIC_MANIFEST")
    if (data["chunk_drive_file_id"] != chunk.file_id
        or data["chunk_sha256"] != chunk_sha
        or data["chunk_md5"] != md5(chunk.body, usedforsecurity=False).hexdigest()
        or type(data["chunk_size_bytes"]) is not int
        or data["chunk_size_bytes"] != len(chunk.body)):
        _reject("MANIFEST_CHUNK_REFERENCE_INTEGRITY_FAILURE")
    return SyntheticDriveSmokeReceipt(
        manifest_sha, chunk_sha, len(chunk.body), data["pair"],
    )
