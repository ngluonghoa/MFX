# MFX A03/P0.5 — coverage-gap probe: bounded synthetic QA only

Decision: DEC-MFX-001, A03/P0.5 stage 1. Base main `1a7f0ce49a9c2a4897f9630199cef6297e5e27d0`.
Cloud execution: GitHub-hosted Python 3.11/3.12 + Google Drive governance only.
Source: original Forex 1.0 frozen at `7e1c1c012b1b189be5ad7b9d07756eac012a8309`;
MFX import `6ee5e7c07baf4ea8f06a28889175808ea53c2316`.

## Deliverable
- Add 17 synthetic safety-boundary unittest methods on provider parsing, request scope, quote OHLC/side, DAG validation, cache reuse, refresh, snapshot capacity, immutable generation and lineage.
- Instrumented coverage.py JSON remains the actual evidence; report each observed missing branch arc in the five historically weakest modules. Any increase must be measured on BOTH Python runners; never claim all branch gaps eliminated.
- Preserve original P0.4 line/branch minima, 50 Forex/MFX source golden comparisons, 17/17 targeted mutants, strict mypy 30 modules, 24 frozen F401, source SHA-delta protection and wheel parity. Tests use no real data.
- No `src/` file edits, price feed requests, rights assumptions, scheduler, cache persistence, LKG release, order placement or broker connection.

## Explicit limitations
This is a scoped negative-test expansion and measured branch-gap inventory. No adaptive coverage-feedback-guided fuzzer has been implemented yet. Full A03 remains PARTIAL pending measured remaining arcs, true coverage-feedback campaign, full mutation scope and executable detector/TP-SL/broker-fill/OOS proof. Do not treat branch coverage as forecasting or trading accuracy.

## QA receipt
Complete only after exact-head PR 3/3 PASS, post-main CI 3/3 PASS, readback of real counts and an Handoff/QA/Roadmap update. Failed CI and provisional branches remain visible; do not silently relax baselines.
