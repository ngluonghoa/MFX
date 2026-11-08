"""Drive v3 synthetic raw binary protocol; all HTTP handled by a fake transport."""
from dataclasses import replace
from hashlib import md5, sha256
from json import dumps, loads
from urllib.parse import parse_qs, urlsplit
import unittest

from forex_trading.google_drive_wire_contract import (
    DriveWireRequest, DriveWireResponse, SYNTHETIC_MAGIC,
    SyntheticGoogleDriveBlobPort,
)

FOLDER = "SYNTHETIC_FOLDER_ID_0001"


class FakeDriveWire:
    """Tiny fake server with deliberately no sockets, auth, or real Google IO."""
    def __init__(self):
        self.data = {}
        self.requests = []
        self.next_id = 0
        self.force_list_status = None
        self.force_upload_status = None
        self.force_download_status = None
        self.force_paginated_list = False
        self.force_duplicate_list = False
        self.force_bad_upload_checksum = False
        self.force_bad_upload_json = False

    def _meta(self, file_id):
        name, parent, payload = self.data[file_id]
        return {
            "id": file_id, "name": name,
            "mimeType": "application/octet-stream",
            "parents": [parent],
            "size": str(len(payload)),
            "md5Checksum": md5(payload).hexdigest(),
        }

    def __call__(self, request):
        if not isinstance(request, DriveWireRequest):
            raise TypeError("Only typed DriveWireRequest")
        self.requests.append(request)
        parsed = urlsplit(request.url)
        args = parse_qs(parsed.query)
        if request.method == "GET" and parsed.path == "/drive/v3/files":
            if self.force_list_status:
                return DriveWireResponse(self.force_list_status, b"{}")
            assert args["supportsAllDrives"] == ["true"]
            assert args["pageSize"] == ["100"]
            query = args["q"][0]
            target = query.split("name = '", 1)[1].split("'", 1)[0]
            filtered = [self._meta(fid) for fid in self.data
                        if self.data[fid][0] == target]
            if self.force_duplicate_list and filtered:
                filtered.append(dict(filtered[0]))
            reply = {"files": filtered}
            if self.force_paginated_list:
                reply["nextPageToken"] = "SECRET_NEXT_PAGE"
            return DriveWireResponse(200, dumps(reply).encode("utf-8"))

        if request.method == "POST" and parsed.path == "/upload/drive/v3/files":
            if self.force_upload_status:
                return DriveWireResponse(self.force_upload_status, b"{}")
            assert args["uploadType"] == ["multipart"]
            assert args["supportsAllDrives"] == ["true"]
            assert "Authorization" not in dict(request.headers)
            marker = b"Content-Type: application/octet-stream\r\n\r\n"
            assert marker in request.body
            payload = request.body.split(marker, 1)[1].rsplit(b"\r\n--", 1)[0]
            meta = loads(request.body.split(b"\r\n\r\n", 1)[1].split(b"\r\n--", 1)[0])
            assert meta["mimeType"] == "application/octet-stream"
            assert meta["parents"] == [FOLDER]
            self.next_id += 1
            file_id = "FAKEFILE%04d" % self.next_id
            self.data[file_id] = (meta["name"], meta["parents"][0], payload)
            if self.force_bad_upload_json:
                return DriveWireResponse(201, b"{bad json")
            result = self._meta(file_id)
            if self.force_bad_upload_checksum:
                result["md5Checksum"] = "0" * 32
            return DriveWireResponse(201, dumps(result).encode())

        if request.method == "GET" and parsed.path.startswith("/drive/v3/files/"):
            file_id = parsed.path.rsplit("/", 1)[1]
            if file_id not in self.data:
                return DriveWireResponse(404, b"{}")
            if args.get("alt") == ["media"]:
                if self.force_download_status:
                    return DriveWireResponse(self.force_download_status, b"")
                return DriveWireResponse(200, self.data[file_id][2])
            return DriveWireResponse(200, dumps(self._meta(file_id)).encode())
        raise AssertionError("UNRECOGNIZED_FAKE_DRIVE_HTTP_REQUEST:" + request.url)


def sample(pair):
    return SYNTHETIC_MAGIC + ("CLOSED SYNTHETIC DATA FOR " + pair).encode()


def partition(pair):
    return sha256(pair.encode()).hexdigest()


class SyntheticGoogleDriveWireTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDriveWire()
        self.port = SyntheticGoogleDriveBlobPort(FOLDER, self.fake)

    def save(self, pair):
        return self.port.store_synthetic_fixture(partition(pair), sample(pair))

    def test_actual_shape_multipart_upload_metadata_media_readback(self):
        r = self.save("TESTPAIR00")
        self.assertTrue(r.simulated_created)
        self.assertEqual(r.verified_size_bytes, len(sample("TESTPAIR00")))
        self.assertEqual(r.content_sha256, sha256(sample("TESTPAIR00")).hexdigest())
        self.assertEqual(r.actual_google_drive_calls, 0)
        self.assertFalse(r.may_store_real_data)
        self.assertEqual(self.fake.next_id, 1)
        self.assertEqual([x.method for x in self.fake.requests],
                         ["GET", "POST", "GET", "GET"])
        self.assertEqual(urlsplit(self.fake.requests[1].url).hostname,
                         "www.googleapis.com")
        self.assertIn("uploadType=multipart", self.fake.requests[1].url)
        self.assertIn("alt=media", self.fake.requests[-1].url)

    def test_exact_content_address_returns_reuse_without_post(self):
        a = self.save("TESTPAIR03")
        b = self.save("TESTPAIR03")
        self.assertTrue(a.simulated_created)
        self.assertFalse(b.simulated_created)
        self.assertEqual(a.file_id, b.file_id)
        self.assertEqual(self.fake.next_id, 1)
        self.assertEqual(len([r for r in self.fake.requests if r.method == "POST"]), 1)

    def test_acceptance_5_20_1_20_never_reuploads_unchanged_chunks(self):
        catalog = ["TESTPAIR%02d" % i for i in range(20)]
        first = [self.save(p) for p in catalog[:5]]
        self.assertEqual(sum(r.simulated_created for r in first), 5)
        second = [self.save(p) for p in catalog]
        self.assertEqual(sum(r.simulated_created for r in second), 15)
        one = self.save(catalog[2])
        self.assertFalse(one.simulated_created)
        final = [self.save(p) for p in catalog]
        self.assertEqual(sum(r.simulated_created for r in final), 0)
        self.assertEqual(self.fake.next_id, 20)
        self.assertEqual(len([r for r in self.fake.requests if r.method == "POST"]), 20)
        self.assertEqual(first[0].file_id, second[0].file_id)
        self.assertEqual(second[2].file_id, one.file_id)
        self.assertEqual([x.file_id for x in second], [x.file_id for x in final])

    def test_different_revision_same_partition_creates_another_immutable_object(self):
        a = self.save("TESTPAIR04")
        newer = sample("TESTPAIR04") + b" REVISION 2"
        b = self.port.store_synthetic_fixture(partition("TESTPAIR04"), newer)
        self.assertNotEqual(a.file_id, b.file_id)
        self.assertNotEqual(a.content_sha256, b.content_sha256)
        self.assertEqual(self.fake.next_id, 2)
        self.assertEqual(self.fake.data[a.file_id][2], sample("TESTPAIR04"))

    def test_broken_download_fails_closed_even_if_metadata_md5_matches(self):
        a = self.save("TESTPAIR01")
        name, parent, _ = self.fake.data[a.file_id]
        self.fake.data[a.file_id] = (name, parent, sample("TESTPAIR01") + b"x")
        with self.assertRaisesRegex(ValueError, "METADATA_MISMATCH"):
            self.save("TESTPAIR01")

    def test_corrupt_content_same_size_fails_md5(self):
        a = self.save("TESTPAIR01")
        name, parent, old = self.fake.data[a.file_id]
        self.fake.data[a.file_id] = (name, parent, old[:-1] + b"X")
        with self.assertRaisesRegex(ValueError, "METADATA_MISMATCH"):
            self.save("TESTPAIR01")

    def test_corrupt_media_after_metadata_get_is_detected(self):
        a = self.save("TESTPAIR01")
        original = self.fake
        def tampering(req):
            resp = original(req)
            if "alt=media" in req.url:
                return DriveWireResponse(200, resp.body[:-1] + b"X")
            return resp
        client = SyntheticGoogleDriveBlobPort(FOLDER, tampering)
        with self.assertRaisesRegex(ValueError, "READBACK_CONTENT_CORRUPT"):
            client.store_synthetic_fixture(partition("TESTPAIR01"), sample("TESTPAIR01"))
        self.assertEqual(a.file_id, list(self.fake.data)[0])

    def test_pagination_fails_closed(self):
        self.fake.force_paginated_list = True
        with self.assertRaisesRegex(ValueError, "LIST_INCOMPLETE_OR_PAGINATED"):
            self.save("TESTPAIR01")
        self.assertEqual(self.fake.next_id, 0)

    def test_duplicate_name_fails_closed(self):
        self.save("TESTPAIR01")
        self.fake.force_duplicate_list = True
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CONTENT_ADDRESS"):
            self.save("TESTPAIR01")

    def test_429_on_list_never_retries_unsafely(self):
        self.fake.force_list_status = 429
        with self.assertRaisesRegex(ValueError, "DRIVE_WIRE_ERROR"):
            self.save("TESTPAIR01")
        self.assertEqual(len(self.fake.requests), 1)

    def test_503_on_create_is_ambiguous_no_blind_retry(self):
        self.fake.force_upload_status = 503
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS_WRITE"):
            self.save("TESTPAIR01")
        self.assertEqual(len([x for x in self.fake.requests if x.method == "POST"]), 1)

    def test_upload_server_bad_checksum_rejected(self):
        self.fake.force_bad_upload_checksum = True
        with self.assertRaisesRegex(ValueError, "METADATA_MISMATCH"):
            self.save("TESTPAIR01")

    def test_upload_server_bad_json_rejected(self):
        self.fake.force_bad_upload_json = True
        with self.assertRaisesRegex(ValueError, "MALFORMED_DRIVE_JSON"):
            self.save("TESTPAIR01")

    def test_read_503_fails_closed(self):
        self.fake.force_download_status = 503
        with self.assertRaisesRegex(ValueError, "DRIVE_DOWNLOAD_FAILED"):
            self.save("TESTPAIR01")

    def test_nonfixture_payload_rejected_before_any_request(self):
        with self.assertRaisesRegex(ValueError, "ONLY_BOUNDED_SYNTHETIC"):
            self.port.store_synthetic_fixture(partition("TESTPAIR00"), b"USDJPY price=150")
        self.assertEqual(self.fake.requests, [])

    def test_marker_only_rejected(self):
        with self.assertRaisesRegex(ValueError, "ONLY_BOUNDED_SYNTHETIC"):
            self.port.store_synthetic_fixture(partition("TESTPAIR00"), SYNTHETIC_MAGIC)

    def test_oversized_fixture_rejected(self):
        with self.assertRaisesRegex(ValueError, "ONLY_BOUNDED_SYNTHETIC"):
            self.port.store_synthetic_fixture(
                partition("TESTPAIR00"), SYNTHETIC_MAGIC + b"a" * (8 * 1024 * 1024)
            )
        self.assertEqual(self.fake.requests, [])

    def test_invalid_partition_and_folder_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_PARTITION"):
            self.port.store_synthetic_fixture("EURUSD", sample("TESTPAIR00"))
        with self.assertRaisesRegex(ValueError, "INVALID_FOLDER"):
            SyntheticGoogleDriveBlobPort("https://drive.google.com", self.fake)

    def test_response_wrong_type_rejected(self):
        port = SyntheticGoogleDriveBlobPort(FOLDER, lambda req: {"status": 200})
        with self.assertRaisesRegex(TypeError, "TYPED_DRIVE_WIRE_RESPONSE"):
            port.store_synthetic_fixture(partition("TESTPAIR00"), sample("TESTPAIR00"))


if __name__ == "__main__":
    unittest.main()
