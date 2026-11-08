# M1/P0.4b — MFX Python distribution/import collision guard

**Scope:** Cloud-only CI protection, not a Python package rename, source/provider implementation, trading rule change, release or order execution.

## Why this exists

The MFX wheel distribution is `mfx-forex-core`, but the frozen Forex Trading 1:1 API continues importing Python package `forex_trading`. Distribution names and import package names are different concepts. Co-installing upstream `forex-trading-core` with `mfx-forex-core` into the same Python environment would cause ambiguous/overwritten `forex_trading` modules.

## Testable safety rule

On each protected Python 3.11 and 3.12 CI job, after building the wheel, install that **local wheel** with `--no-index --no-deps` into a brand-new ephemeral Cloud virtual environment and run `tools/check_mfx_import_ownership.py`.

The guard MUST reject: missing/wrong distribution name or version; upstream distribution co-installed; interpreter outside venv; absent/multiple/wrong distribution owners for `forex_trading`; missing import module; module whose resolved path lies outside the isolated virtual environment. Synthetic negative and positive tests are in `tests/test_mfx_import_ownership.py`.

This intentionally does **not** invoke Twelve Data or any other market-data MCP, use credentials, store data or activate a Cloud scheduler. It is a packaging/install boundary check. Existing 556 synthetic contracts still run, plus the new ownership tests.

## Status and limits

- Frozen original Forex source tree: `5df2058346f6dc96ed5bb02581b139fe2aa2d803` at source commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`.
- MFX immutable original import snapshot: `6ee5e7c07baf4ea8f06a28889175808ea53c2316`.
- MFX first identity release-metadata change: PR #1 squash-merged at `d11e6dedfc3150d49a8c5a49e648e46b23d68795`, with 3/3 main CI PASS.
- This PR modifies only one GitHub CI file, a standalone build-time guard, its tests and this document. No `src/forex_trading/**` domain source file or financial behavior is changed.
- A full native import namespace transition (e.g. to `mfx_forex`) is **not** claimed here. It would require a separate explicit migration/compatibility policy, comparable source and 1:1 fixtures, full testing, and rollback. Until then run the two projects in separate Cloud environments.
- Existing `DEC-MFX-002`: Twelve Data is the **only currently connected market data MCP**; no verified historical broker-specific BID/ASK rights/quotes, no production runtime token or provider fallback.
- No live orders, broker integration, real-money trading, release promotion, scheduler or actual deployment are permitted by this change.
