# MFX A04/P0.55 — Manual-only native H4/D1 immutable private Drive cache

**Status: STAGED — no authenticated real H4/D1 vendor probe or Drive H4/D1 write acceptance yet.** MFX remains Cloud-only (GitHub + Google Drive), independent, original Forex Trading 1:1 baseline frozen, no broker execution.

## Verified prior live M5 evidence

- Twelve Data EUR/USD composite MID M5 has 8 sealed one-hour batches with 96 closed bars on app-owned private Drive, 8 Chunks + 8 Manifests, covering UTC 2026-11-10 18:00 through 2026-11-11 01:00.
- Real scheduled writer #42936519530 restored 2 complete hours in ONE provider request. Read-only audit #42940618953 reported contiguous recent parent linkage, freshness and no vendor calls.
- Last observed scheduled writer #42949661252 returned `UTC_HOUR_ALREADY_COMMITTED_NO_API_CALL`: idempotent on repeated window, not a new candle commit.
- P0.52 native H4/D1 provider-time axis and P0.53 *manual provider-only* receipt have passed GitHub CI, but the actual H4/D1 REST proof **has not been run**.
- P0.54 pure native per-pair/TF immutable archive planning CI PASS PR #96/main f6ad296a5206551892c3d00cf2335e2a9c8ec0e2.

## P0.55 design

- Pure orchestration with an OAuth Drive adapter under `tools/mfx_native_htf_drive_seal.py`; separate manual entrypoint `tools/run_mfx_native_htf_drive_commit.py`.
- **No schedule.** New workflow `.github/workflows/mfx-native-htf-drive-commit.yml` is **workflow_dispatch only** and has an additional independent Repository Variable `MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED` that must be explicitly `true` on top of the existing two M5 vars. Unset/false skips the job; the entrypoint also checks the three flags before loading credentials. It does not modify the hourly M5 workflow, its activation variables or the V3 HOT disabled gate.
- One manual run retrieves at most two native provider series, **EUR/USD 4h with timezone=UTC** and **EUR/USD 1day with no timezone parameter**, with vendor quota checks before the first and second price request. The native parser validates symbol, metadata, closed candles, source time zone and OHLC; BOTH series must pass BEFORE any OAuth Drive write.
- The adapter reuses the same private OAuth app-created Drive `CHUNKS` and `MANIFESTS` **physical folders**, but uses strictly isolated per-pair/native-TF object prefixes:
  `MFX_TD_EURUSD_H4_NATIVE_V1_chunk_...` and `MFX_TD_EURUSD_D1_NATIVE_V1_chunk_...` with matching isolated Manifest prefixes. This is **logical namespace isolation, not separate physical folders**. Existing `MFX_TD_EURUSD_M5_V2` objects are never modified/enumerated by the native prefix scanner.
- Every commit scans and validates the *complete bounded native history* (at most **256** Chunk/Manifest objects in each namespace), matching canonical SHA names, data, source axes, total counts, recent-index hashes, exact parent hashes, with each pair reconstructed using the P0.54 pure verifier. Exceeding the bound fails closed; no unverifiable append.
- Candidate pair is one content-addressed Chunk and one linked Manifest. Parent is re-read immediately before and after the Chunk is created. Each upload receives exact JSON readback. An existing identical Chunk can be adopted after a prior orphan interruption; an orphan that does not exactly match is quarantined and no file is deleted.
- GitHub concurrency group is the SAME `mfx-twelvedata-private-cache` as hourly M5/Audit to reduce cooperative collisions. Drive has no multi-file atomic compare-and-swap, so a malicious external writer can still fork history; no adversarial race guarantee.
- Provider source `MID` is not executable BID/ASK. Numeric signal approval remains false and broker orders zero. GitHub logs emit only status, native labels, closed candle counts and SHA digests, not raw OHLC or secrets.
- Limited recent-overlap revision detection (16 bars) applies; old historical quote revisions beyond this window are not fully re-queried, though already sealed archive pairs are SHA-verified on a subsequent archive audit.
- Real Twelve Data private data retention rights have not been independently verified; user explicitly instructed the project to keep using their private Drive cache without further vendor inquiry.

## Acceptance / separate activation

1. GitHub P0.55 PR CI must pass Python 3.11 + 3.12, 22 offline positive/fail-closed/readback tests, source-freeze manifest and cross-Python wheel parity. After protected merge, independently confirm main push CI.
2. Recommended independent **provider-only proof first**: run `https://github.com/ngluonghoa/MFX/actions/workflows/mfx-native-htf-manual-probe.yml` on `main`. Required marker `MFX_A04_P53_NATIVE_H4_D1_METADATA_ONLY_TWO_REQUESTS_PASS`, not merely job Success.
3. To permit H4+D1 real Drive write, explicitly configure new GitHub Repository Variable `MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED=true`. This is not configured/activated by the PR. It is distinct from existing M5 `MFX_REAL_CACHE_ENABLED` and `MFX_V2_BATCH_CACHE_ACCEPTED`.
4. Manually dispatch `https://github.com/ngluonghoa/MFX/actions/workflows/mfx-native-htf-drive-commit.yml` on main. Require `MFX_A04_P55_NATIVE_H4_D1_DRIVE_PAIR_SHA_READBACK_PASS`, an exact 2-series source receipt and at least one `NATIVE_BATCH_COMMITTED` per native TF; `NO_NEW_CLOSED_NATIVE_BAR` is not a new commit.
5. Independently open the two new native TF Chunk/Manifest pairs in Google Drive and validate full SHA, source zone and isolation from M5. This must be real provider/Drive verification, not unit-test evidence.
6. Only after real acceptance consider separate H4/D1 hourly schedules, per-pair rollouts and retention/compaction policy. Do not automatically enable new schedules.

Rollback: disable `MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED` and revert PR through protected GitHub branch governance; leave previously sealed private Drive data immutable. No Mac/MOCHI/local infrastructure involved.

## P0.63 256-object native scope capacity guard

Legacy P0.55 manual two-source native workflow still fetches/validates H4 and D1 **before** authenticating and reading Drive, so vendor price/usage credits may already be consumed when a full archive is discovered. However P0.63 now preflights both native archives for enough remaining SHA-auditable immutable Chunk+Manifest slots **before writing either TF**. It rejects `P063_NATIVE_LEGACY_CAPACITY_NO_DRIVE_WRITES` if a due append would exceed 256 objects per native interval/bucket, avoiding a one-sided H4 append if D1 cannot append (and vice versa). Additionally the underlying `commit_native_batch` rejects capacity exhaustion before its first write, while allowing an exact already-written orphan Chunk to be completed by one Manifest when within the limit. Prefer P0.59 incremental writer for source-budget efficiency; its P0.63 capacity gate is **before** all vendor API calls. Full details: `docs/MFX_A04_P63_NATIVE_ARCHIVE_CAPACITY_FAILCLOSED.md`.
