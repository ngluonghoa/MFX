# MFX A04/P0.8 — minimal adapter boundary before any runtime code changes

Preflight: protected main `261e38ff44da0ba0678b9e3ca9e9e918c001c4e2`; independent main CI
`42581900058` 3/3 PASS; no open PRs. Original frozen Forex 1.0
`7e1c1c012b1b189be5ad7b9d07756eac012a8309`; initial exact 102
tracked Git blobs import `6ee5e7c07baf4ea8f06a28889175808ea53c2316`.
MFX current source 24/30 Python files byte-identical, six pinned A02
type-only exceptions. NO new `src/` edits.

## Critical architectural distinction
P0.1–P0.5 established ONLY declared future four-role ABI,
schema and canary/inert rollback gates. P0.6 measured 30 real source
modules and 14 existing function/class names; P0.7 proved seven
pass-through wrappers exactly equal the real Forex source on 34
synthetic cases. NONE of this creates callable compatibility with
P0.2's proposed port schemas.

The seven existing **reference** functions are:
- PROVIDER role *vicinity* (not provider adapter):
  quotes.indicative_price, market_data.evaluate_closed_bar,
  market_data.select_asof_revision
- INDICATOR reference arithmetic (not generic feature port):
  cache_indicators.ema_full, cache_indicators.ema_recompute
- DETECTOR role *vicinity* only (catalog taxonomy, no detector):
  catalog.catalog_counts, catalog.validate_catalog
- TP_POLICY: **zero** executable source functions or engine qualified.

A04/P0.8 provides a strictly typed CI-only `ProposedSeam` design
review: exact existing Python symbol, frozen per-file SHA256, measured
P0.6 AST signature SHA, P0.7 34-case wrapper output/error SHA, exact
A04/P0.2 expected future PluginKind/PortSchema tuple and ABI v1.
A good review is **documentation only**. No actual callable ABI
compatibility is inferred, and EVERY runtime/real data/real cache/
detector/TP/trading authority remains FALSE.

## 28-case first CI baseline
7 reference cases documented-only; 21 blocked variants test cross-
project, unknown symbol, mismatched role, TP phantom, plugin identity,
ABI/schema/port version drift, raw source/AST SHA drift,
P0.7 wrapper digest mismatch, runtime/fallback/real-data/cache/
trading requests and unverified external vendor/numeric engine claims.
The matrix draws exact provenance from *existing pinned files*:
A04 P0.2 50 golden/four port graph, A04 P0.3 14 schema cases,
A04 P0.6 30 real source file digests and 14 symbol signatures,
A04 P0.7 34 source+MFX wrapper case SHA. All run on GitHub-hosted CI.

Initial PR runs `--bootstrap-measure` and must be 3/3 PASS with
identical Python 3.11/3.12 receipts before locking SHA.
Final commit removes bootstrap mode and adds negative baseline
tampering tests, then exact-head PR 3/3 PASS and independent postmain
3/3. Keep original Forex 50 golden, 17 mutation sentinels, 80-case
feedback, strict mypy all source, wheel and credential/security
scans unchanged. No Mac/MOCHI/local.

## Nonclaims, decision and next prerequisite
No plugin is dynamically loaded. This review does NOT authorize
implementation of an adapter or any source change. Before actual
runtime integration, a separate source delta decision would need
typed callable protocol, actual provider entitlement and reconciliation,
detector numerical and TP/SL rule implementations, original-vs-MFX
economic parity, OOS evidence, signed release rollback and an
individually authorized protected-main PR. This work remains separate
from Forex Trading 1.0 and MOCHIFX.
