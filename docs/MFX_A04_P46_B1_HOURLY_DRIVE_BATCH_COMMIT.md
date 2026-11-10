# MFX A04/P0.46-B1 — staged hourly M5 Drive batch writer (not activated)

**Owner decision:** Continue upgrading Cache Engine V2 beyond FX 2.0/P0.45. Parent issue #76, implementation issue #78. Cloud-only GitHub + private MFX Google Drive; frozen Forex 1:1 original source, MFX 22-label design and no broker/order integration unchanged.

## What was actually integrated

P0.45's former scheduled every-five-minute raw-chunk/manifest writer has been **removed from the registered workflow's execution path**. Its source module is retained for compatible REST/Drive access primitives. The schedule in `.github/workflows/twelve-data-cache.yml` is initially **once per UTC hour at minute 10**, to write at most one complete preceding hourly bucket. Example: the 13:10 UTC run requests explicitly `timezone=UTC`, checks for twelve CLOSED EUR/USD M5 candles covering 12:00–12:55 UTC, and writes one immutable hourly batch containing the 12 M5 bars plus exactly 4 derived M15, 2 M30 and 1 H1. The pure P046-A derivation engine SHA-pins the source windows. An incomplete hour produces no chunk and no manifest. No H4 or D1 is fabricated from M5.

This is a deliberately less-fresh initial storage schedule, **not** a claim of five-minute signal freshness. It trades the initial write rate for lower Drive object pressure; future near-real-time hot state and multi-pair priority scheduling require a different durable buffer design. No source-approved live BUY/SELL signals depend on this cache yet. A run that misses an hour does not call that hour contiguous: `MISSING_PRIOR_HOURS_UNVERIFIED` records the gap. Weekend/holiday/session semantics are not inferred or auto-repaired.

For a full liquid day, **theoretical maximum two Drive files per committed hour** (hourly chunk+manifest) = about 48 files/day before skipped/incomplete hours, compared to P0.45's possible maximum 576/day with two per five-minute poll. This ~12x illustrative file-count reduction is **not measured throughput**, benchmarked API cost, validated actual Drive operations or evidence of better 5-minute market freshness. The old workflow was disabled, so there is no real-world before-after runtime comparison.

## Crash recovery and origin safeguards

`mfx_cache/v2_batch_commit.py` contains the pure transaction plan and two-stage append-only commit. Chunk object is content-addressed, includes exact parent manifest SHA and versioned original MID/UTC/provider source; Manifest points to chunk hash and its parent hash. Both must be re-read and compared after upload. Replaying the same hour is a no-op. If interruption occurs after writing the chunk but before creating the Manifest, the next run scans for a single valid uncommitted chunk and reconstructs/commits the Manifest **without another Twelve Data data request**. Different or corrupt immutable bytes, malformed source, competing chunks from the same parent, duplicate Manifests or broken recent parent links fail closed rather than guessing a winner. No parent deletion. Previous original archives/Cache not touched.

**This is NOT true Google Drive multi-object atomic CAS.** Google Drive cannot atomically compare and swap creation of two separate files; the GitHub Actions concurrency group provides single-writer protection only among cooperating runs of this workflow. Unexpected external concurrent writers or eventual consistency can still create forks: ambiguity is rejected, and an operator must reconcile before data is trusted. Staged synthetic tests exercise partial writes and recovery; no actual Drive fault injection or throughput measurements exist yet.

The adapter `tools/run_a04_p46_cloud_batch_cache.py` uses the existing credential-isolated REST/Google Drive primitives, paginated private folder listing, name→SHA integrity validation, raw closed-candle parser and a provider usage check. Up to 120 raw M5 candles are fetched to select exactly the immediately preceding full UTC hour, and all input is validated before write. Only source-native M5 is requested; H4/D1 and provider-plan/session-aware gap replay remain pending separate work.

## Double activation gate: nothing runs by merging this PR

- Repository variable `MFX_REAL_CACHE_ENABLED` must be `true`.
- A second, new repository variable `MFX_V2_BATCH_CACHE_ACCEPTED` must independently be `true`.
- GitHub secrets `MFX_TWELVE_DATA_API_KEY` and `MFX_GDRIVE_SERVICE_ACCOUNT_JSON` and actual service-account writer permissions to the MFX manifest/chunk folders must be valid.

The actual GitHub job checks both vars and the Python code checks both env settings. An empty or false setting means the workflow job is skipped or the runner exits without real requests. **No credentials have been entered, no live Twelve Data vendor REST calls or private Drive raw price writes performed during this PR, and no automated market-data Cache is claimed running.** Original ChatGPT Twelve Data/Drive connector OAuth access does not grant GitHub Actions access.

## Test/remaining milestones

`tests/test_a04_p46_b1_hourly_drive_batch.py` includes 35 offline fake-Drive tests for exact closed-hour/M15-M30-H1 completeness, SHA names, omitted hours and history flags, idempotence, failed chunk/manifest uploads, orphan recovery, bad manifest/child hashes, competing forks, source-change hashes, explicit double-activation skip and absence of real market actions. `tools/run_a04_p46_b1_batch_demo.py` prints an offline no-provider receipt. Mandatory Python3.11+3.12 hosted CI, source frozen golden, strict typed mypy, security and wheel parity must PASS.

Parent Issue #76 remains OPEN for B2: actual daily compaction writer with verified manifest promotion and zero parent deletion before independent readback; proper bounded gap backfill on authenticated session calendar, native H4/D1, retention/expiry, cost metrics. Issue #74 remains OPEN for first actual real raw price capture/Drive readback. Provider tier-specific raw cache retention Gate L and historic executable BID/ASK/OOS Gate Q #27 still unverified. B2/S2 owner-approved numeric source decision #45 remains 0/36 and all MFX official numerical entry strategies 0/16, even if private MID raw cache eventually runs. No confirmed user BUY/SELL signal or broker execution released.
