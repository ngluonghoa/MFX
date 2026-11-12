# A04/P0.86 — Independent REAL read-only M5 full SHA, native H4 parity checkpoint

Evidence date: **12 November 2026**. All recorded timestamps below use UTC. No new production writer, workflow, provider request, GitHub privilege, local/MOCHI/Mac action, signal, HOT or broker operation was authorized or performed by this checkpoint.

## Authorized read-only GitHub Actions verification

Previously existing workflow: MFX P0.66 M5-to-Native-H4 READ-ONLY SHA Parity (NO vendor/trading), at .github/workflows/mfx-m5-h4-parity-readonly.yml. An authorized retry of its successful historical read-only job was accepted by GitHub; **run #43138482666, attempt #2**, job #130980635166, with actual started time **2026-11-12T04:51:10Z** and log evidence time **04:52:06Z**, completed SUCCESS at approximately **04:52:08Z**. Browser: https://github.com/ngluonghoa/MFX/actions/runs/43138482666 .

This run's checked-out historical commit was **4c60644d0a812eabee0e89519a29e1cce9731b61** (P0.81). Before interpreting its result, GitHub immutable blob SHAs were compared against P0.85 main **207c3cb2e5032d89942408fd1de7fb56c2ac559d** and found identical for all four decisive files:

- tools/run_mfx_m5_h4_live_parity_audit.py — blob 7e2a2d00b53b8e895552d7826cdc9013f7bfdda9
- tools/mfx_m5_rolling_manifest_audit.py — blob 4cd5b06d61d41ad9ccca60b295bda180dda90344
- mfx_cache/v2_batch_commit.py — blob a6f930ca5fe81db6ebde265bd090c37708015c5f
- .github/workflows/mfx-m5-h4-parity-readonly.yml — blob ea078d9f55fff2cc7dace5844176a1ba030b8cfe

Therefore the audited production read-only algorithm and its workflow content were unchanged by P0.82–P0.85. No new workflow was needed.

## Exact real read-only log receipt

Run attempt #2 logged the marker **MFX_A04_P66_READONLY_SOURCE_SHA_PARITY_AUDIT_PASS** followed by a structured report. Independently verified values from that report:

| Evidence | Exact value |
| --- | --- |
| M5 Manifest + Chunk pairs **full SHA verified** | **33 / 33** |
| M5 complete CLOSED source bars verified | **396** |
| M5 full bounded SHA-parent-chain verified | **true** |
| Most recent M5 source hour (UTC) | **2026-11-12T02:00:00+00:00** |
| Most recent M5 manifest SHA256 | **478840990e3a8bc4a745da5d694a98193aa5f614bd1abad92f487a530a213d76** |
| Native H4 Manifest + Chunk pairs full SHA verified | **7 / 7** |
| Native H4 closed bars in archive | **125** |
| Native H4 latest manifest SHA256 | **13304493801ab69860d6e088d120ab8bcf849164b63de4c16f7fd4920403a53e** |
| Exact full 48xM5-derived H4 compared with native | **7 matches, 0 mismatch, 0 native missing** |
| Full H4 qualification >=30 matches and >=7 days | **false** |
| H4 partial boundary windows | **2** |
| H4 interior incomplete windows | **0** |
| Read-only, provider API calls, Drive writes, broker orders | **true, 0, 0, 0** |
| Permission to reduce/replace native H4 | **false / false** |
| Operational status | **OBSERVATION_WINDOW_NOT_YET_QUALIFIED** |

The M5 archive at scan time is exactly the bounded 33-pair archive, not merely the latest three-pair rolling-tail audit (earlier Actions #43155201019). The prior 31-pair full check at #43138482666 attempt #1 also existed, but the evidence is now **same-run full 33/33 SHA**, not an inference by splicing older receipts. Previously reviewed genesis root SHA and P0.85's 31-pair checkpoint remain frozen; independent trusted monotonic witness/CAS is STILL NOT attested by the SHA chain.

## Production and trust boundaries

- This is a **point-in-time** cryptographic/structural audit of the M5 archive as then present in private Google Drive; it is not proof of price authenticity, historical trading data before genesis, retention licensing, all future writes, FX holiday/session calendar, or permanent elimination of M5 scheduling lag.
- Existing hourly P0.50 read-only audit still reported one-hour lag in its earlier 04:30Z receipt; a structurally sound 33-pair archive can still be behind the expected publish time.
- The source-native H4 request may NOT be reduced: only 7 matching complete UTC H4 windows, not >=30 exact windows spanning >=7 real calendar days including legitimate session gaps. Australia/Sydney D1 remains native. No numeric BUY/SELL source-owner approval or broker order permission.
- P0.85 source-only two-anchor module was **not** the code executed in the historical P0.66 retry. The exact existing full-bounded audit implementation (_m5_archive) was executed. This distinction is material.
- The ChatGPT hourly engineering automation remains disabled, and its disablement does **not** pause pre-existing GitHub Actions cache writers.

## Next research gates

Preserve run attempt #2 as the independently reproducible SHA evidence checkpoint for 33/33. At a later time, repeat the established full read-only job as needed, compare true M5 ingestion lag against GitHub scheduled/dispatched/started timestamps, serial writer lock, provider publication, and market trading session calendar without inventing scheduler root cause. Collect minimum 30 matching complete H4 windows over >=7 days before even requesting owner permission for changing native H4. Future source-only code or doc PRs must keep protected main exact-head CI, immutable Forex102, SHA-pinned allowlist and independent main push CI.
