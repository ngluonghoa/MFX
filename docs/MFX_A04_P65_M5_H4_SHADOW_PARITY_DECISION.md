# MFX A04/P0.65 — Owner-approved M5-derived H4 shadow, native parity before source optimization

Date: 2026-11-11 ICT. Decision origin: owner explicitly approved the M5-first optimization proposal in the current MFX project discussion. This is approval to RESEARCH, VERIFY and PLAN the migration, not permission to silently replace source-native candles or claim live parity. Independent Forex Trading 1.0 original 102 Git blob baseline and 11 source-locked Docs stay unchanged.

## Why: M5 already contains 48 five-minute slots per four-hour H4 window

P0.46 MFX Cache V2 already derives M15 (3 M5), M30 (6 M5), H1 (12 M5) from closed UTC M5. Its deliberately frozen derivation API rejects H4/D1, and P0.54/P0.64 explicitly label H4/D1 as independent Twelve Data native MID data. M5 feed is also TWELVE_DATA_COMPOSITE_MID, not BID/ASK. Therefore a derived H4 can be COMPUTED, but may still be numerically different from the vendor's own native H4 due to missing/late/revised source bars, vendor aggregation rules and price precision. The native H4 is independent evidence, never to be misrepresented as M5 data.

P0.65 introduces separate pure research module `mfx_cache/h4_shadow.py`, not a change to `derive_intraday` or a scheduled production writer.

### Proposed eventual model (no runtime activation in P0.65)

- Continue the existing **hourly M5 source-to-private-Drive immutable batch**, subject to source quota and gates.
- Keep deriving **M15/M30/H1** from precisely complete UTC M5 groups as in existing P0.46.
- For research, derive **H4 from exactly 48 contiguous closed M5** on UTC 00/04/08/12/16/20 four-hour boundaries; no partial bars, invented holes, aggregation with future bars, implicit revisions, or shift to Sydney session start. H4 shadow is labeled `is_source_native=False` with 48-M5 input fingerprint and derivation version.
- Keep **H4 source-native** in the P0.64 hourly event-driven workflow as the comparison/fallback anchor until the complete staged evidence and separate protected change approval. A research match is NOT a license to turn off H4 source.
- Keep **D1 source-native** on the exact Australia/Sydney local-session and DST calendar; UTC-day 288 M5 bars must not be silently promoted to vendor-native D1. A future D1 shadow would need a separate timezone- and session-aware proposal.
- Store derived cache partitions only after immutable authenticated M5 Chunk/Manifest parent and SHA-chain readbacks, exact parent fingerprint, versioned derivation and idempotent Drive write contracts are implemented and QA approved. **P0.65 does NOT write H4 derived data to live Google Drive**, change retention policy or create a new provider request.
- No trading, BUY/SELL numerics, HOT V3 or broker actions. No user-local Mac/MOCHI compute.

### Research parity receipt

`derive_h4_shadow`: receives a bounded typed tuple of already verified closed M5 bars and explicit UTC as-of; generates zero or more H4 windows only when all 48 expected UTC start labels exist. A missing window is explicitly reported, not filled, even if the source has skipped a weekend or session.

`compare_shadow_to_native`: accepts SHA-fingerprint-bearing H4 shadow and independently sourced typed H4 native EUR/USD UTC-open labels; validates native MID/provenance, exact four-hour grid and positive OHLC, then compares decimal O/H/L/C exactly. Every shadow bar is classified **MATCH**, **MISMATCH** (with the differing fields) or **NATIVE_MISSING**. These are in-memory pure-computation receipts; zero provider calls, zero Drive writes, zero signals, zero broker orders. Even an all-MATCH receipt reports `fully_verified=False` until authentic source, Drive lineage and sufficient live-range evidence have been proven externally.

These SHA fingerprints are hashes of canonical 48-M5 input content, not proof that the caller read authenticated live Google Drive. Cache parent / history proof must be added as a separate bounded connector job, not inferred from an offline test.

### Acceptance gates before any H4 native reduction

1. **Hermetic hosted QA:** unit/negative cases for 47/48, 48, 96 slots, clock/cross-midnight/UTC grids, missing M5, unordered/duplicate data, unclosed candle, price provenance, numeric comparator MATCH/MISMATCH/MISSING, no D1 derivation. Hosted Python 3.11 and 3.12 CI, frozen 102-source parity, type/lint/static/security, wheel byte parity.
2. **Live read-only proof:** implement GitHub-hosted auditor that only reads the existing authenticated M5 and H4 native Drive objects, checks both immutable SHA chains and every parent Chunk/Manifest, assembles 48-M5 windows across hourly chunk boundaries, and independently hashes every window. No provider requests or Drive writes in the auditor.
3. **Observation window:** compare at least 30 FULL, consecutive, independently source-audited overlapping H4 windows spanning at least seven days, including session boundaries/weekend where native source actually publishes. Require zero unsupported gaps and zero unexplained OHLC mismatches; otherwise block optimization, report differences and stay on native H4. Any older-than-index revision, provider rounding difference or source timezone ambiguity requires explicit separate policy.
4. **Operational compatibility:** verify delayed GitHub cron, restart/skip, vendor quota, D1 Sydney DST, append races and multi-parent M5 history cases. Source entitlement for long-term private historical storage remains owner subscription-specific and unverified; do not assume perpetual unlimited rights.
5. **Owner-gated cutover:** a new explicitly approved PR + exact protected-main CI may reduce H4 source requests / automatic wake-ups after the above proofs. Keep independent native H4 fallback/audit cadence and a fail-closed one-commit rollback path. Never disable D1 native, never mutate/delete previous H4 source archives, and never reinterpret a shadow H4 as native.

## What P0.65 does and does not do

**DOES:** preserve the owner decision as an additive design, create standalone H4 shadow computation and hermetic native comparator, identify future Cloud-only live auditor, and require evidence before any cost/performance optimization.

**DOES NOT:** modify the approved P0.64 hourly H4+D1 writer workflow, M5 writer, provider quota, gates/secrets, existing Drive payloads, P0.46 production derivation API, frozen source, D1 source provenance, numeric BUY/SELL authorizations or broker controls.

**Truthful checkpoint:** code/CI may pass without proving any real M5↔H4 OHLC equality; real authenticated Drive comparison, derived-cache write path, first scheduled P0.64 event and first D1 incremental append are distinct operational proofs. Until the later change merges, the existing automatic H4+D1 writer continues at UTC minute :25, subject to GitHub best-effort cron.
