# M2/P0.2 — Forex Smart Incremental Cache: implementation contract (2026-11-07)

**Status: synthetic pure-core PARTIAL IMPLEMENTATION. Real FX data fetching, persistent cache storage, approved provider rights, live analyses, paper/backtest and scheduled refresh are NOT implemented.** This deliberately reuses the five logical cache tiers designed for Swing Trading 1.8, with Forex-specific quote-side and temporal constraints, but does not copy its stock-only VNINDEX, corporate-actions, T+2 or native stock volume semantics.

## 1. User outcome: check every ~5 minutes without downloading old history

A) Cold start: qualify the provider/entitlement + choose instrument/product/timeframes/side, then, **once separately authorized**, collect a bounded initial history. Current code returns BOOTSTRAP_NEEDED and does not fetch.

B) Recheck after 5 minutes: for each pair/product/side/timeframe, validate cached version and source claim, then:
- Trusted externally authenticated remote revision/head unchanged and sufficiently fresh: no old-history data fetch *may be planned*. Current code returns REUSE_HEAD_CLAIM with source_claim_authenticated=false and may_fetch_real_data=false. It is **not** production-safe permission to skip checking.
- No independently verified change token: plan one **small bounded range**, starting at a configurable number of recent CLOSED candles (default not fixed in code: example overlap 2) and including newly closed bars; do not request the whole history. Real source connector must honor and log the requested range rather than silently calling full history.
- Unknown entitlement, unsupported bounded endpoint, source failure, ambiguous correction or missing initial history: STOP/BLOCK/UNVERIFIED. No hidden network fallback to full re-download.
- No assumption that "no candle closed since last poll" proves the provider has not revised an older candle. For sources lacking reliable revision support, overlap reconciles recent changes and a separately approved slower history audit is required for older silent corrections.

Forex candles may close on provider-defined clocks. Do **not** assume D1 fixed 24 hours across DST, universal Sunday bars, broker parity, or exact M5/MTF boundaries without vendor calendar/aggregation policy.

## 2. Five levels and versioned invalidation

| Level | Current implementation | Future planned data |
| --- | --- | --- |
| L1 candles / source | \`CachePartition\`, \`CandleSnapshot\`, \`plan_incremental_refresh\`, \`reconcile_closed_delta\` | Real licensed source adapter, revision/changetoken, controlled encrypted persistent storage |
| L2 indicators | Typed DAG, \`ema_full\` and \`ema_recompute\` **reference only** | EMA/RSI/ATR/MACD/ADX with versioned causal checkpoints/warmup and native broker price-side input |
| L3 structure | DAG invalidation only | causal pivots, HH/HL, BOS/CHoCH, range, higher-TF dependencies |
| L4 signals | DAG invalidation only | approved B/S zone detectors, early/confirmed state and dedup; no actual predicates yet |
| L5 audit/history | DAG invalidation + fingerprints | eight-stage verified audit, report/history, source errors, cache metrics and controlled immutable publication |

Full L2–L5 data cache stores are **NOT implemented**; only dependency contracts exist. An L5 cache hit cannot auto-mark the eight pipeline stages COMPLETE without revalidation.

Dependency graph is explicit, node IDs identify per-pair/per-timeframe product lineage. A EUR/USD M5 change should not invalidate all other pairs; only explicit cross-pair currency-strength/correlation dependencies may propagate. A source revision at bar *t* makes EMA/RMA/ATR/RSI recursive tails dirty from the nearest verified checkpoint preceding *t*, while rolling windows/pivots must honor indicator-specific lookbacks and right-bars. The current EMA function demonstrates FULL == INCREMENTAL for append and historical revision with deterministic Decimal; it **does not** certify other indicators.

## 3. Immutable source and cache identity

Cache partition fingerprint includes provider_id, opaque broker product reference (no raw account numbers), instrument version/pair, BID/ASK/MID, timeframe, vendor calendar & aggregation version, source timezone policy, rights policy ref and cache schema version. Candle fingerprint additionally covers closed candle timestamps, BID/ASK and revision/provenance/OHLC/quality. Hashes are reproducibility keys, **not signed proof of source rights**.

Never merge price sides, provider streams, broker account products, differing calendar or aggregation versions. MID can remain a separate reference input but must not silently substitute for the native executable BID/ASK basis. The linked M2/P0.1 source-qualification gate keeps real historical rights / cache / backtest **blocked**.

OPEN/provisional bars are transient separate overlays; reject any attempt to persist them as verified CLOSED. Fail closed on future-known, wrong partition, incomplete, unverified, duplicate or overlapping bars. Native M15 is the default source for early/confirmed design and M5 remains conditional; a cache result does not promote a signal.

## 4. Delta reconciliation and corrections

One immutable old snapshot + bounded closed-candle delta → changed set classified NO_CHANGE / APPEND / REVISE / APPEND_AND_REVISE with earliest dirty UTC. Changes to historical bar require a strictly newer revision number **and** first-known timestamp; the old snapshot is not mutated. No deletion is inferred from missing entries in a possibly partial provider response; a future explicit authoritative deletion/tombstone contract is needed. The in-memory snapshot rejects resource overflow rather than silently deleting older evidence. Incremental history must be audited for silent older corrections that lie outside the requested overlap.

Source version/correction invalidation must eventually propagate L1 → affected L2 → L3 → L4 → L5 only for proven dependencies. Cache policy/error/cancel/restart must retain old verified immutable versions and never equate LAST_KNOWN/STALE with fresh CONFIRMED trade signal.

## 5. Example request at ~09:00 / 09:05 / 09:10 / 09:15

- 09:00: a *separately approved* bootstrap for EURUSD BID+ASK M5/M15/H1/H4/D1 with explicit source cutoffs and revision manifests. No such approval or actual fetch exists now.
- 09:05: ask only the source's delta range beginning at the recent overlap boundary (or check a properly authenticated remote revision token); do not re-download unchanged years of D1/H4 history.
- 09:10: append new M5, reuse valid M15/H1/H4/D1 and their indicators where dependencies/freshness permit; replay only affected descendants.
- 09:15: when source-defined M15 closes, update its own BID and ASK history, EMA/structure/signals using source-close causal stamps, not a universal UTC clock guess.

For a 20-pair scan, every pair has an isolated namespace and shared-data dependencies **only when explicit**; schedule bounded concurrent requests under actual vendor quota and return source error report. Do not promise 20-pair performance until measured.

## 6. Acceptance gates and nonclaims

1. Synthetic tests: no-change fingerprint reused; bounded overlap vs full history; append/revision/incomplete/open/mixed provider/side/future-known/duplicate/overflow; source head claim does not grant authority.
2. L1–L5 dependency tests: EURUSD invalidation does not poison GBPUSD, rule/parameter changes affect L4–L5, report version changes only L5, source revision flows L1–L5, audit always rechecks.
3. EMA append & revised-history suffix recompute must be bit-for-bit deterministic Decimal equal to FULL for validated preceding checkpoints.
4. Future before release: deterministic full-vs-incremental for EMA/ATR/RSI/MACD/ADX and all 18 label states; persistence/restart/rollback/corruption/entitlement revocation; monitored cache hits, fetched bytes/calls and wall clock; provider-specific local business-day/session/DST correctness.
5. No approved persistent store currently. Google Drive holds canonical documentation; GitHub holds code; neither may be used as an accidental licensed price data cache. MOCHI is optional only with separate approval and compliance controls. No unauthorized M15001.

**Meaning:** This PR implements *only* the in-memory data/delta planner and synthetic reference for dependency/EMA arithmetic. It does not autonomously poll every five minutes, skip remote history based on authenticated provider evidence, retain bars across ChatGPT sessions, or certify data rights. These are separately staged M2/production tasks.
