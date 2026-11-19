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
