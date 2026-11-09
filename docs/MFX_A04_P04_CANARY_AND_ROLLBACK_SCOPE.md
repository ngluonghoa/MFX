# MFX A04/P0.4 — synthetic canary and isolated real-Git revert rehearsal

Protected checkpoint: MFX main `42485d9589adcc7cd6c93368cb25290699c56c14`; frozen Forex source
`7e1c1c012b1b189be5ad7b9d07756eac012a8309` and initial
102-blob imported baseline `6ee5e7c07baf4ea8f06a28889175808ea53c2316`.
100% Cloud-only: GitHub Actions for ephemeral compute, Google Drive for
canonical governance; no Mac/MOCHI/local, market source, trading or release.

## Scope

P0.4 adds a **synthetic declaration-only canary** with stages
BASELINE -> DECLARATION_SHADOW -> SYNTHETIC_REPLAY_SMALL ->
SYNTHETIC_REPLAY_EXTENDED. The names are QA stages, NOT percentages
or actual deployment/traffic. Forward skipping, replay/reverse,
missing 50-case frozen golden, missing 14-case P0.3 matrix,
failed source SHA parity/security gate, failed rollback drill,
unapproved credentials or any actual live data, automatic provider
failover or broker order request block the review. A PASS means only
STRUCTURAL REVIEW ELIGIBILITY and NEVER activation.

Unlike the previous P0.3 immutable JSON snapshot equality check,
the CI-only drill executes **real git init, commit, commit, git revert**
inside a new, isolated no-remotes temporary repository on the
GitHub-hosted runner. It verifies initial and restored Git *tree SHA*,
restored source bytes, clean temporary history (three commits),
no remote, and unchanged MFX working checkout HEAD and status.
No production Git branch is reverted, reset, force pushed, deployed
or tagged. This is not disaster-recovery evidence for GitHub cloud
availability or a production release.

The first PR CI run is an explicitly tagged bootstrap measurement;
after verifying matching receipts on both Python versions, its SHA,
candidate matrix and stable Git tree hashes will be pinned in
`docs/MFX_A04_P04_CANARY_GIT_DRILL_BASELINE.json`. The mandatory
CI step then switches to verification mode and fails closed on
budget, original source hashes, protected checkout, Git tree and
runtime-authority drift. Subsequent exact-head and independent
postmain 3/3 CI must pass before checkpoint signoff.

## Controlled future GitHub rollback procedure — NOT executed on main

1. Freeze canary/release attempts, record offending protected-main
   squash commit, audit baseline SHA, original Forex manifest and
   currently running (if any) deployment/release identifiers.
2. Do not reset/force push `main` or overwrite a signed release.
   On a fresh branch from CURRENT protected main, perform an
   isolated revert of the offending squash commit (or a reviewed
   forward-fix) only after checking dependent commits.
3. Submit one rollback PR with exact commit/diff, frozen 50-case
   golden, A01/A02/A03/A04 safeguards and no new source exceptions
   except explicit reviewed delta. Require all three CI jobs PASS.
4. Merge via reviewed exact-head Squash Merge; independently verify
   three postmain CI jobs, restore applicable runtime deployment
   ONLY via separately authorized release/operations procedure,
   and update Google Drive Handoff, QA, Traceability and incident log.
5. A previous Git commit is not automatically a signed LKG release.
   Without deployment/artifact provenance or broker/data authority,
   NEVER claim that a Git revert restored production or trades.

## Nonclaims

This is a real disposable-Git revert drill, NOT an actual revert of
the MFX protected main branch. No plugin runtime is wired; no
schema transformer, authenticated Twelve Data bridge, broker,
native historical BID/ASK execution quality, numeric 18-zone detector,
TP/SL fill simulation, OOS results, signed release or trading.
A04 overall remains PARTIAL. A04/P0.5 may formalize protected-main
recovery SOP, differential schema selection and architecture
integration decision, but no source modification without separate
approval and postmain parity gates.

## First GitHub Actions red evidence
PR #16 initial bootstrap Actions run 42572072272 executed 757
synthetic unittest methods and a real isolated no-remotes Git
commit/commit/revert drill. The A04 strict mypy step rejected ten
uses of Optional dict fields in the new pinned-receipt validator.
Corrected solely by explicit independent isinstance checks of each
mapping, retaining the exact fail-closed validation. No ignore,
no disabled typing and no source/runtime changes. Retain this red
run; require a fresh 3/3 green bootstrap before using measured
SHA in the pinned baseline.
