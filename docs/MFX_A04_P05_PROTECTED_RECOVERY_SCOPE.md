# MFX A04/P0.5 — protected main recovery SOP and explicit schema selection

**Checkpoint**: protected main `ec87e33c71ccf6a44c1ffbe24d2ce75480a15830`; independent CI
`42572748419` 3/3 PASS. Frozen Forex baseline
`7e1c1c012b1b189be5ad7b9d07756eac012a8309`, exact first MFX
102-blob import `6ee5e7c07baf4ea8f06a28889175808ea53c2316`.
A04/P0.1–P0.4 tested only inert schema/plugin declarations, with
P0.4 REAL git revert exclusively within disposable GitHub-hosted
no-remotes clone, NOT the MFX main branch.

## Recovery SOP — only after actual incident, fresh user authorization
1. Freeze writer / other PRs and any change or release attempt; record
   the exact protected main SHA, GitHub ruleset and CI run, incident
   symptom, affected squash SHA, its dependency graph, and original
   Forex source baseline. Pause runtime rollback claims.
2. Read live GitHub protected-main head. If it moved, abort the plan,
   refresh from authoritative HEAD and re-audit dependent commits.
3. Inspect whether the offending squash commit is safe to revert
   independently. If later commits depend on it, use a reviewed
   forward-fix or coordinated PR; no arbitrary `git reset --hard`,
   force-push or direct main push.
4. On a **new GitHub-hosted change branch**, revert the exact offending
   squash commit (or create a forward-fix) only when independently
   approved; preserve Git history. Open a normal PR targeting
   protected main. Enforce source-lock 102 manifest, six prior A02
   typing-only delta guards, 50 frozen golden, A02 30 strict mypy,
   A03 coverage/mutation/fuzz, A04 all synthetic contracts, security,
   build/wheel parity and any incident-specific probes.
5. Review one PR/one writer. Squash Merge only with exact expected
   PR-head SHA and all required checks PASS. After merge, independently
   verify 3/3 on new main and record Drive Handoff, QA, Traceability
   and Incident/Release decision.
6. **Real production restoration remains a SEPARATE operations
   decision**, dependent on signed artifact/LKG provenance, licensed
   data, deployment rights and independent post-cutover validation.
   A Git revert never implies production rollback or a broker action.

## A04/P0.5 executable CI-only scope
- `tools/a04_p05_recovery_selection.py`: pure immutable review of
  protected-main recovery *facts*; no GitHub network/read/write,
  branch creation or implementation permission.
- Exact schema request by PortSchema + major/minor, bounded candidate
  set and exact single result. No version downgrades, other-schema
  mutation, automatic fallback, implicit migration, semantic drift,
  external provider substitutions or runtime calls. Additive minor
  changes are STRUCTURAL REVIEW ONLY, not approval.
- Integration decision is fail-closed. All signals remain
  documentation-only, even if the 50 synthetic golden contracts,
  14-case P0.3 schema matrix, 19-case P0.4 canary, source SHA and
  prior CI are valid. Plugin runtime, real BID/ASK and real trading
  are explicitly denied.
- `tools/check_a04_p05_recovery_gate.py` runs a bounded deterministic
  matrix on GitHub runners, sourcing SHA from earlier PINNED
  P0.3/P0.4 files, and explicitly forbids remote Git actions.

## Controls and nonclaims
The initial PR CI run is measurement-only via
`--bootstrap-measure`. Pin the observed matrix SHA after both
Python3.11/3.12 receipts match, switch to mandatory verification and
negative tamper tests, enforce strict mypy and all prior gates. Merge
only exact-head PR CI 3/3 PASS and independent postmain CI 3/3 PASS,
then update Drive four governance documents.

Neither the CI synthetic recovery *facts* nor this runbook verify
a real disaster recovery incident or GitHub ancestry. No actual
protected-main revert, runtime plugin loader, licensed market data,
numerical 18-zone detector, TP/SL fill simulation, OOS, signed release,
scheduler or trading. MFX stays Cloud-only GitHub+Google Drive; zero
Mac/MOCHI/local and zero `src/forex_trading` edits.

## First PR CI (red) technical evidence
Run 42574581730: both Python3.11/3.12 executed 773/773 synthetic
unittest methods successfully; observed identical 28-case
recovery/schema/integration matrix, 23 cases blocked and five
structural-only review decisions. New strict mypy on eight A04 tooling
modules found eight errors because two loops reused variables named
`facts` and `result` across incompatible Recovery and Integration
typed dataclasses. Replaced ONLY the integration-loop variable names
with `integration_facts` and `integration_result`, preserving every
fail-closed rule and zero `src/` changes. The red run remains retained;
require fresh 3/3 before pinning a reproducible baseline.

## Evidence: cross-Python bootstrap and locked final CI

First PR run 42574581730 RED: 773/773 unittest methods passed per
Python, but the new eight-module strict mypy audit rejected reuse
of `facts/result` identifiers across distinct Recovery and
Integration dataclass types (8 typing errors). Repaired by distinct
names, no ignored diagnostics and no source/runtime changes.

Second PR bootstrap Actions run
https://github.com/ngluonghoa/MFX/actions/runs/42574766022:
3/3 PASS, both Python3.11 job 129019882717 and Python3.12 job
129019882425 ran 773 synthetic tests; original Forex 50 golden,
A03 17 targeted mutation sentinels, A04/P0.3 14-case schema,
A04/P0.4 19-case canary and true disposable no-remotes Git revert,
source SHA, strict mypy for eight A04 tooling modules, coverage
2546/2683 source lines (94.89%) and 973/1112 branches (87.50%)
and cross-Python wheel parity PASS.

Observed identical 28-case offline P0.5 review matrix: 23 blocked,
5 structurally reviewable ONLY (not permission). Canonical matrix
SHA256 `6a55e6a7f04f9d20b36cdc882c021583962cba938c05b573ca148255b9b1068c`,
same on 3.11 and 3.12; P0.3/P0.4 ancestor digests pinned.
`docs/MFX_A04_P05_RECOVERY_SELECTION_BASELINE.json` now locks
observed counts, SHA, provenance and six mandatory no-runtime flags.
After this commit, bootstrap mode is removed, four negative SHA/
authority tampering tests are added, and a fresh exact-head PR 3/3,
followed by independent postmain 3/3, remain mandatory.

No actual GitHub production rollback, runtime plug-in integration,
market feed, broker, OOS, release or trading occurred.
