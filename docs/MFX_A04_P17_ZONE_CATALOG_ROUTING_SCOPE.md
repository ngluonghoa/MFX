# A04/P0.17 — Source-locked 18-label routing is executable; numeric detectors are NOT

## Evidence (frozen Forex Trading 1.0 design)

Read official copied SOURCE_LOCKED_04 Zone Taxonomy v0.5, SOURCE_LOCKED_03 Detector Audit v0.7, SOURCE_LOCKED_08 Signal Lifecycle v1.2 and source src/forex_trading/catalog.py. Original frozen Forex commit: `7e1c1c012b1b189be5ad7b9d07756eac012a8309`. The 18-label taxonomy has **7 LONG entry-candidate labels, 8 SHORT entry-candidate labels, 1 B7 watch-only, 2 S3/S8 exit-LONG warning-only**; FX-B9 excluded. Approved design says all numeric zone predicates/calibration and OOS are NOT IMPLEMENTED / NOT RUN. No quantitative threshold may be inferred from qualitative descriptions.

## What code actually does

Add `mfx_research.zone_catalog_gate.route_unverified_zone_claims`: a pure, runnable classification/dedup routine using frozen original `ZONES` and `ZonePurpose` exactly, under research-only MFX package that is NOT bundled into the release wheel. It maps a **claimed label** to BUY_CANDIDATE_UNVERIFIED, SELL_CANDIDATE_UNVERIFIED, WATCH_ONLY or EXIT_LONG_WARNING_ONLY. It will not classify an unknown zone, FX-B9, stale-conversation malformed identity, duplicated event-label or future-known claim. It groups B5/B6/B8, S7/FX-S9/FX-S10 sharing the same pair/origin/direction into ONE unverified evidence group; does not invent a primary signal or arbitrary rule precedence. For opposing direction claims, separate groups remain UNVERIFIED, no trade signal. Strictly ZERO numeric detector invocations / source entitlement / actual BUY/SELL alerts / provider I/O / real Drive cache writes / broker trades. Using a `UnverifiedZoneClaim` is *not* proof the zone existed on a price chart.

## Scope and roadmap

This is a necessary executable **source-native domain routing step**, not completion of 15 numerical BUY/SELL strategies. Prior P0.16 EMA2/EMA3 experiment remains explicitly NON-PARITY and is not relabeled B2/S2 or any other original zone. The source spec names **B2 LONG and S2 SHORT** as initial numerical pilots, but quantitative pivot/near/phase/invalidations/market-cost rule parameters are still pending; must version and approve rule manifests and deterministic no-lookahead fixtures before claiming implemented detectors. No source 30-module bytes touched; seven NON-src Git paths only, SHA-pinned; protected PR exact-head and independent postmain CI. Retain all 50 original Forex frozen golden, P0.7 34 wrappers, prior rights/QA, A03 coverage/mutation, strict mypy, secrets and wheel cross-Python checks. Any live price/Google Drive cache remains blocked in GitHub Issue #27.

## Authoritative Drive docs

- Zone Taxonomy (frozen): https://docs.google.com/document/d/18LbpRqzYn3XN5xHPKNsTv1NEMvBjL49iAyk7jTHWuV0/edit
- Detector Audit (frozen): https://docs.google.com/document/d/10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA/edit
- Signal Lifecycle (frozen): https://docs.google.com/document/d/1YDFIridOHHtARMNTI-vvGZBqv2H58WtOooSHbsy9Mk8/edit
