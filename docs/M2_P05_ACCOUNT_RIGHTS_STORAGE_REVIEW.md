# M2/P0.5 — Account-specific Forex data entitlement & durable cache location review

**State: fail-closed PAPERWORK REVIEW ONLY. No selected FX vendor, broker account, vendor-specific permission, approved host, actual market data, cache database or automatic 5-minute polling.** The code never grants real access, even if an applicant marks a case as approved.

## Objective

Maintain the user-approved DEC-FX-020 Smart Cache L1–L5 objective without assuming that permission to query historical candles includes permission to retain them, build indicators, replay them, use for Backtest, or copy to a second region/host. Account contracts, signed vendor evidence, pricing source and storage residency must be verified **independently**, separately per actual vendor/product/jurisdiction/account subscription.

## Public documentation checked on 2026-11-07

| Candidate | Publicly documented technical/policy details | What is **not** established |
| --- | --- | --- |
| OANDA v20 | [Official introduction](https://developer.oanda.com/rest-live-v20/introduction/) says an eligible v20 account and acceptance of API license are required to obtain a personal access token. [Pricing endpoints](https://developer.oanda.com/rest-live-v20/pricing-ep/) expose historical candle BID/ASK selection and bounded from/to access. | *An individual account's* license and region, raw/derived storage and cache retention limits, replay/backtest permission, authenticated correction feed, actual account vs history price parity. An API token itself is not a legal rights proof. |
| Twelve Data | [Forex API v2](https://support.twelvedata.com/en/articles/12520817-forex-api-v2) describes aggregated candles and minute mid-price real-time updates with plan-specific licensing. [Terms](https://twelvedata.com/terms) restrict storing/caching data beyond permitted periods, and redistribution needs additional authorization. | No validated native two-sided historical BID+ASK per-broker stream or user's specific retention terms. Available API quota does not establish these rights. |
| Dukascopy/JForex | [Historical Data overview](https://www.dukascopy.com/wiki/en/development/strategy-api/historical-data/overview-historical-data/) documents IHistory access; [official FAQ](https://www.dukascopy.com/swiss/english/about/faq/) says JForex itself saves reconstructed bars locally in its cache, with four downloaded underlying resolutions. | The vendor's own platform cache does **not** grant this independent project rights to export, keep, derive, redistribute or backtest native data in a new store. Demo/live tick-source differences and provider-specific day clocks must be tested. |

These are **public source references**, not verified contract grants or legal advice. The rights table is intentionally account-agnostic; **no provider chosen, no market price sampled, no entitlement attested**.

## New typed implementation

`src/forex_trading/account_data_review.py` builds on `source_qualification.py` and `cache_storage_review.py` rather than making a second competing permission oracle.

- `AccountContractClaim`: opaque *nonsecret* provider/product, jurisdiction, account scope, plan, contract version, effective/expiry, first-known-by-us UTC. Do not include account number, username, API key, actual endpoint or token in GitHub/Drive.
- `DataRetentionClaim`: maximum claimed retention days, allowed storage residency regions, separate claimed right to retain derived indicators/features. Unknown maximum or unknown region is **blocking**.
- `CandidateStorageLocation`: abstract location class and region, referencing the existing `DurableStorageProposal` control claims. This does not choose a concrete hostname, cloud project or price-data repository.
- `RevocationNoticeClaim`: effective and **first-seen-by-us** UTC are distinct, so a retroactive vendor change cannot silently alter historic as-of approval.
- `review_account_data_packet`: compares provider/product identity, rights per use, source BID/ASK/TF/time semantics, account first-known/effective/expiry, freshness of evidence, retention duration, storage proposal duration/region, derived-data rights and revocation. Distinct states: `BLOCKED_MISSING_EVIDENCE`, `READY_FOR_INDEPENDENT_REVIEW`, `SUSPEND_AND_REVIEW_RETENTION`.
- Even a complete positive *claimed* questionnaire returns only `READY_FOR_INDEPENDENT_REVIEW`; `account_entitlement_independently_verified=False`, `storage_host_approved=False`, `may_fetch_real_fx_data=False`, `may_cache_real_fx_data=False`, `may_retain_derived_indicators=False`, `may_run_real_backtests=False`.
- Expiration or observed-effective revocation requests a **future operational** freeze of new fetch/writes and a retention/legal review. No physical deletion, quarantine, data transfer, backfill or access revocation is implemented; preserve lawful audit evidence and evaluate any legal hold before actual purge.

## Storage design alternatives — no host selected

| Option | Merits | Gaps requiring explicit approval | Current verdict |
| --- | --- | --- | --- |
| In-memory synthetic | Fast reference tests without real price retention | Lost across sessions; not durable or suitable for the requested real cache | **Synthetic only** |
| Encrypted local database / disk cache | Predictable latency, local atomic transactions, selective timeframe indexes | Approved always-on host, disk encryption/key backup, ACL, crash/restart/rollback, data rights in region and approved retention; **MOCHI only optional** | **Review candidate, not approved** |
| Encrypted remote object/database store | Durable managed snapshots possible, multi-device access independent of one Mac | License allowing remote storage/transfers, residency and provider terms, credentials/roles, costs, backup/restore/versioning, audit/wipe and real read/byte performance | **Review candidate, not approved** |

A vendor's permitted retention of *raw candles* does not automatically authorize derived features, historical replay, cross-border replication, storage in Google Drive, keeping data in GitHub or use in a cloud notebook. Reuse from a licensed local cache also requires rights that survive the user session.

## Production promotion prerequisites (all OPEN)

1. User-selected vendor and applicable account/product/jurisdiction + exact current contract or vendor written clarification (no secrets uploaded).
2. Distinct rights to API access, raw storage, derive, cache incremental, replay, internal backtest; redistribution separate. Explicit maximum retention and derived indicator retention, regions/residency, renewal/expiry/revocation, source data authenticity and attribution requirements.
3. Independent reviewer and trusted evidence custody (verified document bytes, version, origin, first-seen, external approval), not a self-asserted `ALLOW_CLAIMED` or SHA field.
4. Chosen encrypted durable store host/platform/region with security control approval, schema migrations, atomic snapshot, integrity, backup/restore, audit retention, revocation deletion workflow and operational rollback drill; no hidden costs or production deploy.
5. Source-specific native BID/ASK historical bounded fetch test after authorization; verified vendor session/DST, actual source corrections, network bytes/calls, provider quota units, restart-safe incremental cache and measured 20-pair five-minute cold/warm performance.
6. FULL-vs-INCREMENTAL indicator+zone test, status/no-lookahead gates and backtest/OOS held separately behind licensed data/strategy acceptance.

**No live trading, no broker orders, no real FX source download, no automatic refresh. No M15001-FG-3; MOCHI optional, not touched. Forex repo only.** All tests use synthetic fake account/rights documents and mocked records; no legal truth or market effectiveness is implied.

### Next after M2/P0.5

Before an actual provider trial, choose a provider/product **only on evidence**, obtain the matching independent rights confirmation and approve a suitable host/storage class. Until then, the project can continue provider-independent synthetic unit tests, but it must not claim operational Smart Cache savings.
