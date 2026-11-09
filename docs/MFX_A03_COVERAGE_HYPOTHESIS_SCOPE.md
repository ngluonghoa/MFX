# A03/P0.4 — measured branch/line coverage and shrinkable property-based fuzz (Cloud-only)

## Governance and boundaries

This is an A03 quality improvement authorized under DEC-MFX-001. Frozen Forex original repository remains at commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309` and immutable original MFX 102/102 source import `6ee5e7c07baf4ea8f06a28889175808ea53c2316`. Protected MFX parent before the scoped PR is `daf53f3f59d8d4fcf8658ab31963e70d4b74bb1d`. Current MFX source has 24/30 original Python blobs byte-equal and six approved SHA-pinned A02 typing-only differences. **This PR modifies no `src/` file and does not modify Forex Trading.**

All computation is on disposable GitHub-hosted runners. `coverage==7.10.7` and `hypothesis==6.142.4` are explicitly pinned **CI-only** tools, not `pyproject.toml` runtime dependencies. Hypothesis's `derandomize=True`, `max_examples=80`, `deadline=None`, `database=None` preserve stable property-case generation and shrinking without needing durable local state. No third-party market data, Cloud runner Twelve Data credentials, paid scheduler, live cache, order or broker use.

## Instrumented real source coverage, no fictitious percentages

CI instruments `python -m unittest discover` with `coverage run --branch --source=src/forex_trading` on **both Python 3.11 and 3.12**. It emits a structured JSON report, parsed by `tools/check_a03_coverage.py`. Integrity checks require exactly **30 source Python modules**, nonzero and internally coherent statement/branch counts and pinned tool version. Measured per-module statement and branch counts are included in a Cloud CI receipt; only real observed metrics may be recorded. `tests/test_a03_coverage_guard.py` adds six fail-closed checker tests (report identity, missing/extra files, branch disabled, global and per-core regression).

**Two-stage measured gate, now locked:** Initial red run [42551169888](https://github.com/ngluonghoa/MFX/actions/runs/42551169888) executed **659/659** unittest methods on BOTH Python versions but the newly authored `coverage json --output` CLI option was unsupported; corrected to `coverage json -o`, with no change to any test or business source. The subsequent **MEASURED_ONLY_BASELINE_PENDING** CI audit [42551298052](https://github.com/ngluonghoa/MFX/actions/runs/42551298052) measured identical real results in Python 3.11 and 3.12 across all 30 source modules: **2,529/2,683 lines (94.26%) and 956/1,112 branches (85.97%)**. These are instrumented source execution statistics, not estimates. The measured data is recorded in `docs/MFX_A03_COVERAGE_BASELINE.json` as frozen exact nonregression floors. Seven safety-relevant core modules have their own per-module covered-line and covered-branch minima: quotes, market_data, cache_core, cache_dependency, cache_indicators, source_calendar and provider_delta_contract. This freezes observed reality, NOT a fabricated 100% goal. Final CI must emit `FROZEN_NONREGRESSION_GATE_PASS` on both Python versions; lowering these minima requires a separately authorized governed change.

## Shrinkable property-based fuzz scope

`tests/test_a03_hypothesis_properties.py` adds **five** Hypothesis test methods (up to 80 generated examples each, deterministic, with automatic minimal counterexamples for failures). They cover:
- independent long/short BUY/SELL BID/ASK mapping and tick translation invariance;
- strictly causal first-known and quote max-age cutoffs, including boundary and future cases;
- Decimal EMA full-history recompute vs dirty-index incremental recompute for varying period and candles;
- one-slot revised cache history, previous snapshot immutability, dirty timestamp and deny real-data persistence;
- L1-L5 DAG pair isolation, union monotonicity and shuffled-order invariance.

This is **property-based/shrinkable fuzz**, not a feedback-driven coverage-guided fuzzer. A later A03 sub-milestone can use measured missing arcs to prioritize strategies or implement a genuinely coverage-feedback-driven runner without mislabeling this work.

## Mandatory acceptance and known gaps

Before this PR, MFX had **648** discovered unit-test methods per Python (including A03/P0.1–P0.3). This PR adds five Hypothesis methods and six coverage guard tests = **659** total per Python. Clean pre-mutation A03 control suite expands **36 -> 47** and all original **17 targeted mutants must still be killed** on each Python runner.

All prior A01 50 independent original-Forex-vs-MFX synthetic golden contracts, exact source SHA/exception gate, A02 mypy strict 30 modules and exact 24 legacy F401, security and cross-Python wheel parity remain required. No Squash merge without protected PR 3/3 PASS, source diff review, exact-head merge and independent post-main 3/3 PASS. Coverage floor must be based on observed CI receipts and scoped SHA-pinned docs.

This does **not** establish full-project fuzz adequacy, verified numeric 18-zone detectors, broker-equivalent TP/SL, qualified matched BID/ASK historical data, real Twelve Data provider adapter, valid trading returns/OOS, signed LKG or trading eligibility. Full A03 remains partial until those components have separate real executable source and QA.

## Observed priority coverage gaps, not silently exempted

Sorted by missing branches in the measured coverage report (run 42551298052): `provider_delta_contract.py` 16 missing branches, `cache_core.py` 14, `cache_storage_review.py` 14, `synthetic_evidence_lineage.py` 11, `cache_dependency.py` 10. Other source modules also contain unvisited branches. This is the measured feedback used to prioritize subsequent tests; no claim that Hypothesis dynamically reads or maximizes branch coverage. Further broadening should focus on adversarial provider delta, cache storage failure/anti-rollback, evidence lineage, and dependency invalidation without source changes. No real Twelve Data rights or production data are inferred from synthetic coverage.
