# MFX P0.206 — Close the seven missing **decision specifications**, not the seven missing approvals

**Scope:** P0.188 already contains eleven paired B2 LONG/S2 SHORT *MFX-only experimental research formulas*. This change adds seven **symbolic, owner-and-source-dependent review questions** so all eighteen qualitative requirements in frozen `SOURCE_LOCKED_03` can be presented with explicit mirrored evaluation paths. The original Forex numerical approvals remain **0 of 36**, not 22 or 36 completed; an unfilled evidence requirement is **not** an approved numeric predicate. No strategy is executed or released by this change.

## Seven paired unresolved decisions

| Source requirement | B2 LONG conditional design | S2 SHORT conditional design | Still requires |
|---|---|---|---|
| `structural_hl_lh_invalidation` | Cancel when CLOSED price breaches *pre-known* higher-low support minus approved buffer | Cancel when CLOSED price breaches *pre-known* lower-high resistance plus approved buffer | Pivot provenance, buffer/method, invalidation approval |
| `bid_ask_spread_and_cost_gate` | ASK entry, BID exit; actual spread+fees+slippage within owner-defined budget | BID entry, ASK exit; identical cost gate | Licensed historical executable side quotes, account fees, max spread/slippage |
| `session_dst_rollover_news_gate` | Only approved sessions; block unverified DST/rollover/news windows | Identical session guard | Verified source-specific calendar, time-versioned news/blackout windows |
| `structural_sl_tp_net_r_gate` | SL below pre-known support, TP at pre-known resistance; after-cost net R threshold | SL above pre-known resistance, TP at pre-known support; after-cost net R threshold | Stops/targets, touch-order uncertainty, minimum net R, BIDASK execution costs |
| `event_expiry_and_idempotence` | Source-version+origin+CLOSED trigger identity, owner-defined M15 expiry, prevent replay duplicates | Same identity and expiry, SHORT side | Expiry N, origin identity, revision/retirement policy |
| `licensed_source_first_known_revision` | No signal if source first-known/licence/active D1 revision authority absent | Identical strict source gate | Actual account rights, immutable original/revised D1 lineage, publisher first-known |
| `historical_walkforward_oos_qualification` | Pre-registered chronological LONG OOS plus after-cost scoring | Equivalent SHORT OOS with same temporal discipline | Minimum samples, folds, embargo, drawdown/expectancy thresholds, independent acceptance |

All numeric variables are **blank intentionally**. `P206` defines a deterministic, source-indexed, non-executable contract rather than filling or signing them. The new code reads and cross-validates P188's eleven existing proposals against the original eighteen requirements, refuses a changed seven-gate contract, enforces original paragraph/phase indices, and reports only source-review counts and `NO_SIGNAL`.

## Official Twelve Data feasibility findings (not account entitlements)

- Twelve Data describes Forex as typically **MID** quotes by default, with variation across sources; an OHLC MID candle is not a historical tradeable BID/ASK price: https://support.twelvedata.com/en/articles/11850499-understanding-price-deviations-in-commodities-and-forex-data
- Twelve Data WebSocket documents **bid/ask where available**, not an EUR/USD account-specific entitlement, nor first-known or historical replay authorization: https://twelvedata.com/docs/websocket/websocket-getting-started
- The vendor's April 2026 update clarifies the `timezone` query option applies only to intraday; `1day` follows the exchange-local timezone. It does **not** guarantee OHLC immutability: https://twelvedata.com/news/april-2026-updates
- The vendor's publication-delay guidance is latency context, not evidence of an immutable daily source vintage: https://support.twelvedata.com/en/articles/5203307-data-delays

## Acceptance and next owner/source work

Maintain strict 1:1 frozen Forex 102 source Git blobs and 11 `SOURCE_LOCKED` Docs. All P0.206 tests are **hermetic** and fail closed, no provider I/O, Google Drive read/write, extra cron, OAuth, manual 6TF bypass, source D1 canonical revision, production signal, broker connection or local compute. Preserve approved existing M5/H4 writer and quarantined P192 18-Nov D1. Require exact PR-head Python3.11/3.12, baseline/golden/security and crosswheel, protected squash-only merge, independently verified main CI.

This creates **7 explicitly reviewable external decisions**, not 7 approved strategies. Actual progress to signals still needs signed source owner 36-row numerical evidence (#45), account-specific quote/retention/BIDASK permission (#27), separate append-only 18-Nov D1 source revision admission and publisher first-known (#180), net-cost time-causal OOS and explicit release authorization (#138). Do not assert release readiness, profitability, or a fixed delivery date from this development-only step.
