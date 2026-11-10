# MFX A04/P0.46 — Cache Engine V2, Stage A (Cloud-only offline core)

**Decision:** owner approved on 2026-11-10 to upgrade MFX beyond FX 2.0 rather than simply reuse FX 2.0's Google Drive archive method. MFX's cache architecture must remain independent and cloud-only (GitHub + private Google Drive). This milestone is a pure, reviewable engine and **does not activate** the P0.45 scheduled Twelve Data/Drive writer.

## Baseline facts and real gaps

FX 2.0.10's separate operator-run design already contained M5→M15/M30/H1 exact 3/6/12 closed candle aggregation, native H4/D1, adaptive quota scheduling and a local SQLite ledger. FX 2.0's final 2026-10-29 master configuration **forbade automatic polling**, favoring manual requests. FX 2.0's separate November 4 Google Drive checkpoint verified 120/120 frame files in 4 archives and SHA readback but was MOCHI/local-dependent, and did not prove an autonomous production price feed.

MFX P0.45 has private cloud storage architecture, exact MID UTC request, per-bar SHA validation and a five-minute schedule registered but DISABLED. However, the current writer would generate a new Manifest after every successful poll and separate small chunks when a bar advances. It still lacks mature timed compaction, provider-native H4/D1, source dependency invalidation, indicators and Crash/CAS recovery. Calling P0.45 a superior finished cache would be false.

## P046 Stage A — pure executable invariants

Implementation `mfx_cache/v2_engine.py` provides:

1. **Causal MTF from existing M5**: exact contiguous preclosed M5 groups of 3/6/12, UTC day/session version-tagged boundaries for M15/M30/H1; incomplete windows explicitly skipped and reported; strict no derivation of H4/D1, which must be obtained from provider-native bars. This UTC intraday convention is an explicitly versioned research mapping, *not* a proof that broker sessions or non-UTC platform candle boundaries match.
2. **Source SHA and selective derived-window invalidation**: every derived bar has source fingerprint for only its own 3/6/12 closed input candles. A revised M5 changes affected window SHA without invalidating unrelated derivations. Real provider revisions still require external quarantine and review.
3. **Gap detection**: counts missing M5 slots but never fills them by interpolation. Long discontinuities are `SESSION_UNKNOWN`, not automatically treated as bad quotes (weekend/holiday/rollover session calendar must be externally verified). All gaps have `auto_backfill_allowed=false`; stage B will separately implement calendar-authorized bounded backfill.
4. **Additive batch compaction proposal**: bundles verified M5 chunks into deterministic UTC-day partitions with sorted parent SHA256 references, exact duplicate elimination, conflicting overlapping closed bars hard-error/quarantine and immutable content SHA. Insufficient parents do not compact. The resulting object is only a PROPOSAL; `parent_deletion_authorized=false` and `drive_verified_readback=false` until an independent cloud writer safely commits, validates SHA, atomically updates the current manifest and separately applies retention.
5. **Indicator result caching**: independent, deterministic EMA(close) and Wilder-style ATR research calculator with explicit period, Decimal fixed calculation context, version and source fingerprint. Identical inputs re-use cached output without a recalculation, changed source windows/period invalidate. These calculations are *not* source-approved Forex BUY/SELL indicator formulas.
6. **Smart fetch quota-admission planning**: deterministic due checks for M5 plus mandatory native H4/D1, no duplicate current polling slot, explicit priorities, source freshness checks, per-minute/day credit caps, 7-request max batch and no API calls. Actual caller must account for real Twelve Data credits, timestamp corrections and other apps sharing the tier. Priorities cannot magically grant source-validated Forex signal status.
7. **Theoretical file-pressure model**, explicitly not a benchmark: if P0.45 wrote two files on each of 288 polls/day and V2 flushed two files eight times/day, for seven days, scenario yields 4032 versus 112 objects (3920 fewer). This is an *upper-bound illustrative case*, not a measurement of Drive latency, compression ratio, vendor pricing, cloud cost or real throughput; baseline often skips raw chunk when no new bars.

46 independent synthetic positive/negative tests plus deterministic no-network hosted demo check all parts, including malformed OHLC, UTC offsets, future/open candles, incomplete windows, weekend gaps, source mutation and overlap quarantine, wrong indicator cache version, quota refusal and no real provider calls. GitHub CI Python3.11/3.12, strict mypy/Ruff, frozen Forex source and artifact/wheel parity must PASS before merge.

## Stages not yet implemented — do not confuse plans with operation

**Stage B (next scoped PR):** integrate P046 algorithms into P0.45 cloud writer. Use a time/size bounded hot buffer, write batch chunks and compaction proposals to private Drive, durable manifest pointer with safe compare-and-swap or robust retry/rollback, readback each object, event journal and retention cleanup only under provider rights. Enforce manifest idempotence/concurrency across retries; test forced mid-upload failures and partial Drive writes. Implement exact H4/D1 provider-native caching, session-aware bounded gap repair, re-derivation and indicator updates. Gate real activation until safe.

**Stage C:** measure real provider credits and Drive file/list/read latency from allowed data, restore actual manifest and chunks after failure, compare to FX 2.0 checkpoint under equivalent workloads. Configure separate GitHub Actions API key and Drive service-account writer access, validate vendor/tier retention terms, and only then activate. P0.45 GitHub cron remains opt-in disabled today.

## Non-negotiable boundaries

No Mac/MOCHI/local runtime, no copying FX2.0 files into MFX, no original Forex Trading 1.0 source edits, no expansion of unapproved numeric signal predicates. Frozen Forex catalog 18, MFX approved-design 22, source-approved numeric entry policies 0/16, B2/S2 original owner signoffs 0/36 (#45), provider-specific legal raw cache retention and BIDASK/Q economics (#27) unresolved. ZERO live market quotes read in this P046 Stage A, ZERO real Drive cache writes or confirmed market BUY/SELL alerts, ZERO broker orders. No release claim.

Links: Issue #76, PR (see GitHub issue), previous P0.45 Issue #74 and docs/MFX_A04_P45_TWELVE_DATA_DRIVE_CACHE.md.
