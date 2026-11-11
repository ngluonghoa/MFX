# MFX A04/P0.58 — Native H4+D1 Hourly READ-ONLY Drive Integrity Audit

Date: 2026-11-11 ICT. Scope: only authenticated private EUR/USD native H4 and D1, source Twelve Data composite MID. Production M5 V2 writer/audit continues independently, original 102 Forex source blobs remain frozen. No broker, no source-approved numeric signals.

## Verified starting point

- PR #99 P0.57 protected main SHA `21fb5d563759fa5d9e21f1c5bf0b7e7c21314d3e`; independent main CI #42963262045 success. Manual native H4+D1 run [#42964328456](https://github.com/ngluonghoa/MFX/actions/runs/42964328456) completed success at 2026-11-11 05:14:10 UTC. Explicit marker `MFX_A04_P55_NATIVE_H4_D1_DRIVE_PAIR_SHA_READBACK_PASS` with two real provider price requests and no M5 modification.
- H4 root 119 bars latest UTC intraday open `2026-11-11 00:00:00`, H4 root manifest SHA `d47177c09abe5a42c38eb8e3c9c48b48505a21e9915691c269d9c13c218a2d28`. Existing H4 root re-used without rewrite.
- D1 root 119 bars latest provider/exchange-local session date `2026-11-10`, D1 root manifest SHA `f1397af5537ca0c3297f98c9fa8bc3df3e59159bf00eb71880df0e282ee70d65`. Both root files independently fetched from the owner's Google Drive and their SHA/manifest links inspected; 9 existing M5 V2 pairs remained unmodified.
- Both native TFs identify `Australia/Sydney` and per-bar SHA-pinned `DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT` timezone provenance, NOT independently vendor-supplied metadata. D1 is NOT reconstructed from UTC H4/M5.

## What the new A04/P0.58 workflow does

- New workflow `.github/workflows/mfx-native-htf-cache-audit.yml` runs hourly at **UTC minute 45** via `schedule` plus manual `workflow_dispatch`; same cross-workflow `mfx-twelvedata-private-cache` concurrency group as M5 and native writer, never simultaneous in-flight multipart commit by cooperating Actions.
- Existing owner-enabled three gates `MFX_REAL_CACHE_ENABLED`, `MFX_V2_BATCH_CACHE_ACCEPTED`, `MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED` must all be true. No new repo variable/secret or user intervention required for read-only audit. GitHub job grants `contents: read` and uses existing three OAuth secrets and app-created CHUNKS/MANIFESTS folders.
- Exactly **zero provider price calls**, no Twelve Data key in environment, **zero Drive write/create/delete**, no broker orders or numeric BUY/SELL. Archive data are read through existing authenticated `PrivateNativeDriveStore` functions (only `list_names` and `read`). HTTPS/OAuth client packages are pinned.
- Full bounded archive audit for EACH interval independently re-evaluates canonical content SHA, exact Chunk+Manifest names/refs, every parent SHA link, native interval/time references, provenance, last labels and counts, duplicate/missing artifacts and orphan chunks. A single unresolved orphan is an AUDIT FAILURE (writer may recover it later only with separate manual authorization), not silently ignored. No source prices appear in Actions log.
- Last fully closed H4 UTC 4-hour slot determined by `floor(now_utc, 4h)-4h`. Last finished D1 source session date is checked against `now in Australia/Sydney` minus one calendar day, with IANA DST support. An unclosed/future candle is integrity FAIL. The output identifies numerical *calendar* lag only; no broker session hours or holidays are assumed.
- Lagging archives return `LAGGING_OR_MARKET_CLOSED_REVIEW_REQUIRED` and a successful integrity audit, **NOT** a false automatic incident. This is deliberate because there is currently no accepted periodic native H4+D1 source writer. The user must NOT interpret an hourly read-only audit as live candle freshness or scheduling of H4/D1 refreshes.
- Single marker `MFX_A04_P58_NATIVE_H4_D1_READONLY_FULL_SHA_AUDIT_PASS` only if both interval audits pass. Strict errors fail the job and require investigation; do not mutate or automatically rerun writer.

## Quota, scale, and governance

- Twelve Data quota delta per hourly read-only audit **0 credits**; nominal GitHub runner workload 24 audit opportunities/day, Drive API read/list calls proportional to archive length and adapter readbacks. At most 256 native Chunk/Manifest objects per namespace are currently supported by A04/P0.55; new pagination/compaction design must be reviewed before growth reaches bounds. Full historical real-world market calendar QA is not claimed.
- Scheduled M5 writer remains UTC minute :10, M5 read-only audit :35; independent native read-only audit :45. HOT V3 stays disabled; native H4+D1 **writer stays manual-only**, no new provider polling schedule, no order placement. Vendor account-specific data retention/storage rights still require independent owner attestation.
- 24 deterministic no-network tests cover H4/D1 full SHA roots, source-local D1 dates and DST, weekend/manual-writer lag observation, orphan/duplicate/missing/altered/chain faults, future/unclosed labels, UTC grid, no vendor/secrets and unchanged manual writer workflow.
- PR must pass hosted Python 3.11 and 3.12 full CI (including frozen Forex parity/strict static security and wheel checks), merge on protected main and independent exact-main GitHub CI. First authenticated hourly/manual audit must PASS without calling provider or Drive write before **real scheduler acceptance**; isolated offline/CI PASS alone does not establish the live hourly audit.

## Operator acceptance checks

1. Open GitHub `https://github.com/ngluonghoa/MFX/actions/workflows/mfx-native-htf-cache-audit.yml`. Verify first scheduled UTC :45 job or manually run from protected main after merge.
2. Check job has `MFX_A04_P58_NATIVE_H4_D1_READONLY_FULL_SHA_AUDIT_PASS`, `provider_price_requests=0`, `drive_writes=0`, `broker_orders=0`; inspect H4/D1 separate `last_manifest_sha256`, `total_closed_native_bars`, `lag`, `lag_unit`.
3. Independently re-list Google Drive CHUNKS and MANIFESTS after run; no new H4/D1/M5 objects should appear solely because of read-only audit. Verify source H4+D1 existing last SHAs unchanged.
4. Distinguish structurally valid, **lagging/manual** source cache from genuine fresh source candles; only a subsequent independently approved native periodic writer could close this gap.

**Current A04/P0.58 scope:** read-only integrity and calendar-lag observation. No promotion to live trading or automated H4/D1 write.
