# MFX A04/P0.51 — bounded hourly Cache V2 recovery

Status: **STAGED until GitHub PR CI/main CI and real scheduled writer receipts are observed**. This change only touches cloud tooling, tests, source delta manifest, and documentation; the frozen Forex Trading 1:1 model remains unchanged.

## Problem and evidence

- The first real MFX OAuth/Twelve Data EUR/USD M5 12-bar hourly B1 chunk+manifest commit succeeded on Actions #42882112799 for **2026-11-10 18:00 UTC**.
- An independent read-only audit on Actions #42884727473 returned `MFX_A04_P50_READONLY_DRIVE_CACHE_AUDIT_PASS` with one Chunk, one Manifest, 12 closed M5, no vendor calls, and no mutation.
- Before this change, `tools.run_a04_p46_cloud_batch_cache` used the B1 engine with actual `now_utc` and could commit only the latest full previous hour. Missing older hours inside the vendor 120-candle result would be skipped.

## Design / sealed data discipline

- Keep the existing `twelve-data-cache.yml` schedule at **UTC minute 10 each hour**, the dual `MFX_REAL_CACHE_ENABLED` + `MFX_V2_BATCH_CACHE_ACCEPTED` gates, GitHub concurrency, OAuth Drive app-owned folders, and the vendor quota preflight.
- Keep **one** Twelve Data `time_series` call per due workflow invocation, requesting at most 120 M5 records with `timezone=UTC`.
- New pure planner `tools/mfx_hourly_catchup.py`: select **at most four** eligible, *complete* 12-bar UTC hours within that response, oldest-first, strictly after the latest sealed Manifest and no newer than the immediately preceding full UTC hour.
- Preserve initial bootstrap behavior: when no Manifest exists, only commit the most recent full UTC hour, not the entire vendor history.
- For each selected historical hour, invoke the unmodified, existing immutable B1 `commit_hour` two-object writer with an as-of time of **hour close + 5 min**. The as-of time cannot be later than the real action clock. This preserves the existing B1 SHA, parent-link, derived M15/M30/H1 and readback constraints.
- Existing orphan chunk recovery still runs **before vendor calls**. If an orphan was recovered, exit without additional provider calls.
- Partial or absent UTC hours are skipped, **never filled/synthesized**. If a later complete hour exists, the B1 engine records `MISSING_PRIOR_HOURS_UNVERIFIED`, retaining explicit gap information.
- No editing/deletion of previously sealed Chunk/Manifest. No Drive multi-file atomic CAS is claimed. MFX remains research-only; user BUY/SELL signals and broker orders are unchanged and unapproved.

## Hard limits and operational behavior

- Bounded catchup: **up to 4 hours** (48 original M5 bars, plus MTF derived bars) per invocation, at most 8 new Drive JSON objects for four batches.
- Bounded provider response: at most **120** M5 records, approximately ten hours of trading data. Longer gaps, holidays, weekends, provider outages and missing bars are **not guaranteed recoverable** by this one-call mechanism.
- One provider call may yield zero complete hours, logging `NOT_DUE_OR_INCOMPLETE_HOUR`; do not treat that as a successful cache write.
- Jobs can be delayed by GitHub, so an audit at :35 may legitimately report lag. Weekend/session calendar remains unspecified, and a lag warning is not proof of an infrastructure fault.
- Quota threshold (previous P0.49 fix) remains in effect; no real vendor request occurs when usage exceeds safe headroom.
- Since market candles here are Twelve Data **MID**, data is not an executable BID/ASK feed and does not establish correctness/approval for numeric FX strategy signals.
- Rights to retain/cache provider data have not been independently verified; that fact is not represented as an approval in any receipt.

## Acceptance sequence

1. GitHub PR CI: Python 3.11, 3.12, wheel parity and the 19 new recovery regressions all PASS.
2. Protected `main` merge, then a separate successful main-push CI.
3. Read the next scheduled hourly writer logs (no manual dispatch necessary) for `committed_batches`, `committed_hours_utc`, `m5_bars_total`, `vendor_price_requests=1`, and `broker_orders=0`.
4. Read independent Google Drive Chunk/Manifest folder metadata; confirm each new hour is unique and its SHA name matches content.
5. Run or inspect the `mfx-hourly-cache-audit.yml` no-vendor read-only receipt (UTC :35), confirm continuity and zero broker orders.
6. Only mark **multiple contiguous live hours** PASS if actual newly sealed consecutive hours have been observed and parent hashes agree. Do not infer this from CI or first-hour-only data.

## Revert

Revert the PR through protected GitHub governance, leaving the sealed Google Drive objects untouched. Either real-cache gate can be disabled if a source-integrity problem is detected. No Mac, MOCHI or local compute is required.
