# MFX A04/P0.71 — Read-only native H4/D1 lag aligned to existing 2m15s source publication guard

Date: 2026-11-11 ICT. This is a **diagnostic correctness** repair with no source API, Drive, scheduling or trading changes.

## Root cause supported by shipped source

P0.59/P0.64 native EUR/USD H4+D1 production writer's `plan_native_fetch` computes the eligible closed candle **only after** `SOURCE_PUBLICATION_BUFFER = 2 minutes 15 seconds`. For H4 it subtracts this from UTC before placing the 4h open on the 00/04/08/12/16/20 UTC grid; for D1 it subtracts from UTC BEFORE converting to Australia/Sydney local calendar date, correctly handling AEDT/AEST DST.

But P0.58 **READ-ONLY** full native source SHA auditor, `tools/run_mfx_native_htf_cache_audit.py`, previously computed expected newest closed H4 from bare `now_utc`, and daily expected last closed Sydney date from bare `now_utc.astimezone(zone)`. Within the first 2m15s after a 4-hour/ Sydney-local calendar boundary, P0.58 would incorrectly mark source-native H4/D1 as lagging even though P0.59/P0.64 rightly withheld provider calls until its conservative publication grace elapsed. This discrepancy is an observation/SLO false positive, NOT evidence that Google Drive or vendor is broken.

P0.64 four-way-gated native writer remains **hourly cron UTC :25**. For a November AEDT Sydney midnight at 2026-11-11 13:00:00Z, the existing D1 source request is not eligible until 13:02:15Z, with the next *intended* writer schedule at 13:25Z UTC subject to GitHub's best-effort scheduling; the exact minute is not guaranteed. At first project read during this continuation, source D1 private Drive still contained 1 native D1 sealed Chunk and 1 Manifest through Sydney-local 2026-11-10/119 bars, and there was no completed due-slot writer run after the 13:17Z P0.70 checkpoint. This is NOT by itself a failure.

## P0.71 exact fix, source read-only only

- Import the **same shared SOURCE_PUBLICATION_BUFFER** used by native writer from `mfx_cache.native_htf_incremental`; never introduce a duplicate constant.
- Within P0.58 `audit_native_cache` compute `publication_safe_utc=now_utc-SOURCE_PUBLICATION_BUFFER`. For H4 use this safe instant for UTC 4h closed-open label; for D1 use `publication_safe_utc.astimezone(ZoneInfo('Australia/Sydney')).date()-1 day`. Never infer a synthetic UTC-open D1 label or a foreign FX market session calendar.
- Preserve full source-native full-bounded SHA/parent chain, strict future/unclosed bar rejection, orphan fail-closed, provenance and zero vendor/Drive/broker effects.
- Add transparent receipt fields `latest_publication_eligible_label`, `publication_grace_seconds=135`, `publication_grace_aligned_to_writer=true`, retaining `lag` and `lag_unit=calendar_days_not_market_sessions` for D1.
- Repair the stale top-level P0.58 audit log claim `no_automated_native_writer=true`, invalid since P0.64 scheduled hourly native writer is operational. Emit `no_automated_native_writer=false`, `this_job_writes_native_archive=false`, `native_writer_schedule_evaluated_here=false`. These indicate the audit has not itself proved any writer ran.
- Unchanged native H4/D1 source writer source quota, actual provider price / usage calls, OAuth, Chunk/Manifest append/sealing, three/four workflow gates, cron schedule and exact private Drive objects; M5, H4 derived shadow P0.65 and weekend diagnostics P0.70 also unchanged. No original frozen Forex 1.0 102 blobs, new source predicate approval, HOT V3 or broker changes.

## Hermetic QA and live acceptance

Add 14 new tests covering exact :02:14 vs :02:15 UTC H4/D1 grace edges, true H4 08:00 due only after 12:02:15 UTC, Sydney Nov11 AEDT local midnight 13Z, April 2026 DST end +10 and October 2026 DST start +11, future H4/D1 rejection before grace, same eligibility as existing `plan_native_fetch`, read-only zero-call summary log and unchanged protected hourly workflows.

Require final PR-head Python 3.11+3.12 complete CI with golden exact 102 frozen Forex original sources, changed MFX-only SHA pins, security/static/wheel parity. Merge only after green and independently validate exact protected main push CI. P0.58 read-only source audit workflow runs every UTC :45 best-effort; future due D1 must be observed separately by **actual** P0.64 four-way-gated scheduled writer + P0.58 FULL D1 SHA source readback, no fake claims from a passing unit test or a D1 lag metric alone.

Remaining MFX owner gates: M5↔H4 source parity 4/4 real exact MID OHLC at P0.70, still need >=30 complete matching H4 over >=7 full days with no interior gaps; do not reduce H4 native cadence without a separately approved PR and rollback. Source-native D1 first true append and private Drive independent SHA proof separately PENDING. The 257–1024 M5 rolling auditor P0.69 is still hermetic-only until archive size grows; source copyright/long-term entitlement independently unverified.

Rollback only the P0.71 read-only auditor+tests+doc and SHA allowlist from approved previous main; source-native writer untouched.
