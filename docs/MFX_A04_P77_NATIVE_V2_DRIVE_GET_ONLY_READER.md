# MFX A04/P0.77 — Scoped GET-only native H4/D1 V2 Drive reader

**Status:** SOURCE-ONLY, NONPRODUCTION, NO LIVE V2 ACTIVATION. This is a read-only Google Drive adapter contract tested with hermetic HTTP mocks, not an accepted real-V2 archival read or a new GitHub Actions workflow.

## Context and exact scope

MFX runs native V1 H4/D1 using immutable SHA-linked chunks and manifests, with a 256-object per-bucket fail-closed limit. P0.74 designed an inert V1→V2 shard handoff; P0.75 implemented a pure, bounded SHA recomputation across native V2 shards; P0.76 modeled caller-supplied witness hashes without claiming authenticated external anti-rollback. This P0.77 adds a **GET-only** listing/reading adapter for the *hypothetical* V2 namespace, without changing any existing V1 code paths or schedules.

The adapter:

1. Accepts an externally injected `session.get`, an exact P0.74 EUR/USD H4 or D1 proposal, and a 1..64 pair-per-shard research bound. It **does not obtain credentials**, define a runnable main CLI, add a workflow or call Twelve Data.
2. Uses existing configured OAuth-app-owned Google Drive CHUNK and MANIFEST parent folder IDs as read-only discovery scopes. Discovery requests filter the exact proposed V2-prefix and a specific parent; local checks enforce an anchored namespace regex, six-digit shard and four-digit position, allowed H4 UTC/D1 local stamp, strict 1..8 shards, exact MIME application/json, exact parent and ID/size metadata. The server's Google Drive `name contains` behavior is never accepted as scope proof by itself.
3. Paginates with a bound of 10 pages per bucket; refuses missing/repeated page tokens, duplicate name, file ID or shard/position index, oversize or malformed list rows. Maximum object body size is 262144 bytes; bounded research total is 8×64 pairs (512 Chunk + 512 Manifest objects) and is **not a production storage policy**.
4. Requires exact one-to-one Chunk and Manifest index enumeration **before reading JSON bodies**, rejecting orphans and missing pairs. Reads only referenced IDs via Drive GET / alt=media; no write, POST, PATCH, DELETE or Drive upload API.
5. Recomputes each V2 pair from canonical JSON, checks exact content-addressed names, every parent and cross-shard SHA bridge, native bar semantics and closed-publication eligibility through the P0.75 pure verifier. Uses initial and final full enumeration to catch changed names/IDs during the pass; this is not an atomic Cloud snapshot and does **not** remove any race that preserves names and IDs while changing unprotected content between GETs.
6. Requires the caller-provided expected V1 manifest SHA and expected V2 tip SHA. A **current real V1 archive below 256 pairs is rejected before any HTTP request**. A hermetically fabricated 256-pair V1 fixture is not independent evidence of old history or a right to publish V2.
7. Returns a receipt that explicitly declares `independent_external_tail_witness_verified=false`, `live_v2_activation_authorized=false`, 0 price/provider requests, 0 Drive writes and 0 broker orders. Passing a fully consistent dataset against a caller-supplied tip does **not** establish trusted anti-rollback against simultaneous replacement of dataset and tip.

## Security, concurrency and rollout blockers

No live V2 objects were created, migrated or verified. There is no durable authenticated witness, no lease/fencing, no server-side conditional CAS, no trustworthy root rotation or key lifecycle, no crash recovery, no automatic writer and no production V2 release. The original source-locked Forex Trading 102 blobs and 11 Docs, V1 256 bound, current M5/H4/D1 workflow schedules, Secrets/Variables and numeric strategy/broker gates remain untouched.

P0.77 is accepted only after: latest exact-head protected PR CI and independent exact-main CI, Python 3.11/3.12 unit-negative tests, original frozen Forex source SHA/golden parity, static/security/dependency gates, cross-Python wheel and SHA-pinned MFX-only delta allowlist. Existing V1 data rollback is **never** part of this change; rollback only added MFX-only source/test/design paths and manifest entries.

**Next:** independently choose a trusted external witness provider and owner-approved key/fencing authority, then develop a nonproduction Drive V2 recovery/readback deployment with true Google OAuth read-only evidence and explicitly authorize real V2 writes only in a separately protected owner decision. H4 source-native calls cannot be reduced before 30+ fully closed exact 48×M5 parity windows over >=7 days with genuine market-session gap analysis. D1 stays Australia/Sydney native.
