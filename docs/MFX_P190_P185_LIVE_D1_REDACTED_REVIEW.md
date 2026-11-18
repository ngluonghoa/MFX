# MFX P0.190 — P185 source-version owner review on the actual native P171 D1 writer

**Date:** 2026-11-18 ICT. **Scope:** MFX-only Cloud GitHub production-writer error path, no original Forex source modifications, no D1 source-vintage admission. Incident [#180](https://github.com/ngluonghoa/MFX/issues/180), conditional limited signal-only target [#138](https://github.com/ngluonghoa/MFX/issues/138).

## Observed reason for this change

The real native hourly writer [#44276092914](https://github.com/ngluonghoa/MFX/actions/runs/44276092914) remains RED because its P171 source-native D1 reretrieve conflicts with exactly **one of five** existing immutable overlap SHA indexes (four unchanged, none absent). That same run safely appended one independent H4 closed bar, later archived H4+D1 SHA auditor [#44277644213](https://github.com/ngluonghoa/MFX/actions/runs/44277644213) passed. These are **technical archive** observations; the publisher's original first-known D1 source version and licensed historical custody remain unproved.

P185 already contained a pure, strict **PRIVATE** one-revision candidate builder and public redaction verifier, but they were not invoked on the actual hourly provider-fetch failure. Operators received only P180 redacted counts. This PR wires that existing verified component into the actual scheduled/read-only diagnosis path without creating or accepting a new revision.

## Minimal implementation

- Only for the existing exact `P171_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE` exception, after P180 validated `CHANGED_OVERLAP_SHA`, exactly one changed SHA and zero missing, use the SAME already-fetched native D1 source batch and same full-SHA-audited in-memory `FreshEpochState`.
- Build P185's private SHA-only owner-review candidate with actual **runner observed UTC**, then immediately validate/emit **only** `public_p171_revision_review` (one under-review row, aggregate counts, explicit false publisher/vendor/canonical rights, zero I/O authority). No private date, raw OHLC, stored/refetched SHA, manifest/object ID or API secrets are logged.
- If the private builder or public validator rejects the case, print only the fixed `MFX_P190_P185_REVIEW_UNAVAILABLE_D1_HELD` marker. No exception content is logged. Existing P180 quarantine and P183 H4-only eligibility remain independent of the review receipt; **D1 is never committed**.
- No newly scheduled workflow, source request, additional OAuth/Drive GET/PUT, changes to existing P171 or legacy D1 archive, cache retention, source-root manifest, broker calls, or price/SL/TP release. No private candidate is persisted or declared an authenticated signature.

## Bounded QA

`tests/test_mfx_p183_p171_h4_isolation.py` adds four actual `main()` runner-path regressions: (1) exact P185 public schema/redaction on one changed overlap, original P183 H4-only path still appends and D1 stays RED; (2) missing overlap or two changes never produces P185 review and cannot append H4; (3) P185 private review failure prints only a static marker without leaking exception/quotes and preserves D1 hold; (4) public redaction rejection likewise preserves H4 isolation and D1 hold. Existing P180/P183/P185/P186 and entire original Forex source/golden tests remain in full CI.

**Gate:** final PR exact-head hosted CI on Python 3.11/3.12, original frozen 102 Forex Git blobs, security/source-delta and cross-Python wheels; protected squash-only merge and independent main-push CI before declaring integrated. This document and the test/code Git blobs must be pinned in `docs/MFX_ALLOWED_BASELINE_DELTAS.json`. No new source-owner numerical values have been signed.

**Not solved:** A private SHA review *proposal* is not historical data first-known or vendor correction attestation. [#180](https://github.com/ngluonghoa/MFX/issues/180) must stay open until independent source publisher/owner evidence resolves which version is eligible and how to handle history append-only. [#27](https://github.com/ngluonghoa/MFX/issues/27) source account/tier rights, [#45](https://github.com/ngluonghoa/MFX/issues/45) original B2/S2 numeric 0/36 and untouched historical OOS/net-R in [#138](https://github.com/ngluonghoa/MFX/issues/138) remain blockers. Public remains `NO_SIGNAL / UNVERIFIED`; no broker execution.
