# MFX P0.166 — Option B v2 chronological B2/S2 + explicit simulated BID/ASK net R

**Scope:** signal-first integration of existing independent MFX Option B v2 right-confirmed OHLC pattern, replay and existing BID/ASK risk calculator. 2026-11-14 ICT. Cloud-only. Synthetic in-memory scenario, NOT public trading advice or a real historical backtest.

## Gap closed (does not duplicate existing modules)

- P0.161 `mfx_b2s2_confirmed_policy_v2`: true right-closed D1/H4 pivots, confirmed pre-trigger M15 pivot and H1 zone, experimental B2 BUY/S2 SELL with all public source/trade permissions false.
- P0.165 `option_b_v2_chronological_replay`: actual P0.161 calculations recomputed across chronological snapshots, same-source event dedup, changed OHLC or contrary same-event B2/S2 denied, private SHA trace.
- P0.151 `bidask_cost_aware_sim_risk`: Decimal LONG ASK entry, BID stop/target, SHORT BID entry, ASK stop/target and separate entry/exit slippage+fees; no double-counted spread and no guessed fill.
- P0.152 `p152_sim_signal_risk_vertical_slice._join_quote`: existing same M15 closed synthetic MID-to-BID/ASK quote provider/event/first-known/spread bracket gate; originally linked older two-HTF extrema proxy, not P0.161's independently right-confirmed v2 detector.

New `mfx_research/option_b_v2_bidask_replay_bridge.py` composes those **four already proven components** without re-implementing source-price algebra. Each selected P0.165 v2 candidate optionally receives caller-specified complete `SimRiskBundle`: one immutable synthetic quote, explicit hypothetical EXIT-side stop/target, per-base-unit fees/slippage and maximum quote age. B2/S2 direction comes from *actual recalculation*, never caller-supplied permission flags. For each unique closed event, same-source and same-M15 quote join is enforced before calculating cost. No candidate -> no pricing; absent bundle -> no economic claim. Exact duplicate historical event with same risk input is suppressed and cannot generate a second calculation; changed same-event BID/ASK, stop/target or fees are rejected, not retroactively repriced. Source conflict is already rejected by P0.165. Private results and SHA chains remain internal to hermetic test/research; public safe record displays only counts and NO_SIGNAL/UNVERIFIED.

## Rights and evidence boundaries

- SIM quote BID/ASK and hypothetical stop/TP are *invented test inputs*, not observed executable prices or automatically derived structural stops.
- Decimal net R:R computation mathematically accounts for assumptions but says **nothing** about actual slippage, broker fills, future target/stop paths, trading profitability or genuine OOS.
- Exact first-known, source rights and publisher revision evidence are not inferred from caller-claimed fixture metadata or hashes.
- No new vendor quote/API, Google Drive GET/PUT, Cache writer, scheduled workflow, secrets, MT4/MT5, broker order, Mac/MOCHI/local code path; original 102 Forex source Git blobs and 11 SOURCE_LOCKED Google Docs remain unchanged.
- Critical external stops: Issue #147 real Sydney D1 2026-11-11 numeric OHLC revision remains quarantined; Issue #27 exact Twelve Data account/tier licence, private derived/raw Drive replay/retention still unresolved. MFX Option B v2 numeric pivot widths and thresholds remain unapproved, original B2/S2 36 source numeric obligations unsigned; true real as-of replay, BID/ASK market costs and untouched chronological OOS not established. **MFX publicly NO_SIGNAL/UNVERIFIED; no orders.**

## Acceptance and rollback

26 hermetic actual-integration tests for B2+S2, 2-window chronology, duplicated quote prevention, quote/cost restatement rejection, stale/future/mismatched quote, source MID bracket, side-specific SL/TP, cost monotonicity, no-pattern gate, mutated receipt/replay, no real-provider injection, deterministic internal chain, redacted public output, zero external I/O. Requires hosted exact PR Python 3.11/3.12 and crosswheel, source-golden/security; then independent exact protected-main CI and canonical Google Drive documentation. Rollback only new MFX adapter/tests/doc and their SHA-ledger exceptions, not original Forex frozen sources or actual cache.
