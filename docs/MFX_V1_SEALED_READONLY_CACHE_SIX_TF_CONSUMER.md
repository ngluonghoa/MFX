# MFX 1.0 — sealed READ-ONLY archive-to-six-TF research consumer

Date: 2026-11-12 ICT. Owner-approved signal-first MFX 1.0 Issue #138.
Scope: additive MFX-only research source consumer. NO production activation, no new
Twelve Data price request, no Google Drive cache mutation, no broker/orders,
no source Forex Trading 1:1 bytes or SOURCE_LOCKED Google Docs changes.

## Implemented

The new mfx_research/six_tf_sealed_archive_consumer.py accepts three
caller-injected *read/list-only* stores for the existing EUR/USD composite MID
M5 hourly V2 archive, H4 provider-native archive and Sydney-local native D1.
It executes the existing P0.66 complete bounded M5 raw+derived SHA/parent
chain verifier, independently compares its immutable source-reviewed
GitHub root and 31-pair checkpoint SHA pins from P0.85 by default, and
fails closed on missing, forked, out-of-bound, or changed listings. The current
strict full-content bounded M5 proof supports up to 256 manifest/chunk pairs;
it does not relabel an older unscanned history as a full proof after this limit.
The synthetic fixture-only pin override is explicitly marked as NOT
GitHub-reviewed and cannot authorize an operational source.

The existing P0.55 native H4/D1 auditor checks all available SHA and
manifest ancestry. The new consumer separately re-reads the source chunk
bytes and manifest tips, rejects orphans, inconsistent bar counts, duplicate
native labels, changed listings, wrong source/TF/axis and malformed UTC or
Sydney-local dates, then passes at most the final 120 native bars into the
already implemented six-frame context. M5 output is the verified final
twelve closed bars; the original six-TF validator performs strict newest
M5/M15/M30/H1 3/6/12 CLOSED and native UTC H4 and Sydney D1 checks.

Return includes three SHA tip fingerprints, verified bounded pair counts,
the typed six-TF technical context and explicit zero external actions.
A successful SHA hash checks content consistency for the supplied store,
NOT authenticated first-known time, vendor feed/legal rights, account tier,
independent anti-rollback witness, source numeric strategy authorization
(36/36 B2/S2 owner decisions remain pending), historical as-of fidelity,
BID/ASK cost/SL/TP/net R:R, or permission to issue verified BUY/SELL.
All outcomes remain NO_SIGNAL/research-only; the included typed six-TF
receipt itself retains all upstream UNVERIFIED flags.

## Test and release boundary

Thirty hermetic cases use actual MFX P0.46 M5 sealed-batch builder,
P0.54 native sealed builder, and P0.66/P0.55 SHA verifier with
read/list-only fake stores. They exercise positive six-frame composition,
strict root/checkpoint guards, tampered old/new raw chunks, corrupted
native H4/D1, rollback, orphan, stale M5/H4/Sydney D1, incorrect TF,
as-of UTC, future H4 and no-write/no-broker/research-only invariants.
Passing these tests is NOT live Google Drive OAuth/authenticated readback.
The module has no runtime CLI, GitHub workflow, schedule, new secrets,
external provider call or Google Drive writer.

If any tested cache is incomplete/stale, six-frame output is NO_SIGNAL with
explicit missing frames. Cryptographic consistency does not demonstrate
publisher authenticity; independently verified real Drive OAuth principal,
fresh archive head, rights, first-known chain and cost model require later
separate evidence. An authenticated Drive live reader remains a release blocker.

## Next

1. Independent owner-gated *manual read-only* GitHub Actions integration using
   the existing approved OAuth Drive identity and current M5/H4/D1 folders,
   without enabling any new schedule or vendor price polling; check latest
   live SHA and report only masked digests/counts and NO_SIGNAL.
2. Source-owner signed exact original B2/S2 numeric parameters; 0/36 approved
   at this checkpoint, and the other 14 entry designs lack source-approved
   numeric predicates. Never copy synthetic demo numbers into live rules.
3. After account-specific licensed source and BID/ASK/SL/TP/net-R evidence,
   add deterministic historical as-of replay and independently measured OOS
   evidence; owner/QA GO before any signal-only release.
4. Original Forex102, 11 SOURCE_LOCKED Docs, 22 MFX design labels and existing
   H4/D1/M5 GitHub production cron remain intact. No Mac/MOCHI/local,
   ChatGPT recurring automation or broker execution.
