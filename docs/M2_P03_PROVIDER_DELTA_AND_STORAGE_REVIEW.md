# M2/P0.3 — Forex provider delta adapter contract and durable cache review

**Status: SYNTHETIC FIXTURES / READ-ONLY DESIGN AND CODE. No provider API call, no token, no market candle ingestion, no persistent database and no automatic scheduler.**

## Scope

Continuation of user-approved DEC-FX-020 / Forex Master Spec v0.9 §24: minimize repeated historical fetches during on-demand ~5-minute scans while preserving correct BID/ASK, late corrections and immutable audit. These contracts use an **OANDA v20 response *shape* as a reference**, but do not connect to OANDA, enroll an account, sample licensed history or assert any vendor/retention entitlement.

### Source documentation checked

Official OANDA [Instrument Definitions](https://developer.oanda.com/rest-live-v20/instrument-df/) defines Candlestick with `time`, `bid`, `ask`, `mid`, `complete` and `volume`; BID and ASK appear **only when requested**, with distinct OHLC fields. [Pricing Endpoints](https://developer.oanda.com/rest-live-v20/pricing-ep/) documents `from`, `to`, `includeFirst`, dailyAlignment and alignmentTimezone in candle requests. Requesting `BA` allows a *paired* two-price-sided contract, not tick-aligned broker fills. Historical-vs-account pricing differences and product/account licensing are still **unverified**. Official docs are public technical references, not permission to store raw responses or backtest.

## Implemented synthetic API boundary

`src/forex_trading/provider_delta_contract.py`:
- `SyntheticOandaRequest` preserves provider-bound Forex `CachePartition`, instrument `EUR_USD`, bounded UTC `from/to`, explicit `includeFirst=True` for overlap, `price=BA`, `smooth=False`. Only M1/M5/M15/M30/H1 implemented; D1/H4/W1 need verified provider-specific alignment and DST before use.
- `plan_synthetic_oanda_delta` converts an existing M2/P0.2 bounded DELTA_WINDOW to a proposed request, **never constructs a network client**, always `may_issue_network_call=False` and `may_store_real_data=False`. Unsupported/empty range refuses work, not a silent full download.
- `parse_synthetic_oanda_candles` takes caller-provided OANDA-shaped mappings only: require matching instrument/granularity, two genuine BID+ASK OHLC sides for complete rows, monotonic/unique UTC timestamps, bounded request interval, positive/finite Decimal, sane OHLC, explicit complete boolean and non-negative integer price-count metadata; incomplete rows remain provisional and skipped. Cap page size; no gap is equated to a market closure.
- Nanosecond RFC3339 Z is parsed explicitly; sub-microsecond times are NOT silently rounded to Python microseconds and are rejected for the current normalized-bar contract. This is a conservative engineering restriction until nanosecond-preserving native source clocks are supported.
- `diff_synthetic_delta` compares stable canonical row digests for overlapping candles; reports unchanged/new/revised, earliest dirty UTC; **missing previous rows do not imply deletion**. Content digest is locally computed, NOT a signed vendor revision, authenticated remote head or verified historical first-known.
- Parsed candles stay **STAGED/UNVERIFIED**, and are intentionally not promoted to verified `MarketBar`/L1 persistent cache or executable BID/ASK fill prices. Even a complete=true flag does not verify session coverage, timestamp provenance, volume, account price parity or data rights.

## Durable storage review — no backend yet

`src/forex_trading/cache_storage_review.py`:
- A `DurableStorageProposal` describes an *opaque nonsecret candidate class*, encryption, checksum, atomic commits, restart/recovery, append-only audit, retention period, revocation/purge procedure and schema. It is never a storage URL or active credential.
- `assess_durable_cache_proposal` identifies unmet technical *claims* and independent legal/operational evidence. Always `provider_retention_right_independently_verified=False`, `host_security_approved=False`, `may_write_real_data=False`, `may_restore_real_data=False` even when caller claims rights.
- `make_synthetic_generation` and `validate_synthetic_generation_chain` create and check immutable **metadata-only** hash-chain snapshots of an existing synthetic `CandleSnapshot`; reject tampering, generation rollback/gap, cross-pair, schema mismatch or backdated generation. This is NOT actual atomic storage, encrypted database, backup, restart recovery or cryptographically signed source evidence.

## Invariants and missing production gates

| Topic | Current synthetic scope | Production gate (NOT MET) |
| --- | --- | --- |
| Five-minute delta | Plans bounded time window and parses OANDA-shaped synthetic rows | Account-specific read-only native BID/ASK source, entitlement, bounded request log, actual HTTP byte/API metrics |
| Integrity | Local deterministic digest of synthetic rows and cache generation metadata | Independently trusted source revision, vendor corrections outside overlap, signed/tamper-resistant custody |
| Calendar | Strict UTC M1/M5/M15/M30/H1, reject unsupported higher alignments | Vendor-verified H4/D1/W1 closing, NY rollover, DST/weekend/sessions, real source coverage |
| L1–L5 | L1 synthetic diff + L2 EMA reference + L1–L5 DAG invalidation | Full connected indicators, structure/zone/signal/report caching, 8-step audit, FULL-vs-INCREMENTAL parity |
| Persistence | Read-only candidate controls and metadata checksum chain | Approved host/storage, encryption/keys, atomic journal/backup, actual restart/rollback/corruption drill |
| Rights | External source qualification remains fail-closed | Explicit account+jurisdiction rights to collect/store/derive/cache/replay/backtest, expiry/revocation evidence |

**Important:** An OANDA `includeFirst`-compatible time window can reduce duplicate *requests* by itself, but sources can revise historical data. Until authenticated revisions or periodic deep reconciliation are available, overlap does not prove unchanged older history. `REUSE_HEAD_CLAIM` from M2/P0.2 remains a proposal, NOT permission to blindly skip an external revision check. For a 20-pair scan, the adapter must ultimately report actual calls, bytes, timeout/freshness, and data errors without assuming every timeframe closed on the same local clock.

Current synthetic testing is software-contract testing only. No latency/performance gains or financial strategy accuracy are claimed. Do not use GitHub for licensed prices, don't treat ChatGPT Python memory as durable cache. No unauthorized M15001; MOCHI stays optional and requires separate permission.
