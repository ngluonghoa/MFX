# MFX P0.200 — No-price P192 D1 overlap revision forensics; quarantine stays fail-closed

## Confirmed real incident

The OWNER-selected MFX Sydney-local EUR/USD native D1 epoch begins 2026-11-18. It has exactly ONE SHA-sealed 18-Nov candle under original P192 manifest root 64c00f878e2ebe1425d9895069e1405d39402e8dc73bb7eacd2ff226e51f09ad. The protected native H4/D1 real OAuth SHA audit, run #44581413611, job #135762746928, confirms the expected closed session 2026-11-19 is one calendar day ahead of the last archived session, though SHA custody still PASS. Actual hourly native D1 writer GitHub jobs #135603489803, #135664052059, #135708167373 FAIL identically on `ValueError: P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE`. Source checks properly rejected the newer provider snapshot because its sealed 18-Nov OHLC+metadata row SHA did not match or the overlap was missing; no new canonical D1 chunk/manifest was written. We cannot yet claim it was a true vendor *price* correction as opposed to metadata or numeric string representation.

## Atomic P0.200 change

- A pure, strictly one-root single-chunk P192 forensic classifier `mfx_cache/p200_p192_d1_sha_diff_forensics.py` checks the already SHA-bound last chunk and the SAME already-fetched source-native D1 batch that triggered the original P192 overlap error. It rechecks exact chunk SHA, owner origin, saved index and original source schema. It categorizes missing overlap, true decimal-valued OHLC change, non-price metadata change, numeric representation-only change or combinations.
- Add an exception-only branch in the existing `tools/run_mfx_native_htf_incremental_commit.py`: after **the original P192 hard-stop** raises exact known code, re-GET one already sealed P192 chunk from the existing authorized Google Drive account (one extra GET, zero extra quote provider calls), compare purely in memory, print only a price/label/SHA-redacted category and counts, then **re-raise the original error** without altering any Drive source or H4/D1 commit semantics. Missing/changed data cannot become approved evidence merely by classification.
- Add ten synthetic adverse tests, including real writer integration with already seeded P192 single-root 18-Nov, changed OHLC, changed metadata only, lexical numeric format difference, missing 18-Nov source, SHA tamper refusal, wrong source parent, no raw prices/labels/hashes in print, unchanged source rejection, zero extra writes/vendor calls. SHA exception allowlist reflects only MFX-only files.

## Boundaries and safety

No auto-reset of D1 source date, no pre-18Nov D1 splice, no revision acceptance, no source-publisher first-known certification, no source licence, no new hourly workflow, cron, secrets, API budget, real BID/ASK or broker integration. All workflows continue to mark the original P192 failed run RED; 18-Nov candle remains immutable. Only if independent source-owner approval and publisher/rights evidence later establish a safe revision handling policy would canonical changes be considered. A classification from a single vendor observation is **not** that approval.

Market release remains `NO_SIGNAL / UNVERIFIED` with B2/S2 0/36 original source numerical approvals, no licensed executable MID-to-bid/ask economics, no independent chronological OOS/net SLTP risk. Nov22 is conditional strict GO/NO-GO.

## Required QA and rollback

Exact-head PR Python3.11/3.12 full suite, original Forex source 102-blob SHA/golden/security, wheel parity, squash-only protected main, independent main-push CI. Real category is only proved when the existing **scheduled** native writer later runs through this code and prints the P200 REDACTED marker; synthetic test PASS must never be reported as a real vendor diagnostic. Rollback only new pure forensic helper, the exception-only additional no-price observation, synthetic tests/docs and their SHA allowlist entries. Never rewrite existing immutable Google Drive D1 manifest or old P171/Forex frozen source.
