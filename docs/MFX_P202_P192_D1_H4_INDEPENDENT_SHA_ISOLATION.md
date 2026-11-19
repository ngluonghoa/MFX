# MFX P0.202 — Independently validated H4 append while P192 D1 stays in numeric-OHLC quarantine

## Production incident and constraint

On 2026-11-19, real post-P200 native writer runs [#44598491050](https://github.com/ngluonghoa/MFX/actions/runs/44598491050) and [#44616713529](https://github.com/ngluonghoa/MFX/actions/runs/44616713529) each returned `MFX_P200_P192_D1_SHA_DIFF_REDACTED_NO_COMMIT`: `NUMERIC_OHLC_VALUE_CHANGED`, exactly one SHA-sealed 18-Nov Sydney-local P192 D1 overlap numeric value changed, no label missing/metadata/text-format difference. Both runs returned the original `P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE` hard failure. Current canonical owner D1 retains only one 18-Nov frozen candle, with no 19-Nov appended; old 11-Nov/P171 epoch must never be mixed in.

Because the existing native hourly incremental writer prepares H4 first and D1 second under one SHA audit and commit plan, the RED D1 overlap caused it to discard an otherwise independently valid native H4 fetch. A previous **narrow** P183 solution permitted H4 continuity only for separately SHA-verified P171 D1 overlap revisions. This P202 applies the same principle to this different source and actual known P192 issue while deliberately *never accepting D1*.

## Atomic P0.202 owner P192 H4-only isolation

- Add pure `mfx_cache/p202_p192_h4_only_isolation.py`, requiring the exact P200 redacted proof schema and strict counts: one original sealed P192 18-Nov owner epoch, a single changed NUMERIC OHLC overlap value, no missing/metadata/format changes, all source-admission/publisher/market/trade rights false, no orphan, exactly one P192 chunk+manifest pair. Arbitrary new classifications or additional changed bars fail closed.
- In the existing `tools/run_mfx_native_htf_incremental_commit.py`, **only** on the original P192 SHA rejection and successful P200 source redacted diagnosis, keep separately prepared H4 when and only when this exact scope is satisfied. All normal H4 vendor and overlap validation remains. Before H4 write, re-audit *both* original sealed native Drive archives, re-audit complete P192 isolated Drive epoch, and verify the independent closed H4 proposal again. Then run the existing `commit_native_batch` immutable H4 two-object SHA readback writer; permit zero P192 D1 canonical writes. After logging a no-price H4 receipt, deliberately re-raise the original P192 D1 overlap exception and keep scheduled job **RED**. H4 caching is not D1 approval, live BUY/SELL signal authority or broker execution.
- No new scheduler, cron, provider API calls, quote interval or user prompt. User already approved silently caching. The source P192 D1 original 18-Nov immutable archive is unchanged. No direct price logging, source numeric condition permission, or code path to make a revised P192 bar canonical.
- 11 new hermetic tests covering full real writer synthetic ports and provider/Drive error branches, 0 D1 mutations, H4 exactly once, expected RED job, original V1/owner epoch race refusals, missing overlap hold, H4 itself invalid, no H4 due, quota refusal, redaction and forged P200 proofs. Exact blob SHA allowlist only for modified MFX files.

## Verification and true runtime witness

PR exact-head CI 3.11/3.12, frozen original Forex 102 blob SHA/golden/security and wheel parity, squash-only protected-main merge and independent main-push CI. **A green PR CI does NOT prove a production H4 append.** Check a subsequent **actual scheduled** native writer job for `MFX_P202_H4_ONLY_P192_D1_NUMERIC_REVISED_STILL_HELD_RED` and verify real sealed H4 SHA count/tip in the independent native audit. If the native writer does not have a new closed H4 slot at a given run, there must be no H4 write.

## Release hard STOP

P192 D1 remains quarantined at 18-Nov; no 19-Nov owner source promotion and no rewrite of stored 18-Nov. A source-owner canonical revision policy still requires independently verified publisher first-known, rights/retention and explicit approval. B2/S2 original numerical rules remain 0/36 approved, BID/ASK net SL/TP/R, clean chronological OOS and actual market readiness are not cleared. Thus MFX remains `NO_SIGNAL / UNVERIFIED`. Owner 22-Nov target is a strict GO/NO-GO, not a promised numerical strategy release.

**Rollback:** remove only P202 pure isolation helper, the exception-only P192 H4 scope, P202 tests/docs and exact allowlist; original P192 source SHA audit and original P171/P183 incident paths are unchanged.
