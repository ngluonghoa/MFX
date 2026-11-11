# MFX A04/P0.75 — Bounded native V2 cross-shard SHA chain (offline QA only)

**Disposition: RESEARCH_ONLY / NO_LIVE_STORE / NO_SHARD_ACTIVATION.**

P0.74 established an inert V1→V2 namespace and a proposed SHA anchor; it did **not** build a sharded archive, prove trusted external anti-rollback or change any native H4/D1 writer. P0.75 adds a pure plan/audit model and 24 hermetic tests. This model is designed to find data-loss and integrity hazards before considering a separately approved real Google Drive adapter.

## Model

- Native source scope remains EUR/USD Twelve Data composite **MID**. H4 candles use UTC 00/04/08/12/16/20 four-hour opens. D1 uses **Australia/Sydney local session dates**, not artificial UTC D1 labels; publication grace remains **135 seconds**.
- A V2 proposal is accepted only after a caller presents a V1 metadata state with exactly 256 matching Chunk/Manifest counts, no orphan and a matching V1 tail SHA. Fake 256-tail fixtures deliberately do **not** attest a real 256-object archive.
- All V2 records have an immutable canonical chunk SHA, immutable manifest SHA and explicit parent SHA. The first V2 record is anchored to the P0.74 proposal digest; the first record of each new shard binds the **previous shard tail manifest SHA**. Shard ordinal and global ordinal are independently recomputed. V1 and V2 namespace prefixes cannot collide.
- Pure append planning re-verifies every supplied prior V2 pair from origin to tip before building a candidate, rejects overwrites and nonmonotonic labels, and never performs a network, Drive or broker operation. The read-only verifier recomputes all supplied chunk/manifest bytes, names, parent links and cross-shard bridges.
- The *research-only* bounds are 64 append pairs per shard, 8 shards total. Hermetic tests use smaller shard capacities (1 or 2) to force cross-shard rollover. These bounds are **not** an accepted production scaling policy.
- The V2 audit requires a **caller-supplied expected tail SHA**. A shorter consistent chain can still pass if the caller substitutes a corresponding shorter tail. Thus "full supplied chain verified" does **not** mean a trusted external anti-rollback witness or trusted recoverable head.
- P0.75 does not claim a source-session calendar; missing real market sessions are neither auto-filled nor automatically waived. Its batch is prevalidated source-native historical OHLC, and its due-clock checks are conservative; no independent provider entitlement is established.

## Explicitly not implemented

This code is **not** a Google Drive reader/writer; there is no atomic conditional CAS, no durable trusted root witness, no multiwriter lease/fencing token, no restart-safe partial Chunk/Manifest repair, no production schedule, no Cloud folder creation and no real V1→V2 data migration. The legacy H4/D1 256-file cap remains strict and **must not be raised** by this change. HOT V3 and numeric BUY/SELL, licensed retention rights and broker/trading permissions remain unchanged.

## Acceptance and rollback

Evidence must include a complete latest-PR-head CI PASS on Python 3.11/3.12, frozen original Forex 102-blob/golden parity, strict static/security/dependency checks, cross-Python wheel, protected-main commit, independent exact-main CI and SHA-pinned MFX-only delta entries. The only rollback is reverting these added offline files and their allowlist entries; existing cloud data and schedules never change.

**Next separately gated delivery:** isolated Google Drive V2 adapter and read-only full-chain retrieval, external independently stored trusted tail-anchor policy, concurrency/CAS-or-fail-closed proof, crash-injection/restart/orphan reconciliation, backups and rollback acceptance. Do not enable V2 in production or reduce H4 native requests without separate owner authorization. M5→H4 needs 30+ fully matching H4 windows over >=7 days and real session-gap research; it continues in parallel.
