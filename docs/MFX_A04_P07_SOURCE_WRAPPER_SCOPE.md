# MFX A04/P0.7 — read-only wrapper parity against frozen Forex

Protected source baseline MFX main `9e495ca3a4425ac3f2f6051f5a67c4b29ef3a655`, independent main Actions
`42578101090` 3/3 PASS. Original Forex Trading source
`7e1c1c012b1b189be5ad7b9d07756eac012a8309` with exact frozen
tree SHA `5df2058346f6dc96ed5bb02581b139fe2aa2d803`.

## Exact narrow implementation
A04/P0.6 established 30 real source Python modules and SHA, 14 selected
actual read-only function/class signatures, 16 package exports, no hot
swappable plugin architecture. P0.7 adds a **tooling-only transparent
function wrapper**, never in `src/` and never in the distributable
wheel, for only:
- quote-side causal `indicative_price` (four action intents)
- existing `evaluate_closed_bar` and `select_asof_revision`
- reference `ema_full` and `ema_recompute`
- catalog-only `catalog_counts` and `validate_catalog`

The wrapper delegates 1:1 without filtering or rewriting exceptions or
outputs. It does not create an adapter registry or data source, and
`catalog` is NOT a numeric 18-zone detector. No TP/SL engine exists to wrap.

## Real frozen-source behavior proof (synthetic fixtures)
After GitHub CI checks out the exact immutable Forex source, execute the
SAME wrapper-rendering Python module under two separate PYTHONPATH roots:
one frozen Forex source and one current MFX source. Each run compares
wrapper output and error type/message DIRECTLY to the function it wraps.
A separate strict comparison matches the two sources for all 34 scenarios
(quote, as-of, closed-bar gate, EMA and catalog), including negative
causality/quality/version/error outcomes. This extends, NOT replaces,
the original A01 50 original-vs-MFX synthetic golden and A04/P0.2 pinned
eight-group bridge. All fixtures are synthetic; no quote or bar represents
licensed provider data or broker execution.

The initial PR CI uses `--bootstrap-measure` only after BOTH
unmodified original and MFX outputs pass parity. On matching measured
SHA, pin the observed exact 34-case SHA and full snapshot SHA into
`docs/MFX_A04_P07_SOURCE_WRAPPER_BASELINE.json` and remove
bootstrap mode; add negative tests for SHA mismatch/authority flags.
Require exact-head PR 3/3 PASS and independent postmain 3/3 PASS before
checkpoint is DONE.

## Explicit integration limits
These are test-only pass-through wrappers: not native extension slots,
not dynamically loaded plugins, no provider/network IO, no qualified
historical BID/ASK entitlement, no numeric detector, no executed TP/SL,
no actual broker fills, no market OOS, no release or trade. No `src/`
file, original Forex history, Google Drive source-locked document,
cache, action secrets, ruleset or signed release may change. Full A04
remains PARTIAL. Any production code change needs independent
authorization and strict 1:1 economic parity governance.

## First PR red CI record
Initial GitHub Actions run 42580347359: previous 789 tests loaded,
but P0.7's new test module failed import because a syntax typo
(unmatched closing parenthesis in the tools-only comparator at line 48).
Both Python runners rejected this before any new wrapper parity could be
certified. Removed that unmatched parenthesis, changed no source/Forex
files, and kept this RED historical CI receipt. A fresh full run and
cross-root exact output/error parity are required before pinning or merge.

## Second PR red CI: strict mypy helper dependency
GitHub Actions run 42580566038: both Python3.11 and 3.12 ran
801/801 unit methods successfully; exact frozen Forex/MFX 34-case
wrapper output and error reasons all passed, with identical measured
case SHA `6ccb082b7940a3bb5c2c27d86151cde1874c6f791eb02cfeac12cf94c2ff49f5`
and snapshot SHA `b4aca14200ec2312970850a7c3500b2d73d3045e012575ca3f15c724aca00485`.
Strict mypy then caught 17 diagnostics: five from importing the
historical A01 golden renderer (a CLI not previously strict typed),
and twelve from default-bound lambda inference. Removed the
runtime import of that CLI in P0.7 and introduced a locally typed
pure serialization/receipt helper preserving the same output
structure. Switched default-bound lambdas to `functools.partial`
for explicit input types, no `# type: ignore` or relaxed CI gate.
The RED run remains in QA history; source/runtime unchanged.

## Third PR red: Ruff E402 import placement
Run 42580882400: exact original Forex vs MFX 34/34 scenarios and
801/801 unit methods both Python versions PASS; CI rejected one
new P0.7 module-level import appearing below its locally typed helper
definitions (Ruff E402). Moved the import before the helper functions,
without any functional change. This RED run is retained. Require fresh
3/3 PR bootstrap with mypy strict before SHA pinning.

## Verified CI source-root 1:1 measurement and strict pinned gate

GitHub Actions bootstrap run
https://github.com/ngluonghoa/MFX/actions/runs/42581189845
**3/3 PASS**, Python3.11 job 129040047899 and Python3.12 job
129040048364 each **801/801 unittest methods PASS**, strict mypy
30 source modules + 13 A04 tool modules PASS, original 50/50 Forex
golden, A03 17/17 targeted mutants, pinned 80-case feedback,
source 2546/2683 lines (94.89%) and 973/1112 branches (87.50%)
unchanged, source-manifest/security/wheel 3/3 PASS.

Original exact frozen Forex import root and MFX import root produced
**IDENTICAL** 34-case wrapper-vs-direct and reference-vs-MFX
observations across all five pure source function groups. Observed
case matrix SHA256
`6ccb082b7940a3bb5c2c27d86151cde1874c6f791eb02cfeac12cf94c2ff49f5`;
full snapshot SHA256
`b4aca14200ec2312970850a7c3500b2d73d3045e012575ca3f15c724aca00485`.
These are measured directly on BOTH Python versions; now pinned in
`docs/MFX_A04_P07_SOURCE_WRAPPER_BASELINE.json`.
Mandatory CI no longer accepts `--bootstrap-measure`, negative SHA,
authority and baseline weakening tests added; require final exact-head
PR 3/3 then independent postmain 3/3 before checkpoint complete.

Three earlier red CI runs were kept: syntax typo 42580347359,
strict mypy source helper/default lambda 42580566038,
Ruff E402 import placement 42580882400. All issues corrected
solely in P0.7 tool code, never in original Forex or MFX source.
