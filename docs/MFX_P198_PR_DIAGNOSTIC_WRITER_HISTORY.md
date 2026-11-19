# MFX P0.198 — Verify P197 writer history through an existing PR-only diagnostic

## Exact scope

P197 on protected main 9350ce6ddf275c2d35a67769124dd719de505e06 added a separate GitHub-Actions-only read of the scheduled M5 writer history to the existing hourly native SHA workflow. However, the authenticated GH connector currently permits read of a run ID but does not expose a workflow run-history listing action; the P197 native workflow run ID itself is also not surfaced from its exact push commit through that connector. Do not falsely report that a writer schedule run was seen merely because P197 PR/main CI are green.

P198 reuses the **existing** PR-only `p037-read-main-push` GitHub diagnostic job in `.github/workflows/ci.yml`, already restricted to `ngluonghoa/MFX` `pull_request`, `actions: read`, and official GitHub API. It adds one best-effort GitHub REST read of the existing M5 writer schedule history through the source-validated P197 parser (fixed scoped endpoint, no arbitrary URL). No new cron, workflow_dispatch, OAuth scope, vendor requests, Drive reads/writes, raw OHLC, change to original M5 writer, H4/D1 auditor, or new permissions. This gives reviewable *real* writer run IDs within the exact-head PR CI diagnostics before squash merge; the older P037 main CI check remains independently intact.

The standalone wrapper is callable only from trusted PR metadata. The script prints `MFX_P198_PR_ONLY_REAL_GITHUB_M5_WRITER_RUN_HISTORY_PASS` **only** after actual GitHub API response and strict parser acceptance, not in a synthetic test. A GitHub API outage or missing permissions must not mark market data as current, and the failure is reported solely as nonblocking diagnostic evidence. Five hermetic negative/scope/secret tests plus the existing P197 tests enforce boundaries.

## Gates

Verify PR exact head Python 3.11/3.12 full tests, frozen Forex 1.0 102 source SHA, security and wheel parity, then squash merge protected main and verify postmain CI. Inspect actual P198 PR diagnostic job log, extract only real GitHub run IDs; use those IDs to fetch specific M5 writer job statuses/logs and compare with independently observed immutable Drive created timestamps. Do not assume scheduled clock `:10` equals GitHub event creation, and do not infer missed runs from an incomplete first page or provider outcomes from a GitHub job SUCCESS alone.

MFX signal-first release remains `NO_SIGNAL / UNVERIFIED`: B2/S2 original source numeric approvals **0/36**, provider tier/data rights, real BID/ASK and net SL/TP R, publisher first-known and untouched historical chronological OOS not independently approved; only one owner-cutoff D1 native Sydney candle from 18 Nov is physically sealed. Target 22-Nov requires strict owner GO/NO-GO, never automatic approval. No account-specific vendor quote requests or trades in this PR.
