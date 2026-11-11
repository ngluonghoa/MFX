# MFX A04/P0.74 — Native H4/D1 immutable V2 shard handoff (OFFLINE DESIGN)

Status: RESEARCH_ONLY / NO_GO / NO_LIVE_V2_ADAPTER. No production migration, cache expansion, or source qualification.

## Context

EUR/USD native H4 and Australia/Sydney native D1 currently use isolated immutable V1 Chunk+Manifest pairs. The full SHA auditor and hourly writer both fail closed at 256 files per bucket per native interval. P0.73 independently observed H4 3/256 and D1 2/256; no imminent capacity pressure.

## Safety invariants

1. Preserve ALL original V1 files, exact namespace, SHA/parent chain, UTC 4-hour H4 labels, Sydney-local D1 labels, composite MID provenance, schedules and existing 256-file fail-closed guard.
2. Use a separate hypothetical V2 namespace per native TF, e.g. MFX_TD_EURUSD_H4_NATIVE_V2_SHARD000001. Names never collide with existing V1 and a V2 proposal is never an actual Drive object.
3. Pin the proposal deterministically to the verified V1 tail manifest filename and SHA; reject mismatched source, missing/corrupted head, an orphan, unequal Chunk/Manifest counts, bad H4 UTC grid, impossible >256 legacy count, and an altered proposal.
4. The pure function accepts an independently audited NativeArchiveState as caller-provided metadata but DOES NOT perform that full historical verification itself. A caller-supplied SHA, even when it matches an object hash, does not establish an external anti-rollback witness.
5. The proposal reports the number of remaining V1 append pairs but never authorizes V2 activation, rewrites existing history, expands capacity, makes provider/Drive calls, or sends broker orders. A fabricated 256th metadata example in hermetic tests does not prove historic contents.
6. A future operational V2 write/read adapter needs independent V1 SHA full-chain readback, trusted external anchor, immutable V1→V2 bridge, per-shard integrity, bounded pagination/index, anti-rollback, a real Drive conditional-write/lease design, contention and crash/restore tests, retention/legal assessment, per-interval fail-closed recovery, and separate owner-protected activation approval.
7. Do not reduce H4 native usage until 30 or more fully matching 48×M5 H4 windows across at least 7 days, with genuine weekend/source-gap evidence. D1 remains Sydney-local native; HOT V3, broker and numeric signal permissions unchanged.

## Artifacts and acceptance

- Pure source proposal: tools/mfx_native_shard_v2_design.py
- Hermetic 15-case negative test suite: tests/test_a04_p74_native_v2_handoff.py
- No change to any existing runtime writer, auditor, workflow schedule, provider credentials, native data, locked 102 Forex source Git blobs, or 11 source-locked documents.
- Acceptance evidence: exact PR-head CI on Python 3.11/3.12, cross-wheel, frozen source golden parity; protected-main merge/readback; independent exact-main CI; SHA-pinned manifest entry and Google Drive canonical handoff/QA/roadmap update.

Rollback: revert only the new MFX-only design/test/docs files and corresponding allowlist entries; do not modify or delete any V1 Drive price objects. Runtime source operations stay on the protected V1 implementation.

Next independent work after this closed design: build a separately gated V2 real-cloud shard store and independently reviewed restart/fork race semantics, then source SHA anchor and rollback witness validation; do not claim operations are complete merely from this design proof.
