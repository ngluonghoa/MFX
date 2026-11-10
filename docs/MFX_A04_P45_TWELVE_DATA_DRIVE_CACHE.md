# A04/P0.45 — Cloud-only Twelve Data → private MFX Google Drive incremental Cache

Status: **IMPLEMENTED INFRASTRUCTURE, NOT YET ACTIVATED OR LIVE-READBACK VERIFIED**. User explicitly directed MFX to reuse previous Twelve Data caching practice. Exact source Forex 1:1 original 18 / MFX 22-zone design and approved numeric source strategy gates unchanged. User wants Forex analysis and BUY/SELL information, never broker execution.

## Previous project evidence versus MFX

A separate project FX 2.0 / FX 2.0.10 had proven Google Drive readback of four cache archives containing 120 frames on 2026-11-04, with 120/120 SHA256 verification. That proof is about storage/integrity, not proof of live Twelve Data API capture or the current subscription's third-party cache license. MFX must be independent and never read from Mac/MOCHI or depend on another project's runtime. MFX Google Drive cache staging has already been created; use MFX-only private folders.

## What P045 actually supports

- **One symbol initially: EUR/USD** (5min composite MID technical OHLC). Request URL deliberately pins `timezone=UTC`; Twelve Data otherwise defaults Forex to `Australia/Sydney`. Reject naive timestamps, unexpected symbol/timeframe, malformed OHLC, duplicate or future/open bars. Keep only CLOSED bars with minimum 15 seconds closure grace.
- **Incremental only**: first request max 120 M5 rows, later requests max 16 rows; overlap bars are SHA256-checked, changed already-closed bars fail closed for quarantine (never silent history rewrite). No new bars => no raw chunk; permit a tiny manifest to register already-consumed provider API credit.
- **Cloud storage**: private Google Drive folder for immutable content-addressed JSON delta chunks, separate append-only JSON manifests with previous SHA256 links, exact provider/symbol/side/timezone, last 120 bar SHA256 index, UTC day credit counter, last poll slot and cumulative counters. After every new file upload, the Google Drive API is queried again and canonical JSON compared for readback, not just upload status. No raw quotes/keys in GitHub public source or logs.
- **Scheduled pipeline**: `.github/workflows/twelve-data-cache.yml` scheduled every 5 minutes plus manual dispatch, read-only GitHub checkout, concurrency mutex, one EUR/USD M5 request per run when activated. ~288 M5 calls/day before provider cost differences, separate conservative MFX local credit cap default 400/day, and provider `/api_usage` check with 10-credit headroom. If another app uses the same account, MFX's local ledger cannot reflect their spending, so provider usage is rechecked. GitHub cron can be delayed and is not a precise 5-minute market clock.
- Separate existing MFX Drive folders: manifest/index `1mwYFXWoxSC-R4opm23-5VQKaz1xQazDc`, immutable raw delta chunks `1cmq6oOb3NB7jQdeua_wcRnmrhERhFkLQ`, audit/quarantine `1BTIxWq9-U5sSE4n8KZR9o42zmIYkfAb0`. No other-project Drive cache folders reused.
- **Not implemented by this phase**: H4/D1 provider-native, M15/M30/H1 exact M5 aggregation, shared quota for 20 pairs, real quote BID/ASK, OOS, derived indicators, retention policy enforcement and confirmed user signal delivery. Those require separate controlled milestones. No original source/forex_trading modifications.

## The only remaining activation prerequisites

The ChatGPT Twelve Data MCP OAuth connection **does not transfer authentication** to GitHub Actions. ChatGPT's Google Drive connection likewise does not give a GitHub workflow access to Drive. These are separate principals.

GitHub repository Settings → Secrets and variables → Actions:

1. Add secret `MFX_TWELVE_DATA_API_KEY` (an actual Twelve Data REST API key; never put it in public Issues/Docs/chat).
2. Add secret `MFX_GDRIVE_SERVICE_ACCOUNT_JSON` (Google service account JSON key, private). Share the **two MFX cache subfolders** above with the service account `client_email` as an authorized writer. No Mac/MOCHI/local environment involved.
3. Optional repo variable `MFX_TD_DAILY_CREDIT_CAP` (default `400`, valid 1–720).
4. **Only after valid credentials and folder permissions**, set repository variable `MFX_REAL_CACHE_ENABLED=true`; the scheduled job then runs. Until then the workflow is registered but its job is intentionally skipped, and it would be false to claim a real Drive cache write.

No secrets or vendor license approval were available in the engineering session to configure or run the GitHub principal. The connected Twelve Data plugin was used for one read-only EUR/USD M5 query (table output had Sydney local timestamps, not storage-ready UTC); direct Google Drive cache folder readback confirmed existing three subfolders; no real market data was written by this P045 PR. Any future change to registered job activation must be read back with source quote time, Drive chunk ID, canonical content hash, manifest, quota and fresh subsequent delta.

## Licensing and scope caveat

The **user authorized engineering and storing Cache**. That consent does not by itself attest third-party contractual rights. Twelve Data public terms (2026-01-01) §2.3(g) and §16 bound raw market data retention to actual subscription terms and provider-specific permission; account/tier-specific indefinite Google Drive storage rights remain unverified. Until separately established, do not claim unlimited archival rights; implement a retention/expiry policy before broad long-term deployment. The current code stores no data while the activation flag is absent, rather than silently using connected ChatGPT OAuth tokens. Issue #27 Gate L is operationally approved for engineering but provider-license evidence remains open; economic/as-of BIDASK Gate Q remains open. Source owner numeric B2/S2 0/36 (#45) and all MFX source numeric entries 0/16 remain unapproved. No alerts, no broker orders, no live release.

References: [Twelve Data Forex timezone](https://support.twelvedata.com/en/articles/5745849-timezones), [Twelve Data Terms](https://twelvedata.com/terms), MFX Issue #27 and #74.
