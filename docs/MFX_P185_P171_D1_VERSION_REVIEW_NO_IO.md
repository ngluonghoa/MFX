# MFX P0.185 — P171 revised D1 SHA: private version-review proposal (NO write)

**Date:** 2026-11-17 ICT. **Evidence incident:** [#180](https://github.com/ngluonghoa/MFX/issues/180). **Scope:** no-network/no-Drive/no-vendor Python research/control plane, separate from the original Forex Trading 1.0 frozen source.

## Exact real-world motivation

Natural hourly P171 D1 refetch fails the original overlap guard with **one changed SHA out of five indexed D1 source bars and zero missing**. The existing independently sealed original native D1 V1 history and owner-selected 11-Nov P171 fresh epoch MUST both remain immutable. P183 successfully writes eligible H4 despite the continuing D1 HOLD, and independent native H4 full SHA audits after those writes now PASS (17-Nov #44084196644: H4 20 immutable manifest/chunk pairs; 157 closed bars; last UTC 08:00 H4 label; lag zero at audit). This is not a D1 resolution or valid live signal.

## What is implemented

Pure module `mfx_cache/p185_p171_d1_revision_review.py` consumes **only an already independently full-SHA-audited** P171 `FreshEpochState`, the **already fetched** strictly typed closed provider-native D1 batch, and exact runner UTC observation time. It reuses the P180 redacted diagnostic and rejects:

- Same SHA with no actual revision; **missing** overlap labels; **more than one** changed overlap SHA; malformed/untrusted source or epoch state; orphan/partial state; incorrect source, quote role or authority.
- Fake publisher-first-known, vendor rights, canonical owner approval, historical as-of backfill, live BUY/SELL, broker orders, untrusted time and clock rollback.
- Private candidate data leaked through the deliberately separate **aggregate-only** public projection.

Successful evaluation produces an immutable **in-memory** review packet containing a single changed pair of *old/new SHA identities and local date* (PRIVATE only), the independently read sealed P171 manifest tip digest, runner observed time and P180 redacted counts. The packet content digest is deterministic for identical inputs, but **is not a digital signature, vendor attestation or owner approval**. Revalidation enforces the same fail-closed flags.

**Operational boundaries:** This PR does **NOT** plug into the hourly native writer, persist a new Drive object, modify an existing SHA, create a D1 canonical version, backfill an as-of observation, send any provider request, change credentials, settings or GitHub Actions workflow, run the owner-gated manual six-TF read, or publish real BUY/SELL. It neither diagnoses the vendor's reason for revision nor independently proves publisher first-known/time of publication.

## Independent next gate

A subsequent independently reviewed PR/owner decision can design an **append-only versioned revision observation lineage** under a new private MFX-only namespace using actual existing source, first-runner-observed semantics and full old/new SHA custody. Any new write path must be preauthorized, quota-bound, readback-verified, and unable to edit either original V1 or P171 immutable epoch. Never automatically activate the revised D1 for live signals. Source entitlement/private storage/retention #27, source owner numeric B2/S2 approvals 0/36 #45/#62, real executable BID/ASK costs/SLTP/net-R, source first-known and untouched historical chronological OOS remain independent NO-GO gates.

**QA:** 14 hermetic tests cover changed/missing/identical/multiple overlap classification, source/orphan/clock tamper, immutable original store, denied signoffs and privacy/no-I/O. All original 102 frozen Forex Git blobs, 11 SOURCE_LOCKED Docs, existing Cache scheduler and broker boundaries remain unchanged. Require protected PR-head Python 3.11+3.12 full/golden/security/crosswheel CI; protected squash-only merge and independently witnessed post-main CI before describing the code as accepted.

**Rollback:** revert only MFX P185 helper/test/doc and matching SHA allowlist rows. Never remove a previously accepted immutable source object.
