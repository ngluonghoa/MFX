"""Create a Drive cache area owned by the user's Gmail OAuth app.

Manual GitHub Actions bootstrap only. A drive.file token cannot assume
access to the pre-existing human-created MFX project folders, so this
creates fresh app-managed folders at My Drive root. No vendor API calls.
"""
from __future__ import annotations

import json

from tools.run_a04_p45_cloud_twelve_data_cache import (
    _drive_auth_info, _session,
)

DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"
MIME_FOLDER = "application/vnd.google-apps.folder"
ROOT_NAME = "MFX_OAUTH_CACHE_V1"


def find_or_create_folder(session: object, name: str, parent: str | None) -> str:
    """Reruns are idempotent; ambiguous duplicates fail instead of branching."""
    if not name.startswith("MFX_") and name not in ("STAGING_ONLY", "CHUNKS", "MANIFESTS"):
        raise ValueError("MFX_OAUTH_UNEXPECTED_FOLDER_NAME")
    where = "'root' in parents" if parent is None else f"'{parent}' in parents"
    params = {
        "q": f"{where} and name = '{name}' and mimeType = '{MIME_FOLDER}' and trashed = false",
        "pageSize": 100,
        "fields": "nextPageToken,files(id,name,mimeType,parents)",
    }
    response = session.get(DRIVE_FILES, params=params, timeout=45)
    response.raise_for_status()
    data = response.json()
    found = data.get("files")
    if (not isinstance(found, list) or data.get("nextPageToken")
            or len(found) > 1):
        raise ValueError("MFX_OAUTH_FOLDER_NOT_UNIQUE_OR_LIST_INCOMPLETE")
    if found:
        fid = found[0].get("id")
        if not isinstance(fid, str) or not fid:
            raise ValueError("MFX_OAUTH_FOLDER_ID_INVALID")
    else:
        metadata = {"name": name, "mimeType": MIME_FOLDER}
        if parent is not None:
            metadata["parents"] = [parent]
        created = session.post(
            DRIVE_FILES, params={"fields": "id,name,mimeType,parents"},
            json=metadata, timeout=45,
        )
        created.raise_for_status()
        fid = created.json().get("id")
        if not isinstance(fid, str) or not fid:
            raise ValueError("MFX_OAUTH_CREATED_FOLDER_ID_INVALID")
    checked = session.get(
        f"{DRIVE_FILES}/{fid}",
        params={"fields": "id,name,mimeType,parents,trashed"},
        timeout=45,
    )
    checked.raise_for_status()
    actual = checked.json()
    if (actual.get("id") != fid or actual.get("name") != name
            or actual.get("mimeType") != MIME_FOLDER or actual.get("trashed")):
        raise ValueError("MFX_OAUTH_FOLDER_METADATA_READBACK_MISMATCH")
    if parent is not None and parent not in actual.get("parents", []):
        raise ValueError("MFX_OAUTH_FOLDER_PARENT_READBACK_MISMATCH")
    return fid


def main() -> None:
    auth = _drive_auth_info()
    if auth.get("type") != "authorized_user":
        raise ValueError("MFX_OAUTH_BOOTSTRAP_REQUIRES_GMAIL_OAUTH_TRIO")
    session = _session(auth)
    root = find_or_create_folder(session, ROOT_NAME, None)
    staging = find_or_create_folder(session, "STAGING_ONLY", root)
    chunks = find_or_create_folder(session, "CHUNKS", root)
    manifests = find_or_create_folder(session, "MANIFESTS", root)
    print("MFX_OAUTH_APP_OWNED_FOLDERS_READBACK_PASS")
    print(json.dumps({
        "status": "CREATED_OR_VERIFIED_APP_OWNED_FOLDERS",
        "root_folder_id": root,
        "MFX_CACHE_STAGING_FOLDER_ID": staging,
        "MFX_CACHE_CHUNK_FOLDER_ID": chunks,
        "MFX_CACHE_MANIFEST_FOLDER_ID": manifests,
        "source": "GMAIL_OAUTH_DRIVE_FILE_APP_CREATED",
        "old_mfx_folders_mutated": False,
        "twelve_data_api_calls": 0,
        "live_signals": 0,
        "broker_orders": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
