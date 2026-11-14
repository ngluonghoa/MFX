# MFX P0.167 — post-entry BID/ASK M5 OHLC exit-touch ambiguity audit

Date 2026-11-15 ICT. Narrow new capability after P0.166: **observed price-range level touch is not a verified executable fill or P&L**.

## Functional change

P0.166 already computes hypothetical private B2/S2 ASK/BID entry and exit reference levels with spread, commissions, exit slippage and Decimal net R:R, but **does not inspect any later quote-side bars for whether the stop/TP would be touched**. Reusing that receipt, P0.167 introduces a purely in-memory, side-specific M5 OHLC event-path audit. It NEVER re-runs the signal on later candles; earlier B2/S2 closed-bar causality remains sealed.

The audit requires fully CLOSED/COMPLETE and SIM-claimed quality M5 bars in strictly contiguous order. LONG must use BID after entry, SHORT must use ASK. Each new record must match the earlier M15 trigger source instrument, calendar/aggregation, provider and stream and must be first-known and retrieved before the **later audit UTC**. Earlier than entry or future-known bars, gaps, other sides, non-SIM vendor names, missing coverage, mixed streams and invalid counts all fail closed. No real price, source rights or vendor authorization can be laundered into the evaluation.

For each P0.166 unique economic event it scans up to 96 future five-minute bars and returns ONLY the first observed breach category: stop-only, target-only, **both same bar ambiguous**, first-visible-open already beyond stop/TP (cannot infer fill at level), no level touched in supplied valid interval, or no future path supplied. An absent pricing bundle or replay duplicate cannot supply a second exit path. Importantly, a bar that spans both SL and TP is **never** treated as a profit or sequenced by an arbitrary stop-first/TP-first guess; no realized money/return is computed, even for single touches. Private provenance and level-bar contents are SHA chained for deterministic verification; public safe record contains aggregate counts, NO_SIGNAL/UNVERIFIED, and no private OHLC, directional hints, level prices or fingerprints.

## Hard boundaries

All tests use explicitly created synthetic BID/ASK M5 bars with simulated first-known UTC; not live Twelve Data composite MID, not broker tick path or executable fills, not real historical OOS, real WIN/LOSS, cash P&L or measured expectation. True intrabar order remains unresolvable from M5 OHLC. Real future source correction first-known, revision lineage, quote-side use and lawful retention/Replay permissions require independent vendor evidence.

Issue #147 D1 2026-11-11 OHLC dispute and source quarantine persist. Issue #27 plan-specific data licences/raw+derived Drive storage retention/replay/display still open. MFX Option B v2 H1/ATR/confirmed pivot/anti-chase thresholds are engineering drafts, not signed; true historical as-of, no-lookahead OOS, realistic gap/slippage/fees/swap, stop/target strategy-owner approval and protected release all pending.

No new provider calls or real Drive reads/writes, scheduled workflow, secrets, source-cache mutation, account, order, MT4/MT5 or Mac/MOCHI/local. Immutable original Forex102 Git blob baseline and eleven SOURCE_LOCKED Docs unchanged.

## QA and release gates

26 hermetic cases for side-specific stop/target, both-collision ambiguity, gap/no-path distinction, contiguous M5, UTC first-known/retrieved, source identity, SIM only, duplicate and no-pattern exclusion, receipt chain tamper, redacted public counts and rights/PNL false. Accept only exact PR and independent protected main Python 3.11+3.12 CI, static/security/frozen-source and crosswheel. Roll back only the P0.167 helper/test/doc/allowlist; do not rewrite original D1 or source quarantine.
