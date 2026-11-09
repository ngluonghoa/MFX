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
