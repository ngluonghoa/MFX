# M2/P0.8 — Approved Google Drive location & synthetic mixed-scope Smart Cache

**User approval (2026-11-07):** Choose Google Drive as the durable destination for Forex Trading 1.0 Smart Cache, and make **5 → 20 → 1 → 20 pairs** an explicit regression/acceptance sequence. Valid existing cached candles and derived checkpoints must be reused across scan modes; do not fetch entire history of a previously scanned pair merely because scope increases.

## Created Google Drive staging folder (no price data)

Project folder: `Forex Trading 1.0 - Independent Project`.

Cache staging root: https://drive.google.com/drive/folders/12iWh528iFnfF6zyHBGpI4WFOSrrubmX5

- `00_MANIFESTS_AND_INDEX__STAGING`: https://drive.google.com/drive/folders/1OPBHzq5sPNV9ohqlsfi_I5e35ve1qvkD
- `01_IMMUTABLE_CHUNKS__STAGING`: https://drive.google.com/drive/folders/1mE7Zx29kDjyN8DYfvZn4HYx-OIoYaScw
- `02_AUDIT_AND_QUARANTINE__STAGING`: https://drive.google.com/drive/folders/1ihSmQHycUxeWgQc-Wh69EXT9HnkLb-G_

These are **ordinary visible Google Drive folders**, not hidden `appDataFolder`; the latter is scoped to a specific OAuth app and may be inaccessible to other connected apps. Folder provisioning is NOT evidence of Drive API raw-file IO, encryption, access-token scopes, quota or real-price licensing. No actual cache files have been uploaded.

## Approved target architecture (not yet operational)

- Storage destination = Google Drive, using a future adapter to store **small immutable, content-addressed per-partition chunks** and **versioned manifests**. Do not open a SQLite WAL DB on Google Drive or re-upload one giant DB on every scan. Retain the exact provider/product/instrument/BID+ASK/TF/calendar/aggregation/schema/rights partition fingerprint from DEC-FX-020.
- A per-partition manifest references exactly the active chunk digest and previous manifest generation. Scan selection happens *before* any Drive read / provider request. A 5-pair scan loads only required partitions; 20-pair scan reuses those 5 and bootstraps 15 missing pairs; 1-pair scan touches only the requested pair. Never mix bid and ask or use MID as an executable quote.
- On append/late correction, use existing `plan_incremental_refresh` bounded windows and `reconcile_closed_delta`; re-materialize only the affected partition artifact and dependent L2–L5 features. Unaffected partitions never get forced into a full history reload. Claim-only provider change heads must not authorize real skipping.
- A real **single-writer / version and lease coordination mechanism** must be independently engineered and tested; Google Drive object writes do not by themselves provide a trusted atomic multi-object transaction or externally anchored rollback witness. Write new immutable chunk, validate upload/content checksum, then publish active manifest/index under a real concurrency protocol; orphan stages may be quarantined. Recovery must reject tampering and stale pointers. Do not interpret local hash chains as authentic vendor data.
- Use envelope encryption with independent key handling, minimal folder ACL and immutable audit retention/revocation policy only after verifying the vendor's permissions. Provider/API credentials and any sensitive account identifiers must NEVER be stored in GitHub or raw document manifests. Deletion/retention/legal hold needs source-specific policy.
- Google Drive quota and transient 403/429/5xx errors require bounded exponential backoff and budget observability; no per-candle Drive file spam. Folder/partition grouping and periodic packing must be benchmarked with real allowed data before SLO claims.
- One source of truth for code is GitHub; Google Docs 00/01/02/06 document decisions; Google Drive cache folders are a separate data location. MOCHI/VPS/Colab/M15001 not required or authorized by this storage choice. A running compute environment is still needed on demand; Drive is storage, NOT an always-on execution scheduler.

## Executable SYNTHETIC reference

`src/forex_trading/synthetic_drive_cache_staging.py` adds:
- `SyntheticDriveCacheStaging` fully in-memory test double of partition-specific immutable chunks, manifests, checksum/pointer check, stale-writer guard, orphan-before-publish crash and corruption fail-closed. It **never** calls Google Drive or writes a file.
- `run_mixed_scope_synthetic_drive_scan` routes SINGLE/CUSTOM/ALL selections into existing immutable L1 candle cache, validates BID/ASK and timeframe completeness before writing, bootstraps only missing partitions, and reconciles only bounded overlap/new oracle bars for cached partitions. It does **not** implement real vendor delta IO, full L2–L5 or production retention and privacy.
- Negative tests cover 5→20→1→20, untouched pair preservation, correction inside overlap, incomplete BID/ASK, unknown pair, staged crash, forged active pointer, missing chunk, stale writer, and no API calls.

Fixture metrics are **not** network metrics. A particular deterministic 20 FAKE-pair × 2 sides × 5 synthetic TF fixture initially has 8 bars/partition:
- Scan 5 initial: 50 partitions × 8 old bars = 400 synthetic bootstrap rows.
- Five minutes later scan 20: reuse 50 existing partitions via bounded overlap+delta and bootstrap 150 newly requested partitions; no full refetch for those 50.
- Then scan 1, then scan 20 with no subsequent source change: ZERO additional synthetic chunk writes (but bounded overlap checks still occur). This proves only the reference algorithm's selected reuse, not elapsed time saved by the real Drive or data vendor.

## Release/data rights blockers

Google Drive **selected as location and staging folders created**, but **real market data storage remains BLOCKED** until the actual provider account/plan/region grants historical native BID/ASK fetch, raw/derived cache retention, replay/Backtest as required, and an approved Drive residency/security/ACL/encryption/key/retention/backup/recovery process exists. Drive API connection for Docs is not automatically proof that raw binary file uploads/real-cache updates are available to a scanner. Next real release gates: production Drive adapter, source adapter, independent witness/consistency + anti-rollback, crash/restart exercise, source corrections outside overlap, per-pair actual bytes/API calls/latency (5→20→1→20), full L2–L5 parity, and backtest/OOS/strategy gates. No broker trading or ACTIVE/LKG release.
