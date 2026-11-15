# MFX P0.168 — resume H4 native Cache with strict D1 source quarantine

Date: 2026-11-15 ICT. Existing owner-approved cache schedule preserved; no new vendor calls, Drive price objects, API grants, cron, secrets, broker execution or original Forex source edits.

## Observed actual production failure

On current protected main P0.167, latest scheduled native H4+D1 writer [run 43684513528](https://github.com/ngluonghoa/MFX/actions/runs/43684513528) FAILED on the **D1** original source SHA overlap 2026-11-11. The 1/16 numeric OHLC difference matched immutable original SHA and full old-raw-audited forensic witness; no D1 writes occurred. Existing full H4+D1 archive audit [run 43685865133](https://github.com/ngluonghoa/MFX/actions/runs/43685865133) PASSED old SHA history but showed H4 last 2026-11-12 08:00 UTC (16 four-hour calendar slots behind) and D1 last Sydney 2026-11-11 (3 calendar days behind). This is lag, not automatically missing market sessions. Actual independent M5 writer [run 43683199575](https://github.com/ngluonghoa/MFX/actions/runs/43683199575) committed one hourly batch of 12 closed M5 bars for source hour 2026-11-15T04:00:00Z, preserving existing user-authorized hourly M5 cache.

Root of H4 stall: current existing **all-scopes prepared-before-commit** loop requires H4 and D1 source overlap both clean. It verifies H4 first, then D1 and throws before H4 was saved. This couples valid H4 continuity to an unrelated known D1 price-restatement HOLD.

## Narrow source-preserving remediation

Existing hourly P0.64 source writer remains the single workflow and four-way authorization, original common Drive lock and quota policy, source SHA preflight, existing provider calls, existing two-object SHA/parent readback writer and schedule. A tiny P0.168 **conditional isolation** allows H4 to commit through the **unchanged** SHA-safe `commit_native_batch` ONLY when ALL conditions hold:

- BOTH old H4 and D1 archives passed full SHA/parent preflight with zero orphan and bounded append capacity.
- H4 independently passed existing provider SHA overlap validation, immutable sealed proposal, and has actual new CLOSED bars to commit. A missing/stale H4 or H4 revision never passes as a new batch.
- The **real** D1 old recent raw rows are full-SHA-verified from the unchanged audit read-through witness, and the existing already-fetched D1 provider batch differs numerically at **only Sydney local D1 2026-11-11**, 1/16 changed, 15 unchanged, 0 missing; vendor revision cause is still UNKNOWN, no new GET or vendor request by forensics.
- The D1 quarantine is exactly `P059_SOURCE_NATIVE_REVISION_QUARANTINE`; any different source mismatch (including 2026-11-12 revisions, missing archived SHA index, mismatch in H4, inconsistent forensic counts or forged scope) continues to hard STOP before any write.
- An additional full native archive audit of **both** H4 and D1 shows neither parent changed during fetching. If either changed, STOP.
- Then and only then commit **H4 only** with its original immutable Chunk+Manifest and readback; D1 commit is never called. Log redacted H4 success counts / D1 zero writes / source HOLD, then raise the original D1 quarantine to leave the GitHub job **nonzero/red** and avoid a misleading joint H4/D1 success.

This is NOT a D1 source restatement, D1 backfill, D1 owner approval, legal validation, new source namespace, rolling HOLD clearance, or BUY/SELL release. Existing M5/H4/D1 archive bytes preserved and no price data appears in GitHub logs. Real H4 append must still be confirmed by subsequent natural scheduled job + read-only full SHA audit; a synthetic CI PASS does not prove a real H4 write.

## QA, rollback and remaining release gates

Offline tests for known incident proof and stale/forged input, D1/H4 SHA revisions, parent races, quota gate, no D1 mutations, redacted receipts and preserved job failure. Require full exact PR/head and postmain Python3.11/3.12/frozen Forex and wheel CI, then observe actual scheduled H4 append and new SHA audit independently. Rollback only this small MFX writer change/new test/doc SHA ledger entries; preserve original sealed D1, #147 OPEN, Source HOLD and signal NO_SIGNAL/UNVERIFIED. #27 exact account-specific rights still not externally verified but this patch does not change existing approved cache mechanism/usage.
