# MFX Gmail OAuth → GitHub Actions → Google Drive (STAGING)

Status: **NOT ACTIVATED**. This change adds code and dry-run gates; it does not
establish authenticated production Drive access, source caching rights, or
permission to trade. MFX remains Cloud-only.

## Why a separate app-created Drive area

The owner uses a personal Gmail **My Drive**. A service account cannot own new
user-drive content. The least-privilege OAuth `drive.file` scope allows the
OAuth client to create and manage its own files, but does **not** automatically
grant access to MFX folders previously created by the user/Drive connector.

The first-run GitHub Actions workflow creates this structure at **My Drive root**
with the user's OAuth credential, without modifying the previous MFX folder:

```text
My Drive/
  MFX_OAUTH_CACHE_V1/
    STAGING_ONLY/
    CHUNKS/
    MANIFESTS/
```

The new folders are MFX-dedicated and owned by the authenticated Gmail user.
Existing folders `02_MFX_CACHE — STAGING_ONLY` and its subfolders are left
untouched. A later move into the existing MFX tree would require separately
verified access or manual owner action; do not assume this has happened.

## Credentials (GitHub Actions repository Secrets)

- `MFX_GDRIVE_OAUTH_CLIENT_ID`
- `MFX_GDRIVE_OAUTH_CLIENT_SECRET`
- `MFX_GDRIVE_OAUTH_REFRESH_TOKEN`

The OAuth authorization must include `drive.file` and was obtained using the
same OAuth Client ID as the token. Secrets never go in code, comments, logs,
Google Docs or PRs. No token values should be sent to ChatGPT.

All three OAuth fields are required together. Partial OAuth configuration is
rejected rather than falling back to the historical service-account path.
A legacy service-account path remains for compatibility but is **not** the
recommended approach for personal Gmail My Drive.

## Manual first run, no market data

1. Merge and finish CI of this PR before running anything.
2. In Actions, run `MFX Gmail OAuth Drive cache folder bootstrap (MANUAL, NO prices)`
   on main. This is manual only and does **not** query Twelve Data.
3. Inspect the run log for `MFX_OAUTH_APP_OWNED_FOLDERS_READBACK_PASS`.
   Confirm three distinct ID fields are printed and were read back.
4. Copy exactly these three IDs to GitHub Repository **Variables**, not Secrets:

   - `MFX_CACHE_STAGING_FOLDER_ID`
   - `MFX_CACHE_CHUNK_FOLDER_ID`
   - `MFX_CACHE_MANIFEST_FOLDER_ID`

   The bootstrap can be rerun. Duplicated app-created folder names fail closed.
5. Keep `MFX_REAL_CACHE_ENABLED=false`,
   `MFX_V2_BATCH_CACHE_ACCEPTED=false`,
   `MFX_V3_HOT_CACHE_ACCEPTED=false`,
   `MFX_TD_ACCOUNT_CACHE_RIGHTS_CONFIRMED=false`, and
   `MFX_B3B_SEALED_INDEX_ACCEPTED=false`.
6. To test **synthetic data only**, change just
   `MFX_B3B_SYNTHETIC_DRIVE_STAGING_ACCEPTED=true`,
   then manually run
   `MFX B3B authenticated SYNTHETIC-ONLY private Drive fixed-file staging`.
7. Confirm the actual Actions log includes
   `MFX_A04_P46_B3B_CLOUD_DRIVE_SYNTHETIC_TWO_WRITE_READBACK_PASS`,
   an actual `file_id`, two SHA256 snapshots, same-file replacement,
   and both readback indicators.
8. Set `MFX_B3B_SYNTHETIC_DRIVE_STAGING_ACCEPTED=false` after proof.

No service account, live prices, broker, BUY/SELL signals or changes to
canonical sealed B1 history are involved in the synthetic test.

## Operational blockers to real hourly caching

- **OAuth lifetime:** Google's external OAuth `Testing` mode can expire
  non-basic refresh tokens after 7 days. A single passing job is insufficient
  for hourly unattended reliability. Resolve publishing/verification or choose
  an approved alternative *before* enabling 24/7 cache.
- Twelve Data account-specific API rights, historical caching/retention and
  quotas must be verified for this account before real vendor storage.
- Idempotency/retry, authenticated two-write synthetic staging and B1/HOT
  cross-source readback must be observed **from actual GitHub Actions runs**.
- `drive.file` does not grant access to old MFX user-created folders.
- No cloud storage provides a true multi-file atomic compare-and-swap in this
  implementation. Treat these files as staged research only.

## Recovery / rollback

Leave all real-cache activation variables false, disable the synthetic gate,
and revert the PR if necessary. Never remove existing MFX folders or OAuth
Secrets via a code rollback. Revoke OAuth permission in the Google Account
security settings if a credential is suspected of exposure; replace the
refresh token through the controlled GitHub Secrets UI afterward. No token
values should appear in audit output.
