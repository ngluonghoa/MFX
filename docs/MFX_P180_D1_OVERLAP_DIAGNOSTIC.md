# MFX P0.180 — Native P171 fresh D1 overlap SHA differential, fail closed

Date 2026-11-17 ICT. Incident: [#180](https://github.com/ngluonghoa/MFX/issues/180).
Base protected main `42baa71b802dd6a3f58e84c4ca2db0eaaacde494`.
Original 102 frozen Forex source blobs and 11 SOURCE_LOCKED Docs must not change.

## Observed, not inferred

Two REAL scheduled native H4/D1 writer failures,
[runs 43901745308](https://github.com/ngluonghoa/MFX/actions/runs/43901745308) and
[43920323384](https://github.com/ngluonghoa/MFX/actions/runs/43920323384),
failed in `plan_fresh_epoch_seal` at
`P171_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE`.
The existing implementation compares the exact recent SHA-indexed P171 fresh D1
labels to an already-fetched later provider response and refuses to commit
if any label is missing **OR** a prior candle SHA changed. Neither the
exact disagreeing label nor publisher cause is supported by the old traceback.

A separate real SHA read-only auditor [43912980063](https://github.com/ngluonghoa/MFX/actions/runs/43912980063)
accepted existing immutable H4/D1 archives; this does **not** approve the
newly offered provider overlap. The owner's one-off manual six-TF
[43926666660](https://github.com/ngluonghoa/MFX/actions/runs/43926666660)
successfully audited archived source without mutation but flagged M5
hourly freshness, so six-frame technical readiness remains incomplete.

## What P0.180 changes

- Add a pure closed native D1 SHA diagnostic,
  `mfx_cache/p180_d1_overlap_diagnosis.py`, with strict typed source
  checks and bounded manifest index.
- Run it **only** when the original `plan_fresh_epoch_seal` already throws
  the exact P171 overlap quarantine. Count missing previous labels separately
  from changed SHA labels. Do not log per-label dates, prices, actual private
  bar hashes, Drive identifiers, API keys, or any private observations.
- On a scheduled recurrence emit
  `MFX_P180_D1_OVERLAP_SHA_DIAGNOSED_FAIL_CLOSED` and a redacted
  `MISSING_OVERLAP_LABELS`, `CHANGED_OVERLAP_SHA`, or
  `MISSING_AND_CHANGED` receipt. If diagnosis itself fails, emit
  `MFX_P180_DIAGNOSTIC_UNAVAILABLE_FAIL_CLOSED`.
- **Always re-raise the original P171 failure**; job stays RED, no H4 or D1
  append on the affected all-or-nothing writer execution. Never silently
  move the P171 2026-11-11 owner baseline or bypass SHA quarantine.
- Reuse the same previously fetched `NativeFXBatch` and fully verified
  in-memory `FreshEpochState`. Provider calls, Drive GETs and writes,
  workflow/schedule/secrets/permissions, broker orders: all unchanged.

## QA and next gate

Hermetic tests: identical SHA cannot be classified as a conflict; genuine
SHA drift distinct from missing history; mixed case; forged index/state/source
rejected; confidentiality/no extra I/O; writer fail-closed integration guard.
Protected PR Python 3.11 and 3.12 full CI, golden 102 frozen SHA and main-push
check required before merging. Do **not** describe a test-only diagnostic as a
recovered production writer. After a natural hourly failure on protected main,
use only the redacted classification to decide a separately reviewed append-only
source recovery plan; do not order new vendor calls just to diagnose.

Owner original numeric B2/S2 0/36, source vendor licence tier #27,
publisher-first-known, BID/ASK net economics and untouched OOS remain unverified;
public research API remains `NO_SIGNAL / UNVERIFIED`, no trade execution.
