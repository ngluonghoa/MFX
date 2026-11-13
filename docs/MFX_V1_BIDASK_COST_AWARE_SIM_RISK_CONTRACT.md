# MFX 1.0 — P0.151 LONG/SHORT BID-ASK cost-aware NET R:R, SIM research only

Date: 2026-11-13 ICT. Parent critical path [Issue #138](https://github.com/ngluonghoa/MFX/issues/138), B2/S2 source owner 0/36 [Issue #45](https://github.com/ngluonghoa/MFX/issues/45), real data rights [Issue #27](https://github.com/ngluonghoa/MFX/issues/27), native D1 SHA discrepancy [Issue #147](https://github.com/ngluonghoa/MFX/issues/147) HOLD.

## Concrete calculation

New MFX-only pure `mfx_research/bidask_cost_aware_sim_risk.py` uses **existing frozen Forex** `forex_trading.quotes.indicative_price` for explicit, causal input quote reference:
- hypothetical LONG entry is the quote's ASK; hypothetical stop loss/take profit exits are **BID-side absolute price levels** (not MID);
- hypothetical SHORT entry is the quote's BID; stop loss/take profit exits are **ASK-side absolute price levels**;
- each model requires an explicit `SIM:` versioned exit plan and `SIM:` versioned cost set. No default execution costs or numerical source detector thresholds are invented;
- entry/exit slippage and entry/exit fees are specified as **nonnegative absolute quote-currency units per ONE base-currency unit**, not percentages, pips, lot cost, or user account currency. The explicitly supplied BID-ASK market quote already includes contemporaneous spread. Spread MUST NOT be subtracted again as a separate fee or the model would double count it;
- LONG effective entry = ASK + entry slippage; stop/target exit = specified BID level − exit slippage. SHORT effective entry = BID − entry slippage; stop/target exit = specified ASK level + exit slippage;
- net risk per base unit = absolute adverse effective entry-to-stop price loss + both fees. Net reward per base unit = favorable effective entry-to-target price gain − both fees. Experimental net R:R = net reward / net risk. Negative net reward is an unprofitable research result, never silently changed to zero or made a BUY/SELL;
- check stop/target ordering against the **current actual side reference**; reject crossing, wrong exit side, zero/negative/nonfinite effective price, negative/nonfinite fees/slippage, float/string numeric inputs, non-UTC decision time, stale or future-first-known quote claims and exit-only actions.

## Distinct TRUST and PRODUCT gates (FAIL CLOSED)

All `Quote` objects are caller-supplied, even if their `quality` enum says VERIFIED. That flag is NOT independent account rights, publisher signature, licensed retention, original Forex quantitative policy, first-known timestamp attestation, matching instrument identity, executable fill, spread guarantee or future exit quote. Exact instrument must be caller-claimed EUR/USD and is not independently cross-certified against the quote. The stop/target prices and cost amounts are all **SIM assumptions**; a zero fee is not proof live trading has zero fees. The model deliberately exposes numerical research values **in memory only** and MUST NOT serialize them to public CI/GitHub Actions logs or the P0.150 safe Drive audit report.

Receipt is immutable with `action=NO_SIGNAL`, `stage=UNVERIFIED`, `original_forex_numeric_rules_approved=False`, independent rights/first-known/economic/OOS approval all False, no publish permission, no trade permission, zero vendor calls/Drive writes/broker orders. No production scanner or six-timeframe signal engine calls this module; it is a reusable numeric research unit for later separately approved source policy. The frozen original 102 Git blobs, 11 locked Drive Docs, original SIM B2/S2 prototypes, P0.149/150 signal-only shell, active M5/H4/D1 writer/cron, Drive cache SHA, and secrets are unchanged. No Mac/MOCHI/local compute or recurring ChatGPT agent action.

## Cloud CI, acceptance and rollback

The separate `tests/test_mfx_v1_bidask_cost_aware_sim_risk.py` exercises 31 hermetic long/short Decimal cases, cross-spread and slippage sensitivity, negative economics, causal quote windows, source/side misuse, nonfinite costs, wrong intent, denial of forged production rights, no IO and receipt immutability. Tests use `SIM:` quote/exit/cost fixtures and are not backtests or evidence of profitable/lawful market strategies. GitHub Actions Python3.11/3.12 full original Forex-parity tests, crosswheel and post-merge independent protected-main success are required before this checkpoint is accepted. No real market data or credentials can be present in QA logs.

Rollback only new MFX-only risk source, hermetic tests, this document and exact Git blob SHA allowlist entries. Never alter original quote semantics, source owner dossier, real cache or P059 quarantine. Downstream priority: independently source-approved B2/S2 quantitative predicates (currently 0/36), verified live BID/ASK provider rights and first-known clock, cost policy and exact event boundaries, causal OOS and only then controlled signal-only publication. No broker execution.
