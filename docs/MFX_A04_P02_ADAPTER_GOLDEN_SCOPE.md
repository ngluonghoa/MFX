# A04/P0.2 — inert adapter-port schema conformance & frozen golden bridge

**Source checkpoint:** protected MFX main `d76f521edc9618c0f5dcc27447b4e641ec991ca4`, immutable original Forex
source commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`,
first 102-blob MFX import `6ee5e7c07baf4ea8f06a28889175808ea53c2316`.
Decision DEC-MFX-001 A04/U-09 and DEC-MFX-002 provider authority boundaries.

## Scope (synthetic only)
- Add CI-only `tools/a04_adapter_conformance.py`: four immutable ABI-v1
  plugin port declarations, exact input/output schema identity, full dependency
  graph checks (provider -> indicator -> detector -> TP policy), explicit
  no invocation, broker/trade, real data and runtime loading.
- Add `tools/check_a04_adapter_golden.py`: consume the existing frozen original
  Forex and MFX synthetic golden files in GitHub Actions; exact compare by
  scenario ID/output/**error reason**, enumerate and SHA each grouped subset;
  require exactly 50 original scenarios and eight contract groups. Report
  the independent *declared* four-port graph fingerprint and scope flags.
- Add negative/positive synthetic tests, strict mypy for new typed port module,
  and a real CI step after A01 golden render/compare. No new source
  `src/forex_trading` paths and no changes in the installable Python wheel.

## Important distinctions
The original 50 golden scenarios cover contract groups bar, cache, catalog,
pipeline, quote, scan, signal, version. **None runs a real numerical
18-label detector or actual TP/SL engine**, and this step does not produce
or execute an adapter. Golden parity is tested between actual frozen source
and unchanged MFX source, NOT between a nonexistent alternate provider
implementation and production runtime. An identical `PluginManifest`
implementation_sha256_claim is UNTRUSTED metadata until an independently
verified runtime artifact exists.

A04/P0.2 declares input/output schema boundaries in principle:
provider output UNVERIFIED candidate -> indicator UNVERIFIED features ->
detector UNVERIFIED candidates -> TP UNVERIFIED proposal. This is NOT
confirmation, execution price, signal, order routing or entitlement.
Twelve Data remains an unqueried candidate MCP connector, not an
installed Cloud provider runtime. Google Drive cache STAGING_ONLY,
source rights, scheduler, signed artifacts and broker are out of scope.

## Acceptance and rollback
Complete only after exact PR head and clean 3/3 GitHub Actions (Python
3.11/3.12 full suite, mypy strict, coverage and mutation sentinels, frozen
source SHA, wheel parity), read the 50-case group hashes and four-port
graph fingerprint from actual CI, protect new non-src file SHA exceptions,
merge via expected-head squash, confirm independent 3/3 main CI, then
update four Drive governance documents. No branch main/direct push or
local compute, no real data, no trades.

## CI-observed baseline lock
Initial PR CI run 42564185516 completed 3/3 SUCCESS. Both GitHub-hosted
Python3.11 job 128986976145 and Python3.12 job 128986975861 ran 716 unit
tests and independently returned the SAME 50 original golden scenario
results across 8 groups: bar 10, cache 10, catalog 4, pipeline 3,
quote 8, scan 7, signal 4, version 4. Original golden SHA256
`747d029192e080f88b214c76967fa9b91c8e1283f6a4464673cb2bff0b4eabb2`.
Four-role inert declared graph SHA256
`fee5c25ab04139a3da502ebc372d981946c1e1e22965fb36987915220cff9ebe`.
The exact eight group SHA256 digests are taken only from observed CI,
written in `docs/MFX_A04_P02_GOLDEN_GROUP_BASELINE.json` and checked
fail-closed by `tools/check_a04_adapter_golden.py`. Negative tests require
the baseline to reject drift or any claim of executing real adapters/trades.
These hashes only establish frozen 50-case read-only parity and a synthetic
declarative ABI shape; they do NOT establish implementation equivalence for
detector/indicator/TP/broker or wider, real-market correctness.

Final PR exact-head 3/3 and post-main 3/3 are required after this baseline
commit, along with Google Drive governance sync.
