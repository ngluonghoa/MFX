# MFX P0.204 — P192 18-Nov native D1 numerical source revision: private owner-review evidence, NO automatic source admission

**As of:** 20 Nov 2026. **Mode:** GitHub + Google Drive Cloud-only. **Existing cutover:** Australia/Sydney local D1 begins at the *original* owner-approved date 2026-11-18. Legacy V1/P171 D1 and old pre-18 Nov prices remain immutable and excluded from selected epoch.

## Confirmed production facts

- Original selected P192 18-Nov native D1 manifest: `64c00f878e2ebe1425d9895069e1405d39402e8dc73bb7eacd2ff226e51f09ad`, one SHA-sealed 18-Nov candle, no 19-Nov selected D1 manifest in authenticated Drive folder at 20 Nov 15:39 UTC.
- Real native writer logs: [#44598491050](https://github.com/ngluonghoa/MFX/actions/runs/44598491050) and [#44616713529](https://github.com/ngluonghoa/MFX/actions/runs/44616713529), followed by [#44626402900](https://github.com/ngluonghoa/MFX/actions/runs/44626402900), all classified `NUMERIC_OHLC_VALUE_CHANGED` for one and only one originally sealed 18-Nov D1 overlap bar. Zero missing labels, zero nonprice metadata-only or numeric textual-format-only mismatches. Each D1 source admission remained blocked by original `P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE`.
- P202 native H4-only path is **proven live**: run #44626402900 committed two validated 19-Nov H4 bars independently, with 2 immutable H4 Drive objects while D1 remains RED. H4 continued into 20-Nov; latest independently observed H4 manifest was for 20-Nov 08:00 UTC created 12:23Z. M5 continued; latest observed complete hourly M5 manifest was 20-Nov 13:00 UTC created 14:59Z. Owner D1 source still one 18-Nov candle.
- P203 exact protected-main `mfx/main-push-full-ci=SUCCESS` for `61eb571d662dcd04827ebbeddd668644345404cb`, Actions run #44628147090. No open PR at that initial checkpoint.

## Why this P204 is needed

P200 proves a **numerical** source revision was returned, but cannot itself present an audited owner revision proposal for the *new* P192 18-Nov owner epoch. P185 already implemented a private candidate for the **different legacy P171 11-Nov** incident; copying its source authority would be wrong. Any 18-Nov revision must be tied to the SHA of the exact *original P192 source* and must remain non-promotable without a separate owner decision.

## Implementation

- Add pure `mfx_cache/p204_p192_d1_revision_review.py`: build a **private, ephemeral SHA-bound proposal** from the independently audited, unchanged one-root P192 chunk plus exactly the SAME already fetched provider-native D1 batch that P192 rejects. Rerun the trusted P200 numeric-versus-metadata classifier, require exactly one changed 18-Nov numeric OHLC overlap, no missing or metadata/format changes, exact original SHA-index/manifest/root, strict UTC runner-observation later than original first seal. Private proposal contains old and new row SHA, not prices; its digest is a content hash **not** a source-owner signature.
- Validate exact private proposal shape and no implicit authority. Explicitly false: source publisher first-known, account rights, historical as-of rewrite, owner canonical revision, D1 write, BUY/SELL publication, trade. Added provider requests = 0, added Drive reads by proposal = 0, Drive writes = 0, broker orders = 0. The already existing P200 SHA forensic GET remains unchanged.
- Emit only `MFX_P204_P192_REDACTED_OWNER_REVIEW_ONLY` and the **public redacted projection** on the existing P200 known-one-row incident path in `tools/run_mfx_native_htf_incremental_commit.py`. Never print the private source label, old/new SHA, raw OHLC, credentials or runner timestamp. If candidate fails, report `MFX_P204_P192_REVIEW_UNAVAILABLE_D1_HELD`, then original P200 diagnostic and original P192 error still persist. Emit P204 before P200 so prior P200/P202 redacted receipt ordering remains unchanged.
- Ten hermetic tests include bad clock, original SHA tamper, missing/unchanged/metadata-only overlap, SHA digest tampering, forged approvals even with recomputed digest, public data minimization and integration with the existing actual writer code path. No new workflow, cron, quote vendor request, Google Drive OAuth permission or cache mutation.

## Decision that remains deliberately OPEN

**Option A — current authoritative archive (default):** Preserve the initial 18-Nov SHA as canonical and keep D1 out of use when the provider revises it. No trading. This conserves chronological provenance but 6TF D1 stays stale.

**Option B — separately approved parallel **research-only** revised variant:** Preserve the original SHA immutably, capture a new disjoint owner-review snapshot of the revised 18-Nov row and later closed D1 rows, including vendor first-known/source-rights evidence, never label it executable or silently overwrite. A later PR would need **explicit source-owner approval** of the version transition and separate reproducible historical-as-of rules. Merely building this P204 private in-memory review does NOT approve or persist such a variant.

**Option C — decline the source as unsuitable:** Keep H4/M5 healthy, continue research with D1 unavailable, investigate alternate legally usable versioned provider/bid-ask source under independent budget/rights approval. No synthetic mixing of D1 candles.

The developer may continue building independent QA/source custody proof and running source-only reviews without owner prompts. **No owner permission to rewrite the original 18-Nov candle or to approve the revised source has been received.** The previous permission to cache raw data is not authority to promote a revised price source into canonical historical signals.

## Release hard STOP / rollback

MFX signal-first B2/S2 original numerical parameter approvals remain **0/36**. Missing accepted account quote rights and retention, executable BID/ASK economics (spread/slippage/commission, net SL/TP/R), publisher first-known and independent chronological OOS. Thus `NO_SIGNAL / UNVERIFIED`; no source-quality-only CI is a trade/signal release gate. Target **22-Nov-2026** remains strict conditional GO/NO-GO.

Accept P204 code only after exact PR-head Python3.11 and 3.12 full QA, frozen original Forex 102-blob SHA/golden/security, cross-Python wheel parity, protected squash merge, independently observed main CI, then first real scheduled **P204** review-only marker in the originally RED D1 job. Roll back only P204 pure module, exception-only redacted proof path, tests/doc and exact source SHA allowlist. Original P192 source and P202 H4-only isolation must remain untouched.
