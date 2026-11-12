# MFX A04/P0.91 — Real read-only 41/41 M5 SHA and 9/9 native H4 comparison
Evidence: 2026-11-12 UTC. Owner-interactive P0.91. This is a source-only evidence acceptance PR; existing production GH workflows, cron, M5/H4/D1 cache, secrets, vendor, rights, source-verified signal, witness/CAS and broker are NOT changed.

## Before the read-only audit
- Protected main was `7ed0f13894129650776f81b1f71826c9d74c5f8f` (P0.90 PASS); no open PR. The previous independently verified historic P0.89 full M5 SHA head was **40/40 pairs**, **480 CLOSED M5 bars**, last hour `2026-11-12T09:00:00+00:00`, latest manifest SHA256 `9354cbe797c69b40a7466218db8cc8018b2c454396c95c33a66146d4939ec91d`.
- Current source and historical checkout SHA `4c60644d0a812eabee0e89519a29e1cce9731b61` share identical unchanged original `.github/workflows/mfx-m5-h4-parity-readonly.yml` Git blob `ea078d9f55fff2cc7dace5844176a1ba030b8cfe`. Existing workflow uses only GitHub contents:read, Google Drive OAuth GET/list and the cooperative single-writer cache group. No Twelve Data API key in the job or network price call. Existing source audit module `tools/run_mfx_m5_h4_live_parity_audit.py` remains untouched.

## Actual GitHub owner-authorized READ-ONLY rerun
- GitHub Actions [#43138482666 attempt #5](https://github.com/ngluonghoa/MFX/actions/runs/43138482666), job ID **131148019162**, completed **SUCCESS**, PASS marker `MFX_A04_P66_READONLY_SOURCE_SHA_PARITY_AUDIT_PASS` at **2026-11-12T11:19:20.351Z**.
- **M5:** Entire *currently bounded* immutable manifest + raw chunk + parent + derived SHA archive full-scan **41/41** PASS; **492 fully CLOSED M5 bars**; newest covered hour `2026-11-12T10:00:00+00:00`; latest manifest SHA256 `2676a0f5695c5639fb5a9d2800debb6d40cb3c0343e9d482144b3e3472f42ea1`; `m5_full_bounded_chain_verified=true`.
- **Native H4:** native archive **8** manifest+chunk pairs independently SHA-verified; **126** native H4 closed bars; **9** exactly matched complete UTC 48xM5-derived/native H4 windows; **zero OHLC mismatches** and zero native-only/M5-only missing complete slots. There are **two archive-boundary partial 4H windows**, zero interior incomplete windows. Observed complete H4 UTC starts `2026-11-10T20:00Z` to `2026-11-12T04:00Z`. Span >=7 days **FALSE**, qualifying >=30 windows **FALSE**. Market weekend/session calendar not independently verified. `may_reduce_native_h4_requests=false`, `may_replace_native_h4=false`.
- Explicit read-only receipt: `provider_api_calls=0`, `drive_writes=0`, `broker_orders=0`, `raw_ohlc_logged=false`, `d1_native_untouched=true`, `source_numeric_signals_approved=false`, `status=OBSERVATION_WINDOW_NOT_YET_QUALIFIED`. Price basis is reference **TWELVE_DATA_COMPOSITE_MID**, not execution-validated BID/ASK.

## Separate direct private Google Drive name enumeration
In this same work session the authenticated Google Drive connector listed the existing real production Cache manifest and chunk folders, separately from GH logs:
- manifest folder: **51 file objects** = **41 M5** + **8 native H4** + **2 native D1**;
- chunk folder: **51 file objects** = **41 M5** + **8 native H4** + **2 native D1**.
- The newest M5 manifest **filename** embeds the exact observed head hour and SHA `2676a0f5695c5639fb5a9d2800debb6d40cb3c0343e9d482144b3e3472f42ea1`; Drive metadata created time **2026-11-12T11:11:46.346Z**.

Direct Drive metadata confirms object presence/names only. It is NOT a second independent full raw-blob SHA scan, an authenticated vendor price/rights claim, or an external monotonic antirollback witness. The GitHub same-run P0.66 auditor supplies the full-bounded cryptographic/derived validation; it cannot prove pre-genesis history or future writes.

## Change safety and next
This P0.91 PR adds only this documentation record and a source SHA-pinned exception to `docs/MFX_ALLOWED_BASELINE_DELTAS.json`. No existing source, CI, operational workflow, secrets, repo permissions or cache record changes. Original frozen Forex Trading 102 Git blobs and 11 SOURCE_LOCKED Google Docs remain unchanged; no local Mac/MOCHI/desktop runtime.
- **P0.92 NEXT:** continue the safe, source-only qualification design for H4 eligibility and live session-gap evidence. Requalify SHA when new heads arrive, but do not add repeated price calls or alter schedules. Since only 9/30 matches over <7 real days, native H4 continues and Sydney native D1 remains unchanged. H4 cutover additionally requires explicit owner GO, market session validation and recovery tests.
- Vendor legal raw retention and BID/ASK rights, external witness/CAS for live V2, B2/S2 numeric source approvals 0/36, live BUY/SELL/HOT and broker remain separately gated. ChatGPT hourly engineering task remains OFF; GitHub production cache workflows operate independently.
