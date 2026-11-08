# M2/P0.4 — Synthetic Forex 5-minute 20-pair sweep and source first-seen custody

**Classification: deterministic fixture COUNTERS, not measured provider/API bandwidth, latency, real data/cache readiness or profitable trading.**

## Engineering scope

Extends DEC-FX-020 (five-level Forex Smart Incremental Cache), Spec v0.9 §24, after M2/P0.3 synthetic provider delta / storage proposal review.

### A. Repeat-scan synthetic workload

`src/forex_trading/synthetic_scan_workload.py` accepts typed in-memory `CandleSnapshot` baselines and complete synthetic *oracle* snapshots; checks only BID and ASK partitions are present per provider/product/pair/timeframe/calendar/version; rejects duplicate partitions, future oracle, missing side and wrong input type. Reuses the actual M2/P0.2 `plan_incremental_refresh` and `reconcile_closed_delta` implementation; does NOT replace production source fetching.

The fixture comparison reports:

- `baseline_naive_full_history_rows`: counterfactual number of historical candle **rows** if each stream were fully refetched once; not actual bytes.
- `planned_bounded_range_queries`: pure planned bounded source queries, not actual HTTP calls.
- `simulated_returned_bar_rows`: number of rows selected from the fixture oracle within the requested overlap+delta range, not actual network bytes/API quota.
- `simulated_head_claim_reuses`: proposed skip decisions using caller-supplied, **unverified** remote head claims. These skips are *not authorized* for real market data.
- `old_cached_rows_retained`, appended/revised counts, earliest dirty time per stream and `UNSEEN_HISTORY_CORRECTION` mismatch flags.
- `actual_http_calls=0`, `actual_http_bytes=0`, `actual_elapsed_ms_measured=False`, `may_run_real_scan=False` **by design**.

#### Representative deterministic fixture, NOT measured savings

20 synthetic pair identifiers × BID/ASK × M5/M15/H1/H4/D1 = **200 partitions**, 8 closed cached bars per partition. For one synthetic 5-minute step, only M5 produces one new bar on each quote side: 40 new bars across 20 pairs. Two-overlap policy:

| Scenario | Full-history counterfactual rows | Bounded planned rows | Planned requests | Notes |
| --- | ---: | ---: | ---: | --- |
| Fresh claimed head for unchanged M15/H1/H4/D1, changed head for M5 | 1,640 | 120 | 40 | 160 streams claim unchanged (not authenticated). **1,520 fewer synthetic rows** than counterfactual, NOT a real API gain |
| No head/revision evidence at all | 1,640 | 440 | 200 | Recheck two closed bars in each unchanged stream; no automatic full redownload |
| Silent correction outside overlap and unmodified claimed head | Fixture detects `UNSEEN_HISTORY_CORRECTION` | Insufficient | Depends | The *synthetic oracle* reveals the gap; production cannot see unqueried old revisions |

These counts depend on synthetic structure (8 cached rows/stream), invented closed times, and claimed change heads. The 97%-like reduction implied by row counts must **not** be represented as real bandwidth savings, runtime acceleration, latency, source correctness, provider support or quota. The public provider may not expose a reliable change token at all. Vendor request billing, metadata checks, paging, corrections, continuous/open bars, broker sessions and rights are unverified.

The fixture treats H4 and D1 as simplified fixed-UTC intervals only to exercise cache key separation; **not a valid real Forex daily rollover/DST/calendar**.

### B. Causal first-seen-by-us source receipt chain

`src/forex_trading/synthetic_source_custody.py` creates a local-only immutable SHA-256 parent-linked record: partition, vendor revision/event timestamp **claims**, actual simulated observed timestamp, **first-seen-by-us** UTC, payload SHA-256 claim, ordinal and previous digest.

- Strictly prevent first-seen being earlier than observed, vendor claim being future of observation, decreasing local observation/first-seen clocks, partition fork, same vendor revision with changed payload, invalid digest, generation skips, parent tampering or inconsistent as-of chain.
- `select_synthetic_receipt_asof` uses **our first-seen clock** at decision time. A source publishing an older candle with a retroactive vendor clock cannot turn a late correction into information the system had in the past.
- Hash-chain integrity is **local tamper-evidence, not authenticity**. A malicious party able to rewrite the whole chain and its trusted anchor may forge consistent hashes; vendor signature, external immutable anchor, licensing and source provenance remain unresolved.
- `assess_synthetic_custody` always returns independent vendor signature, retention rights and real Backtest permission as **false**.

### C. Operational and rights gates NOT implemented

1. Contractually eligible provider/account/jurisdiction and independent license evidence covering raw+derived price, incremental cache, replay and internal Backtest.
2. Real vendor adapter with bounded range, native BID/ASK completeness, no silent full-reload, pagination, retries/rate limits/quota metrics and direct verified source revision or scheduled historical reconciliation.
3. Timeframe D1/H4/W1 provider-aligned session/DST audit and first-known-of-closed event semantics.
4. Secure encrypted durable cache with chosen host/ACL, atomic writes and tested checksum/corruption, restart, source revocation and rollback; no raw prices in GitHub or transient ChatGPT Python.
5. Full indicator suite and structure/zone/report L2–L5 cached semantics, deterministic full vs incremental validation on qualified data, 18 zone states, strategy/SL/TP/backtest/OOS acceptance.
6. Real 20-pair warm/cold repeat-scan test with **actual** API calls, provider billed units, bytes transferred and wall-time measured within approved quotas.

**No OANDA connection or real FX data requested in this work.** No hourly background automation, actual 5-minute poll, user broker order, M15001 or MOCHI use. Github repo remains private; QA/Handoff snapshots are independently controlled.
