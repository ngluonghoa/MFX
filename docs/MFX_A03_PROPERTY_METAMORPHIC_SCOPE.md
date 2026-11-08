# A03/P0.1 — deterministic synthetic property and metamorphic QA

## Governing policy and frozen base

This is an incremental **A03** test-only improvement, under `DEC-MFX-001`. MFX protected-main parent `b6926d747440c301c350c31322b84e2a2b78436c`; frozen Forex Trading original `ngluonghoa/forex-trading-1-0` commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`; immutable MFX initial source import remains `6ee5e7c07baf4ea8f06a28889175808ea53c2316`.

A03/P0.1 changes **no files under `src/`**. Current MFX already contains six narrowly authorized A02 type-only source deviations (24/30 original source Python Git blobs remain identical), each SHA-pinned. This PR adds test and QA plumbing only; A01 verifier, source SHA gates, strict mypy 30/30, pinned 24 legacy F401, 50 synthetic Forex-vs-MFX golden checks and cross-Python wheel parity remain enforced.

## Synthetic adversarial properties

`tests/test_a03_seeded_properties.py` is a 24-method, standard-library-only deterministic fuzz/metamorphic test suite, with seed `0xA032026`; randomized methods exercise up to 96 independently drawn synthetic scenarios per test and thousands of subtests across both hosted Python 3.11 and Python 3.12 runners. The fixed seed makes regressions reproducible.

Test groups:
- **BID/ASK**: four intent-to-side mappings, positive/noncrossed spreads, quote-side translation invariance, controlled spread widening, first-known and age cutoff inclusivity, future/unverified and NaN/crossed rejection.
- **Causal bars and early detection**: historical as-of is unchanged by revisions not yet known, `M5` only arms with prior HTF context, no `ReadOnlyBarGate` ever grants trade permission, `MID` bars remain non-executable.
- **DST/session clock**: each minute of New York autumn overlap requires explicit `fold` and resolves to two UTC instants one hour apart; every spring-gap minute is rejected; ordinary wall times reject spurious `fold=1`. IANA timezone uses the runner-installed tzdb; its provider calendar contents are NOT independently attested.
- **EMA incremental metamorphic**: exact Decimal equality of full history versus earliest-dirty-index recomputation after revised history or appended candle, plus constant-price fixed points. This tests a synthetic EMA cache reference only, **not** 18-zone strategy calibration.
- **Cache L1–L5**: exact bounded overlap for refresh plan, reject no bounded-range support, unmodified candle delta is idempotent, late revisions report earliest dirty candle, same-revision conflicts fail closed, DAG invalidation never leaks to unrelated pairs, closure monotonicity and permutation invariance, fingerprint reuse can never grant production permissions.

`tools/check_a03_property_suite.py` fails if the suite file, declared seed, 96-case range or discovered 24 test methods disappear. The regular `python -m unittest discover -s tests -v` runs all properties and existing tests on both Python versions, while a dedicated CI inventory step adds `MFX_A03_SEEDED_PROPERTY_SUITE_PRESENT` receipt.

## Explicit not-yet-implemented A03 components

A03/P0.1 is **not full A03**. No external provider call or live bid/ask source is used. No Hypothesis/coverage-guided fuzz engine, source-mutant survival score, autonomous mutation campaign, production scheduler, genuine tick-level fill TP/SL engine, economic backtest, or real trade validation is claimed. A03/P0.2 should add a controlled mutation adequacy campaign and broader adversarial verification; true TP/SL and execution validation must wait for actual executable, qualified detector and market-data contracts. Do not invent numeric trading results.

## Acceptance evidence and governance

Require protected PR 3/3 CI PASS, suite inventory 24 methods, original-vs-MFX 50 golden cases PASS, all-source mypy strict 30, A02 Pyflakes exact inherited F401 gate and no new F-code, original 102-source path tree SHA/approved changes, wheel isolation/byte parity, and independent post-Squash protected-main run before marking `A03/P0.1 DONE`.

Use only GitHub-hosted CI and Google Drive Docs. Twelve Data remains the only currently connected market-data MCP candidate, not activated by these tests. No Mac, MOCHI, local compute, broker, live order, paid scheduler or release.
