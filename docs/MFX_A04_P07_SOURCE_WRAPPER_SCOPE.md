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
