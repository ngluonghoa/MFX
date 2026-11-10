"""Single explicitly scoped Google Drive JSON slot, no standalone secrets.

Used ONLY for B3-B synthetic staging and B1 sealed index. This wrapper
does NOT confer an atomic multi-writer CAS; GitHub shared concurrency
prevents cooperating runs, external writers can still race. Re-read and
recheck file ID and bytes after every replace.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from mfx_cache.td_m5_codec import canonical
from tools.run_a04_p45_cloud_twelve_data_cache import (
    _drive_create, _drive_get,
)


class CloudJsonSlot:
    def __init__(
        self, session: Any, *, folder_id: str, file_name: str,
        validator: Callable[[object, datetime], dict[str, Any]],
    ) -> None:
        if (not folder_id or not file_name
                or "/" in file_name or "'" in file_name
                or not file_name.endswith(".json")
                or file_name.startswith(".")):
            raise ValueError("P046_B3B_INVALID_SCOPED_JSON_SLOT")
        self.session = session
        self.folder_id = folder_id
        self.file_name = file_name
        self.validator = validator
        self.file_id: str | None = None

    def _find(self) -> str | None:
        r = self.session.get(
            "https://www.googleapis.com/drive/v3/files",
            params={
                "q": (f"'{self.folder_id}' in parents and "
                      f"name = '{self.file_name}' and trashed = false"),
                "pageSize": 100,
                "fields": "nextPageToken,files(id,name,mimeType,parents)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },
            timeout=45,
        )
        r.raise_for_status()
        result = r.json()
        if (type(result) is not dict
                or type(result.get("files")) is not list
                or result.get("nextPageToken") is not None):
            raise ValueError("P046_B3B_INCOMPLETE_JSON_SLOT_LIST")
        found = result["files"]
        if len(found)>1:
            raise ValueError("P046_B3B_DUPLICATE_JSON_SLOT_FORK")
        if not found:
            self.file_id = None
            return None
        item = found[0]
        if (type(item) is not dict
                or type(item.get("id")) is not str
                or item.get("name") != self.file_name
                or item.get("mimeType") != "application/json"
                or self.folder_id not in item.get("parents",[])):
            raise ValueError("P046_B3B_UNEXPECTED_JSON_SLOT_METADATA")
        self.file_id = item["id"]
        return self.file_id

    def load(self) -> dict[str, Any] | None:
        name = self._find()
        if name is None:
            return None
        raw = _drive_get(self.session, name)
        return self.validator(raw,datetime.now(timezone.utc))

    def write(
        self, *, expected: dict[str, Any] | None,
        replacement: dict[str, Any],
    ) -> None:
        self.validator(replacement,datetime.now(timezone.utc))
        current = self.load()
        if current != expected:
            raise ValueError("P046_B3B_JSON_SLOT_CHANGED_BEFORE_WRITE")
        original_id = self.file_id
        if original_id is None:
            _drive_create(self.session,self.folder_id,
                          self.file_name,replacement)
            # First creation must still be unique in the folder.
        else:
            response = self.session.patch(
                "https://www.googleapis.com/upload/drive/v3/files/"+original_id,
                params={
                    "uploadType":"media",
                    "supportsAllDrives":"true",
                    "fields":"id,name,mimeType,version",
                },
                headers={"Content-Type":"application/json; charset=UTF-8"},
                data=canonical(replacement),timeout=60,
            )
            response.raise_for_status()
            response_meta = response.json()
            if (type(response_meta) is not dict
                    or response_meta.get("id") != original_id):
                raise ValueError("P046_B3B_DRIVE_PATCH_FILE_ID_CHANGED")
        new_state = self.load()
        if new_state != replacement:
            raise ValueError("P046_B3B_JSON_SLOT_READBACK_MISMATCH")
        if original_id is not None and self.file_id != original_id:
            raise ValueError("P046_B3B_JSON_SLOT_FILE_ID_REPLACED")
        if original_id is None and self.file_id is None:
            raise ValueError("P046_B3B_JSON_SLOT_CREATE_NOT_VISIBLE")
