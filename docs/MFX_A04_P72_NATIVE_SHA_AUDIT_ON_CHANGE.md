# MFX A04/P0.72 — Protected-main post-change native H4/D1 READ-ONLY SHA audit

Date: 2026-11-11 ICT. Only the native H4+D1 read-only source integrity workflow is extended. No native writer, provider/API quota, D1 calendar, private Drive writes, broker/signal, or market session waiver is changed.

## Observed D1 operational milestone

P0.71 code CI was accepted at protected main `9e88a0d6ff4543213172eb3bb7e6d57851dc6603`, independent CI #43030451039 (2102 unittest cases on EACH Python3.11/3.12 plus original frozen 102 Forex SHA, security/static and wheel parity). The existing P0.64 four-way-gated hourly native writer then actually fired as **event=schedule** run #43030973696 (2026-11-11 13:38 UTC), and job log #130557605228 printed `MFX_A04_P64_HOURLY_NATIVE_INCREMENTAL_SHA_READBACK_PASS`. Its exact summary: `status=NATIVE_INCREMENTAL_NEW_BARS_COMMITTED`, `intervals_with_new_native_bars=["1day"]`, `total_newly_closed_native_bars=1`, D1 `last_native_open_label=2026-11-11` Australia/Sydney exchange-local, `total_closed_native_bars=120`, `manifest_sha256=346ef3e48bec1b33e489d86233b9a5fa200810ef48563367d059ee098978fcae`, `drive_objects_created_max=2`, 1 source-native Twelve Data price request, 1 provider usage request, `intervals_skipped_no_new_closed_slot=["4h"]`, M5 unmodified and zero broker. This is the FIRST proven REAL D1 native incremental child, after root bootstrap 119 bars.

Independently listing the app-owned authenticated Google Drive CHUNKS/MANIFESTS folders then confirmed exactly two D1 Chunk and two D1 Manifest names (root 2026-11-10 and child 2026-11-11): new child Chunk SHA `4198dcc5fcd2236ac337512ded2be3b88c001185dcb561cc6d56d4cba301b865`, child Manifest SHA `346ef3e48bec1b33e489d86233b9a5fa200810ef48563367d059ee098978fcae`. This corroborates the writer's SHA post-write readback and independent **object names**, but an independent P0.58 full native SHA audit after D1 child append is **separately required** for strong acceptance.

## Gap / action

P0.58 native H4+D1 full SHA audit already runs on GitHub Actions UTC :45 hourly best-effort, plus manual dispatch, with existing 3 owner-enabled gates and shared `mfx-twelvedata-private-cache` no-cancel lock. However after an approved change to the audit code or its source sealed model, there is no immediate main-push read-only job; one must wait for a scheduled tick to observe whether the new code and live latest 1day Chunk/Manifest verify. P0.66 M5/H4 read-only parity has an already-approved protected-main push-on-change check.

P0.72 extends ONLY the P0.58 READ-ONLY YAML to run one owner-gated source SHA audit on protected-main push when any of:
- `tools/run_mfx_native_htf_cache_audit.py`
- `tools/mfx_native_htf_drive_seal.py`
- `mfx_cache/native_fx_htf.py`
- `mfx_cache/native_htf_archive.py`
- `.github/workflows/mfx-native-htf-cache-audit.yml`

These are exact allowlisted path triggers, not every repo push. Existing schedule `45 * * * *` and manual dispatch unchanged. Same 3 environment gates, pinned setup/checkout, `contents:read` only, same OAuth app-owned folder scope, shared non-cancellable concurrency group, no Twelve Data API key, no vendor call and no Drive mutation. The workflow is NOT a release or numeric signal authorization.

## Acceptance evidence

Add 9 hermetic QA checks: correct protected main path trigger, original hourly cron, dispatch and 3-way gate, read permission, absence of price key/writer calls, shared lock, and synthetic 2-pair independently FULL SHA-verified D1 child archive with modified historical Chunk/missing Manifest negative cases. Full latest-head PR Python3.11/3.12 CI, 102 golden Forex source SHA parity, static/security and cross Python wheel; independently verify exact protected-main CI.

After P0.72 protected merge, its automatic one-off **push event read-only** P0.58 job should authenticate existing Drive native H4 and D1 history and yield `MFX_A04_P58_NATIVE_H4_D1_READONLY_FULL_SHA_AUDIT_PASS`, with D1 full SHA 2/2 manifest+chunk pairs, last D1 local 2026-11-11, 120 total bars and 0 vendor requests/Drive writes/broker. A green simulated test or writer commit alone is NOT sufficient to claim this additional independent operational validation. If such run fails because Drive SHA differs, fail closed and retain H4/D1 native independent sources; never silently repair or delete objects.

No modification to existing P0.64 source-native writer and schedules; no H4 source substitution until owner-gated >=30 48xM5 H4 exact matches spanning >=7days with source session parity and rollback. Rolling M5 P0.69 >256 currently QA only, >1024 hard stop; Forex original 102 blobs source-locked. Source raw data long-term retention entitlement remains account-specific/unverified.
