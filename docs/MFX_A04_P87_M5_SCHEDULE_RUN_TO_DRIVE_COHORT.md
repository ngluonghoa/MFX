# A04/P0.87 — Real M5 scheduled-run → Drive-manifest latency evidence (RESEARCH ONLY)

## Scope and observed UTC evidence, 11–12 Nov 2026

MFX's existing hourly M5 writer is .github/workflows/twelve-data-cache.yml, cron 10 * * * * in UTC, cooperative concurrency group mfx-twelvedata-private-cache, cancel-in-progress=false. Existing tools/run_a04_p46_cloud_batch_cache.py uses 5-minute candle-close grace and bounded plan_bounded_catchup, up to four exact 12-M5 hours from a single vendor fetch. Neither the workflow nor production cache writer is changed in this milestone.

Twelve already completed scheduled M5 Actions runs were inspected independently using GitHub API run metadata and original job logs, then cross-checked against private Google Drive immutable M5 manifest-name and file creation metadata. These 12 runs report one provider-price request each, and correspond to 14 observed complete M5 hourly batches in uninterrupted sequence 2026-11-11T14:00Z through 2026-11-12T03:00Z. Two separate catchup runs committed two hours each: #43105022518 (19:00 and 20:00 UTC) and #43133264975 (23:00 and 00:00 UTC). Neither a complete OHLC market history nor a causal explanation is proved by filename metadata.

### Exact per-run ledger (all dates UTC)

| Actions run | Run created UTC | Committed hour(s) from job receipt | Drive manifest created UTC |
| --- | --- | --- | --- |
| 43158866760 | 12-Nov 05:04:06 | 12-Nov 03:00 | 12-Nov 05:04:29.852 |
| 43151652891 | 12-Nov 03:58:01 | 12-Nov 02:00 | 12-Nov 03:58:23.357 |
| 43144695651 | 12-Nov 02:55:29 | 12-Nov 01:00 | 12-Nov 02:55:50.051 |
| 43133264975 | 12-Nov 01:15:37 | 11-Nov 23:00; 12-Nov 00:00 | 12-Nov 01:15:59.054; 01:16:10.893 |
| 43123068939 | 11-Nov 23:52:12 | 11-Nov 22:00 | 11-Nov 23:52:30.321 |
| 43115786422 | 11-Nov 22:55:44 | 11-Nov 21:00 | 11-Nov 22:56:04.349 |
| 43105022518 | 11-Nov 21:39:50 | 11-Nov 19:00; 20:00 | 11-Nov 21:40:14.949; 21:40:26.199 |
| 43092969245 | 11-Nov 20:03:55 | 11-Nov 18:00 | 11-Nov 20:04:12.030 |
| 43082949666 | 11-Nov 18:59:30 | 11-Nov 17:00 | 11-Nov 18:59:50.977 |
| 43073227903 | 11-Nov 17:58:13 | 11-Nov 16:00 | 11-Nov 17:58:29.330 |
| 43063687329 | 11-Nov 16:59:19 | 11-Nov 15:00 | 11-Nov 16:59:57.138 |
| 43053200735 | 11-Nov 15:55:42 | 11-Nov 14:00 | 11-Nov 15:56:01.047 |

All runs are directly traceable at https://github.com/ngluonghoa/MFX/actions/runs/ followed by the ID. Latest main before P0.87: d61fe9ecb7c4214699f3d027e17fabada42a3b63. The existing P0.86 independent FULL 33-pair SHA archive proof through M5 02:00 UTC remains separate: the newly observed 03:00 M5 manifest is NOT included in the previously authenticated 33/33 SHA scan, and this P0.87 exercise is NOT a substitute.

## Derived observation, never scheduler-cause attestation

The first theoretically eligible hourly cron tick for one batch is hour-open + 70 minutes (hour-close + 10 minutes), reflecting cron :10 and candle-close +5-minute grace. But GitHub REST run metadata does NOT establish which actual scheduled event tick created a given run. A run created during the next hour can be delayed from an earlier tick and can commit a later eligible batch. Treat this time difference solely as a comparison baseline.

Across 14 observed batch events, the following were calculated from verified source metadata, not from price candles:

- Run-created relative to the batch's first theoretically eligible cron tick: median **48.12 minutes**; range **+5.62 to +89.83 minutes**.
- Real private Drive manifest creation relative to that batch-hour closing time: median **58.44 minutes**; range **+16.18 to +100.25 minutes**.
- Manifest creation relative to GitHub run creation: median **21.6 seconds**; range **16.3 to 38.1 seconds**.
- 12 successful scheduled runs, 14 observed manifests, 2 two-batch recovery runs, 12 writer-reported provider-price requests, zero gaps within this 14-hour observation cohort.

The much longer observed pre-run-creation interval compared with run-to-manifest seconds makes pre-run dispatch/schedule timing an important research target. However it is NOT sufficient to identify GitHub internal event latency, runner queue, concurrency wait, provider publication, provider license scope, or a specific dropped schedule event as root cause. Official GitHub documentation says scheduled events can be delayed under high Actions load (and some queued jobs can be dropped), but that is a general known possibility, NOT verified cause for this project: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows .

## New pure code and QA / hard safety boundaries

New tools/mfx_m5_scheduler_cohort_evidence.py receives a bounded tuple of immutable externally supplied scheduled-run receipts with batch hours, manifest names and Drive creation timestamps. It enforces strict UTC clocks, exact SHA-shaped manifest name/slot, no fake run event or writer status, no orphaned duplicate run/hour, no future unclosed batch, no pre-run manifest creation, <=4 batches per run and bounded vendor-request counts. It reports actual observed gaps; does not synthesize missing M5 bars. A negative theoretical-tick offset is permitted when a delayed previous run legitimately creates a batch after close+5 minutes; that must NEVER be described as a GitHub cron firing early. Returned evidence flags always deny proven scheduler/queue/provider cause, real FX session calendar, independently verified full SHA, H4 cutover, live V2, user signals or broker execution.

New tests/test_a04_p87_m5_schedule_cohort.py includes 30 hermetic positive and negative tests (with sanitized actual timestamps and FAKE SHA-shaped test filenames, NOT actual cryptographic Drive attestations). No vendor, HTTP, Drive write, secret, new cron, source Forex baseline, native H4/D1 production cache, numeric trading or broker change.

## Next owner-gated investigation

P0.88 may design additional provider-free read-only timestamp instrumentation to correlate an authenticated GitHub event schedule identity, queue/concurrency, and end-to-end closed M5 availability, but any modification to live workflow/cron or secrets must be separately owner approved. DO NOT change the existing M5 writer schedule merely on this statistical observation. The previous 33/33 full SHA result, 7/7 native H4 parity, and source H4 NO-GO (requires >=30 exact complete 48xM5 H4 windows over >=7 calendar days with market-session validation and owner approval) remain in force. Australia/Sydney D1 stays native. ChatGPT hourly development task remains DISABLED; GitHub production M5/H4/D1 schedules remain independently enabled. Cloud-only GitHub/Google Drive, no local Mac/MOCHI.
