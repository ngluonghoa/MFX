# MFX A04/P0.6 — real-source AST integration boundary inventory

**Cloud-only source of truth**: protected main `b5162740174dc64ef41bc80c3c2d25fabf7d0ff1`,
independent main CI 42575317204 3/3 PASS; frozen Forex Trading source
`7e1c1c012b1b189be5ad7b9d07756eac012a8309`; first 102-blob MFX
import `6ee5e7c07baf4ea8f06a28889175808ea53c2316`.
No Mac/MOCHI/local compute, no new `src/` changes.

## Existing source — actual module/function observations
Read actual tracked `src/forex_trading` source via the Python stdlib
AST parser, **without importing or executing any source module**.
Inventory all 30 Python paths, SHA256 of raw bytes, direct
relative Python import graph, top-level function/class declaration
signature fingerprints and the actual package `__all__`.
Check setuptools package root `src` and absence of a new
unreviewed `project.scripts` entry point.

- **Provider**: real read-only functions
  `market_data.select_asof_revision`,
  `market_data.evaluate_closed_bar`,
  `source_qualification.assess_source_for_m2_review`,
  `source_stream_binding.qualify_snapshot_binding`,
  `side_pair.assess_bid_ask_side_pair`,
  `quotes.indicative_price`. These are provenance, as-of, quote and
  authorization-claim evaluation helpers — **not an installed provider
  adapter** or API entitlement.
- **Indicator**: actual `cache_indicators.ema_full` and
  `cache_indicators.ema_recompute` static Decimal numeric helpers;
  no generic indicator plugin injection interface.
- **Detector**: catalog validation/counting, SignalDisplay DTO and
  synthetic scan selection were identified. None proves an implemented
  numeric detector for 18 actionable zones.
- **TP policy**: existing release candidate review and profile
  rollback preview are **not** an executable take-profit/stop-loss
  engine or fill simulator; no concrete TP policy extension slot
  verified.

## Safety boundaries
All original `src/` module raw byte digests and selected declaration
signatures must match CI-measured immutable baseline, in addition
to existing full Git source-blob/Forex parity gates. Direct imports
from `tools/` into `src/` are denied. Reports intentionally distinguish
static AST evidence from runtime reachability, commercial market-data
rights, broker order semantics and trade execution. No provider calls
or dynamic plugin loading are permitted.

**Decision**: actual source provides multiple safe reference
validation/EMA functions for a FUTURE wrapper design, but not a
replaceable provider/indicator/detector/TP plugin runtime.
Runtime source changes, broker, Twelve Data credentials/licensed
data, cache, signed release or trading require individually reviewed
source-delta/security/rights and real-data parity authorization, not
this milestone. A04 remains PARTIAL.

## Gate
First PR CI emits real-source *un-pinned* observation. After both
Python3.11 and Python3.12 verify matching digests and 3/3 PASS,
pin the actual 30-file SHA256 and API signature inventory into
`docs/MFX_A04_P06_RUNTIME_SEAM_BASELINE.json`, switch to enforced
mode, add negative SHA tamper tests, and require exact-head 3/3 plus
independent postmain 3/3 before merging/documenting DONE.

## First CI red evidence

PR #18 initial CI run https://github.com/ngluonghoa/MFX/actions/runs/42577321465:
Python3.11 and 3.12 each ran 786/786 synthetic unittest methods PASS,
AST reports matched exactly with 30 actual source Python files,
14 selected read-only symbol declarations, source metadata SHA
`b0a958e27aaf8ad83dcc62285298fc81aec419136efdf14802c68e3814aad66b`
and relative import graph SHA
`734f1fda1e590ab1e5341e53b05ce31631b139f0108f7407227c87088b65cb47`.
The strict mypy gate caught one variable inference problem:
function signature tuple vs class signature tuple. Explicitly typed
the internal `info` intermediate as `object` to preserve both exact
SHA inputs, without ignores, runtime changes or source edits.
The red run is retained and is not sign-off; the next run must pass
3/3 before the observed data are pinned.
