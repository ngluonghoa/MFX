# MFX A04/P0.63 — Native H4/D1 bounded archive capacity preflight

Date: 2026-11-11 ICT. Scope: source-native EUR/USD H4 + D1 immutable Google Drive private Cache, NOT market signals or trading. The owner has already successfully dispatched P0.59 manual native H4 incremental source writer #42993880950 (1 new H4 closed bar at 2026-11-11 04:00 UTC, D1 correctly skipped), verified by separate Drive Chunk+Manifest canonical SHA and parent/readback. D1 native incremental append has not yet been observed. This PR modifies neither the original Forex Trading frozen 102 blobs nor M5 V2, native scheduling or owner-approved gates.

## Triggering integrity issue

Existing source-native full SHA auditor in `tools/mfx_native_htf_drive_seal.py` has `MAX_NATIVE_FILES = 256`, applied **per native pair+interval and bucket**. `audit_native_archive` accepts exactly 256 Chunk objects and 256 Manifest objects but rejects 257 of either (`P055_ARCHIVE_TOO_LARGE_TO_VERIFY`).

Before P0.63, `commit_native_batch` could read a valid archive at this limit, derive another immutable append, write the **257th Chunk**, then fail its next full SHA audit, leaving an orphan that cannot be checked by the bounded auditor. Separately, P0.59 could spend native vendor /api_usage and price credits before realizing it could not safely append. P0.55 legacy manual two-series writer could also successfully commit one TF before discovering the other TF was full. These are forward-looking integrity/cost risks, NOT claims that the current small real archive is corrupted.

## Design: fail-closed in three complementary layers

1. `native_append_slots_remaining(state, reuse_existing_orphan=False)`: pure deterministic capacity budget using independently SHA-audited `NativeArchiveState`. With no orphan, returns `max(0,min(256-manifest_count,256-chunk_count))`; the fixed ceiling is per H4 or D1 scope, **not** a single global Google Drive storage quota. Reject impossible counts/types. For the owner-authorized **legacy exact orphan recovery** path, if the orphan Chunk exactly matches the candidate and one Manifest slot remains, `reuse_existing_orphan=True` allows one Manifest-only recovery even when the Chunk bucket is at 256. No delete or overwrite.
2. P0.59 manual **four-way-gated** staged incremental writer audits BOTH H4+D1 before source credits and checks every due interval for room. If either due interval is at limit, fail with `P063_NATIVE_CAPACITY_EXHAUSTED_NO_VENDOR_CALL` before **any** Twelve Data usage/price call and before **any** Google Drive mutation. If neither interval is due, retain the existing zero-vendor no-op even if the archive happens to be full. No new vendor permissions or schedule.
3. P0.55 legacy **three-way-gated** manual initial source writer validates BOTH vendor envelopes before Drive authentication, by its preexisting design. It now preflights **both archive capacities** before the first append; if either cannot accept a new pair, fail `P063_NATIVE_LEGACY_CAPACITY_NO_DRIVE_WRITES`. P0.55 may already have paid for two vendor prices at that point (historical contract unchanged), but it cannot partially append only H4 before failing D1. The underlying `commit_native_batch` always checks capacity before the first remote immutable write (`P063_NATIVE_ARCHIVE_AT_CAPACITY_NO_WRITES`), including callers outside either workflow.

P0.60 manual **read-only** Preview uses the same pure budget: it reports `archive_append_slots_remaining` and `source_fetch_blocked_by_capacity` per interval. If a due TF is full, `decision=NATIVE_ARCHIVE_CAPACITY_BLOCKED_NO_VENDOR_CALL`, its hypothetical provider price request count becomes 0, and its requested outputsize becomes null. Other TFs are still reported separately. Preview always has 0 *real* provider price/usage requests, 0 Drive writes and 0 broker orders. Existing SHA errors or an orphan in a read-only preview remain fail-closed as before.

## Deterministic no-network QA

`tests/test_a04_p63_native_archive_capacity.py` adds **17 hermetic tests** covering:

- exact limit 256/256, one remaining slot at 255/255, valid 255-manifest/256-chunk exact orphan recovery, rejection of negative/overlimit/boolean counts and fabricated orphan recovery;
- real Python `commit_native_batch` with an isolated memory Drive at a simulated small max 1 or 2: root at cap, last available append, next append DENIED before any Chunk write, no-new still idempotent at cap, and exact final orphan recovered by one Manifest write;
- real P0.59 `main()` with mocked Drive/provider/usage: either H4 or D1 at full capacity while due aborts before *any* vendor usage/price calls and before all writes, but no-due at cap does not consume credits or error;
- P0.60 read-only Preview full-bucket due plans 0 hypothetical price calls and projects a remaining TF's available request independently;
- legacy P0.55 `main()` both sources validated but D1 at capacity: no partial H4 Drive commit; workflow remains manually dispatched and owner four-gated P0.59.

All tests use no actual account secrets and no raw OHLC output in logs. Existing P0.55/59/60/61/62 tests must continue passing on Python 3.11 and 3.12. Hosted PR full CI and **independent protected-main** push CI both mandatory. Never claim P0.63 real 256-object boundary testing against Google Drive: these are hermetic accelerated-boundary tests.

## Real current Drive and operations

Prior independently verified owner Drive inventory directly after first P0.59 real H4 append: H4 has **2 Chunk + 2 Manifest**, D1 has **1 + 1**, M5 has **14 + 14**. The actual H4 and D1 append capacities at that instant were 254 and 255 more pairs respectively under the 256-per-bucket SHA-audit ceiling. Recheck live inventory when needed; these are point-in-time values, not a claim that current counts can never change.

No background work, native automatic H4/D1 cron, added vendor price calls, broker, numeric BUY/SELL approval, HOT V3, unscoped Drive overwrite or Mac/MOCHI/local runtime is introduced. The owner-enabled `MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED=true` remains separate; manual dispatch and per-run quota/security checks remain mandatory.

**Future capacity maintenance** after reaching 256 would need an explicit independently reviewed archival compaction/rollover strategy that preserves cryptographic chain provenance, historical reproducibility and the provider subscription's permitted retention. Do NOT silently delete or rewrite immutable existing native Chunk/Manifest, increase the auditor's 256 limit without bounding memory/cost, or bypass original source parity. Twelve Data raw OHLC retention rights are still account-specific and NOT independently validated.

## P0.64 periodic execution does not relax capacity guard

The existing four-gated native incremental writer is now scheduled **UTC :25 each hour**, with `workflow_dispatch` still permitted. Every scheduled run independently audits both Drive archives and executes the P0.63 fail-closed 256-per-native-interval/bucket preflight BEFORE any due H4/D1 Twelve Data usage/price call or Drive write. A native archive at its cap causes safe error/no vendor calls rather than hourly creation of a 257th orphan. Runs with no eligible new native slot still make 0 provider calls and 0 writes. GitHub Actions same cross-workflow lock prevents overlap with M5 writer and P0.58/P0.60 reads. The hourly scheduling choice supersedes this document's earlier manual-only operating-mode descriptions but does not change any tested capacity semantics. See `docs/MFX_A04_P64_HOURLY_NATIVE_H4_D1_AUTOMATION.md`.
