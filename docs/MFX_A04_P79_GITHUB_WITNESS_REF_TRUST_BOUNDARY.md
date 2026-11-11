# MFX A04/P0.79 — GitHub ref witness trust-boundary feasibility (OFFLINE)

**Status: RESEARCH / UNTRUSTED / NO LIVE V2.** GitHub is outside the Google Drive **price archive**, but that alone is not equivalent to an independently authenticated, durable, non-rewritable monotonic witness or a real compare-and-swap (CAS).

## Verified service/API facts

GitHub REST \`PATCH /repos/{owner}/{repo}/git/refs/{ref}\` accepts a new Git object SHA and \`force=false\` (the default). According to GitHub REST docs this enforces **fast-forward ancestry** and rejects non-fast-forward updates; it does **not** take an exact \`expected_current_sha\` field and must not be described as an atomic exact-head CAS. A prepare→read→PATCH sequence does not make the entire multi-system Google Drive + GitHub transaction atomic. See https://docs.github.com/en/rest/git/refs#update-a-reference

GitHub rulesets can protect refs against deletion and non-fast-forward; required checks and PR rules apply to refs selected by the ruleset, not every branch automatically. Administrators can change policy; configured bypass actors, retained credentials and administrator compromise belong to the threat model. See:
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets

### Observed MFX repository governance (read-only research inspection)

Queried GitHub repository ruleset API \`/repos/ngluonghoa/MFX/rulesets/26801788\`. The **active** ruleset is \`MFX-main-protection\`, with \`include=["~DEFAULT_BRANCH"]\` (not all branches), the rules \`deletion\`, \`non_fast_forward\`, \`required_linear_history\`, \`pull_request\`, and required checks \`python-unittest (3.11)\`, \`python-unittest (3.12)\`, \`Cross-Python wheel parity (3.11 / 3.12)\`, and \`bypass_actors=[]\`. This is good protection for **main** but does **NOT** prove a future dedicated \`refs/heads/mfx-native-v2-witness\` branch has the same rules. Attempt to inspect classic \`/branches/main/protection\` returned 403 for this connector, so its precise configuration is **not verified** by that endpoint. No rulesets, branches, secrets or permissions were modified here.

## Candidate design: a dedicated GitHub witness ref (NOT AUTHORIZED)

Keep prices/candle/Chunk/Manifest objects in Google Drive. If owner later selects GitHub as the independent witness domain, use a **separate** dedicated protected ref for monotonic witness *metadata only*. Never publish prices, provider raw OHLC, OAuth credentials or API keys in a publicly accessible repository. Payload should contain the exact prior Git commit SHA, the new P0.78 proposed witness SHA, generation, epoch, fence and domain identity, plus a canonical payload digest; real Git commit SHA is calculated by GitHub on a separately authenticated commit object and cannot be invented as \`digest(payload)\`.

Candidate safe write ordering, *not implemented*: independently read and authenticate witness ref; verify prior commit/payload chain and Google Drive full SHA archive; create an immutable pair in a **separately authorized staging namespace** under an independently reviewed crash-recovery protocol; generate candidate Git single-parent commit whose parent exactly equals observed witness ref SHA; submit \`force=false\` Git ref update; independently read back the ref and candidate commit parent/payload; quarantine any orphan or conflicting pair. The Git ref fast-forward check can reject competing commits with the same parent in a shared branch, but it cannot defend against a principal with administrative bypass, a deleted ref, two separate refs, replacement of the whole trusted origin, or non-atomic Drive/Git multi-step updates. Fencing tokens from the caller are *not* independently issued. Missing real-world permissions or weak consistency must fail closed.

A dedicated ruleset (not created here) would need a ref-specific rule, disabled force/delete, strict protection/no bypass according to the owner's actual GitHub account capabilities, restricted credentials and GitHub App identity, audit access, durable backup and independent monitoring. It must be tested directly; **default-main rule coverage is not inherited** by the witness branch. The dedicated ref's status-check/PR rules must be designed to allow actual append operations without weakening main or auto-authorizing writes. No such ruleset or functioning witness authority currently exists.

## P0.79 code and 28 hermetic regression tests

\`tools/mfx_native_v2_github_witness_policy.py\` is pure. It models a fail-closed ruleset coverage review for **exact named ref** or \`~DEFAULT_BRANCH\` only (arbitrary GitHub glob patterns are *not* evaluated), builds an unauthenticated single-parent witness commit *payload* plan from P0.78, and classifies a caller-supplied readback. All receipts explicitly mark authentic external CAS/antirollback **unverified**, live V2 **disabled**, and zero Drive/provider/broker calls.

\`tests/test_a04_p79_github_witness_policy.py\` adds 28 hermetic tests. A tiny in-memory Git commit DAG models a fast-forward-only ref: two competing commits from one parent cannot both advance the same fake ref, whereas \`force=true\` or two separately controlled fake refs can rewrite/split. Other tests cover default-only ruleset mismatch, missing policies, bypass exposure, epoch/fence/source identity, forged payload and parent, unchanged/stale ref, unexpected fork, tampered flags and existing V1 workflow invariance. Fake tests are **not evidence** of a live GitHub write/permissions/crypto proof.

## Mandatory next gates before any real V2 rollout

1. **Owner decision** on GitHub-protected witness ref versus a different externally trusted monotonic CAS authority while preserving Cloud-only GitHub+Google Drive constraints; explicit acceptance of residual admin/GitHub account risk.
2. Independently verify ref-specific branch ruleset **applies**; protected no-force/no-delete/bypass restrictions; exact Git commit append/run permissions, independent audit, key identity, enforced signature/verification if required. No use of MFX \`main\` as mutable price-cache witness.
3. Prove with **real** authenticated GitHub cloud API requests against a dedicated sandbox ref (not production) that two competing fast-forward updates cannot both succeed, and assess stale heads, admin changes, restore, reorganization, retention and mandatory conditional reads. Treat ordinary \`force=false\` as **ancestry guard**, not an exact-head CAS API.
4. Only then separately approve test-only Google Drive V2 staged write/restore and independent SHA audit with no V1 mutation; real publisher must be owner-approved with operational rollback, backup, race and outage QA.
5. Continue unrelated M5↔native H4 parity requirement of 30+ exact fully closed H4 windows across 7+ real days with source weekend/session gaps. D1 remains Sydney-native. HOT V3, numeric FX BUY/SELL and broker disabled.

Original Forex 102 Git blobs/11 source-locked Docs, existing native V1 hard 256-file bounds and M5/H4/D1 cloud cron, secrets and privileges must not change in P0.79.
