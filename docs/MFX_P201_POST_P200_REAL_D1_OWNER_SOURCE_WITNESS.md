# MFX P0.201 — Live post-P200 D1 quarantine witness and strict decision gate

## Why this checkpoint exists

MFX source D1 owner selected a completely disjoint fresh Sydney-local start at 18-Nov-2026. The only authenticated sealed source manifest on Google Drive is still `MFX_P192_EURUSD_D1_20261118_FRESH_EPOCH_V1_manifest_20261118_64c00f878e2ebe1425d9895069e1405d39402e8dc73bb7eacd2ff226e51f09ad.json` (observed again 20-Nov). Native D1 writer actual jobs at 19-Nov 13:45Z, 15:20Z, 16:26Z each failed with exact `P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE`. This does **not** prove whether stored-vs-refetched numeric OHLC, metadata, textual numerical representation, or a missing overlap label caused mismatch. New P0.200 code has now safely shipped at protected `main` SHA `c52aeeb04e324e1a13e4849c65076fa0943b3353`; independent main CI #44585899458 PASS, but P200's actual source-diff marker has not yet been observed on a real scheduled run.

## Real source-of-truth witness

A new atomic source-safe pull request invokes existing P0.199 **PR-only GitHub Actions read-only diagnostic**, which lists live MFX native H4/D1 writer run IDs from the official GitHub Actions REST endpoint. Read the latest *actual* scheduled writer job after P200 merged, not a pre-P200 job nor synthetic fixture. Inspect its own job logs for `MFX_P200_P192_D1_SHA_DIFF_REDACTED_NO_COMMIT`; if present, only the **redacted** payload is admissible to this document. If the log instead reports `MFX_P200_P192_D1_FORENSICS_UNAVAILABLE_STILL_HELD`, do not invent an outcome. If it reports no new closed slot or the job is skipped, that is also not proof of a resolved P192 source.

The P200 helper receives already-fetched vendor-native batch and one fully SHA-checked original P192 chunk read-only, and re-raises the original P192 exception regardless of classified difference. Expected diagnostic only: numeric OHLC revision / metadata-only / number text-only / missing overlap / combined. No old D1 splice, no reset of 18-Nov, no silent price overwrite, no source-publisher first-known certificate.

## Release decision

Pending actual post-P200 scheduled writer evidence this checkpoint remains:
- **Code CI:** P200 PASS, not evidence that source restored.
- **D1:** one sealed Sydney local session (18-Nov); 19-Nov and later still not authenticated as present.
- **Six TF signal:** NO_SIGNAL / UNVERIFIED, no market-ready B2/S2 BUY/SELL. Source numerical strategy owner signoff remains 0/36, source licence, BID/ASK/spread economics, independent chronological OOS and net SL/TP/R unverified.
- **22-Nov target:** strict conditional GO/NO-GO; never claim executable signals without approved source/risk gates.
- **Allowed:** GH-only read diagnostics, immutable Drive GET-only SHA audit, bounded original vendor writer under existing approvals. No new schedule, vendor budget or trading scope in this PR.
- **Not allowed:** archive/manifest mutation, bypass P192 quarantine, synthetic vendor first-known, or converting a diagnosis into owner-approved revision.

## Next

If actual category is a real changed OHLC value, keep original 18-Nov SHA frozen and produce owner-review decision with independent publisher/rights evidence before discussing a new disjoint forward-only source. If metadata or textual formatting differs only, demonstrate equality of all numeric OHLC Decimal values and independent source/metadata provenance before considering any *separately approved* normalization design. In either case the current writer remains fail closed; no incident fix can be inferred from GitHub CI SUCCESS.

This PR is documentation-only to capture the actual source witness from its existing read-only PR diagnostics, plus exact SHA baseline allowlist. It performs no market or Drive I/O from code.


## REAL post-P200 runtime result — VERIFIED 2026-11-19 UTC, not a synthetic simulation

The existing P199 reader ran for actual PR #201 GitHub Actions #44624349621, PR-diagnostic job #135914089728; marker `MFX_P199_PR_ONLY_REAL_GITHUB_NATIVE_H4_D1_WRITER_HISTORY_PASS` was authenticated at 2026-11-19T22:00:27Z. It listed 26 scheduled native writer runs in 36 hours, 20 SUCCESS and 6 FAILURE (no inference about missing unobserved cron events).

Two **independent** GitHub scheduled post-P200 writer logs were directly fetched and inspected:
- [run 44598491050, native job 135823161112](https://github.com/ngluonghoa/MFX/actions/runs/44598491050/job/135823161112), scheduled 2026-11-19T19:27:24Z; real marker `MFX_P200_P192_D1_SHA_DIFF_REDACTED_NO_COMMIT`, conflict `NUMERIC_OHLC_VALUE_CHANGED`, stored overlap=1, changed SHA overlap=1, `numeric_ohlc_value_changed_count=1`, `metadata_changed_count=0`, `overlap_missing_count=0`, `price_text_format_changed_count=0`, refetched CLOSED native bars count=24; original `ValueError: P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE` re-raised; job RED.
- [run 44616713529, native job 135887265653](https://github.com/ngluonghoa/MFX/actions/runs/44616713529/job/135887265653), scheduled 2026-11-19T21:14:12Z; same **real** `NUMERIC_OHLC_VALUE_CHANGED` classification and 1/1 overlap change; metadata/representation/missing counts remain ZERO, refetched CLOSED native bars count=23; same original exception re-raised, job RED.

The repeated real readbacks prove that a new provider response has a **different numeric OHLC value** for the original 18-Nov Sydney-local D1 candle than the sealed 18-Nov version. They do **not** prove why the provider changed that value, which version is authoritative, the vendor's publisher-first-known timestamp, licensed use/replay rights, or owner-approved canonical revision. The P200 diagnostic made exactly ONE additional immutable original P192 sealed Drive GET per failed run, ZERO additional provider quote requests, ZERO Drive writes, ZERO broker orders. Private prices/sha pairs not copied to this document. No pre-18Nov D1 price has been admitted. Owner 18Nov original unchanged, while 19Nov D1 remains absent from the canonical selected epoch.

**P201 decision: hard D1 quarantine remains in effect.** Do not silently rewrite original 18Nov, fork a promoted executable source, relax P192 compare or let D1 SHA conflicts veto unrelated independently safe H4 *without an separately tested isolation design*. Any controlled future H4 isolation must preserve a RED D1 job, prove full SHA on H4/V1/P192 and never write canonical D1. An owner review of canonical D1 revision requires independent source rights and as-of publisher evidence; 22-Nov B2/S2 signals still hard NO-GO absent original 0/36 approvals and executable BID/ASK economics.
