# MFX A04/P0.59 — Native H4/D1 source-incremental MANUAL writer

## Purpose, state and non-goals

MFX EUR/USD native H4 and D1 roots have been actually authenticated and SHA-verified in Google Drive (manual GitHub Actions #42964328456, 2026-11-11, 119 H4 bars + 119 D1 bars), using Twelve Data composite MID, source-native H4 UTC interval open and D1 Australia/Sydney source session date. P0.58 read-only hourly integrity auditor is independent and retains its existing schedule. This P0.59 addition stages a **new, separate, four-way-gated, manually dispatched** incremental writer. No automated H4/D1 price polling or broker execution is introduced. Original P0.55 manual writer is deliberately left intact as a rollback.

New paths:
- `mfx_cache/native_htf_incremental.py`: pure deterministic time-based fetch planner and strict source-candle overlap SHA/quarantine;
- `tools/run_mfx_native_htf_incremental_commit.py`: authenticated manual-only preflight, bounded quota, selective vendor fetching, readback, immutable append using existing verified P0.55 code;
- `.github/workflows/mfx-native-htf-incremental-commit.yml`: manual workflow, existing shared concurrency lock with M5/P0.58, pinned OAuth dependencies and `contents: read`;
- `tests/test_a04_p59_native_incremental.py`: 26 hermetic negative/positive cases, no vendor/network calls.

## Plan (0, 1 or 2 price requests)

1. Four explicit gates: `MFX_REAL_CACHE_ENABLED`, `MFX_V2_BATCH_CACHE_ACCEPTED`, `MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED`, and **new independent** `MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED` all must be exact `true`. The new gate is **not implicitly accepted** merely because the existing native writer was approved. The owner must separately enable it if they choose to test real P0.59. Never change any repo variable from this PR.
2. Authenticate the existing app-owned private Google Drive CHUNKS/MANIFESTS folders. Before invoking the vendor, audit BOTH full bounded H4/D1 archive chains, parent SHA and orphan objects. If there is an orphan, stop and require separate recovery.
3. Determine whether the next provider-native candle is eligible for a new API price request. P0.62 retains the parser's 15-second H4 minimum close grace but adds a **2-minute-15-second provider-publication buffer** to the incremental fetch planner: H4 UTC 4-hour closure AND D1 Australia/Sydney local calendar midnight must pass this buffer before triggering a new source call. Subtract from UTC before Sydney timezone conversion (DST-safe). The buffer is based on Twelve Data's documented typical 0.3–2-minute REST candle latency; it is NOT proof that a candle is published or final. Forex API v2 documents 24/7 quotes, so do not introduce an assumed stock-exchange holiday/weekend filter. If neither interval is due, print `MFX_A04_P59_NATIVE_NO_NEW_CLOSED_SLOTS_ZERO_VENDOR_CALLS` and make **zero vendor usage/price API requests, zero new Drive objects**.
4. If only one is due, query only that native interval. If both are due, query both; all requested provider envelopes must validate before the first Drive write. Each interval's outputsize is `max(24, number of wall-clock slots elapsed + SHA-recent-index count + 4)`; initial bootstrap is 120. A window larger than 120 is blocked before vendor calls and requires a separate explicit backfill design. **Reducing outputsize shrinks provider JSON/transfer, but does NOT prove less API credit per call.** Real credit efficiency comes from selective skipping of intervals without a newly closed slot.
5. Every source response must reproduce **every SHA-stamped recent archived native bar**, normally the previous 16, with unchanged OHLC and metadata; missing overlap or mismatched SHA raises `P059_SOURCE_MISSING_SHA_OVERLAP` or `P059_SOURCE_NATIVE_REVISION_QUARANTINE`. Old root Chain and original source labels are immutable. Historical revisions beyond the available 16-bar recent index are NOT independently detected from a small incremental response. Never silently overwrite an old object.
6. Conservatively check quota before source price calls using the existing policy; recheck before the second price request. Twelve Data documents that `/api_usage` itself consumes a credit. The local cap and server-reported usage are a conservative operational budget, not a substitute for vendor billing-period accounting. After validating all selected native envelopes and confirming the archives did not change, execute the existing P0.55 SHA-sealed append/readback. No new M5 writes. Up to two objects created per due interval, or none for an unchanged vendor envelope. A partial multi-TF write failure remains possible because Drive has no atomic cross-object transaction; the append-only verifier/quarantine remains the recovery boundary.

## Explicitly not activated in P0.59

- No native scheduled writer, even if the independent P0.58 read-only audit has a :45 UTC schedule. P0.59 workflow has **workflow_dispatch only**.
- No automatic BUY/SELL signals (original source-approved numeric signals remain 0/16 and B2/S2 decisions 0/36), no broker orders, no execution-level bid/ask spread model.
- No historical recovery of >120 native calendar-slot outages, arbitrary source revisions, multiple Forex symbols, new Drive credentials, machine-local/Mac/MOCHI dependencies, modified M5 V2 writer, changes to original frozen Forex Trading parity or ownership assertions about Twelve Data licensed retention.

## Next acceptance requirements

- Hosted PR and **independent exact-main CI**: Python 3.11+3.12 full tests, frozen-source integrity, static/security and crosswheel.
- New repo variable `MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED=true` only after owner chooses real manual trial. Do not turn on a periodic writer.
- Launch new workflow manually on **protected main**. A no-new-closed-slot trial must print `MFX_A04_P59_NATIVE_NO_NEW_CLOSED_SLOTS_ZERO_VENDOR_CALLS`; a due-slot trial must print `MFX_A04_P59_NATIVE_INCREMENTAL_MANUAL_SHA_READBACK_PASS` with per-interval count, bounded outputsize and verified new immutable Drive files. Never claim a real incremental write or vendor credit saving until those logs are observed.
- Independently re-list M5/H4/D1 Drive objects and compare old Manifest SHA, emitted new SHA and prior parent chain. Require P0.58 audit still passing after any actual write, and separately audit provider licensed persistence rights.
