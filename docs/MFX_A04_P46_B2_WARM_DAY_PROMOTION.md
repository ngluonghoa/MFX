# MFX A04/P0.46-B2 — SHA-linked WARM UTC-day promotion (STAGED)

Owner authorized continued Cloud-only Cache Engine V2 beyond FX 2.0, with private Google Drive as primary. Child GitHub Issue #80 under #76. Base B1 main ee284b27edcf2690526530ef87dee94f6b8f004f. Frozen original Forex Trading 1:1 source, 18 original labels, 11 SOURCE_LOCKED Docs, MFX design22, numeric source governance and broker exclusion unchanged.

## Stage B2 — Implemented source and activation contract

The new pure mfx_cache/v2_warm_promotion.py verifies every available B1 source Manifest in a bounded list, its full ordinal SHA-linked parent history (not only latest), each referenced hourly immutable chunk and original CLOSED twelve UTC/MID/source M5 candles. It independently re-derives 4 M15, 2 M30 and 1 H1 windows and rejects inconsistent hashes or source lineage. H4/D1 are not fabricated.

Eligible only for **the immediately prior completed UTC day after 01:00 UTC**, with 2–24 original complete hourly chunks. A UTC day need not be a valid Forex session: missing UTC hours are listed explicitly and any missing observation is left UNVERIFIED. WARM contains source Manifest/chunk SHA references, sorted M5 bars and derived M15/M30/H1, original provider and no signal or broker rights.

Two additive objects per day: one SHA-addressed WARM chunk under the private MFX immutable-chunks folder, then a separate SHA-addressed promotion receipt under MFX private manifests. Both require readback and exact canonical JSON hash. Sources are rechecked before promotion. If the first upload succeeded but receipt failed, the next attempt can recover without a Twelve Data call; duplicate receipt is a no-op. Source revisions, competing candidate WARM objects or receipts, broken parent chain, missing source, forged derived hash or mismatched readbacks fail closed.

**No original hourly raw chunk or Manifest is deleted or overwritten.** This is WARM read optimization and consolidated lineage, NOT yet fewer physical Drive files or lower total storage. It temporarily ADDS two objects per UTC day. Only future legal retention/backup/rollback review can authorize safe garbage collection. Also no Google Drive multi-file atomic CAS guarantee; single-writer GitHub concurrency prevents only cooperating overlap. External racing writers and eventual listing lag remain limitations.

Cloud adapter tools/run_a04_p46_cloud_batch_cache.py now maps the separate warm and promotion prefixes to the existing *MFX-owned* private folders. Dedicated tools/run_a04_p46_b2_cloud_warm.py reads only private Drive, no provider REST calls. Separate .github/workflows/mfx-warm-promotion.yml is **manual workflow_dispatch only** (NO schedule), and requires all THREE GitHub repository variables MFX_REAL_CACHE_ENABLED=true, MFX_V2_BATCH_CACHE_ACCEPTED=true, MFX_V2_WARM_PROMOTION_ACCEPTED=true plus separately supplied GDrive service-account writer credential. The ChatGPT connected Drive OAuth token does not become a GitHub Actions credential. No real raw market Cache activity is claimed.

## Verification scope / remaining work

New 32 fake Google Drive tests plus standalone no-network hosted demo and all source immutability, strict mypy, Python3.11+3.12, security and crosswheel must pass before merge. No live provider credentials, quote calls, or real Google Drive raw price writes in Stage B2. Accurate latency, compression or cost savings are NOT measured by this synthetic exercise.

Parent #76 remains OPEN for stage B3/C: authenticated synthetic Drive adapter fault testing, indexed long-term Manifest rather than full-chain scan bound of 12,000 objects, source-native H4/D1, calendar-certified bounded session backfill, legal TTL/retention and safe restore, five-minute-fresh HOT Cache rather than hourly-only, 20-pair quota policy and actual provider/Drive metrics. Live raw quote acceptance issue #74 remains OPEN. Third-party plan-specific storage and BIDASK/Q rights #27 still unverified. No source-owner numeric approvals (#45 0/36; original source-approved strategy labels 0/16), no real BUY/SELL alerts or broker orders.
