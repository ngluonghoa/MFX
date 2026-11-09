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

## Observed premerge QA (GitHub Cloud, 2026-11-09 UTC)
- First PR CI run `42557175069` RED: one mismatched generation-parent error-message expectation. This was corrected in the QA-only test file; no source change.
- Green measured PR run `42557308499`, head `17114e8bb46c2ca58e1b4c8d747949870cf44df5`, Python 3.11 and 3.12 both 676/676 unit methods PASS, 50 source-vs-MFX golden PASS, 17/17 targeted mutants PASS, static/security/isolated wheel checks PASS, cross-Python wheel parity PASS. Three jobs SUCCESS.
- Identical observed 30 source-module totals on Python 3.11/3.12: 2546/2683 covered lines (94.89%), 973/1112 covered branches (87.50%), +17 covered lines and +17 covered branches from P0.4.
- Measured remaining missing branches: provider_delta_contract 9; cache_core 14; cache_storage_review 11; synthetic_evidence_lineage 10; cache_dependency 4. P0.5 stage-1 updated frozen nonregression floors to 2546/973 and independent guarded per-module levels. New observation does not erase historical baseline receipt.
- This is coverage-measured gap probing only; no adaptive feedback fuzzer implemented. Future P0.5 stage-2 may tackle remaining reachable arcs and deterministic coverage-guided corpus selection.

## QA receipt
Final after this metadata-only SHA-pinned commit is gated by a fresh exact-head PR 3/3 success, independent post-main 3/3 and readback; Google Drive Handoff/QA/Roadmap update required. Do not silently relax baselines.
