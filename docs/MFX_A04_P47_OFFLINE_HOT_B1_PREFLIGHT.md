# MFX A04/P0.47 — Offline HOT/B1 research preflight (NO provider connection)

## Owner scope and deferral (10 November 2026 ICT)
The owner elected to **defer all provider connectivity/integration testing** for Twelve Data, Massive, EODHD and FMP until a later decision. Do not request/rotate provider keys, activate GitHub scheduled market-source jobs, authenticate the service account, read/write vendor prices on private Google Drive, or claim live market monitoring is running. Cloud-only engineering/QA with GitHub + Drive governance documents may continue. No Mac, MOCHI or user-local computation.

This is a separate offline-only research QA milestone tracked by [Issue #88](https://github.com/ngluonghoa/MFX/issues/88). It adds no data integration.

## Implemented read-only contract
`mfx_cache/v3_offline_preflight.py` combines **existing** exact-hour B1 sealed-source validation, HOT closed-M5 freshness and cross-layer SHA comparison. An injected store is read only after the source index and HOT freshness pass fast fail-closed checks. Output is `OfflinePreflight`, whose flags never permit official BUY/SELL or broker orders. The optional positive status is `OFFLINE_ANCHORED_RESEARCH_ONLY_NO_LATESTNESS_PROOF`: this proves consistency only with the SHA-addressed B1 hour that the index points to. **The index could be stale against another writer**, and Drive has no globally atomic multi-file compare-and-swap.

Negative outcomes: `NO_SEALED_B1_INDEX`, `NO_HOT_OVERLAY`, `HOT_BEHIND_INDEXED_B1`, `HOT_STALE_GAPPED_OR_INSUFFICIENT`, `B1_SOURCE_CONTINUITY_UNVERIFIED`, `HOT_UNANCHORED_SEALED_B1`. Invalid source hashes, impossible timestamps, altered prior candles and forged trade promotion **raise** and must not be swallowed.

The module does not import REST/HTTP/cloud credential adapters. It performs zero external data-provider requests, zero Drive writes, zero broker calls and zero signal publication. The synthetic fixture source is not licensed quote data.

## Acceptance and limitations
Fourteen preregistered adversarial and positive tests under `tests/test_a04_p47_offline_preflight.py` cover missing index/HOT, verified overlap, exactly two immutable-source reads with no archive listing/writes, stale hourly HOT, unanchored HOT, HOT behind B1, missing candle/gap, uncertain B1 continuity, missing chunk, attempted independent digest rehash of an altered HOT price, UTC rejection, forged live permission and deterministic no-trade receipt. Run with hosted Python3.11/3.12, strict type/static/security, original source parity and wheel parity. **Code and CI acceptance is not a live Drive staging or true Forex indicator/market signal acceptance.**

Existing official owner numeric approvals remain **0/16 entry rules** and **0/36 B2/S2 decision rows**, with 14 SIM examples research-only. Keep external evidence gates [#45](https://github.com/ngluonghoa/MFX/issues/45), [#27](https://github.com/ngluonghoa/MFX/issues/27), real source [#74](https://github.com/ngluonghoa/MFX/issues/74), authenticated staging [#84](https://github.com/ngluonghoa/MFX/issues/84) and Cache V2/HOT parents [#76](https://github.com/ngluonghoa/MFX/issues/76), [#82](https://github.com/ngluonghoa/MFX/issues/82) OPEN.

No modifications to the source Forex 102 frozen Git blobs, 18 original roles, 11 source-locked Docs, accepted MFX 22 design roles, GitHub hourly cron, or vendor activation flags are authorized by this work. The candidate PR must pass hosted CI and independent post-merge main CI before being called accepted.
