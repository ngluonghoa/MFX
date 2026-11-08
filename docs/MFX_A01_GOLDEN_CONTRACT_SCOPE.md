# A01/P0.2 — frozen-source vs MFX synthetic golden contract parity

## Why and boundary

A01/P0.1 already verifies all 102 frozen source Git blobs and a SHA-pinned MFX-only delta list. A01/P0.2 adds **runtime output** comparison on the *same deterministic inputs*, independent of byte-level source comparison. It is a golden **contract** check for the currently implemented read-only domain modules, not a real Forex strategy or broker fill test.

**Immutable source reference:** `ngluonghoa/forex-trading-1-0` at commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`, Git root tree `5df2058346f6dc96ed5bb02581b139fe2aa2d803`.

**CI procedure (Python 3.11 and 3.12, on independent GitHub-hosted runners):**

1. Check out exact frozen Forex SHA into a separate ephemeral Cloud workspace folder with pinned `actions/checkout`, with credentials not persisted. Verify both actual commit and Git tree SHA before executing anything.
2. Run exactly the same fixed-input renderer `tools/render_golden_contract.py` against the frozen source checkout and MFX checkout using **separate Python subprocesses and explicit `PYTHONPATH`**. The renderer verifies the actual `forex_trading` import path points to the intended respective `src/` root. It never imports the source project as the MFX distribution or coinstalls both distributions.
3. Run `tools/compare_golden_contracts.py`. Compare typed, canonicalized JSON output, error types/reason codes, and scenario identities; refuse missing/extra cases, ambiguous error semantics and result mismatches. Emit an auditable SHA256 digest of the matched snapshots.
4. Continue the same three required protected CI jobs, A01/P0.1 Git tree/source SHA guard, import ownership guard and cross-Python wheel verification.

## Scenarios covered

Deterministic synthetic-only cases cover: 18-label zone taxonomy, WATCH-only and FX-B9 rejection, all three 20-pair selection modes with no provider-fetch authorization, quote BID/ASK entry/exit mapping and source freshness, typed signal DISPLAY restrictions, eight pipeline stages, M5/M15 first-known/closed bars and controlled early arming, late revisions versus as-of lookahead, synthetic L1 incremental cache overlap/append/revision and L1–L5 dependency closure, profile fingerprint and conservative rollback compatibility. Both positive outcomes and fail-closed reasons must match.

All actual domain source files under `src/forex_trading` are intentionally unchanged by this PR; their 1:1 import API is preserved. Generated golden snapshots are ephemeral GitHub CI artifacts, not persistent market-data cache, and do not access Twelve Data.

## Explicit limitations / release holds

- Synthetic contracts are **not** full executable 18-zone detector numeric algorithms. No assertion is made that market strategies, indicator calculations, broker spread/fills, TP/SL, actual FX data, all pairs/timeframes, latency or backtest performance have been validated.
- Comparison on finite golden fixtures does not prove behavior on every possible input; byte parity currently supplements it for unchanged domain source. Later domain changes require approved source exceptions and expanding golden fixtures with evidence.
- No live source license, historical qualified BID/ASK, production Cloud runtime/MCP auth bridge, Google Drive data storage rights, OOS, signed release/LKG, paid scheduler, broker, or real money orders are granted. Twelve Data remains the single connected market-data MCP candidate, not a source of these synthetic fixtures.
- Never change, push to or rewrite the original Forex Trading repository. MFX main is protected; each subsequent change uses a separate PR with CI and rollback evidence.

## Required acceptance

- Two independent executions per Python, frozen source SHA and tree anchored correctly; matched output/exception/negative-case digest and scenario IDs; strict comparator unit negative tests pass.
- Existing 582 tests + 14 comparator tests = at least 596 tests on each Python version, unless test inventory is changed and explained.
- No `src/` delta; A01 baseline verifier PASS; MFX import ownership PASS; 3/3 CI required checks PASS on both PR and merged `main`.
- Mark A01/P0.2 **synthetic golden contract parity PASS** only when observed in CI; do **not** mark full executable strategy parity PASS.
