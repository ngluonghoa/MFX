# MFX P0.178 — Exact 36 original-source B2/S2 owner-decision queue

Date 2026-11-16 ICT. Coordinated under [signal-first Issue #138](https://github.com/ngluonghoa/MFX/issues/138), #45 and #62. **Source/owner evidence intake—not a new trading strategy.**

## Why

P0.176 restored real-source D1 continuity by combining independently SHA-audited pre-11 Nov V1 native D1 with the fresh 11 Nov+ D1 native provider epoch, without ever consuming the original disputed 11 Nov candle in active technical calculations. P0.177 then computed **private** B2/S2 source-readiness on sealed MID six-frame bars. But the 18 original qualitative obligations for each side (36 distinct owner numeric decisions total) were independently listed in P0.157; there was no typed cross-check proving that every real-source B2/S2 readiness condition is associated with the correct **immutable original Forex requirement, phase and SOURCE_LOCKED_03 document paragraph** before preparing an owner review.

## What changed

- New `mfx_research/p178_b2s2_36_owner_review_queue.py`: compile a deterministic 36-row typed **owner-decision review packet** by reconciling the P0.157 source-locked exact B2/S2 review rows with P0.177 private SHA-source readiness. Each row has rule B2/S2, one of 18 pinned original requirement IDs, phase (R0/R_C/R_E/R_F/INVALIDATION/QA), original paragraph index, existing source computation category, strictly research-only private prerequisite classification, **original numeric owner decision = PENDING**, 0 authenticated approvals.
- The precise B2/S2 difference is retained privately: H4/D1 right-confirmed highs/lows; H1 draft TR3 availability; M15 prior-right-closed level before the latest candle and exact closed crossover; original owner numeric parameters vs independent licensed publisher first-known, BID/ASK risk and true OOS. Experimental technical precursor availability is **not** a source-owner formula, original Forex numerical 1:1, candle publication timing proof, quote-side net-R or a BUY/SELL signal.
- A malicious/incorrect input (wrong original doc/paragraph, duplicate/swapped requirement, changed source SHA, as-of mismatch, forged owner approval, drifted decision count, B2/S2 gate swap) must fail closed. Exactly **36 pending source numeric decisions** and 18 immutable source IDs per side are mandatory.
- Existing optional GitHub Actions **manual/owner-gated** GET-only six-TF source reader includes a new `b2_s2_original_source_owner_review` **public-safe** summary: 18 requirements per B2/S2, six original phase counts, source-locked Doc ID, 36 decisions pending, **zero** numeric approvals, owner/license/quote/OOS flags false and `NO_SIGNAL/UNVERIFIED`. Detailed private source-derived crossing, pivot counts, prices, technical gap codes and raw source fingerprints never appear in the added public projection.
- No new cron, owner variable, OAuth action, Drive GET, provider request, Drive write, quote, broker or source-policy signing endpoint. No edits to the original 102 frozen Forex source Git blobs or 11 SOURCE_LOCKED Docs. Original source legal/account-specific permissions and user-approved ongoing storage are separate matters.

## What counts as a real next decision

For every original row, actual source-owner signoff requires an independently attributable and time/version-specific exact numeric definition with units, source paragraph/supersession and positive/negative/boundary fixtures; it cannot be manufactured from SIM examples such as 1L/1R or ATR 0.5. For release, a separately licensed appropriate native quote-side/feed first-known and after-cost SL/TP net-R and true chronological untouched OOS evidence must be established. GitHub CI green cannot produce that authority. Issue #45 already tracks these external inputs, so do not open a duplicate approval issue.

## QA and rollback

Offline hermetic cases cover 36/36 pinning, correct B2/S2 phases and original source paragraphs, per-side technical vs external evidence, false-approval injection, wrong/duplicate source rows, SHA/as-of drift, safe summary counts, redacted no-signal and no external effects. Merge only after exact PR Python3.11+3.12, source-frozen parity, wheel parity, security and independent protected-main CI; keep the separate manually operator-gated real OAuth six-TF audit unrun unless explicitly approved and executable using supported connector actions. Rollback by reverting only this MFX-owned additive code plus the small GET-only readout adapter; no native source data mutation.
