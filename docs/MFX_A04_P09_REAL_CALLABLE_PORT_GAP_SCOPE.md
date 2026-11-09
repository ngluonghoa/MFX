# MFX A04/P0.9 — actual Python callable ABI versus five future port shapes

Frozen Forex Trading 1.0 source commit
`7e1c1c012b1b189be5ad7b9d07756eac012a8309`.
MFX protected main source checkpoint
`a8e254388d7177e53b45405cee4f1ebf969f2771` with independent
main GitHub Actions `42584804295` 3/3 PASS. Original first 102-Git-blob
import `6ee5e7c07baf4ea8f06a28889175808ea53c2316` unchanged.

## Purpose
Prior A04/P0.8 proves only seven source-reference descriptions and
denies any runtime plugin. A04/P0.9 performs a **fresh AST inspection
of actual callable argument names, type annotations, keyword-only
defaults, and return annotations** in the frozen 30-module source
baseline (selected seven pure helpers). Compare against the **actual
declared synthetic schema field tuples** read by Python AST from
`tools/a04_contract_migration.py` and the exact A04/P0.2
`PORT_SIGNATURE`, never pretending that P0.2's field set is a
callable implementation.

## Measured comparison, not a fake compatibility grant
Expected source functions: quotes.indicative_price, market_data
evaluate_closed_bar/select_asof_revision, cache_indicators
ema_full/ema_recompute, catalog catalog_counts/validate_catalog.
All seven MUST have missing required future input fields and
unverified future output-field semantics. Capture precise missing
input field names, source-only input arguments, source annotations,
AST signatures and return type; each row is SHA-pinned in
`docs/MFX_A04_P09_CALLABLE_ABI_GAP_BASELINE.json` after real
GitHub CI measurement. Provider expected future query includes
instrument_version/price_basis/rights_policy_ref/timeframe which
actual quote/bar functions don't take as corresponding named args.
Indicator EMA returns Decimal tuple, not a verified feature port;
catalog returns taxonomy counts or None, not detected trade
candidate shape. TP_POLICY has NO approved executable source
reference in the seven-function scope.

### Boundary and next decision
Future bridge requires a separately reviewed typed input/output mapper,
source rights, bid/ask lineage, explicit causality and error semantics,
normalized feature payloads, actual numerical detector,
TP/SL executable risk and broker fill definitions, and original-vs-MFX
behavior/economic/OOS evidence; no file under `src/forex_trading`
is edited here. An AST shape gap does NOT prove runtime substitutability
or an implementation. No licensed provider feed, Google Drive cache
writes, source import/invocation, plugin runtime, release or trade.
Use only GitHub-hosted CI and Google Drive documentation.

## QA workflow
Initial PR CI compares actual current source SHA against previously
pinned A04/P0.6 raw SHA and 14 AST signatures. Future schema fields are
parsed from existing P0.2/P0.3 declarations with full five-schema
shape count; prior original 50 golden, 34 P0.7 wrapper golden, P0.8
28-case stop gate, coverage, mutation, mypy, security/wheel remain
mandatory. First CI `--bootstrap-measure` is observation ONLY; after
Python3.11 and 3.12 match and all jobs green, pin exact gap rows SHA
and add fail-closed tampering tests. Require final exact-head PR
3/3 and independent postmain 3/3 before Docs checkpoint.

## Initial GitHub CI RED and measured actual ABI gaps
PR #21 initial cloud Actions run https://github.com/ngluonghoa/MFX/actions/runs/42586933457:
Python 3.11 job 129058898462 and Python 3.12 job 129058898114
each 829/829 unittest methods PASS; identical static AST
seven-source/five-future-schema gap rows SHA256
`06d3abb44df35cccf10c889aaa59f358f73d01937cbbc7529970c1c248e18cba`,
future port field shape SHA256
`e12cd296e96e2a9d0b34f658b1eb9477cdb08e748a4836c10396d4e21c623083`.
Strict mypy found ONE typing error in tuple extraction of ast.Constant
strings: AST's generic value type could not narrow across the
comprehension. Explicit string conversion after independently
checking every AST Constant is a string retains same outputs
without disabling mypy, adding a source edit or changing safety
logic. Original RED run retained; fresh 3/3 green bootstrap remains
mandatory before any SHA pin or merge.

Measured source missing fields, all GAPS not integration readiness:
- Provider quote/evaluate/as-of: no direct instrument_version,
  price_basis, rights_policy_ref or timeframe input named arguments;
  source returns IndicativePrice, ReadOnlyBarGate and MarketBar|None
- EMA full/recompute: no first_known_utc, price_basis, quality,
  source_revision; returns tuple[Decimal, ...], not feature-set packet
- Catalog counts/validate: no asof_utc, feature_set_id or quality;
  returns taxonomy dict or None, NOT numerical detector candidates.
No directly compatible seven function/port pairs, no executable
TP_POLICY reference in the seven-function approved scope.

## Green cross-Python observation and pinned mandatory enforcement

GitHub Actions bootstrap run
https://github.com/ngluonghoa/MFX/actions/runs/42587147546
**3/3 PASS**; Python 3.11 job 129059574815, Python 3.12 job
129059575190, each 829/829 unittest methods PASS.
Mypy strict 30 original source + 17 inert A04 tooling modules PASS.
Original frozen 50 Forex golden + P0.7 34 source wrapper and
P0.8 28-case no-runtime matrix preserved, 17/17 synthetic mutants,
80-case pinned feedback, security/source SHA checks, cross-Python
wheel parity all PASS. Measured 30 core-module coverage remains
2546/2683 source lines (94.89%) and 973/1112 branches (87.50%).

Both Python 3.11/3.12 produced IDENTICAL seven detailed ABI gap
rows SHA256 `06d3abb44df35cccf10c889aaa59f358f73d01937cbbc7529970c1c248e18cba`,
five synthetic future schema shape SHA256
`e12cd296e96e2a9d0b34f658b1eb9477cdb08e748a4836c10396d4e21c623083`,
four future role-to-port route SHA256
`55727bcabe0552f7f2a7db8a870b3304071dd3b72eca0740f5a5e3c3d6bf178f`.
All seven detailed source-function argument/return/gap rows now
pinned in `docs/MFX_A04_P09_CALLABLE_ABI_GAP_BASELINE.json`;
baseline also locks ancestors, no-runtime flags and observed CI run.
The workflow now strictly verifies this file, with six new
negative SHA/port/rights/compatibility/baseline tampering tests.
A final exact-head PR 3/3 and independent postmain 3/3 remain
required before checkpoint DONE.

This is *static source signature evidence*, not automated callable
port conformance; mapping designs cannot be promoted to working
runtime adapters without separate review and permission.
