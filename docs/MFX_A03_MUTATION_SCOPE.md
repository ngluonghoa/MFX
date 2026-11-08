# A03/P0.2 — Cloud-only targeted mutation adequacy, scope and evidence

## Goals and fixed source

Initial source parity is anchored to frozen original Forex Trading commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309` and original MFX import commit `6ee5e7c07baf4ea8f06a28889175808ea53c2316` (original 102 Git blobs). Current protected MFX pre-A03/P0.2 main is `e1ddb398a367f4071beb6284ce30fb21369fb5c5`. The source still has 24 untouched original Python file blobs + six A02 type-only SHA-pinned deviations.

This PR introduces **no tracked `src/` modifications**, no dependency, no live FX data access and no broker/trade permission. It adds deterministic mutation-sentinel quality measurement for implemented synthetic read-only contract behavior.

## Mutation campaign design

`tools/run_a03_mutation_sentinels.py` copies only the 30-module Python source package into a fresh `tempfile.TemporaryDirectory` on a disposable GitHub-hosted runner. It sets `PYTHONPATH` to the **temporary copy only** (plus test directory), verifies the actual `forex_trading.__file__` points to that temporary source, and first executes **all 29 A03 synthetic/oracle test methods on the unmodified copy**. Any baseline failure is an infrastructure error and never counted as a mutation kill.

It then tries **17 fixed, explicit, source-valid, single-anchor mutant definitions**, one at a time, isolated within that temporary directory. Each defined mutated source file is restored from bytes immediately after the test; no Git commit or checked-in source file is changed, and the whole temp directory is deleted at completion. The runner validates AST syntax, required source module count, unique mutation IDs and source anchors, approved module path allowlist, targeted unittest identity and `Ran 1 test` count. Missing imports, source-root escape, malformed results or non-zero tooling errors are **INVALID**, not a successful kill. A target mutation is KILLED only when its specific test fails/errors; if it passes, the mutant SURVIVED and CI is red. An exact target score of **17/17 kills** is required for this limited sentinel set on BOTH Python 3.11 and 3.12 runners. Each receipt includes mutant ID, targeted test, mutated text SHA256 and observed disposition, followed by `MFX_A03_MUTATION_SENTINELS_PASS`.

Mutated semantics cover:
- BID/ASK entry/exit side mapping, fresh-at-boundary vs future-as-of, quote staleness cutoff and unverified quote rejection.
- M5 prior HTF causal cutoff, MID being non-executable, late revision as-of, accidental M5↔M15 early arming swap.
- Cache bounded delta range, overlap size, same-revision number guard and same-known-timestamp guard, L1–L5 invalidation propagation.
- EMA degenerating to raw close or using the wrong smoothing weight.

`tests/test_a03_mutation_oracles.py` adds **five independent synthetic tests**: quote exactly at first-known boundary, EMA known closed-form 3-point sequence and nontrivial smoothing, same-revision with newer known time, and higher-revision with unchanged known time. Expected EMA constants are not computed via the function being tested, avoiding a circular oracle. The A03/P0.1 seeded 24 test suite and 50 original Forex/MFX golden cases are retained unchanged.

## Strict interpretation and limitations

`17/17` is **targeted mutation sentinel adequacy for 17 deliberately chosen mutants**, not a project-wide mutation score, not general coverage-guided fuzzing, not all-input semantic parity, not proof of financial returns. No mutated code is allowed in actual MFX modules, release wheels, production cache, Google Drive data or original Forex repository. The CI step runs before packaging and is limited to disposable GitHub runner processes.

Genuine executable numeric detectors across 18 labels, full TP/SL position/fill models, qualified matched BID/ASK historical prices, Twelve Data cloud-authenticated provider transport, untouched out-of-sample market backtesting, and broker or live orders remain **NOT_IMPLEMENTED / NOT_VERIFIED**. Thus A03 as a whole is still PARTIAL even if this controlled milestone passes.

## QA and promotion

Protected PR requires 3/3 CI checks and both Python versions proving baseline 29 A03 methods PASS and 17/17 mutation sentinels KILLED, as well as:
- original source Git tree/102-path manifest with exact six prior A02 typed SHA exceptions,
- 50 fixed synthetic Forex-vs-MFX golden parity scenarios,
- A02 pinned mypy --strict 30/30 and all-source Pyflakes exact 24 preexisting F401,
- complete prior **636 unit tests + 5 independent oracles = 641 tests per Python**,
- security, isolated MFX wheel and cross-Python reproducible build PASS.

Any red CI means NO merge and explicit review/fix. Record PR run and independent `main` run before promoting A03/P0.2 to DONE. Cloud-only GitHub and Google Drive; Twelve Data is the sole connected market-data MCP candidate but not invoked by mutation work. NO REAL TRADING.
