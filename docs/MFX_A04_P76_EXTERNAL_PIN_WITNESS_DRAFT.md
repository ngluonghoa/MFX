# MFX A04/P0.76 — Native V2 monotonic witness drafts (hermetic-only)

**Status: OFFLINE RESEARCH ONLY. No cryptographic external attestation, no Google Drive V2 runtime, and no authorization to change the MFX cache.**

## Purpose

P0.75 models 64-pair SHA-bound H4/D1 native shard histories and verifies the FULL SUPPLIED chain, but a malicious rollback can substitute BOTH a shortened history and a matching expected tip. P0.76 adds an in-memory monotonic checkpoint *draft* protocol to test necessary controls: a genesis root, canonical snapshot digest, forward-only pair count and generation, exact previous witness digest, and full old-prefix + new-history SHA verification before proposing an update.

## Trust model and limitations

- The `caller_pinned_witness_sha256` is supplied by the caller. P0.76 does NOT check where the pin came from. A SHA hash, a Google Drive object, a modified user variable, a GitHub file in a mutable branch or any pin kept in the same controllable archive cannot by itself prove external anti-rollback authority.
- A malicious caller who can replace the witness draft, its pin and all price data can pass internal integrity checks with a shortened coherent history. A dedicated hermetic regression DEMONSTRATES this, and every verification receipt says `independently_authenticated=false` and `durable_anti_rollback_verified=false`.
- Simulated V1 256/256 tail is a **fake test fixture**, not real historical V1 attestation. New witnesses remain proposal-only; there are no live source or provider requests, no secret keys, no external signatures, no Google Drive file creation and no broker API.
- The proposal does not promise unconditional crash atomicity or conflict resolution; storing V2 objects and a witness as separate Drive files will require independently designed write ordering, split-brain protection and fencing, backed-up recovery, a trusted monotonic anchor, and independent readback.
- The V1 256-file per-bucket cap, M5/H4/D1 automated schedules, native Sydney D1 labels, source-mid provenance, cache owner flags, frozen original Forex 102 blobs and 11 source-locked Docs all stay unchanged.

## Pure algorithm

`draft_genesis` requires a 256-pair closed, SHA-pinned V1 *caller-state* and a validated P0.74 inert root. The output is a canonical witness record of generation zero and no V2 pairs.

`verify_witness_draft` checks exact schema/source/TF/root, expected canonical pin, monotonic generation/count invariants, and re-verifies every supplied V2 SHA chain object. Its receipt expressly provides **NO** independent trust or rollback protection.

`draft_next_witness` first verifies previous checkpoint against the provided pin and the FULL old history prefix, denies non-growing counts, then verifies the entire extended V2 chain and creates a candidate record with previous-digest link and strictly growing generation. A draft cannot be treated as an owner-approved write or signed checkpoint.

## Research QA and future acceptance

20 hermetic tests cover canonical genesis, root/tip binding, rollover, D1 Sydney, wrong prior pin, replay, truncation, data corruption, fork, forged authenticated/live flags, wrong native TF, fake early V1 promotion, malformed pin and unchanged production workflow. Passing these tests is NOT proof of a trustworthy external witness.

Before any real V2 Cloud implementation: independently choose a trust boundary and durable monotonic storage outside the mutable price-data archive, specify authenticated signature/authority, revocation/key rotation, reliable time handling, competing-writer fencing/CAS, failure injection, restore and rollback evidence; separately approve real Cloud OAuth scope and data licensing. Never enable LIVE V2 without explicit owner-approved protected PR and independent QA. Continue M5→native H4 observation for 30+ exact H4 across >=7 days; no native H4 replacement here.
