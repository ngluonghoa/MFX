# A04/P0.32 — Computed synthetic closed-OHLC research bridge (B2/S2 → approved 22-zone router)

**Scope:** This changes the project from *caller-asserted zone labels only* (P0.31) to **OHLC-computed, experimental, synthetic B2/S2 pattern evidence**, but is **NOT** a source-approved numerical Forex 1:1 detector, real BUY/SELL user alert, profitable strategy, broker order or 22-zone detector implementation.

## What is actually calculated
The new separate MFX research module `mfx_research/p032_synthetic_ohlc_bridge.py` calls existing independently derived P0.19 D1/H4/H1/M15 causal SIM context, which computes:
- D1 and H4 two-bar higher-extrema/lower-extrema **trend proxy** (not confirmed structural pivots);
- H1 true-range / ATR proxy, derived recent support/resistance zone and previous M15 known micro level, all from already CLOSED fixture OHLC and first-known/retrieval cutoffs;
- P0.18 **experimental owner-unapproved** B2 LONG or S2 SHORT proximity, microbreak and anti-chase patterns using explicitly supplied versioned `SIM:` numeric research parameter values, which are **not original Forex-1:1 thresholds**.

If **and only if** a real numeric calculation on closed synthetic OHLC meets the experimental pattern, the bridge constructs its own typed SIM claim (the caller never supplies a claimed zone) and passes that one B2/S2 label to the **approved 22-zone** P0.31 router. This creates a deterministic unverified research event with `NO_SIGNAL` as its external action. A calculated `NO_SIGNAL` produces **zero** router labels/events. The bridge deliberately does **not** implement the other 20 zone detectors, and the source numerical approvals for all 16 entry candidates remain **0/16**.

The research origin event ID is derived from SIM instrument/calendar/provider/stream and the two M15 trigger time boundaries, independent of rule/parameter names; a separate full-fixture SHA256 fingerprint covers each D1/H4/H1/M15 OHLC and claimed observation metadata. The SHA256 **is a reproducibility fingerprint, not vendor price attestation, signed data or global idempotence**. Same research identity does not by itself prove independent event equality across differing OHLC; comparison must also consider the source fingerprint.

## Fail-closed and future gate requirements
Existing P0.18/P0.19 reject wrong timeframe, noncontiguous H1/M15, non-CLOSED bars, partial coverage, unverified quality, future-known HTF data, unapproved revisions, mixed SID/provider/calendar and non-SIM source. P0.31 additionally validates exact UTC `closed_candle_end <= first_known <= retrieved <= decision`, approved label roles, dedup and conflict. Our bridge explicitly denies unsupported rule IDs other than B2/S2, mismatched computed direction, and any attempted semantic elevation of `UNVERIFIED` experimental research to confirmed BUY/SELL or exit.

Even a computed `experimental_numeric_action=BUY` or `SELL` is *internal research nomenclature*, not an authorized market alert. Public `action=NO_SIGNAL`, `may_send_buy_sell_or_exit_alert=false`, `actual_buy_sell_signals=0`, `broker_orders=0`, `release_ready=false`. There is no genuine data provider integration, real quote cache, BID/ASK spread, TP/SL/OOS evidence, or verified position state. Original Forex frozen 18 labels and 102 Git source blobs are untouched; historical MFX 19/P028E and current design 22/P030 remain intact.

## QA
[Issue #56](https://github.com/ngluonghoa/MFX/issues/56) preregisters 24 positive and negative OHLC/causal/anti-lookahead/roles/provenance/nonpromotion checks before coding, plus a hosted Cloud-only SIM B2/S2 pass/NO_SIGNAL demo. CI full inherited tests run on Python 3.11 and 3.12, strict mypy/Ruff/security/frozen source blob SHA/wheel parity. Changes restricted to new separate `mfx_research/`, `tests/`, `tools/`, docs and authorized SHA allowlist/CI, never original `src/` or source-locked Google Docs. Independent post-squash main push CI is an additional gate and must be tracked as UNVERIFIED if no connected action can inspect it.

**Remaining owner/data blockers:** [Issue #45](https://github.com/ngluonghoa/MFX/issues/45) 36/36 exact B2/S2 numerical source obligations unsigned; [Issue #27](https://github.com/ngluonghoa/MFX/issues/27) vendor FX licensing/native BID/ASK and real Google Drive quote data cache retention rights missing. Neither is bypassed by this offline engineering milestone.
