"""M2/P0.9 Google Drive v3 raw-blob wire contract, SYNTHETIC ONLY.

Builds real-shaped Google Drive list, multipart-upload, metadata and media
requests for an INJECTED transport. No OAuth, sockets, credential storage,
network implementation, Google Drive invocation, or live Forex data access.
The only admitted payload is an explicitly marked TEST FIXTURE; a marker is
not a security proof against deliberately mislabeled external data.

No multi-object atomic transaction, distributed compare-and-swap, verified
vendor rights, envelope encryption or cross-run rollback witness is implied.
"""
from dataclasses import dataclass
from hashlib import md5, sha256
from json import dumps, loads
from re import fullmatch
from typing import Callable
from urllib.parse import quote, urlencode

SYNTHETIC_MAGIC = b"FX_SYNTHETIC_CACHE_V1\n"
_GOOGLE_API = "https://www.googleapis.com"
_BLOB_MIME = "application/octet-stream"
_FIELDS = "id,name,mimeType,md5Checksum,size,parents"
_MAX_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class DriveWireRequest:
    method: str
    url: str
    headers: tuple[tuple[str, str], ...]
    body: bytes = b""


@dataclass(frozen=True, slots=True)
class DriveWireResponse:
    status: int
    body: bytes


@dataclass(frozen=True, slots=True)
class SyntheticBlobReceipt:
    file_id: str
    partition_fingerprint: str
    content_sha256: str
    verified_size_bytes: int
    # Created/reused in the injected transport, NOT an observed live API.
    simulated_created: bool
    actual_google_drive_calls: int = 0
    may_store_real_data: bool = False


def _sha256_hex(value: str, label: str) -> None:
    if not isinstance(value, str) or not fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("INVALID_" + label)


def _opaque_id(value: str, label: str) -> None:
    if not isinstance(value, str) or not fullmatch(r"[A-Za-z0-9_-]{4,128}", value):
        raise ValueError("INVALID_" + label)


def _json_bytes(value: object) -> bytes:
    return dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _response_json(response: DriveWireResponse, statuses: tuple[int, ...]) -> dict:
    if not isinstance(response, DriveWireResponse):
        raise TypeError("TYPED_DRIVE_WIRE_RESPONSE_REQUIRED")
    if response.status not in statuses:
        # No blind POST retries for 429/5xx: an upload may have committed.
        raise ValueError("DRIVE_WIRE_ERROR_OR_AMBIGUOUS_WRITE:" + str(response.status))
    try:
        payload = loads(response.body.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("MALFORMED_DRIVE_JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("DRIVE_JSON_NOT_OBJECT")
    return payload


class SyntheticGoogleDriveBlobPort:
    """Small, fail-closed real-shaped Drive v3 blob operations via fake port.

    Calls are issued only to an injected callback. A real adapter needs a
    separately approved identity, scopes, client-side encryption, lease and
    retention/right checks; this class must NOT be used for real FX ingestion.
    """

    def __init__(
        self, folder_id: str,
        transport: Callable[[DriveWireRequest], DriveWireResponse],
    ):
        _opaque_id(folder_id, "FOLDER_ID")
        if not callable(transport):
            raise TypeError("INJECTED_TRANSPORT_REQUIRED")
        self.folder_id = folder_id
        self._transport = transport

    def _call(self, request: DriveWireRequest) -> DriveWireResponse:
        response = self._transport(request)
        if not isinstance(response, DriveWireResponse):
            raise TypeError("TYPED_DRIVE_WIRE_RESPONSE_REQUIRED")
        return response

    def _name(self, partition_fingerprint: str, digest: str) -> str:
        return "fxsynthetic-v1-" + partition_fingerprint + "-" + digest + ".blob"

    def _list_one(self, name: str) -> dict | None:
        # Drive filenames are not unique. Require exactly one or fail closed.
        expression = ("'" + self.folder_id + "' in parents and name = '"
                      + name + "' and trashed = false")
        q = urlencode({
            "q": expression, "fields": "nextPageToken,files(" + _FIELDS + ")",
            "pageSize": "100", "supportsAllDrives": "true",
        })
        request = DriveWireRequest(
            "GET", _GOOGLE_API + "/drive/v3/files?" + q, (),
        )
        data = _response_json(self._call(request), (200,))
        files = data.get("files")
        if not isinstance(files, list) or data.get("nextPageToken"):
            raise ValueError("DRIVE_LIST_INCOMPLETE_OR_PAGINATED")
        if len(files) > 1:
            raise ValueError("DUPLICATE_CONTENT_ADDRESS_IN_DRIVE")
        if files and not isinstance(files[0], dict):
            raise ValueError("DRIVE_FILE_METADATA_INVALID")
        return files[0] if files else None

    def _verify_metadata(
        self, obj: dict, *, expected_name: str,
        expected_md5: str, expected_size: int,
    ) -> str:
        if not isinstance(obj, dict):
            raise ValueError("DRIVE_FILE_METADATA_INVALID")
        file_id = obj.get("id")
        _opaque_id(file_id, "FILE_ID")
        if (obj.get("name") != expected_name
            or obj.get("mimeType") != _BLOB_MIME
            or obj.get("md5Checksum") != expected_md5
            or obj.get("size") != str(expected_size)
            or not isinstance(obj.get("parents"), list)
            or obj["parents"] != [self.folder_id]):
            raise ValueError("DRIVE_FILE_METADATA_MISMATCH")
        return file_id

    def _readback(
        self, file_id: str, *, expected_name: str,
        expected_md5: str, expected_size: int, expected_sha: str,
    ) -> None:
        _opaque_id(file_id, "FILE_ID")
        url = _GOOGLE_API + "/drive/v3/files/" + quote(file_id, safe="")
        metadata = _response_json(self._call(DriveWireRequest(
            "GET", url + "?fields=" + quote(_FIELDS, safe=",")
            + "&supportsAllDrives=true", (),
        )), (200,))
        self._verify_metadata(
            metadata, expected_name=expected_name,
            expected_md5=expected_md5, expected_size=expected_size,
        )
        response = self._call(DriveWireRequest(
            "GET", url + "?alt=media&supportsAllDrives=true", (),
        ))
        if response.status != 200:
            raise ValueError("DRIVE_DOWNLOAD_FAILED:" + str(response.status))
        content = response.body
        if (len(content) != expected_size
            or md5(content, usedforsecurity=False).hexdigest() != expected_md5
            or sha256(content).hexdigest() != expected_sha):
            raise ValueError("DRIVE_READBACK_CONTENT_CORRUPT")

    def store_synthetic_fixture(
        self, partition_fingerprint: str, fixture_payload: bytes,
    ) -> SyntheticBlobReceipt:
        _sha256_hex(partition_fingerprint, "PARTITION_FINGERPRINT")
        if (not isinstance(fixture_payload, bytes)
            or not fixture_payload.startswith(SYNTHETIC_MAGIC)
            or len(fixture_payload) <= len(SYNTHETIC_MAGIC)
            or len(fixture_payload) > _MAX_BYTES):
            raise ValueError("ONLY_BOUNDED_SYNTHETIC_FIXTURE_BYTES_ALLOWED")
        digest = sha256(fixture_payload).hexdigest()
        check = md5(fixture_payload, usedforsecurity=False).hexdigest()
        name = self._name(partition_fingerprint, digest)
        metadata = self._list_one(name)
        created = False
        if metadata is None:
            # Real Drive v3 multipart creation; no token or HTTP client exists
            # here. Unique filename is NOT an atomic create-if-absent.
            boundary = "fxsynthetic_" + digest[:32]
            payload = _json_bytes({
                "name": name, "mimeType": _BLOB_MIME,
                "parents": [self.folder_id],
            })
            body = (
                ("--" + boundary + "\r\nContent-Type: application/json; charset=UTF-8"
                 + "\r\n\r\n").encode() + payload
                + ("\r\n--" + boundary + "\r\nContent-Type: " + _BLOB_MIME
                   + "\r\n\r\n").encode()
                + fixture_payload
                + ("\r\n--" + boundary + "--\r\n").encode()
            )
            url = (_GOOGLE_API + "/upload/drive/v3/files?"
                   + urlencode({
                       "uploadType": "multipart", "fields": _FIELDS,
                       "supportsAllDrives": "true",
                   }))
            req = DriveWireRequest(
                "POST", url,
                (("Content-Type", "multipart/related; boundary=" + boundary),),
                body,
            )
            metadata = _response_json(self._call(req), (200, 201))
            created = True
        file_id = self._verify_metadata(
            metadata, expected_name=name,
            expected_md5=check, expected_size=len(fixture_payload),
        )
        # A successful upload response or matching Drive MD5 is not enough:
        # read back the actual media and verify SHA256 before accepting.
        self._readback(
            file_id, expected_name=name, expected_md5=check,
            expected_size=len(fixture_payload), expected_sha=digest,
        )
        return SyntheticBlobReceipt(
            file_id, partition_fingerprint, digest, len(fixture_payload),
            created,
        )
