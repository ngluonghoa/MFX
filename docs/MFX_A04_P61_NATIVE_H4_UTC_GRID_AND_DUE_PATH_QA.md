# MFX A04/P0.61 — Native H4 UTC 4-hour grid and staged writer due-path QA

Date: 2026-11-11 ICT. Scope: incremental source-native EUR/USD H4+D1 private Google Drive cache, not a trading-signal or broker project. Existing P0.55 manual source cache roots, P0.58 scheduled read-only audit, P0.59 independently four-way-gated MANUAL writer, P0.60 manually dispatched read-only preview, M5 V2 scheduled path and the 102 original frozen Forex Trading source blobs stay isolated.

## Source evidence from real PRIVATE Drive before this change

The immutable H4 root Chunk in the app-owned CHUNKS folder is `MFX_TD_EURUSD_H4_NATIVE_V1_chunk_20261111T0000UTC_0800c43b62c0bc96604cff6e5e25d3ecdc16ea1564ad74bf2182a5bf8f8732bd.json`; companion root manifest SHA `d47177c09abe5a42c38eb8e3c9c48b48505a21e9915691c269d9c13c218a2d28`. This root had previously been authenticated via owner-dispatched native writer Actions #42964328456 and revalidated by hosted P0.58 full SHA audit #42973650906 and read-only P0.60 preview #42978814599.

For P0.61, the authenticated **existing H4 Chunk itself** was independently fetched via the Google Drive connection and its `bars[*].native_open_label` fields were inspected without displaying raw OHLC to the user. All **119/119 H4 labels** were on UTC 4-hour open slots. Distribution by UTC hour: 00=20, 04=19, 08=20, 12=20, 16=20, 20=20, all other hours=0. First 2026-10-22 08:00:00, last 2026-11-11 00:00:00. This confirms new validation of the existing root does not reject a preexisting off-grid bar. This does **not** verify every future vendor response; online vendor source acceptance remains separate.

## Integrity hole closed

P0.52 native source parser formerly checked H4 native label syntax and that minute/second were 00, but **did not require hour divisible by four**. A malformed but otherwise valid 01:00 UTC native H4 bar could be accepted by the parser. P0.54 SHA-sealed per-bar validator similarly checked HH:00 but not every bar's four-hour UTC alignment; P0.58's last-label check did not independently prove every internal H4 row aligned. Sealing a mixed on/off-grid batch would permanently pin misleading H4 data with a correct cryptographic SHA.

P0.61 adds fail-closed `P061_H4_UTC_4H_GRID_REQUIRED` at TWO independent verification boundaries:
- `mfx_cache/native_fx_htf.py`: on every H4 provider-native label from authenticated Twelve Data, before accepting closed OHLC;
- `mfx_cache/native_htf_archive.py`: on every incoming/rehydrated H4 archive bar, including archive replay and full SHA/parent audit, before constructing or re-accepting immutable Chunk+Manifest pairs.

The rule is for H4 `timezone=UTC` intraday bar opens only: hour in {0,4,8,12,16,20}, minute=second=0. D1 remains independently exchange-local `Australia/Sydney` session DATE; no UTC H4 grid is applied to D1. If Twelve Data ever begins using off-grid UTC H4 labels, the update is QUARANTINED rather than silently re-anchored or rewritten; user-visible QA must investigate source/exchange timing first. This change is not a newly claimed real-time quote or broker-aligned H4 close.

## Hermetic FULL due-path QA (beyond previous 26 planner cases)

New `tests/test_a04_p61_native_h4_grid_and_due_path.py` adds 16 hermetic, no-network, no-broker cases:

- Provider-native H4 01:00 and 23:00 rejected; 00/04/08 accepted; off-grid archive root and even one off-grid bar in a mixed 3-bar batch rejected; D1 local date remains distinct.
- Full P0.59 four-way-gated `main()` drive/REST mocked: when both H4+D1 are due, exactly two provider price requests and all validated before any append commit, quota preflight/recheck, and truthful `NATIVE_INCREMENTAL_NEW_BARS_COMMITTED` receipt.
- When only H4 due, D1 skipped and exactly one price request; provider returns unchanged recent bars: `NATIVE_INCREMENTAL_PROVIDER_STALE_NO_NEW_BAR` rather than a false write claim.
- Invalid second provider envelope, SHA revision in prior overlap, insufficient quota on preflight or before the second price request, changed parent archive during vendor fetch, and unresolved orphan all reject with ZERO commits.
- H4 provider open 08:00 UTC at 09:15 UTC is excluded as unclosed while 04:00 is already closed (15-second finalization grace); no future candles added to the immutable cache.

Legacy `tests/test_a04_p59_native_incremental.py` off-grid fixture is updated to assert earlier rejection at sealing rather than fabricating an archived off-grid root. The full test count should be checked in hosted PR and exact-main CI; do not treat offline QA as live source/Drive write acceptance.

## CI and production acceptance boundary

- New exact SHA-pinned allowed-delta paths and revisions in `docs/MFX_ALLOWED_BASELINE_DELTAS.json`, preserving protected source-freeze and SHA intent. Python3.11+3.12 full CI, security/strict source parity, independent main-push combined status and wheel parity are required.
- P0.58 hourly native read-only SHA audit and P0.60 read-only preview have genuine hosted success logs; their certificates are independent of this code change.
- P0.59 **has NOT been enabled and has NOT performed a real incremental provider SOURCE write**. Do not change `MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED` or inject a schedule in this task. Its real acceptance still requires separate owner-controlled fourth-gate enablement and manual dispatch, checked vendor quota, all SHA overlap, new immutable H4/D1 append/readback and unaffected M5.
- No source numeric signals have been approved, no broker orders, no HOT V3, no assertion that user/vendor storage rights were independently validated, no Mac/MOCHI/local deployment. Continue only in GitHub + Google Drive.
