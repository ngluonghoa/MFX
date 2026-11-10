"""Offline authorization and Drive folder bootstrap contract for Gmail OAuth.

No credentials and no Google/Twelve Data network calls are used in CI.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.run_a04_p45_cloud_twelve_data_cache import (
    _drive_auth_info, _require_oauth_cache_folders, _settings,
)
from tools.run_mfx_oauth_drive_bootstrap import find_or_create_folder


TRIO = {
    "MFX_GDRIVE_OAUTH_CLIENT_ID": "test.apps.googleusercontent.com",
    "MFX_GDRIVE_OAUTH_CLIENT_SECRET": "not-a-real-secret",
    "MFX_GDRIVE_OAUTH_REFRESH_TOKEN": "synthetic-refresh",
}
FOLDERS = {
    "MFX_CACHE_CHUNK_FOLDER_ID": "synthetic_chunk_12345",
    "MFX_CACHE_MANIFEST_FOLDER_ID": "synthetic_manifest_12345",
    "MFX_CACHE_STAGING_FOLDER_ID": "synthetic_staging_12345",
}


class FakeResponse:
    def __init__(self, obj: dict) -> None:
        self.obj = obj

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.obj


class FolderSession:
    def __init__(self) -> None:
        self.objects: dict[str, dict] = {}
        self.posts = 0

    def get(self, url: str, *, params: dict, timeout: int) -> FakeResponse:
        if url.endswith("/files"):
            query = params["q"]
            rows = [
                obj for obj in self.objects.values()
                if ("name = '" + obj["name"] + "'") in query
                and (("'root' in parents" in query
                      and "root" in obj["parents"])
                     or ("'" + obj["parents"][0] + "' in parents") in query)
            ]
            return FakeResponse({"files": rows})
        fid = url.rsplit("/", 1)[-1]
        return FakeResponse(self.objects[fid])

    def post(self, url: str, *, params: dict, json: dict,
             timeout: int) -> FakeResponse:
        self.posts += 1
        fid = "synthetic_drive_id_" + str(self.posts)
        obj = {
            "id": fid, "name": json["name"], "mimeType": json["mimeType"],
            "parents": json.get("parents", ["root"]),
            "trashed": False,
        }
        self.objects[fid] = obj
        return FakeResponse(obj)


class OAuthCloudCacheTests(unittest.TestCase):
    def test_complete_oauth_prefers_trio(self) -> None:
        with patch.dict(os.environ, TRIO, clear=True):
            info = _drive_auth_info()
        self.assertEqual(info["type"], "authorized_user")
        self.assertEqual(info["refresh_token"], "synthetic-refresh")

    def test_incomplete_oauth_fails_closed_even_if_sa_is_present(self) -> None:
        with patch.dict(os.environ, {
            "MFX_GDRIVE_OAUTH_CLIENT_ID": "incomplete",
            "MFX_GDRIVE_SERVICE_ACCOUNT_JSON": '{"type":"service_account","client_email":"fake@example.com"}',
        }, clear=True):
            with self.assertRaisesRegex(ValueError, "INCOMPLETE_GMAIL_OAUTH"):
                _drive_auth_info()

    def test_legacy_service_account_still_supported(self) -> None:
        with patch.dict(os.environ, {
            "MFX_GDRIVE_SERVICE_ACCOUNT_JSON": json.dumps({
                "type": "service_account",
                "client_email": "fake@example.com",
            }),
        }, clear=True):
            self.assertEqual(_drive_auth_info()["type"], "service_account")

    def test_oauth_requires_app_owned_cache_folders(self) -> None:
        with patch.dict(os.environ, TRIO, clear=True):
            with self.assertRaisesRegex(ValueError, "FOLDER_ID_REQUIRED"):
                _require_oauth_cache_folders(_drive_auth_info())

    def test_oauth_folders_and_vendor_gate_are_separate(self) -> None:
        with patch.dict(os.environ, {
            **TRIO, **FOLDERS, "MFX_TWELVE_DATA_API_KEY": "fake-key",
        }, clear=True):
            key, auth, cap = _settings()
        self.assertEqual(key, "fake-key")
        self.assertEqual(auth["type"], "authorized_user")
        self.assertEqual(cap, 400)

    def test_bootstrap_creates_four_then_reuses_without_writes(self) -> None:
        session = FolderSession()
        root = find_or_create_folder(session, "MFX_OAUTH_CACHE_V1", None)
        one = find_or_create_folder(session, "STAGING_ONLY", root)
        two = find_or_create_folder(session, "CHUNKS", root)
        three = find_or_create_folder(session, "MANIFESTS", root)
        self.assertEqual(session.posts, 4)
        self.assertEqual(find_or_create_folder(session, "MFX_OAUTH_CACHE_V1", None), root)
        self.assertEqual(find_or_create_folder(session, "STAGING_ONLY", root), one)
        self.assertEqual(find_or_create_folder(session, "CHUNKS", root), two)
        self.assertEqual(find_or_create_folder(session, "MANIFESTS", root), three)
        self.assertEqual(session.posts, 4)

    def test_duplicated_app_folder_fails_closed(self) -> None:
        session = FolderSession()
        root = find_or_create_folder(session, "MFX_OAUTH_CACHE_V1", None)
        session.objects["dup"] = dict(session.objects[root], id="dup")
        with self.assertRaisesRegex(ValueError, "NOT_UNIQUE"):
            find_or_create_folder(session, "MFX_OAUTH_CACHE_V1", None)

    def test_activation_unchanged_and_bootstrap_manual(self) -> None:
        boot = Path(".github/workflows/mfx-oauth-drive-bootstrap.yml").read_text()
        synthetic = Path(".github/workflows/mfx-b3b-synthetic-drive-proof.yml").read_text()
        self.assertIn("workflow_dispatch:", boot)
        self.assertNotIn("schedule:", boot)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY", boot)
        self.assertIn("MFX_GDRIVE_OAUTH_REFRESH_TOKEN", boot)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY", synthetic)
        self.assertIn("MFX_B3B_SYNTHETIC_DRIVE_STAGING_ACCEPTED", synthetic)


if __name__ == "__main__":
    unittest.main()
