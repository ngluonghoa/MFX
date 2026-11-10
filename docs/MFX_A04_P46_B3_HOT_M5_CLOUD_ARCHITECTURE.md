# MFX A04/P0.46-B3-A — five-minute HOT M5 overlay (staged, no live activation)

Owner approved continued MFX Cloud-only Cache Engine V2, after P046-B2 WARM day promotion. Parent Issue [#82](https://github.com/ngluonghoa/MFX/issues/82), frozen Forex original 1:1 source and unapproved original strategy parameters unchanged. This scope is deliberately **HOT staging only**, not final production quote ingestion, source-approved BUY/SELL signals, or broker execution.

## Precisely what is built

A new pure `mfx_cache/v3_hot_overlay.py` validates at most **24 CLOSED, UTC-aligned EUR/USD M5 MID candles**, their canonical SHA256 index and per-bar first_seen_utc timestamp. A five-minute 16-row overlapping Twelve Data request (once separately authorized) can append only new CLOSED native M5 bars. An unchanged response yields **zero Drive writes**, a changed overlap triggers a hard quarantine, a missing/unseen historical bar triggers a hard audit gate, a noncontiguous M5 gap is recorded as `source_gap_unverified` and **cannot silently clear by rolling the window**. No source event timestamp is inferred to be our observation timestamp. A freshness view never labels the source fresh if the last M5 close is older than five minutes plus 90 seconds; weekend or vendor session gaps remain unverified until independently reconciled. The "FRESH_RECENT_M5_RESEARCH_ONLY" label authorizes only synthetic/internal research context, **never** a market signal; MID is not executable BID/ASK. Lack of full historical vendor revision evidence means even a fresh recent window does not establish full source quality.

A new Cloud-only `tools/run_a04_p46_b3_hot_cloud.py` implements a **fixed-name JSON Google Drive file**, `MFX_TD_EURUSD_M5_V3_HOT_LATEST.json`, in the existing private MFX Manifest folder. First successful write creates the file once; subsequent fresh M5 data uses Google Drive files.update/upload media on the same file ID, with independent before/after SHA-content readback and monotonic generation/previous-content-hash fields. This avoids adding two NEW Drive objects per 5-minute polling event. It does **not** avoid the HTTP traffic of provider requests or Drive update/readback, and Drive still may retain historical revisions and storage charges. The overwritten predecessor SHA is a consistency aid, **not an independently immutable audit witness or a trusted CAS**. Any crash during update may be reconciled by readback and retry if the object bytes are intact; corrupt state, fork, ambiguous listing, revised historical bar or state race always fail closed. Canonical durable source remains P046-B1 immutable CLOSED M5 hourly batches and B2 original WARM lineage; the HOT overlay is **mutable and non-authoritative**, never a replacement for archival source evidence.

A new gated `.github/workflows/mfx-hot-cache.yml` *defines* an hourly cron at UTC minute :15 (owner selected 2026-11-10; previously a five-minute cron), shares the same concurrency group as B1 hourly writer and B2 manual WARM. Before the job will even run, repository variables must all be explicitly true:
- `MFX_REAL_CACHE_ENABLED`
- `MFX_V3_HOT_CACHE_ACCEPTED`
- `MFX_TD_ACCOUNT_CACHE_RIGHTS_CONFIRMED`

GitHub secrets `MFX_TWELVE_DATA_API_KEY` and `MFX_GDRIVE_SERVICE_ACCOUNT_JSON` plus genuine MFX private folder writer sharing are additionally required. The rights variable represents operational owner acceptance **only after** account-specific Twelve Data raw-data caching/retention rights have been examined; it is NOT itself proof of a vendor license. The ChatGPT connected OAuth plugins do not automatically authorize GitHub Actions. GitHub cron timing is best-effort: an hourly schedule is **not** a guaranteed five-minute freshness SLA. The most recent cached M5 can be stale for nearly an hour between polls and must be marked accordingly. The workflow_dispatch trigger is retained for future on-demand ChatGPT-driven refresh; ChatGPT-to-GitHub dispatch is not yet implemented. B1 separate hourly archival cron remains UTC minute :10, so there can be two independent GitHub job runs per hour when both are enabled; the shared mutex serializes cooperating writes. Shared API credits are checked before each API request, but multi-project shared quota and historical correction coverage require independent monitoring.

## Compare P046-B1/B2 and HOT truthfully

| Aspect | P046-B1 sealed hourly | P046-B2 WARM day | P046-B3-A HOT |
| --- | --- | --- | --- |
| History | Immutable 12 native closed M5/hour | Additive full-day group of verified hourly source | Rolling max 24 most recent closed M5 |
| Target cadence | Hourly, UTC :10 | Manual/UTC day | Schedule every five minutes, not activated |
| Drive objects | ~2 new objects per committed hour | Adds 2 new objects per promoted day, does not delete originals | One fixed-name file per symbol, repeated in-place updates |
| Authority | SHA-pinned raw evidence | SHA-linked provenance and day gaps | Research-only, mutable and replaceable |
| Actual raw quote write/readback verified | No | No | No |
| Drive atomic multi-file CAS | No | No | No |

At most ~one HOT object *name* per symbol; 5-minute actual writes and revision storage are not measured or claimed reduced. No real price feed, licensed historical cache, or live trading accuracy metric has been proved by synthetic CI. This does NOT satisfy Issue #82's complete scope by itself.

## Remaining B3-B / C

- Authenticated **synthetic-only** Google Drive staging through the GitHub service-account principal; verify fixed-file update behavior and SHA on two writes, forced crashes and independent subsequent download. Do not claim achieved without exact verified file ID and readback.
- B1 hourly authoritative source–HOT index anchoring, restart and external-writer concurrency tests, bounded long-term Manifest index/checkpoint (existing B1/B2 still scan potentially 12,000 historical objects), and source version-specific retention/revision audit.
- Native H4/D1 alignment, authenticated market-session calendar, bounded backfill on long gaps, at-scale 20-pair credit orchestration, retention/expiry and measured real Drive cost/latency.
- Explicit provider plan rights Gate L and historic executable BID/ASK Gate Q ([Issue #27](https://github.com/ngluonghoa/MFX/issues/27)); first actual vendor raw quote→Drive readback still unverified ([Issue #74](https://github.com/ngluonghoa/MFX/issues/74)). Owner B2/S2 source numeric decisions 0/36 and all official source numeric entry predicates 0/16 ([Issue #45](https://github.com/ngluonghoa/MFX/issues/45)). No broker, no confirmed real BUY/SELL signals, no Mac/MOCHI/local development.
