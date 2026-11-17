# MFX P0.186 — Private P171 D1 observed-version lineage (PURE, NO I/O)

**Date:** 2026-11-17 ICT. **Source incident:** [MFX #180](https://github.com/ngluonghoa/MFX/issues/180). **Prior contract:** [P0.185](https://github.com/ngluonghoa/MFX/pull/185). **Review scope:** Owner-requested 22-Nov limited B2 BUY/S2 SELL *conditional* signal-only GO/NO-GO.

## Reason for this change

The native Twelve Data EUR/USD D1 hourly feed still conflicts with one of the five already-SHA-sealed P171 fresh-epoch D1 observations (one changed, zero missing). The original immutable V1 archive, P169 quarantined observations and owner-selected P171 2026-11-11 epoch must not be rewritten. H4 has recovered separately and post-write SHA readback passed. A deterministic record of which conflicting *SHA version was observed by the GitHub runner and when* is needed before an independently reviewed, future append-only Drive observation writer can be authorized. No vendor publisher-first-known or source rights are established.

## Implementation

Pure module `mfx_cache/p186_p171_revision_observation_lineage.py` **builds a bounded in-memory private proposal ledger** from validated P185 proposals; it never connects to Drive or provider API. Each candidate requires an independently audited P171 manifest SHA supplied out-of-band. One immutable hash-linked record identifies one native D1 label, original stored SHA, currently refetched SHA, runner-observed UTC, P185 proposal digest and previous record SHA. All entries are content-digested, strictly sequential and checked against the fixed original P171 source root. **A SHA/digest is not an owner authorization, publisher timestamp or trusted external witness.**

- New SHA for the same stored D1 label and baseline becomes a new private observation with strictly greater runner UTC and parent SHA.
- Identical consecutive SHA readback is idempotent, preserving the **first** runner-observed timestamp. Reversion to a prior previously seen SHA is a **new** version observation, not a history rewrite.
- Any mutated parent, sequence, timestamp, source manifest, native label, baseline SHA, digest, extra/private field, ownership/entitlement flag or broker permission fails closed.
- `private_p171_versions_known_by_runner_asof` returns only observations first seen by that runner at or before a supplied UTC time. It does **not** select a canonical D1 market candle, establish vendor first-known, authorize source reconciliation, change previously derived signals, or validate execution.
- `public_p171_lineage_status` exports only bounded aggregate counts and hard **false** rights/signal/writes, never SHA values, native D1 day, OHLC or Drive IDs.

## Explicit non-goals and fail-closed boundaries

This PR does **NOT** introduce a persisted journal, new Drive folder/object/GET/write, vendor call, source historic revision, P171 D1 cache rebase/promotion, scheduler/OAuth/secret modification, trading alert, broker integration, backtest or owner source-numeric approval. P185 only handled one-changed/zero-missing; P186 uses those already-validated candidates. The current natural writer stays RED on D1 conflict while narrowly permitted H4 commits remain independent. Original Forex 102 blobs and 11 SOURCE_LOCKED Docs remain untouched.

A **future separately approved** production observation writer must have a private namespace and policy for authenticating source/account retention rights, append-only Drive CAS and readback, orphan/idempotence/concurrency handling, signed source owner decision, first-known provenance, quota/cost and recovery. Do not treat this in-memory protocol as approval to create that writer. It must keep both V1/P171 archives and their old SHA records immutable and prevent retroactive as-of trading claims.

## Acceptance and next release gate

14 no-network hermetic tests verify first/next/duplicate/reversion version behavior, SHA parent chain and forged flags, privacy, strict observed-as-of prefix, wrong manifest/label/clock, capacity cap, no source store mutation and P185 candidate integrity. Exact-head protected GitHub CI Python3.11/3.12 with frozen Forex golden, security and cross-Python wheel parity, then squash-only main and independent push CI mandatory.

Remaining release STOP: 18 paired B2/S2 rules / 36 numerical original-source signoffs **0/36** [#45](https://github.com/ngluonghoa/MFX/issues/45); vendor/source-specific license, allowed MID vs BID/ASK, Google Drive retention [#27](https://github.com/ngluonghoa/MFX/issues/27); D1 original and updated vendor version independent first-known and accepted source custody [#180](https://github.com/ngluonghoa/MFX/issues/180); fully causal six-TF feed, real BID/ASK costs/SLTP/net-R and untouched OOS [#138](https://github.com/ngluonghoa/MFX/issues/138). Default public `NO_SIGNAL/UNVERIFIED`. No broker orders.

**Rollback:** revert only the new P186 helper/test/doc and corresponding exact-SHA allowlist entries. No Drive source state to undo.
