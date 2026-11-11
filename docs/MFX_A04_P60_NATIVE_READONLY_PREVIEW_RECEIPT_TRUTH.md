# MFX A04/P0.60 — Source-native H4/D1 incremental read-only preview and truthful commit receipts

**Cloud-only scope:** GitHub Actions + app-owned private Google Drive; EUR/USD source-native H4 UTC 4h and D1 Australia/Sydney exchange-local session-date as already sealed in A04/P0.55. Original Forex Trading 102 source blobs remain frozen. No Mac/MOCHI/local runtime, broker, numeric BUY/SELL authorization, or native write schedule is introduced.

## Real starting point

A04/P0.57 manual native writer #42964328456 succeeded: H4 119 closed native bars and D1 119 closed native bars, each immutable Chunk+Manifest pair verified, M5 unchanged. A04/P0.58 read-only hourly audit and A04/P0.59 staged incremental writer are both merged with exact protected-main CI PASS; A04/P0.59 source writer has an independent fourth gate `MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED` that remains owner-only and has NOT been enabled as a result of this work. A04/P0.58 first real live hourly audit must be evaluated separately from CI and the manual writer.

## Problem corrected: provider stale despite an accepted fetch

The prior P0.59 writer always emitted `NATIVE_INCREMENTAL_VALIDATED_AND_COMMITTED` after a successful native fetch even if the provider had only returned the already cached, SHA-consistent overlap. The sealed committer correctly produced `NO_NEW_CLOSED_NATIVE_BAR` and **zero Drive objects**, so the aggregate text was misleading. P0.60 adds `summarize_incremental_receipts`:

- `NATIVE_INCREMENTAL_NEW_BARS_COMMITTED` iff at least one receipt has positive newly closed bars and legitimate immutable append. Reports `total_newly_closed_native_bars` and `intervals_with_new_native_bars`.
- `NATIVE_INCREMENTAL_PROVIDER_STALE_NO_NEW_BAR` if every due interval source response is validated but has no new, closed native candle. Reports `intervals_provider_stale_no_new_bar` and zero newly closed bars; this is distinct from *no API call* when no new wall-clock slot exists.
- Fails closed for duplicate/unknown intervals, impossible new-bar counts, false no-new claims with writes, false commits with zero bars and any broker orders. Retains the preexisting SHA readback marker for successful validation, but no longer claims an append when none occurred.
- **Zero-due workflow** remains `MFX_A04_P59_NATIVE_NO_NEW_CLOSED_SLOTS_ZERO_VENDOR_CALLS`: zero provider PRICE and USAGE requests, zero writes. One or two planned price calls are advisory until actually executed; lowering response `outputsize` lowers transfer size, not necessarily credit cost.

## New standalone PREVIEW workflow (manual-only and no owner gate change)

Workflow file: `.github/workflows/mfx-native-htf-incremental-preview.yml`. GitHub URL: `https://github.com/ngluonghoa/MFX/actions/workflows/mfx-native-htf-incremental-preview.yml`.

It runs `python -m tools.run_mfx_native_htf_incremental_preview` using only the **three existing owner-enabled** cache variables and OAuth secrets for the app-owned folders. No Twelve Data API key or real provider usage request is passed. It shares the `mfx-twelvedata-private-cache` cooperative concurrency group with M5 writer/audits, P0.55 manual writer, P0.58 audit and P0.59 staged incremental writer.

The preview authenticates Google Drive, fully SHA-verifies each existing bounded H4/D1 archive and parent chain, rejects missing root/tampered data/one unresolved orphan, then computes `plan_native_fetch` for both TFs at one UTC clock reading. Emits marker `MFX_A04_P60_NATIVE_INCREMENTAL_READONLY_PREVIEW_PASS` with sanitized JSON containing:

- Current SHA of each last manifest, last native source label, last expected closed H4 UTC slot / D1 Sydney local calendar date, number of calendar slots behind (NOT audited FX trading sessions), SHA overlap count.
- `provider_price_requests_if_approved` in {0,1} per interval, `total_price_requests_if_approved` in {0,1,2}, optional `requested_outputsize_if_approved` in 24..120; **these numbers are potential future actions and not real network calls.**
- `real_provider_price_requests=0`, `real_provider_usage_requests=0`, `drive_writes=0`, `broker_orders=0`, `read_only=true`.
- No raw OHLC values are printed and no data is modified. Over-limit (>120 slots plus recent SHA overlap) or corrupted archives fail closed even in read-only preview; manual provider write is never silently authorized.

Because this workflow only reads existing app-owned objects, it does **not** need the new P0.59 incremental writer acceptance variable. It does NOT automatically call/activate P0.59, nor does its success prove actual provider freshness or valid Twelve Data persistent-storage rights.

## Acceptance and governance

1. Hosted PR CI: full Python3.11+Python3.12 tests, no-network negative cases, wheel parity, source manifest and security/pass. Independent protected-main CI success separately.
2. First real owner-dispatched P0.60 read-only preview on protected main: confirm `MFX_A04_P60_NATIVE_INCREMENTAL_READONLY_PREVIEW_PASS` and real 0/0 vendor calls/Drive writes. Independently compare existing SHA-pinned H4,D1,M5 Drive inventories before/after. Do not mark runtime acceptance from unit tests alone.
3. Separately accept the first actual scheduled P0.58 H4/D1 audit, with `MFX_A04_P58_NATIVE_H4_D1_READONLY_FULL_SHA_AUDIT_PASS` and no Drive writes. A lag report without provider market calendar is informational, not proof of an integrity failure.
4. Only if the owner deliberately approves `MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED=true` may new P0.59 writer be manually dispatched and have real provider/Drive effects. Existing P0.55 manual source writer remains unchanged for rollback. **Do not turn on automatic H4/D1 fetch, change original frozen Forex 1:1 behavior, or infer live BUY/SELL signals.**

## P0.62 source-publication readiness clarification (2026-11-11)

P0.60 Preview calls the same pure `plan_native_fetch` function as the P0.59 manual writer. Since P0.62, that function deliberately **waits 2 minutes 15 seconds** after the corresponding source-native H4 UTC 4-hour close or Sydney-local D1 midnight before projecting a new vendor price request. The original H4 parser still uses its independent 15-second minimum close-validity filter. This reduces possible early/stale vendor requests; it does **not** guarantee source availability or account-specific storage licensing, and a Preview PASS still performs **zero actual provider calls and zero Drive writes**. See `docs/MFX_A04_P62_NATIVE_CANDLE_PUBLICATION_READINESS.md` for vendor primary references, DST edge-case tests and manual writer acceptance boundaries.

## P0.63 read-only capacity projection

P0.60 manual authenticated Drive read-only Preview now reports `archive_append_slots_remaining` and `source_fetch_blocked_by_capacity` for each native interval. When a new H4/D1 source window would otherwise be due but that interval already holds 256 Chunk or Manifest files (per independently audited native pair/interval), the Preview marks `NATIVE_ARCHIVE_CAPACITY_BLOCKED_NO_VENDOR_CALL`, advises **zero** price requests/outputsize null for that blocked TF, and leaves other TF preview independent. It still makes **zero real Twelve Data calls and zero Drive writes**; these are advisory source requests, not provider executions. Do not interpret an archival capacity block as a missing Forex market candle. See `docs/MFX_A04_P63_NATIVE_ARCHIVE_CAPACITY_FAILCLOSED.md`.
