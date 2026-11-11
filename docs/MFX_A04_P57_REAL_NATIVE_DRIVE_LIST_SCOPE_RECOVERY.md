# MFX A04/P0.57 — Real Drive Native H4/D1 List-Scope Recovery (staged)

Date: 2026-11-11 ICT. Scope: independent cloud-only MFX native EUR/USD H4+D1 manual GitHub Actions workflow, protected original Forex 1:1 source and live M5 V2. NO broker / no source-approved numeric BUY/SELL.

## Verified external evidence, not simulated

- P0.56 protected main SHA `94660b0f9ba3f1cffef5418b5f1f9696db877e62` and independent main CI [#42959336185](https://github.com/ngluonghoa/MFX/actions/runs/42959336185) succeeded.
- Real manual native sealed writer [#42960645079](https://github.com/ngluonghoa/MFX/actions/runs/42960645079), started 2026-11-11 04:39:23 UTC, **FAILED**, job `commit-native-htf`, traceback `tools/mfx_native_htf_drive_seal.py` -> `audit_native_archive` -> `PrivateNativeDriveStore.list_names("manifest")`: `P055_NATIVE_DRIVE_WRONG_OBJECT_SCOPE`. This is NOT the earlier P0.56 missing source exchange timezone error. The failing list item itself was not logged, so its exact field(s) are unproven; do not assert one definitive Drive response anomaly.
- Independent private Drive listing after failure: precisely one EUR/USD H4_NATIVE_V1 Chunk ID `1g6Zdkn4HJkSKAmoT5lK_3dpSc5cjRyXH` and one H4_NATIVE_V1 Manifest ID `1cmuDB69NL0TlOxVBmPMq1b3ePzXQgMni`, created 04:39:35/37 UTC; H4 manifest reports 119 closed native bars, 1 sealed root batch, last 2026-11-11 00:00:00 UTC with explicitly SHA-covered documented Australia/Sydney fallback. Independent 9 existing EUR/USD M5 V2 Chunks and 9 Manifests remain in the same physical app-owned folders (last UTC 02:00); no D1 native objects were present on inspection.
- The H4 two-object presence is NOT proof that final H4+D1 job acceptance succeeded. The traceback can occur when a just-created H4 manifest is listed for final audit; from the stack alone it is unsafe to claim D1 execution started. D1 write/readback is still NOT ACCEPTED.

## Root-cause boundary and narrow correction

Prior `PrivateNativeDriveStore.list_names` treated every Google Drive `name contains` list result as automatically equal to the exact native namespace, and rejected any result if its `id`, `name`, `mimeType`, `parents` or exact prefix failed a combined condition. This is brittle in shared CHUNK/MANIFEST folders. The runtime did not emit the offending list-item metadata, so the exact missing/unexpected field remains an observation gap.

P0.57 retains the server-side folder/prefix query, but validates nonempty file IDs and names; accepts optional omission of `parents` because the server already constrains the parent while rejecting explicitly conflicting parent metadata; filters response items by exact native `startswith(prefix)` on the client; and continues to strictly reject mismatched JSON MIME, duplicate names, excessive per-namespace files, bad pagination and full-chain or parent SHA corruption for in-scope native objects. No file is renamed, deleted, overwritten or automatically promoted.

Regression coverage adds three offline cases: a deliberately broad same-folder list including M5, H4, D1 that must still commit both native TFs; an omitted optional `parents` list field; and explicit incorrect-parent/incorrect-MIME that must fail closed. Tests do NOT substitute for real authenticated GitHub/Drive acceptance.

## Safety, re-run and acceptance

- Native writer remains `workflow_dispatch` ONLY, gated by existing three variables; no schedule, new provider, broker access or signal promotion.
- **Do not reset** `MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED`: owner previously enabled it. Active M5 V2 hourly writer and read-only audit remain unchanged.
- Requires GitHub hosted PR Python 3.11/3.12 full tests, strict Ruff/mypy/immutable Forex original, security/wheel parity, protected merge and independent exact-main CI before another live manual run.
- After merge/main CI, operator manually dispatches [native writer](https://github.com/ngluonghoa/MFX/actions/workflows/mfx-native-htf-drive-commit.yml) on main once. Capture job ID and sanitized `MFX_A04_P55_NATIVE_H4_D1_DRIVE_PAIR_SHA_READBACK_PASS` result. If no PASS, diagnose exact safe error; do not imply run succeeded.
- Independently re-list both private Drive folders and verify exact canonical H4 and D1 Chunk+Manifest SHA/readback, source-native H4 UTC-open versus D1 local-date semantics, provenance, parent links and existing M5 unchanged. Existing committed H4 must be reused idempotently if source overlap unchanged; if provider revises data, fail closed. No Drive atomic multi-object transaction is claimed.
- Retention/license, source-approved 16 entry strategies and B2/S2 owner 36 decisions remain separate unverified gates; never auto-issue trade orders.

**Current status:** P0.57 CODE FIX STAGED, REAL H4+D1 PAIR ACCEPTANCE PENDING.