# MFX P0.208 — Owner-approved preparation of a separate revised-D1 version; NO storage or source admission

## Authorization scope — 23 November 2026

The owner approved **preparing** a separate D1 revised-version branch while **not writing** revised D1 prices to Google Drive until relevant source-rights, vintage-admission and first-known conditions are resolved. This is **not** a grant to accept the vendor's revised 18-Nov EUR/USD OHLC as the canonical P192 18-Nov bar, nor a release approval for B2 BUY, S2 SELL, any other Forex zone, or broker execution.

The original active **P192 owner 18-Nov** D1 manifest/chunk remain unchanged and SHA immutable. The old P171/V1 historical archive must never be spliced into the selected post-18Nov epoch. We do not change original Forex Trading 1.0's 102 Git blobs, 11 SOURCE_LOCKED Docs, M5/H4/D1 credential settings, hourly writer cadence or any Drive source file.

## Real evidence present before P208

At [scheduled native writer #45187886958](https://github.com/ngluonghoa/MFX/actions/runs/45187886958) on 23 Nov 13:50 UTC, protected main P207 generated its real `MFX_P207_P192_REVISED_D1_FORK_INMEMORY_ONLY` marker with **6 closed EUR/USD native D1 source rows privately observed**: revised 18-Nov overlap and five later closed rows. This was **not persisted**. P204 and P200 still classified one numerically changed source overlap, publisher first-known not authenticated, and P192 original quarantine remained deliberately RED. A full read-only independent [native audit #45189856296](https://github.com/ngluonghoa/MFX/actions/runs/45189856296) confirmed the original P192 D1 selected source still has only **one** SHA-sealed 18-Nov bar, with a gap of five **calendar days, not asserted FX market sessions**, while native H4 53/53 SHA manifest/chunk pairs and 193 closed bars were present with zero expected-slot lag. [M5 audit #45189082914](https://github.com/ngluonghoa/MFX/actions/runs/45189082914) observed 304 manifest/chunk pairs and UTC 12:00 hour (3 most-recent SHA pairs independently audited, not full archive). These snapshots are observations, not source/account licensing or trading-performance proof.

## What P208 actually prepares

New pure `mfx_cache/p208_p192_revision_vintage_dryrun.py` accepts only an **independently replay-verifiable P207 in-memory fork** and the same already-fetched provider-native CLOSED D1 batch, the same original SHA-audited P192 manifest and P204 private review. It refuses fake authorizations and source mismatches before deriving a **non-stored metadata outline** for a distinct proposed namespace:

`MFX_P208_EURUSD_D1_20261118_REVISED_VINTAGE_REVIEW_ONLY_V1_`

This prefix cannot collide with existing P192, P171 or V1 canonical price objects. The private outline contains only original and revised source-row SHA identifiers, source-local date labels, source-runner observation (explicitly **not** publisher first-known), a deterministic candidate-chunk/manifest name, and an SHA-linked proposal fingerprint. It **does not contain actual OHLC bar bodies** and therefore is **not a write-ready market-data chunk**. It is intentionally in RAM, has no Google Drive store or commit function, and is never written to disk, GitHub, Drive or any provider.

A small guarded addition to the existing P207/P204 diagnostic path emits the safe marker `MFX_P208_D1_REVISED_VINTAGE_DRYRUN_NO_STORAGE` with only row counts and explicit `NO_SIGNAL`. It never exposes private bar dates, OHLC, SHA, candidate file names, runner clock or credentials. The existing P200 numeric-overlap redacted classification, independent safe P202 H4-only append and the final `P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE` exception remain fully intact.

The owner has **not** approved allocating a Google Drive namespace, creating versioned price objects, changing active D1 source selection, source historical-as-of replay from a revised vintage or producing any actionable BUY/SELL. P208 enforces `drive_namespace_allocated=false`, `may_write_drive=false`, `may_select_as_active_d1=false`, `source_first_known_verified=false`, `source_admission=false`, `owner_canonical_revision_approved=false`, `vendor_retention_rights_verified=false`, `may_publish_buy_sell=false`, `may_trade=false` and zero provider/Drive/broker side effects.

## Conditions before considering any later persistence or promotion

**Persistence into a new actual private Drive namespace** requires separately reviewed account- and product-specific lawful Forex raw/derived/private-Drive storage, retention and replay rights (#27), plus a new independently reviewed protected PR that contains an actual disjoint namespace writer, complete SHA audit and rollback. The owner's approval to prepare a branch **does not enable this write**. If the user already allows hourly cache collection, it applies to previously authorized paths, not this unproven revised D1 version.

**Source selection/admission** additionally needs the original D1 source-vintage/18-Nov owner verdict (#180), immutable parent and revised source-row custody and independently evaluated publisher first-known or an explicit source-versioning treatment that never misrepresents original historical as-of availability. A runner's observation timestamp cannot substitute for publisher first-known. NO D1 pivot or causality promotion merely because 6 rows now exist. Never silently reconcile the revision into P192.

**Trading-signal release** separately requires signed original B2/S2 numeric formula/fixtures and 1:1 review (currently **0/36**, #45), executable BID/ASK plus spread/fees/SL/TP/net R, genuine untouched chronological OOS and owner GO (#138); no broker-order mode. Research-only MID cannot stand in for executable BID/ASK.

## QA / rollback

Nineteen hermetic P208 negative and source-symmetry tests cover original SHA, exact P207 replay, fixed disjoint namespace, private SHA identity, separate outline idempotence, source/rights/owner/Drive permission forged-flag rejection, future Sydney-local D1 rejection, missing original row, source tamper and the real mocked scheduled writer still raising P192 quarantine with unchanged vendor request count and old P192 Drive object count. Exact-head Python3.11/3.12 full test suite, golden frozen Forex 102 source blobs, static/security, cross-Python wheel parity, protected squash-only merge and separately verified protected main-push CI are required. Rollback is confined to P208 module, its tests, this documentation, the narrow optional writer log path and SHA manifest. No production market cache data will be changed.

**Completion of P208 means a safe isolated proposed version path is prepared and technically tested, not that a revised D1 source archive has been persisted or admitted.**
