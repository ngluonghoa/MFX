# MFX P0.187 — Cloud-only sealed 6TF → mirrored B2/S2 signal-only gate

**Checkpoint:** 2026-11-17 ICT. **Owner target:** Sun 2026-11-22, strict conditional limited B2 BUY / S2 SELL MVP GO/NO-GO. Source incidents [#27](https://github.com/ngluonghoa/MFX/issues/27), [#45](https://github.com/ngluonghoa/MFX/issues/45), [#62](https://github.com/ngluonghoa/MFX/issues/62), [#180](https://github.com/ngluonghoa/MFX/issues/180), release coordination [#138](https://github.com/ngluonghoa/MFX/issues/138).

## Implemented vertical slice

A single non-writing entrypoint `from_sealed_stores_b2s2_signal_only` now composes, in sequence:

1. **Source-owner proposal:** exact 18-pair P184 public-safe source packet and P035 validated expansion (up to 36 proposed, **zero approved**) BEFORE any storage read; no one-sided numeric source or fake owner decisions.
2. **Real type-checked read-only source path:** existing SHA-verified M5 and native H4/D1 sealed stores, exact GitHub M5 root/checkpoint in production, six closed/as-of UTC-aligned M5/M15/M30/H1/H4/Sydney-local D1 observations, no lookahead; optional synthetic fixture pins are explicitly test-only and never a trusted license or source witness.
3. **Fail-closed output:** the existing `build_signal_only_research_response` independently revalidates sealed-source/permission/coverage and keeps the P171/V1 D1 known revision quarantine. `compose_b2s2_signal_only_gate` maps *design-only* exact mirrored B2 long ASK→BID versus S2 short BID→ASK plus 18 source proposal counts, missing/stale frames and explicit immutable source rights/numeric/D1/OOS/cost blockers into one limited public `NO_SIGNAL/UNVERIFIED` artifact.

The exported public summary contains **no raw prices, pivot levels, shadow directional candidates, source OHLC, entry, stop, TP, net R:R, claimed publisher first-known, vendor secrets or raw owner-formula text**. A SHA-derived research fingerprint is not an external attestation. Explicit quote-side descriptions are hypothetical design, NOT real executable BID/ASK quotes. The existing P152 synthetic B2/S2 BUY/SELL/net R examples cannot be joined into the real path, spoof source numeric approval or publish trade alerts.

The code introduces **no new GitHub workflow, market vendor request, Drive write/new prefix, cache schedule, OAuth credential, persisted signal journal, broker client or original Forex source changes**. The stores are caller-injected GET/list-only. This is a real software composition of existing source and owner input rather than a claim that production already has verified D1 or economics.

## QA and rollback

17 hermetic cases: actual 6TF sealed in-memory source→B2/S2 response, exact mirror/quote-side design, no action/price leakage, one/all proposed pairs with zero signoff, partial/forged source input denied BEFORE cache reads, D1 HOLD preserved, tampered SHA manifest rejected, source stores unmodified, wrong UTC/as-of and privileged sealed claims denied, owner signoff forgery denied, deterministic source/owner fingerprint, P152 synthetic profitable BUY/SELL never appears in output. Require exact-head Python3.11 and3.12 full frozen 102-blob Forex parity/golden/security/crosswheel, protected squash-only merge and independent postmain CI.

**Rollback:** revert only P187 helper/test/doc and SHA-allowlist entries. Original frozen Forex 102 blobs and 11 SOURCE_LOCKED Docs, 18/22 zone taxonomy, M5/H4/D1 scheduler and data archives remain untouched.

## Actual next blocker, not implementable by local code

External original-owner authenticated 36 B2/S2 numeric formula decisions from P184/P035 proposal intake remain **0/36**; verified account entitlement to retain/use private Drive FX source and actionable BID/ASK economic data #27, real D1 source revision & publisher first-known #180, source-licensed six-timeframe historical asof, SL/TP/net-R and untouched OOS remain absent. The user approved a **deadline/scope**, not fake formula values or data rights. The 22-Nov outcome must be explicit GO/NO-GO: if any hard gate missing, ship only safe research-only `NO_SIGNAL` rather than pretending a verified BUY/SELL release.
