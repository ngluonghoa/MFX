# MFX A04/P0.80 — GitHub witness sandbox READ-ONLY preflight contract

**Research-only. No witness ref, ruleset/permission change, Git ref mutation, new Drive data or broker action.** P0.80 evaluates caller-provided API-shaped observations offline. It is neither an HTTP connector nor a production CAS or authenticated authority.

## Verified API and repository findings

1. GitHub documents **GET /repos/{owner}/{repo}/rules/branches/{branch}**, which returns active rules applying to a branch **even when that branch does not exist**. See https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch.
2. Actual MFX ruleset 26801788 (MFX-main-protection) was read through connected GitHub API: active only for ~DEFAULT_BRANCH, with deletion, non_fast_forward, required_linear_history, pull_request and three mandatory CI checks. This does NOT protect a separate native V2 witness branch.
3. Read-only GitHub GET /repos/ngluonghoa/MFX/git/ref/heads/mfx-native-v2-witness returned **404 Not Found**. The candidate witness branch does not exist at inspection. The GitHub connector rejects GET /repos/ngluonghoa/MFX/rules/branches/mfx-native-v2-witness with **400 URL not allowed**, even though that endpoint is documented by GitHub. Thus NO live branch-rules result could be obtained. Never fabricate a successful rules check.
4. GitHub REST PATCH /repos/{owner}/{repo}/git/refs/{ref} documents force=false as a fast-forward ancestry check, NOT an exact expected-current-head CAS. See https://docs.github.com/en/rest/git/refs#update-a-reference.

## P0.80 pure offline contract

Source: tools/mfx_native_v2_github_witness_readonly_preflight.py. It models immutable read-only snapshots: branch-scoped active-rules response; exact Git ref before and after; and an observed single-parent Git commit (candidate SHA, parent, witness payload digest, claimed GitHub signature verification). There is NO network or write method.

The evaluator requires the precise test target refs/heads/mfx-native-v2-witness and the branch-scoped active-rules endpoint. It compares before/after rule snapshots and verifies reported deletion plus non_fast_forward protection; checks bounded rule metadata; requires both ref reads to be consistent or both absent (404); and matches the candidate Git commit and parent to the P0.79 plan. Changed rules, 403/404 active-rules API, default-only substitution, missing rules, branch creation/deletion during reading, unexpected head, malformed SHA, altered payload, extra merge parent or missing signature verification all fail closed. A 404 ref is never silently treated as a signed witness.

ALL receipts explicitly report independently_authenticated_head=false, durable_monotonic_antirollback_verified=false, real_exact_head_atomic_cas_verified=false, ruleset_bypass_protection_verified=false and live_v2_authorized=false; Github mutations, Drive writes, provider calls and broker orders remain zero.

The GitHub branch-rules API returns active rule types, but not a separately authenticated guarantee against administrator bypass, policy rollback, account compromise or immutable retention. A claimed GitHub signature verification bit does not by itself provide an independent, fresh, durable trusted HEAD. Actual candidate payload digest must be verified by retrieving the separately stored payload; a commit JSON alone is not the witness payload. A malicious caller can forge ALL the snapshots used by this research contract.

Tests: tests/test_a04_p80_github_witness_readonly_preflight.py adds 30 hermetic cases including absent/unpublished branch, correct candidate, stale/forked ref, branch appearing/disappearing, drifted/missing/wrong rule sources, bad HTTP status, forged bypass data, malformed parent/payload and H4/D1 separation; no real GitHub requests or cache activity.

## Owner and operational gates

The P0.80 source branch is a normal development PR, NOT a real witness branch. Do not create a production/test witness ref or change rulesets without a separate owner-approved decision. Before real GitHub witness use: owner must select its trust boundary and an accountable GitHub App identity; apply and independently verify an exact witness-ref ruleset without unwanted bypass/force/delete; establish signed commit identity, audit, independent backup/monotonic checkpoint protection against a compromised GitHub admin; then test actual concurrent single-parent fast-forward updates in a separate **sandbox**, not MFX main nor production Cache.

No Cloud-only boundary change, secrets/variables, native H4/D1 V1 256 per-bucket cap, source-native H4+D1 or M5 schedules, Forex source102 blob/11 locked-doc modification, numeric signal approval, HOT V3 or broker activation. H4 reduction requires >=30 fully closed exact 48xM5 H4 windows spanning >=7 days including actual session gaps, plus separate owner approval; D1 Sydney source-native remains.

**Acceptance only authorizes pure source+CI, NOT real external antirollback, witness branch, CAS or Drive V2 migration.**
