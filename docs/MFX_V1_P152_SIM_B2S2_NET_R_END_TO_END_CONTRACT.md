# MFX 1.0 P0.152 — OFFLINE complete B2/S2 SIM candidate → cost-aware net R:R vertical slice

Date: 2026-11-13 ICT. Signals-only MFX v1; protected predecessor PR #151 main `5956f7a22b43bff4d6b6115b15b6413ce52d94f2`. Umbrella issue [#138](https://github.com/ngluonghoa/MFX/issues/138), original source-owner B2/S2 [#45](https://github.com/ngluonghoa/MFX/issues/45), vendor rights [#27](https://github.com/ngluonghoa/MFX/issues/27), native D1 quarantine [#147](https://github.com/ngluonghoa/MFX/issues/147).

## Real code path, experimental input only

This PR first composes three **already existing and CI-tested** MFX-only components in one runnable pure in-memory call `review_sim_b2_s2_with_net_risk`:

1. Existing P0.19/P0.32 authentic *synthetic* closed D1/H4/H1/M15 time-series calculations derive the experimental B2 uptrend/reclaim or S2 downtrend/rejection pattern; B2→BUY and S2→SELL are internal `experimental_pattern` research hints, **NOT original Forex source-approved signal predicates**.
2. Existing P0.31 role router deduplicates into the correct B2 or S2 22-role research event. Missing pattern leaves no fabricated zone event and no economic result.
3. For computed experimental pattern only, an **explicit complete SIM-only** BID/ASK quote + stop/target EXIT-SIDE price levels + entry/exit fees/slippage + quote max-age budget is joined to the same closed M15 event. Quote provider/revision must be `SIM:`, provider must match original synthetic M15 source, quote event and first-known cannot precede closed event, quote event must not exceed decision time, and M15 MID close must be bracketed by same simulated BID/ASK. Quoted price inputs are independently caller-supplied claims, not publisher attestation.
4. Accepted P0.151 risk calculator then computes real Decimal **mathematical** (not market) LONG ASK entry / BID stop-target exits or SHORT BID entry / ASK stop-target exits, net risk/reward including distinct entry and exit slippage/fees; it does not double count spread. Hypothetical stop/target and costs are mandatory user-supplied SIM hypotheses, NOT default Forex 1:1 strategy settings or actual future fill prices.

An immutable `SyntheticPatternWithNetRisk` keeps one event, one experimental hint, optional internally held economic receipt, deterministic non-signed fingerprint and explicit `NO_SIGNAL/UNVERIFIED` external action. It cannot call Twelve Data, real Google Drive, release alert endpoints or brokers, and is **not imported** into the production/sealed private Drive audit pipeline. No raw OHLC/BID/ASK or model economics emitted to public CI logs; tests work with fictitious `SIM:` numbers only.

## Testable behavior and adversarial limits

32 hermetic cases cover computed B2 BUY / S2 SELL internal research hypotheses and corresponding unit-cost math, conflict-free routing, no-pattern/no-economics, empty and partial bundles, provider/quote revision mismatch, future/noncausal first-known, contradictory MID vs BID/ASK snapshot, wrong stop/target quote side, real-provider injection, expired quote, wide spread/cost deterioration, negative net return still research, deterministic input fingerprint and no-laundering `NO_SIGNAL`.

**This is NOT a multi-source authenticated live six-TF signal**: the existing P0.32 P0.19 simulator uses D1/H4/H1/M15 synthetic closed candles, not live M5/M15/M30/H1/native H4/native Sydney D1. The current exact **real** six-TF SHA-driven P0.149/150 read-only response still always `NO_SIGNAL`; it does not call this module. A SIM quote quality claim marked `VERIFIED` is solely a fixture precondition accepted by the frozen original quote guard, never proof of vendor identity, actual BID/ASK executable quote or legally permitted use. SIM local digest is *not* independent issuer/custody signature.

Original frozen Forex 102 Git blob/11 SOURCE_LOCKED Doc parity and 22 roles unchanged. B2/S2 0/36 original source numerics and remaining 14 entry strategies still unapproved. Twelve Data account rights, publisher first-known/revision, real bid/ask/cost, causal true OOS and M5/M15 intrahour freshness not accepted. The actual D1 Nov 11 P059 numeric revision discrepancy remains owner-HOLD #147; no archive/source write, no new provider calls, no cron/workflow/secret or Mac/MOCHI/local engineering, no ChatGPT background automation. Never generate a live user alert or trade.

## Acceptance, rollback, next stage

Require exact-hosted PR Python3.11/3.12 tests (all inherited original Forex parity and MFX SHA guards), security/static checks and cross-wheel; after merge, independently verify protected-main full CI. Roll back only the three added MFX-only files and their pinned SHA exception entries if necessary, preserving P0.151 and all other current integrations.

NEXT source-first: obtain accountable owner numeric B2/S2 rules, genuine licensed BID/ASK economic and temporal evidence and actual closed-source six-TF causal inputs; only those independent gates may enable *separately approved* informational BUY/SELL. Source owner has not signed any numeric strategy in this PR.
