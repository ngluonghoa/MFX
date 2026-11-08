# A02/P0.1 — expanded static-analysis gate (Cloud-only, frozen business logic)

**Status:** reviewed PR candidate, not a production release.

## Scope

The original source snapshot is locked to Forex Trading 1.0 commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`, Git tree `5df2058346f6dc96ed5bb02581b139fe2aa2d803`. The independent MFX baseline import is `6ee5e7c07baf4ea8f06a28889175808ea53c2316`. This A02/P0.1 gate **must not modify any domain code under `src/`**, and all previous 50 golden scenarios and byte-parity checks remain mandatory.

The source contains **30 tracked Python modules**, as verified through the frozen Git tree. Before this PR the strict mypy gate explicitly targeted only five contract modules; the Full Pyflakes gate also explicitly targeted only five. A02/P0.1 expands:

- **Ruff/Pyflakes F checks:** `ruff check --select F src/forex_trading`, recursively against all source modules (no waiver intended at this checkpoint).
- **Strict mypy:** 12 explicitly selected contract modules, all under `src/forex_trading`: `model.py`, `pipeline.py`, `scan_contract.py`, `versioning.py`, `release_readiness.py`, `catalog.py`, `quotes.py`, `market_data.py`, `cache_dependency.py`, `side_pair.py`, `source_calendar.py`, `source_qualification.py`. No `--ignore-missing-imports`, `--follow-imports=skip` or blanket type ignores.
- Retain repo-wide critical Ruff checks, existing security/pip-audit, Python3.11/3.12 unit tests, frozen source blob SHA/exception integrity, independent source-vs-MFX 50-scenario golden replay, Cloud wheel installation ownership guard, deterministic build and cross-Python wheel SHA parity.

This is **A02 partial implementation**, not a claim of full strict typing for all 30 modules. The remainder must be brought under mypy strict through later reviewed PRs with QA evidence and explicit source/golden diff approval **if** any original module must change. Never weaken checks silently to make a failing build pass.

## Release/security constraints

- MFX runs only on GitHub Cloud and Google Drive Cloud; no Mac, MOCHI, M15001 or local compute dependency.
- Twelve Data remains the sole currently available market-data MCP (DEC-MFX-002). Static checks never query its API and do not grant a hosted runner credentials, data storage rights or real BID/ASK.
- No broker connection, real order, cloud scheduler, production cache or live trading. Green CI is not an OOS/backtest claim or signed LKG release.
- A01 source-delta manifest SHA-pins changes to CI and this document; changes to `src/` are prohibited in this PR.
