# MFX P0.160 — Option B authorized: independent MFX numeric B2/S2 strategy **draft**

Date: 2026-11-14 ICT. Owner/user explicitly chose **B**, after considering alternative A strict original Forex Trading 1.0 numerical 1:1 versus B developing independently versioned MFX-specific rules while preserving the frozen Forex source.

## What was authorized, and what was NOT

**Authorized:** pursue an *independent numerical* MFX strategy for B2 LONG and S2 SHORT using the already approved *design-only* Forex Trading qualitative regions and the same project source. Preserve all 102 original frozen Forex Git blobs, 11 SOURCE_LOCKED Google Docs, historical original label IDs, four-state design mapping and base source parity. **Do not claim that independently designed MFX thresholds existed in, or are numeric-parity-identical to, original Forex Trading 1.0.**

**Not yet approved:** specific MFX numeric thresholds or a release-ready detector, historical first-known data provenance, real quote rights, native D1 session/revision correction, bid/ask/fee/slippage risk, no-lookahead untouched OOS or live BUY/SELL alert. Option B is a development-scope decision only; the user did not sign the concrete numbers in this draft. Original B2/S2 source 36/36 absent numeric owner values remain recorded as absent and the original P0.21/P0.35 manifests are neither repurposed nor altered. New numeric MFX approvals must be reviewed against a *separate MFX version*, not falsify original-source approvals.

## Concrete pinned and executable **SYNTHETIC draft** profile

Source: `docs/MFX_V1_B2S2_INDEPENDENT_POLICY_DRAFT.json`
Schema: `MFX_B2S2_INDEPENDENT_NUMERIC_POLICY_DRAFT_V1`
Version: `MFX:B2S2-NEW-STRATEGY-DRAFT-001`
Status: `PROPOSED_NOT_APPROVED`.

All five explicit experimental numeric values deliberately **reuse earlier hermetic P0.18–P0.19 synthetic fixture values**, to establish a reproducible reviewable baseline; they are not calibrated for performance or derived from the Forex original.

| Candidate input | Draft value | Interpretation |
|---|---:|---|
| H1 observed True Range mean period | 3 closed H1 bars | simple arithmetic true-range mean, not Wilder ATR |
| H1 source zone lookback | 3 closed H1 bars | B2 lowest observed low, S2 highest observed high |
| H1 zone width | 0.3 × observed H1 mean TR | B2 above known low, S2 below known high |
| H1 near-zone tolerance | 0.5 × observed H1 mean TR | Prior closed M15 candle intersects expanded H1 zone |
| Maximum micro-break extension | 0.5 × observed H1 mean TR | Latest closed M15 close may not chase beyond previous known micro-level |

Current **technical shortcomings** must not be omitted: D1/H4 use two previously closed candle-extrema proxies, NOT two independently right-confirmed swing highs and lows per TF. The M15 trigger is a strict new crossing of the high/low of a prior CLOSED M15 seed, NOT yet a separately right-bar-confirmed pivot. These lack owner numeric validation and do not satisfy higher-timeframe source revisions or real point-in-time source knowledge; do not claim confirmed trend, actual source parity, or executable market signals. H1 mean TR and scenario zone do not establish economic quality.

The new MFX module `mfx_research/mfx_b2s2_independent_policy_draft.py` validates an exact typed, versioned, canonical SHA256 profile, forbids any self-attested approval/real data rights/production privilege, then **reuses** P0.19/P0.32's already implemented causal CLOSED synthetic OHLC bridge and 22-zone classification. It computes internal experiment BUY for B2, SELL for S2 when fixture conditions actually hold, and NO_SIGNAL for missing triggers, with a hard, separate **public** `NO_SIGNAL / UNVERIFIED` API and repr/private event redaction. No extra origin/zone arithmetic is duplicated in the new wrapper. Other 14 entry zone numerical engines are not claimed.

24 new hermetic tests cover both directions, missing trigger, JSON schema, policy override/forged approval, malformed/future/real source, deterministic version fingerprint, absent provider/cache/broker, strict public no price/direction disclosure. Full Python 3.11+3.12, source-lock/golden/static/security and cross-Python wheel CI required plus independent main-push accepted. No new live historical user-signal runtime, secret, provider API, Drive market cache read/write, GitHub workflow/schedule, client MT4/MT5, ChatGPT automation or broker execution.

## What must be done next to earn production BUY/SELL

1. Owner must independently review and accept or change *this* versioned MFX-only numeric profile: replace weak 2-bar D1/H4 proxies with causal 2-confirmed-high/2-confirmed-low pivots across a sufficiently long **lawfully sourced** D1/H4 history; require strict M15 right-closed pivot + as-of first-known and a real H1 support/retest hypothesis. Do not treat the current profile as accepted merely because tests pass. A strict observed crossed M15 pivot does not automatically satisfy trend/pullback/risk.
2. Resolve **#147 EUR/USD Sydney D1 2026-11-11 original numeric revision** via explicit source-authorized, append-only lineage and publisher first-known; original 16-bar SHA archived history remains immutable and quarantined.
3. Obtain actual account-specific rights for private raw/derived Google Drive retention and display/non-display use (#27), licensed first-known/revisions and broker-specific independent BID/ASK costs if financial R/R/SL/TP are shown. Native H4 + D1 source identity and intra-hour M15 freshness must be established; never silently replace with stale M5 or unlicensed original versions.
4. Run walk-forward and genuinely untouched chronological OOS using source states that existed at each decision; approve economic thresholds, session/news/rollover quality, bounded false signals, dedup and invalidation, then separately approve the versioned MFX-only numeric rule for signal-only output. No broker orders at any point.

Rollback: revert P0.160's MFX-only candidate config/adapter/test/docs and pinned SHA delta rows while preserving protected main P0.159, frozen Forex source, Drive archives, and production Cache schedule. **Final product at this stage remains `NO_SIGNAL / UNVERIFIED`.**
