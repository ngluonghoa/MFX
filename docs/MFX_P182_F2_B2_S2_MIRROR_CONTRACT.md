# MFX P0.182 — F2 B2 LONG ↔ S2 SHORT reversible mirror design contract

Owner agreement 2026-11-17 ICT: F2 B2 BUY and S2 SELL should be **exactly mirrored by directional inversion**, with ONE phase algorithm and an independently reviewed ruleset, rather than separate arbitrary/unequal strategies.

## What is evidenced versus approved

- Authoritative original source Forex Trading 1.0 F2 taxonomy B2 ↔ S2; original `SOURCE_LOCKED_03_DETECTOR_AUDIT` B2 zero-based ¶29–34,37–38 vs S2 ¶117–122,125–126; shared ¶9–11 U1–U8.
- Original source **does not yet contain calibrated executable numeric formulas**. Its asymmetric EARLY draft says B2 `HL OR reclaim` versus S2 `reject OR LH OR BOS_DOWN`. Owner approved a NEW design-normalization objective, not retroactive change of the original locked source.
- Source owner exact 18 rules B2 +18 S2 have **Original owner numeric approvals: **0/36****. Neither simulated mirror fixtures nor same-phase equivalence can approve Forex numeric parity, vendor rights, a tradable entry or any backtest/OOS.
- Repo `ngluonghoa/forex-trading-1-0` decision [#72](https://github.com/ngluonghoa/forex-trading-1-0/issues/72), MFX sources [#45](https://github.com/ngluonghoa/MFX/issues/45) and signal-first [#138](https://github.com/ngluonghoa/MFX/issues/138).

## Code proof — what is and is NOT implemented

`mfx_research/p182_f2_directional_mirror.py` is a **synthetic design phase algebra** with one evaluator `evaluate_f2_design` and one involutive transformation `reflect_f2_design`. A claimant presents closed M15 + known prior micro-level timestamps, claimed D1/H4 HH/HL or LH/LL, H1 support or resistance, M15 HL or LH, mirrored internal BOS_UP/BOS_DOWN, common (uncalibrated) zone re-entry, and a price level reflecting about a positive arbitrary *synthetic anchor*. It is **not** a data feed, source verifier, real pivot/zone extractor, actionable BUY/SELL detector, or a scientifically calibrated strategy.

- Preserve one COMMON gate order: source completeness/first-known, regime, zone, invalidation, micro-close confirm, early reaction or watch. Strict micro-level equality is **not** a confirming break. The same confirmed close cannot produce a second early opportunity.
- Under mirror transformation, LONG HH/HL, support, HL, BOS_UP, above micro-high, below invalidation, ASK entry/BID exit map to SHORT LH/LL, resistance, LH, BOS_DOWN, below micro-low, above invalidation, BID entry/ASK cover.
- `zone_reentry` is ONE claimed Boolean placeholder, instead of assuming vague `reclaim` and `reject` descriptions are mathematically equivalent. Proper sweep/re-entry, ATR units, confirmed right-bars, SL/TP, broker margin, DST, cost and expiry are intentionally **NOT implemented** pending original numeric review.
- Strict first-known UTC causal chain: micro-level known by M15 open, M15 close before source first-known before current as-of. Source completeness claim false becomes `UNVERIFIED`, never `NO_SETUP` or `CONFIRMED`.
- All results public `NO_SIGNAL`; `may_publish_buy_sell=false`, `may_execute_broker_order=false`, zero provider/Drive calls and writes, zero secrets, zero source code changes. The reported hypothetical entry/exit side is explanatory only; no cost/slippage/fill calculated.

## Acceptance matrix and rollback

20 hermetic test cases include BOTH directions and double inversion, all WATCH/EARLY/CONFIRMED_DESIGN_ONLY/INVALIDATED/NO_SETUP/UNVERIFIED stages, strict micro tie, BOS_UP↔BOS_DOWN parity, one-event confirm precedence, invalidation precedence, failed source clocks, future-known pivot, invalid prices, wrong zones/trends/rules, event ID and immutable typed record, no approval or broker mutation.

The actual original 102 frozen Forex source blobs, 11 SOURCE_LOCKED Docs, P021 36-row source queue, P171 source data and #180 SHA quarantine must remain untouched. This PR has NO Cache, OAuth, provider, secret, scheduled ingestion, real BUY/SELL or broker change. Require protected GitHub exact-head Python3.11+3.12 full parity CI, hash-pinned baseline and postmain CI. Rollback is source-specific removal of these three MFX-only paths plus pinned allowlist rows; don't mutate Drive source history.

After owner-approved source formula and permission evidence, a **separate PR** can implement actual causal detectors, zone/ATR and side-specific net-R risk. Until then release remains `NO_SIGNAL / UNVERIFIED`.
