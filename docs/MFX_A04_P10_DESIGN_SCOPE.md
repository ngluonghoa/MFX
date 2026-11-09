# MFX A04/P0.10 — design-only mapper prerequisites (not an adapter)

## Frozen source and evidence
- Source Forex Trading 1.0: `7e1c1c012b1b189be5ad7b9d07756eac012a8309`; first byte-identical 102-blob MFX import: `6ee5e7c07baf4ea8f06a28889175808ea53c2316`.
- P0.9 seven actual AST callable gap rows SHA256: `06d3abb44df35cccf10c889aaa59f358f73d01937cbbc7529970c1c248e18cba`.
- P0.9 five synthetic schema field sets SHA256: `e12cd296e96e2a9d0b34f658b1eb9477cdb08e748a4836c10396d4e21c623083`.
- P0.9 four future declared role-to-port routes SHA256: `55727bcabe0552f7f2a7db8a870b3304071dd3b72eca0740f5a5e3c3d6bf178f`.
- Current scope: design prerequisites only, **zero** callable-compatible source functions, **zero** TP executable source references, **zero** runtime adapters; no modification of `src/`.

## Four interfaces to review before any runtime code
1. **Provider/quote:** per-instrument/timeframe/side/rights product identity and licensed historical BID/ASK; first-known causal bar timestamps, DST/calendar, source revisions; typed errors and missing/rights-denied/stale-source controls. Twelve Data is a read-only research candidate, not proof of native broker BID/ASK, execution, historical storage entitlement, or transferable GitHub Actions authentication.
2. **Indicator:** output schema carrying causal source time, quote side, quality, revision, feature identity, precision and EMA warm-up; pure deterministic full/delta equivalence and failure reasons.
3. **Detector:** catalog taxonomy is NOT numeric detector implementation. Preserve 18 frozen labels and non-entry/research restrictions. Require independently reviewed numerical rule manifests, state transitions, 8-stage reports, and causal/later-economic tests.
4. **TP policy:** no qualified executable reference in the seven-function pure-source set. Separately specify TP/SL, position/risk/cost/quote-side handling and ambiguous fills; no broker or account authority.

## Fail-closed acceptance
The immutable JSON matrix `docs/MFX_A04_P10_MAPPER_PREREQUISITE_MATRIX.json` is generated solely from observed pinned P0.9 AST gaps and explicit design gates. Cloud CI runs `python -m tools.check_a04_p10_mapper_matrix` on Python 3.11/3.12 and negative tamper tests. Any changed frozen source signature, omitted required gap, claim of completed runtime/data entitlement/strategy/trade, or additional candidate MUST fail. The current review-status flags stay false. Seven source-function *mapper candidates* do not imply seven adapter implementations or approved integration.

Retain the original 50 Forex golden, 34 wrapper parity, P0.8 28-case authority denial, 17/17 mutation sentinels, 80-case feedback, A03 coverage, strict mypy and wheel/security gates. Never use a synthetic PASS to claim real data, actual economics, OOS, Google Drive cache activation, deployment, rollback on protected main or trades. Cloud-only GitHub + Google Drive; Forex Trading and MOCHIFX untouched. A later runtime/source change requires a separate explicit owner rights/security/source-delta decision with independent evidence and protected PR.
