# MFX A04/P0.1 — Cloud-only inert typed plugin declarations

Decision DEC-MFX-001 and DEC-MFX-002. Protected main base
`d4b05e1f4a4da3352c39a9f496c86f568c8dd80d`, baseline original Forex 1.0
`7e1c1c012b1b189be5ad7b9d07756eac012a8309`, immutable
MFX 102-blob import `6ee5e7c07baf4ea8f06a28889175808ea53c2316`.

## Phase and invariants

A04 is an approved U-09 typed replaceable architecture workstream. P0.1 is
**declaration and fail-closed negotiation only**, NOT an activated runtime
plugin system. No changes to frozen `src/forex_trading/*` modules, trade
conditions, 18-zone labels, source quote semantics, Forex source, or existing
MFX wheel. This stage adds an inert `tools/a04_plugin_contracts.py`
reference module and synthetic independent test suite outside installed
`src`. It can be imported only in GitHub CI for contract verification.
The existing 50 golden source-vs-MFX scenarios and all other QA stay enabled.

## Design

- A typed immutable, versioned `PluginManifest` with exactly four kinds:
  PROVIDER, DETECTOR, INDICATOR, TP_POLICY. Per-plugin implementation SHA
  is DECLARED, not verified or signed. The registry is order-independent,
  SHA256-identified, rejects duplicates, missing dependencies, and cycles.
- Explicit `abi_major`, version, project=MFX guard and exact plugin/kind
  resolution. Unknown/incompatible plugins return a BLOCKED declaration
  result, never select another provider and never import/activate arbitrary
  code. The manifest is NOT a binary ABI verifier.
- Typed provider structural capability uses existing Forex `Timeframe`
  and `BarSide` enumerations. REFERENCE_OHLC has **no native BID/ASK
  or MID side**. NATIVE_BID_ASK requires both SIDES claimed, and even
  these claims are NOT proof of a qualified broker quote.
- Exact product/instrument/timeframe/price basis/side/calendar/timezone/
  rights-policy identity matching; no silent provider substitution, no
  implicit cross-source candles or rights grant. Execution replay always
  remains blocked. All assessment results deny fetch, storage, real backtest,
  broker routing and trade permission.

## Twelve Data boundary

DEC-MFX-002 identifies Twelve Data as sole currently connected external
market-data MCP candidate; A04/P0.1 **does not call it** and does not infer
capability claims, timeframe entitlements, historical native BID/ASK,
persist/replay licences, quota or Cloud credentials. No direct connected
MCP credential is transferred to GitHub Actions. Adding a real Twelve Data
adapter is a separate gated future step and requires independently
documented rights, matching data provenance and security approval.

## QA acceptance

PR must preserve all A01/A02/A03 unit and golden gates, two Python CI
runners and cross-version wheel. New P0.1 contract methods must PASS and
strict mypy 1.18.2 must report no errors for reference module in GitHub
CI. Source file SHA/size manifest must approve exact new non-src artifacts,
and source 102/102 immutable tree remains untouched. Review exact changed
path list, merge only with expected-head SHA and CI green; require post-main
3/3 and sync Drive Handoff, QA, Roadmap and Traceability.

## Limits / next

A04 overall PARTIAL. No runtime plugin wiring, no A04 detector/indicator/TP
execution ABI, no verified data licence, no data feed, no real cache or
orders, no signed release or trading. Next A04/P0.2 should define safe
runtime-free adapter conformance checks and differential golden scaffolding,
then evaluate actual migration in a separately approved source-delta
governance upgrade; do not bypass existing `src/` exceptions silently.
