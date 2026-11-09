# A04/P0.16 — First executable offline BUY/SELL research evaluator (NOT Forex 1:1 detector)

**User scope:** Forex analysis and BUY/SELL signal presentation ONLY, never broker order placement. Development is Cloud GitHub Actions plus Google Drive governance only.

## What this PR actually implements

Working, pure, deterministic `mfx_research.offline_ema_signals.research_only_ema_signal` in a **separate MFX-owned non-release research package** outside all frozen `src/forex_trading` modules. It consumes **six fully synthetic, causal closed M15 MID bars** using the original frozen Forex `MarketBar`, `evaluate_closed_bar` and `ema_full` helpers. It produces **BUY**, **SELL** or **NO_SIGNAL** when fast EMA2 crosses slow EMA3 on the *last* closed bar only. This explicit EMA crossover is a research demonstration, NOT the frozen source's numerical 18-zone signal policy, threshold, early/confirmed state or TP/SL policy. It is not installed in the `mfx-forex-core` wheel and is not remotely deployed.

An output always contains `SignalStage.UNVERIFIED` (never early/confirmed), `strategy=EXPERIMENTAL_EMA_CROSS_NOT_FOREX_1_TO_1`, `source_verified=false`, `economic_parity_proven=false`, `can_trade=false`, zero provider calls and zero Drive market cache writes. Price basis MID is technical reference only, NEVER executable ASK/BID. All chart/quote values are `SIM:` synthetic; no vendor API or customer credentials.

## Fail-closed behaviors with real code + unit tests

The pure evaluator refuses future revisions, future retrieval, provisional/open candles, incomplete coverage, unverified quality, noncausal calendars, non-M15 source, non-MID price basis, forged real-provider identities, fake licenses, revised bars without explicit as-of, mixed provider/instrument/stream, non-contiguous/gapped/reordered bars, insufficient/bounded history, invalid EMA periods and naive datetimes. No trust is inferred from synthetic `SourceQuality.VERIFIED`.

The CI demo runs three actual artificial series of six prices:
- BUY: 12,11,10,9,8,14 → EMA2 crosses above EMA3 on last closed bar
- SELL: 8,9,10,11,12,6 → EMA2 crosses below EMA3 on last closed bar
- NO_SIGNAL: 10,10,10,10,10,10 → no cross
These are **not actual EUR/USD prices**, not a backtest/OOS claim, not live data or financial performance.

## Governance, parity and gaps

Exact frozen Forex base commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309` and MFX 102 blob initial import `6ee5e7c07baf4ea8f06a28889175808ea53c2316` unchanged. Original 30 core domain modules untouched (24 byte-identical, 6 older approved type-only). A04/P0.11 58 unmapped field obligations and **unimplemented numerical 18-zone detector/TP1/TP2 and realistic quote-side economic proof** remain. This research module DOES NOT demonstrate 1:1 strategy parity or authorize promote to production/confirmed signals. Separate provider licensing/Drive cache rights still blocked in [Issue #27](https://github.com/ngluonghoa/MFX/issues/27).

Expected QA: exact PR-head and independent protected-postmain 3/3; original 50 frozen golden, 34 transparent wrappers, P0.8 28 STOP, all P0.9–P0.14 static and entitlement gates, 17 mutation sentinels, 80 feedback, 30-module coverage non-regression, strict mypy for original 30 plus new research evaluator/runner, Ruff, secrets audit and cross-Python wheel parity. No release and no trading. Next meaningful step is to port **actual frozen numerical 18-zone detector** once original algorithm/source requirements can be identified and proved, without inventing equivalent thresholds.
