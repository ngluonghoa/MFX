"""A04/P0.45 GitHub Actions-only Twelve Data REST -> PRIVATE Drive raw cache.

Requires separately provisioned GitHub secrets. ChatGPT's connected OAuth
plugins are NOT automatically accessible to GitHub Actions. The CLI never
stores credentials in GitHub source, logs, or raw Drive cache payloads.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from mfx_cache.td_m5_codec import (
    INTERVAL, PROVIDER, SYMBOL, canonical, check_manifest, compute_delta,
    content_chunk, digest, initial_manifest, next_manifest,
    parse_closed_utc_m5,
)

CHUNK_FOLDER = (os.environ.get("MFX_CACHE_CHUNK_FOLDER_ID") or "1cmq6oOb3NB7jQdeua_wcRnmrhERhFkLQ")
MANIFEST_FOLDER = (os.environ.get("MFX_CACHE_MANIFEST_FOLDER_ID") or "1mwYFXWoxSC-R4opm23-5VQKaz1xQazDc")
MANIFEST_PREFIX = "MFX_TD_EURUSD_M5_manifest_v1_"
CHUNK_PREFIX = "MFX_TD_EURUSD_M5_chunk_v1_"


def _require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError("P045_MISSING_PRIVATE_CLOUD_CONFIGURATION:" + name)
    return value


def _drive_auth_info() -> dict[str, Any]:
    """Choose a complete Gmail OAuth trio or the legacy service account.

    OAuth does not grant access to old user-created MFX folders. The new
    app-created folder IDs must be separately configured before cache writes.
    """
    keys = (
        "MFX_GDRIVE_OAUTH_CLIENT_ID",
        "MFX_GDRIVE_OAUTH_CLIENT_SECRET",
        "MFX_GDRIVE_OAUTH_REFRESH_TOKEN",
    )
    supplied = [bool(os.environ.get(name)) for name in keys]
    if any(supplied):
        if not all(supplied):
            raise ValueError("P045_INCOMPLETE_GMAIL_OAUTH_TRIO")
        return {
            "type": "authorized_user",
            "client_id": _require_env(keys[0]),
            "client_secret": _require_env(keys[1]),
            "refresh_token": _require_env(keys[2]),
        }
    raw = _require_env("MFX_GDRIVE_SERVICE_ACCOUNT_JSON")
    try:
        sa = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("P045_SERVICE_ACCOUNT_JSON_REQUIRED") from exc
    if (not isinstance(sa, dict)
            or sa.get("type") != "service_account"
            or not isinstance(sa.get("client_email"), str)):
        raise ValueError("P045_INVALID_GDRIVE_SERVICE_ACCOUNT")
    return sa


def _require_oauth_cache_folders(info: dict[str, Any]) -> None:
    if info.get("type") == "authorized_user":
        import re
        for key in ("MFX_CACHE_CHUNK_FOLDER_ID",
                    "MFX_CACHE_MANIFEST_FOLDER_ID"):
            value = os.environ.get(key, "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{10,160}", value):
                raise ValueError("P045_OAUTH_APP_CREATED_FOLDER_ID_REQUIRED:" + key)


def _settings() -> tuple[str, dict[str, Any], int]:
    key = _require_env("MFX_TWELVE_DATA_API_KEY")
    auth = _drive_auth_info()
    _require_oauth_cache_folders(auth)
    cap = int(os.environ.get("MFX_TD_DAILY_CREDIT_CAP", "400"))
    if not 1 <= cap <= 720:
        raise ValueError("P045_DAILY_CAP_MUST_LEAVE_PROVIDER_HEADROOM")
    return key, auth, cap


def _session(info: dict[str, Any]) -> Any:
    # Lazy imports: pure module and unit tests run offline without network deps.
    from google.auth.transport.requests import AuthorizedSession
    if info.get("type") == "authorized_user":
        from google.oauth2.credentials import Credentials
        credentials = Credentials(
            token=None,
            refresh_token=info["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=info["client_id"],
            client_secret=info["client_secret"],
            scopes=("https://www.googleapis.com/auth/drive.file",),
        )
    elif info.get("type") == "service_account":
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=("https://www.googleapis.com/auth/drive.file",),
        )
    else:
        raise ValueError("P045_UNSUPPORTED_DRIVE_AUTH_KIND")
    return AuthorizedSession(credentials)


def _drive_list(session: Any, parent: str, name_prefix: str,
                *, page_size: int = 1) -> list[dict[str, Any]]:
    # Restricted fixed prefix and folder IDs, never user-generated Drive query.
    url = "https://www.googleapis.com/drive/v3/files"
    r = session.get(url, params={
        "q": f"'{parent}' in parents and name contains '{name_prefix}' and trashed = false",
        "orderBy": "createdTime desc", "pageSize": page_size,
        "fields": "files(id,name,mimeType,md5Checksum,createdTime)",
        "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
    }, timeout=40)
    r.raise_for_status()
    files = r.json().get("files")
    if not isinstance(files, list):
        raise ValueError("P045_GDRIVE_LIST_RESPONSE_INVALID")
    return files


def _drive_get(session: Any, file_id: str) -> dict[str, Any]:
    r = session.get(
        "https://www.googleapis.com/drive/v3/files/"+file_id,
        params={"alt": "media", "supportsAllDrives": "true"},
        timeout=40,
    )
    r.raise_for_status()
    value = r.json()
    if not isinstance(value, dict):
        raise ValueError("P045_GDRIVE_JSON_CONTENT_REQUIRED")
    return value


def _drive_create(
    session: Any, folder: str, name: str, data: dict[str, Any],
) -> str:
    from uuid import uuid4
    boundary = "MFXP045_" + uuid4().hex
    metadata = canonical({
        "name": name, "mimeType": "application/json", "parents": [folder],
        "description": "MFX private raw cache; no user signals; provider MID",
    })
    payload = canonical(data)
    body = (
        (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n"
         "\r\n").encode("ascii") + metadata + b"\r\n"
        + (f"--{boundary}\r\nContent-Type: application/json\r\n"
           "\r\n").encode("ascii") + payload + b"\r\n"
        + (f"--{boundary}--\r\n").encode("ascii")
    )
    r = session.post(
        "https://www.googleapis.com/upload/drive/v3/files",
        params={"uploadType": "multipart",
                "fields": "id,name,mimeType,parents,md5Checksum",
                "supportsAllDrives": "true"},
        headers={"Content-Type": "multipart/related; boundary=" + boundary},
        data=body, timeout=60,
    )
    r.raise_for_status()
    res = r.json()
    if (res.get("name") != name or
            res.get("mimeType") != "application/json" or
            folder not in res.get("parents", []) or
            not res.get("id")):
        raise ValueError("P045_GDRIVE_UPLOAD_METADATA_MISMATCH")
    # Read back bytes and compare exact canonical content. Cloud-only provider
    # call, independent of returned upload status.
    if _drive_get(session, res["id"]) != data:
        raise ValueError("P045_GDRIVE_READBACK_JSON_MISMATCH")
    return str(res["id"])


def _vendor_usage(key: str) -> tuple[int, int]:
    import requests
    r = requests.get("https://api.twelvedata.com/api_usage",
                     params={"apikey": key}, timeout=30)
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, dict):
        raise ValueError("P045_VENDOR_USAGE_UNVERIFIED")
    used, limit = payload.get("current_usage"), payload.get("plan_limit")
    if type(used) is not int or type(limit) is not int or limit <= 0:
        raise ValueError("P045_VENDOR_USAGE_OR_PLAN_UNVERIFIED")
    return used, limit


def _vendor_m5(key: str, *, bootstrap: bool) -> dict[str, Any]:
    import requests
    r = requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "apikey": key, "symbol": SYMBOL, "interval": INTERVAL,
            "timezone": "UTC", "format": "JSON",
            "outputsize": 120 if bootstrap else 16,
        },
        timeout=45,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict) or data.get("status") == "error":
        raise ValueError("P045_VENDOR_OHLC_ERROR")
    return data


def main() -> None:
    now = datetime.now(tz=timezone.utc)
    if os.environ.get("MFX_REAL_CACHE_ENABLED") != "true":
        print("MFX_P045_CACHE_DISABLED_EXPLICIT_ACTIVATION_REQUIRED")
        return
    key, sa, daily_cap = _settings()
    session = _session(sa)
    objects = _drive_list(session, MANIFEST_FOLDER, MANIFEST_PREFIX)
    if objects:
        current = check_manifest(_drive_get(session, objects[0]["id"]))
    else:
        current = initial_manifest(now)

    today = now.date().isoformat()
    spent = (current["credits_reserved_today"]
             if current["credit_day_utc"] == today else 0)
    if spent >= daily_cap:
        print("MFX_P045_LOCAL_CREDIT_CAP_REACHED_NO_API_REQUEST")
        return
    slot = now.replace(minute=now.minute//5*5, second=0,
                       microsecond=0).isoformat()
    if current["last_poll_slot_utc"] == slot:
        print("MFX_P045_DUPLICATE_POLL_SLOT_NO_API_REQUEST")
        return
    used, limit = _vendor_usage(key)
    if used >= limit - 10:
        print("MFX_P045_PROVIDER_CREDIT_HEADROOM_TOO_LOW_NO_PRICE_REQUEST")
        return
    payload = _vendor_m5(key, bootstrap=current["total_chunks"] == 0)
    observed = parse_closed_utc_m5(payload, now_utc=now)
    delta = compute_delta(current, observed)
    chunk_sha: str | None = None
    if delta.new_bars:
        chunk = content_chunk(delta, now)
        chunk_sha = digest(chunk)
        name = (CHUNK_PREFIX + delta.new_bars[0].start_utc[:16].replace(":", "-")
                + "_" + chunk_sha[:16] + ".json")
        existing = _drive_list(session, CHUNK_FOLDER, name, page_size=20)
        matches = [x for x in existing if x.get("name") == name]
        if matches:
            if _drive_get(session, matches[0]["id"]) != chunk:
                raise ValueError("P045_CHUNK_NAME_HASH_COLLISION_OR_MUTATION")
        else:
            _drive_create(session, CHUNK_FOLDER, name, chunk)
    new_manifest = next_manifest(current, delta, now_utc=now,
                                 new_chunk_sha256=chunk_sha)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    name = MANIFEST_PREFIX + stamp + "_" + digest(new_manifest)[:16] + ".json"
    _drive_create(session, MANIFEST_FOLDER, name, new_manifest)
    print(json.dumps({
        "result": "MFX_P045_PRIVATE_DRIVE_CACHE_READBACK_PASS",
        "provider": PROVIDER, "symbol": SYMBOL, "side": "MID",
        "timezone": "UTC", "new_closed_bars": len(delta.new_bars),
        "gaps_not_synthesized": delta.gaps_detected,
        "total_archived_bars": new_manifest["total_closed_bars_archived"],
        "local_credits_reserved_today": new_manifest["credits_reserved_today"],
        "outbound_signals": 0, "broker_orders": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
