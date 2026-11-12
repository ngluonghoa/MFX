# MFX 1.0 — SIGNAL-FIRST release-critical path (owner-approved 2026-11-12)

**Canonical GitHub coordination:** [Issue #138](https://github.com/ngluonghoa/MFX/issues/138). Supersedes **the *priority order*** in P0.95 and older H4 qualification roadmap, NOT historical facts, source gates, approved workflows, immutable Forex source, or permission limitations.

## User-facing product

- **Signal-only** Forex analysis. Report BUY, SELL or NO_SIGNAL for verified, causal, closed candles when source-approved numerical criteria are met; show zone, timeframe, stage, first-known evidence, entry, SL, TP, net R:R with spread/fees/invalidation/freshness and a clear reason; never broker execution, account linkage, automated position order or fake fill.
- **1:1 baseline** to Forex Trading 1.0: original 102 Git source blobs, 11 SOURCE_LOCKED Docs unchanged; preserve original 18 taxonomy, original semantics. Effective **MFX 22-zone design overlay** is separate, with **16 entry candidates (8 LONG/8 SHORT) and six non-entry/watch/exit protections**. A design role is not proof of an executable numeric detector.
- **Cloud-only** GitHub Actions + Google Drive; no Mac/MOCHI/local runtime, no ChatGPT scheduled engineering task (owner turned it off). Do not touch existing authorized production M5/H4/D1 caches, cron, secrets, batch windows or write schedules without separate authorization.

## Actual code baseline at owner pivot

| Layer | Existing code/source | Observed state | Product gap |
|---|---|---|---|
| Forex original parity | `src/forex_trading/*`, original 102 Git blobs/11 locked Docs | Source frozen, CI proven through P0.95 | Preserve continuously, no source rewriting |
| Zone classification | `mfx_research/p030_approved_nonentry_design.py`, `p031_sim_22_zone_router.py` | 22 design labels, 16 entries/six nonentry; typed SIM labels only, public `NO_SIGNAL` | Computed real BUY/SELL predicates not present |
| B2/S2 pilot | `mfx_research/p032_synthetic_ohlc_bridge.py`, causal SIM D1/H4/H1/M15 | Two experimental OHLC-research candidates; not 16 zone detectors | Source-approved numeric B2/S2, then other eligible source-defined zones |
| Approval of original numeric requirements | `mfx_research/source_parameter_review.py`, `docs/MFX_A04_P21_SOURCE_PARAMETER_REGISTER.json`, [#45](https://github.com/ngluonghoa/MFX/issues/45)/[#62](https://github.com/ngluonghoa/MFX/issues/62) | **0/36 B2/S2 approved**; numeric source for other entries not indexed/approved | Independently establish source-authoritative formula/parameters per rule; never copy SIM demo numbers as originals |
| Real M5 data | `mfx_cache/td_m5_codec.py`, `tools/run_a04_p45_cloud_twelve_data_cache.py`, [#74](https://github.com/ngluonghoa/MFX/issues/74) | Actual EUR/USD M5 CLOSED MID incremental Drive archive exists | Read-only authenticated downstream integration; MID is not executable BID/ASK |
| H4/D1 | `mfx_cache/native_fx_htf.py`, `native_htf_archive.py` | **Native H4 and Sydney D1 exist** | Use for v1, don't wait for M5-derived H4 parity/cutover |
| Higher-timeframe M15/M30/H1 | `mfx_cache/v2_engine.py` and native/original contracts | 3/6/12 x complete CLOSED M5 architecture tested, not a proven live six-TF signal chain | Validate exact UTC alignment, gap/source calendar/provenance and as-of joins from actual cache |
| Full scanner | `src/forex_trading/pipeline.py` | **8-step design contract**, not an executable production scanner | Build actual one-symbol end-to-end signal-only vertical slice |
| Backtest/SL-TP/R:R | P0.18/P0.19/P0.32 SIM demonstrations; [#56](https://github.com/ngluonghoa/MFX/issues/56) | Research-only, not source-approved, no real net-R OOS | Deterministic historical replay and cost-aware risk outputs after verified original rules |
| Data rights | [#27](https://github.com/ngluonghoa/MFX/issues/27) | Cloud M5 MID gathering authorized by user, actual account-specific provider licence/cache reuse and BID/ASK economic pricing not independently verified | Distinguish analysis research vs permitted published actionable signals; verify actual vendor rights |

**Do not claim last actual head is current:** latest independently authenticated bounded private Drive P0.91 audit #43138482666 attempt5 verified M5 41/41 SHA (492 CLOSED M5 to 2026-11-12 10:00 UTC) and nine exact full H4 native/shadow windows. A newer real head requires a fresh authorized read-only audit. This checkpoint did NOT fetch new real candles or Drive price bytes.

## Three milestone targets (conditional)

**12–19 November 2026 — original rules + executable analysis contract.** Source-specify B2/S2 36 qualitative-to-numeric obligations (#45/#62), distinguish owner sign-off from calculations; choose first causally testable source-authorized vertical slice; typed M5,M15,M30,H1,H4,D1 CLOSED-as-of input; immutable BUY/SELL/NO_SIGNAL output contract with reason, entry, SL, TP, R:R and distinct NO_SIGNAL/RESEARCH. No fake source approval or unsourced numeric defaults. Preserve 22 zone design roles.

**20–26 November — real-data read-only integration + replay.** Use *existing* private M5 and native H4/D1 source with independently verified licences/permissions; verify 3/6/12 M5 aggregation M15/M30/H1, gaps/closed/first-known/Sydney-DST, identical time/version identity; run as-of historical and OOS backtests including BID/ASK or legitimate cost bounds, spread, slippage, no lookahead/repaint, dedup, contradictory signals and archive rollback. No added unsanctioned polling.

**27 November–10 December — acceptance/release if gates pass.** Verify source 1:1 parity, original numeric rule owner evidence, lawful data usage, reproducible deterministic signal evidence, all six TF, TP/SL/net-R, OOS performance and invalidation, security and recovery, exact main-push CI Python3.11/3.12 wheels; independently approved signal-only release and operator procedures. **10 December is an ambition, not unconditional delivery.** If numeric source/rights remain pending, publish a transparent NO_SIGNAL/research-only demonstrator and blocked QA report, *never* a misleading verified BUY/SELL release.

## P0.96+ reprioritization (NOT removal/rollback)

Pause **new work** on independent Forex session-signature calendar, provider H4 substitution and optional Cache V2/V3 upgrades until core v1 signal path is working and blockers assessed. Preserve all prior source H4 calendar research, tests, 394 allowed deltas, existing main and workflows; no deletion or rollback. Native H4 avoids needing >=30 exact M5-to-H4 windows or seven actual days **for v1 signal development**; any later H4 replacement still requires its own independent qualifying evidence and explicit owner authorization.

## Minimal release blockers / release stop conditions

1. No independently verified source-authoritative formula per included numeric entry zone means **no verified BUY/SELL** for that zone; never substitute experimental B2/S2 thresholds.
2. No permitted actual feed/account data and suitable timing/price-side accuracy means **no live verified signals**; MID-only does not certify spread/ASK/BID.
3. No causal six-frame history, invalidation, entry/SL/TP/net-R and OOS evidence means **no quality-approved release**.
4. No explicit owner operational signoff or full original 1:1 parity CI means **no published full signal-only MFX 1.0**.
5. No broker integration or automated execution **under any circumstances** in MFX 1.0 signal-only.

**Next code change:** work on a genuinely useful read-only, causal multi-TF signal vertical slice that runs offline against closed typed fixture data and then verified existing archive. Attach exact per-zone source-evidence decision, not another standalone high-numbered H4-research gate.
