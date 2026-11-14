# MFX P0.164 — independent issue #147 source-HOLD governance audit

Date: 2026-11-14 ICT. Scope: narrowly prevent a **misleading GitHub governance green** when the real D1 source remains explicitly quarantined. No price or signal changes.

## Verified governance incident

GitHub Issue [#147](https://github.com/ngluonghoa/MFX/issues/147) closed at 2026-11-14T12:19:03Z immediately after PR [#164](https://github.com/ngluonghoa/MFX/pull/164) merge. PR #164 fixed only a read-only `NO_SIGNAL` report and expressly **did not** adjudicate the EUR/USD native Sydney D1 2026-11-11 source numeric OHLC mismatch (1/16 changed source bars). Thus GitHub issue state was factually inconsistent with the still-active code HOLD, the documented release gates and publisher/rights uncertainty. A similar premature close/reopen occurred on 2026-11-13. Issue #147 was explicitly reopened on 2026-11-14T12:49:56Z and an audit-trail comment was added; incident is not resolved.

## What the new workflow does

`.github/workflows/mfx-issue147-source-hold-audit.yml` listens to GitHub `issues` activity `closed` or `reopened`, on the existing `main` code, and processes ONLY issue #147 of exact repo `ngluonghoa/MFX`. It checks GitHub-supplied event JSON locally, plus the existing P0.162 source constant `D1_KNOWN_SOURCE_REVISION_HOLD=True` and exact incident fingerprint. A `closed` issue must emit a **nonzero GitHub Actions failure** with redacted stop marker; `reopened` must pass. This is monitoring/auditing, **not an auto-reopen or an owner approval**; no mutation of GitHub issues occurs from the workflow.

The workflow has least-privilege `contents: read` and `issues: read` (no write scopes), pinned checkout/setup actions, a 2-minute job cap, and no schedule, additional server, secrets, provider/Drive calls, cache writes, MT4/MT5, broker or trading. A runtime GitHub Issue action cannot be substituted as publisher revision first-known proof. Guard can be superseded only through a separately documented owner-reviewed source remediation checkpoint, not through an issue edit, synthetic test or simple code flag.

## Deterministic QA

Sixteen hermetic tests cover correct issue state transitions, premature close, wrong repository/issue/action/state/number types, inconsistent source-HOLD state/incident, exact GITHUB_EVENT_PATH CLI behavior, redacted error, and zero external I/O. Full PR CI and independently observed protected-main CI must pass Python 3.11/3.12, SHA source-golden, static/security and wheel-parity before accepting the code. Verify trigger in a later natural issue event; offline tests do not pretend a live issue-event run has occurred.

## Unchanged STOP conditions and rollback

Original sealed D1 values never overwritten; #147 source policy HOLD persists. #27 exact Twelve Data account/tier rights and Drive retention/replay/display not proven, real publisher first-known/revision cause not proven, MFX Option B numeric rule owner approval absent, BID/ASK economics and untouched real OOS unapproved. MFX remains `NO_SIGNAL/UNVERIFIED`. Roll back only the four added MFX-specific files and SHA allowlist entries; **never** roll back immutable source data or disable D1 quarantine as a side effect.
