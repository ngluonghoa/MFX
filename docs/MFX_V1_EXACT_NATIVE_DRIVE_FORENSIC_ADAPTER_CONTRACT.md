# MFX 1.0 — exact private Drive native forensics integration acceptance

Checkpoint: 2026-11-13 ICT; cloud-only source SHA custody validation.

Prior milestones:
- First **real** user-approved GitHub OAuth GET-only authenticated M5/H4/D1 read
  [#43269657301](https://github.com/ngluonghoa/MFX/actions/runs/43269657301)
  verified archived SHA M5 47/47, native H4 9/9, D1 2/2, zero market
  price API calls or Drive writes. Six-frame decision-time context remained
  stale for M5/M15.
- PR #144 made source-tip clock delay exact and logs native P059 label
  evidence, still fail-closed. Subsequent existing live native job
  [#43357324770](https://github.com/ngluonghoa/MFX/actions/runs/43357324770)
  found D1 2026-11-11 ONE changed overlap SHA, 15 unchanged, zero missing;
  full stored native archive read-only SHA audit #43359463766 passed.
- PR #145 added a source-independent **bounded 16-bar witness** from already
  SHA-audited old raw archive and a count-only pure numeric-vs-format/
  provenance classifier. Original source quarantine always re-raises;
  it does not approve source-data restatement. At this checkpoint there
  is **no new post-PR #145 natural scheduled native run** to identify the
  actual 2026-11-11 D1 difference class.

## Why this test suite exists

The initial PR #145 test run failed on legacy writer simulator doubles,
which are not the actual `PrivateNativeDriveStore` production adapter.
That compatibility was repaired before protected-main merge, but the
existing source-side witness tests used an in-memory `ReadOnlyStore`
rather than actual Google Drive v3 `files` list/media GET contracts.
Therefore **no unsupported claim of new live private Drive forensic
readback** is made for PR #145.

PR #146 adds strictly hermetic production-adapter integration tests
using the existing P0.55 vetted Google Drive mock session. They exercise
**exact `PrivateNativeDriveStore` identity**, its real listing query
folder/interval prefixes, the `_drive_get` media helper behavior,
`audit_native_archive` full SHA and parent-chain, and the exact same
read-through witness now installed for that production store type.

The full SHA audit is run both with and without the wrapper against
the same synthetic immutable H4/D1 object sets. **Media read count and
Drive-list GET count must be identical**, with equal archive
`NativeArchiveState` receipt and zero `_drive_create` calls.
Multi-batch H4 archive tests prove last-16 witness crosses an immutable
manifest parent boundary without skipping early SHA verification.
H4 and D1 (and unrelated same-folder M5 names) remain separate.

An end-to-end mocked `tools.run_mfx_native_htf_incremental_commit.main`
test forces **only the already authorized D1 due request** and one
simulated response with SHA discrepancy on the synthetic
`2026-11-11` label. Exact real Drive store, GET-counted audit and
verified-old-row numeric/format classifier execute; original
`P059_SOURCE_NATIVE_REVISION_QUARANTINE` is re-raised; a count-only log
asserts numeric or lexical category without OHLC/credentials. There
must be **one and only one** mocked existing vendor price request,
one existing usage call, no new reads and no Drive write. No API
credentials, real market quotes, GitHub owner workflow dispatch, or
real source reconciliation is performed by these tests.

Do NOT treat a test-mocked result as proof of actual historical
Twelve Data corrections, first-known timestamp, account licence,
source-owner numeric strategy approval or freshness.

## Governance

- No change to original Forex 1.0 102 frozen Git blobs or 11 source-locked
  Google Docs, original MFX 1:1 parity or established production workflows.
- No change in provider cadence, GitHub Actions variables, cache writers,
  append policy, original P059 fail-closed error or source price history.
- No BUY/SELL; `NO_SIGNAL` and `UNVERIFIED` until independently accepted
  source/data rights, deterministic numeric B2/S2 source rules (0/36),
  all other entry models, BID/ASK cost, SL/TP, net R:R, and causal OOS.
- Next source task remains to **observe the next naturally scheduled
  native GitHub job** on exact accepted main for forensic count-only
  marker. If numeric OHLC changed, a separately **owner-reviewed,
  source-licensed, versioned append-only** exception policy is needed.
  Never silently rewrite stored native chunk or suppress SHA quarantine.
- All development and CI remain GitHub+Drive Cloud-only; no local
  Mac/MOCHI and no recurring ChatGPT engineering automation.
