# MFX P0.174 — Active P0.171 fresh-D1 source → real six-TF private reader

Date: 2026-11-15 ICT. Priority: [MFX signal-first Issue #138](https://github.com/ngluonghoa/MFX/issues/138), six-timeframe workstream B. **Real source-cache recovery P0.171–P0.173 was accepted; this PR connects the fresh D1 source to a genuine read-only six-timeframe analysis consumer.**

## Why this work is necessary

Until P0.173, MFX wrote the new, SHA-verifiable EUR/USD native Sydney-local D1 cache beginning at **2026-11-11**, but the existing optional GitHub-Drive six-TF read-only consumer still read *only the old immutable V1 D1 archive*, whose 2026-11-11 OHLC conflicted with a later Twelve Data fetch. A hard-coded legacy `P059` HOLD suppressed private six-TF analysis. This was a critical consumer/source selection gap: **a cache that is correctly written but never consumed does not restore the D1 analysis path.**

## Exact source selection and safety contract

1. Keep the original 120-bar D1 V1 archive SHA and *all* H4, M5, P0.169 quarantine evidence independently audited/read-only. The historical D1 source restatement Issue #147 remains documented, but the owner-authorized **new active source** is independent.
2. For the optional owner-gated manual six-TF Drive GET-only workflow, load **both** D1 stores: original V1 D1 for full SHA/origin verification, and P0.171 `MFX_P171_EURUSD_D1_20261111_FRESH_EPOCH_V1_` for **the actual D1 candle calculation**. This is explicit: not a silent fallback or a global P059 override. The original source D1 OHLC is never fed into the new private D1 computations.
3. The P0.174 reader independently audits the complete new epoch's SHA/parent chain, validates SHA and exact names for every new D1 native chunk/manifest, the `>=2026-11-11` label and the original archived V1 manifest SHA root. It rejects missing, orphan, corrupted, duplicated, wrong-origin, unordered or changing sources; no fallback to original V1 if the new cache fails.
4. **As-of safety:** every new epoch manifest's **GitHub runner first-observed UTC** must be no later than the analysis `asof_utc`, and observation order must be monotonic. A current revision cannot be projected backwards into a historical decision time before the source was observed. These are runner-observed timestamps, **not** independently verified *publisher first-known* or as-of OOS certification.
5. The original six-timeframe evaluator still strictly enforces exact CLOSED M5/M15/M30/H1 derived windows, native UTC H4, native Sydney-local D1 closed session date and SHA input provenance. The new private B2/S2 multi-bar, pivot and M15 microbreak research is allowed to *calculate* again only with the separately SHA-audited fresh D1 and the rest of the bounded cache; its **public** action/stage remains `NO_SIGNAL / UNVERIFIED`.
6. Original V1-only consumer path remains **HOLD / NO_SIGNAL**. Caller-supplied synthetic M5 pins cannot accompany the fresh real D1 source; tests may hermetically monkeypatch anchors but no fixture pin is permitted as an API parameter in production mode.
7. Cloud identity is unchanged. The GET-only proxy allows the exact P0.171 extra Drive filename prefix on the existing private Chunk/Manifest folders. It never exposes POST/PATCH/PUT/DELETE, Twelve Data API endpoints, original price values, derived OHLC, private pivot levels, broker order endpoints, or new vendor calls. No schedule, secret, provider quota, cache writer or Drive source mutation is introduced.

## What does NOT become approved

Original Forex B2/S2 36 numeric obligations, independent Option B v2 threshold final sign-off, quote-side BID/ASK/spread/SL/TP net-R economics, publisher-signed first-known, account licensing/retention, true out-of-sample and BUY/SELL publication all remain separate. This integrates **read-only MID-OHLC research**, not trading advice or executable signal production. The original 102 frozen Forex blobs and 11 SOURCE_LOCKED Docs must remain byte-identical.

## QA and acceptance

New hermetic matrix covers immutable origin V1 parent binding, P171 SHA/filename/row verification, no source replays, no stale/retroactive as-of, duplicate/missing/tampered/empty source, explicit old-path HOLD, new technical/private computation path, no synthetic caller pin, new OAuth GET-only namespace and zero external writes. Require exact PR head Python 3.11 and 3.12 suites, frozen-source golden parity, crosswheel, then independently protected-main CI. A **real optional owner-gated manual GET-only six-TF run** on GitHub must separately establish actual runtime integration; test fixtures and CI do **not** falsely claim this step occurred. Preserve no-new-cron, no background ChatGPT tasks, no Mac/MOCHI, no broker. 
