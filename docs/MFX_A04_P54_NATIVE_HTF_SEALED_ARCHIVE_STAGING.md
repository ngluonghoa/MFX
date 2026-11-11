# MFX A04/P0.54 — Native H4/D1 private archive, pure staging

Status: **OFFLINE CONTRACT ONLY — no real H4/D1 provider proof or Drive write.** The existing production EUR/USD M5 V2 writer and hourly monitor remain unchanged. All development/CI/docs stay GitHub + Google Drive Cloud-only.

## Verified predecessor evidence

- MFX EUR/USD MID M5 hourly Cache B1 stores 8 consecutive UTC hourly batches from 2026-11-10 18:00 through 2026-11-11 01:00 UTC, 96 closed M5 bars, eight immutable Chunk objects plus eight Manifest objects on private Drive. Actual GitHub V2 writer #42936519530 committed **two** hours from **one** price API request; #42943983338 committed the next hour. Read-only hourly Audit #42940618953 verified the last three manifests, count seven then, parent chain and zero vendor queries.
- P0.52 native source contracts / PR #94 CI approved; D1 is exchange-local session date, not a synthetic UTC D1 candle.
- P0.53 manual native H4/D1 provider metadata probe / PR #95 CI approved and available at https://github.com/ngluonghoa/MFX/actions/workflows/mfx-native-htf-manual-probe.yml. **No actual P0.53 manual run found yet**; native H4/D1 vendor proof is not claimed.

## P0.54 scope

`mfx_cache/native_htf_archive.py` is **pure**. No Twelve Data, no Google Drive, no network, no local disk, no trading.

- Separate immutable object namespaces: `MFX_TD_EURUSD_H4_NATIVE_V1_...` vs `MFX_TD_EURUSD_D1_NATIVE_V1_...`; changing pair changes namespace, e.g. `MFX_TD_GBPUSD_H4_NATIVE_V1_...`. No M5 namespace overlap.
- Accept **only** prevalidated `NativeFXBatch` / `NativeFXBar` (source MID native H4/D1), preserve provider `exchange_timezone` and time-axis.
- H4 native labels remain `YYYY-MM-DD HH:MM:SS` on explicit `UTC_INTRADAY_OPEN` axis. D1 labels remain `YYYY-MM-DD` on `EXCHANGE_LOCAL_SESSION_DATE`. The two timestamps cannot be treated as interchangeable.
- Make one candidate *content-addressed* Chunk plus linked Manifest with canonical SHA-256 names, parent manifest digest, source identity, index of up to 16 recently closed native candles, source bar total and immutable batch counter.
- Incrementally append only newer source-native labels. If the incoming batch contains an overlapping recent label with a changed canonical SHA, **quarantine rather than silently revise**. If no new complete candle exists, return `None` and plan zero writes.
- Validate exact symbol/TF/timezone/source/axis, full OHLC ordering, price finite/positive, no broker/confirmed numeric signals. The helper `verify_native_sealed` replays construction and compares all bytes-level source data and SHA identifiers in memory; it does not claim an actual Drive readback.
- Bound each candidate batch to at most 120 native OHLC rows and rolling revision index to 16 labels. **Old overlap beyond the 16-label recent index is not re-verified**; provider historical corrections outside that window require an explicit reconciliation policy, never silent replacement.

## Non-goals and gates

- No OAuth Google Drive object writes, no new folder variables, no quota change, no API requests, no H4/D1 schedule, no broker automation, no source-owner approval of numeric BUY/SELL, no D1 UTC re-anchoring.
- Twelve Data data retention permissions have not been independently verified, despite user's instruction to continue private Google Drive caching.
- Native H4/D1 archived Cache is **NOT ENABLED**; P0.54 is purely schema and validation. GitHub CI proof != vendor proof != Drive live readback.

## Next stage acceptance

1. PR P0.54 offline unit tests on Python 3.11 + 3.12, source-frozen parity, cross-Python wheel and exact SHA manifest PASS, protected main CI PASS.
2. Manual P0.53 `mfx-native-htf-manual-probe.yml` authenticated metadata-only two-provider-request receipt PASS (with H4 UTC and D1 exchange-local labels) before any H4/D1 live writer.
3. Implement separate **manual-only** provider H4/D1 staged private Drive writer adapter mapping pair/TF namespaces, `put_if_absent`, strict readback and rollback. Use opt-in independent activation variables; never reuse existing M5 acceptance gate as authorization to write new TF data.
4. Prove two real native TF folders/files with SHA and manifest readback independently in Google Drive; only then consider controlled schedules.
5. Expand approved Forex pairs one at a time after per-symbol/source/timezone/credit and cache isolation proofs.

Reference source: https://github.com/ngluonghoa/MFX and Google Drive 00_MASTER_HANDOFF.
