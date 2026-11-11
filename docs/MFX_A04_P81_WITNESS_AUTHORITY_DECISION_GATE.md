# MFX A04/P0.81 — GitHub witness authority decision gate (source-only)

**Status: RESEARCH ONLY / BLOCKED / NO LIVE WITNESS OR NATIVE V2.**

P0.81 resolves a subtle source-evidence ambiguity in P0.79/P0.80 and creates a deterministic fail-closed checklist, without any real GitHub branch/ruleset operations. P0.80 passed 2292 tests per Python version at protected main `627509cc4971b3222ccdfc97eba93d85b14fb44c`. This file does **not** assert fresh main or operational audit beyond the cited baseline.

## Verified distinction from actual read-only inspection

- Active MFX `MFX-main-protection` ruleset 26801788 targets only `~DEFAULT_BRANCH`, not prospective `refs/heads/mfx-native-v2-witness`. Existing protected main must not be changed to solve the witness problem.
- Candidate witness ref was **HTTP 404** at P0.80 readback. No prospective witness ref was created.
- The installed GitHub connector returned a **connector allowlist denial**, rendered as an HTTP wrapper 400, on the official `GET /repos/ngluonghoa/MFX/rules/branches/mfx-native-v2-witness` endpoint. That is NOT a GitHub API response proving missing rules or permission denial. P0.81 models `CONNECTOR_ALLOWLIST_DENIED` separately from `GITHUB_HTTP_200`.
- GitHub documents that branch-effective-rules GET can work for a nonexistent branch, with repository Metadata(read). It separately requires repository Administration(write) to create rulesets. Neither documented API capability nor connector authorization equals owner authorization to mutate settings.
- GitHub Git ref PATCH with `force=false` enforces a fast-forward ancestry constraint; it has no exact `expected_current_sha` atomic CAS input. A signed commit, a SHA pin, and protection rules are not independently authenticated monotonic external authority against an administrator, policy rollback, split authority or a compromised account.

References: https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch and https://docs.github.com/en/rest/git/refs#update-a-reference; historical P0.80 docs and PR #122.

## Implemented research-only acceptance gate

`tools/mfx_native_v2_witness_authority_decision.py` accepts only a typed, caller-supplied snapshot for exact MFX repo/ref. It enumerates missing proof for owner trust boundary, test-only mutation approval, real ref readback, distinct effective branch rules, independent signer, bypass/admin residual threat decision, independently backed-up append-only checkpoint, genuine competing cloud fast-forward requests, independently authenticated monotonic head, and externally atomic exact-head CAS.

Any attempt to report the GitHub `force=false` mechanism as exact-head CAS is rejected. Main-only protection never substitutes for witness protection, and an unavailable branch-rules endpoint cannot be silently described as an HTTP 200 GitHub result. Even if a caller sets every other claimed proof bit to true, the receipt *always* declines trusted antirollback and live V2 authorization; no evidence has been independently obtained by this pure source module.

`tests/test_a04_p81_witness_authority_decision.py` adds 24 hermetic contract tests including forged API evidence, false CAS, owner approval, missing branch protections, signature/backup gaps, immutable production cron and hard negative runtime flags.

## Current decision and next real gates

**CURRENT:** `BLOCKED_RESEARCH_ONLY`. No GitHub witness production/test ref, ruleset, admin permissions, secret, Cloud Drive V2 archive, live V2 read or write, or broker execution. Existing native V1 H4/D1 256 hard cap and its hourly writer, M5 hourly writer and independent read-only audits unchanged; original frozen Forex Trading 102 blobs and 11 SOURCE_LOCKED Docs unchanged.

**NEXT P0.82 (owner-gated):** Owner selects acceptable GitHub-only witness residual risk or another independent authenticated CAS authority within approved Cloud-only services. Separately approve a test-only ref/ruleset with actual branch-scoped rules GET and signer / GitHub App permissions; prove real concurrent fast-forward behavior with no force and separately backed-up/monotonic head readback. Only after independent accepted evidence, design isolated OAuth Drive V2 read-only and separate future writer/recovery acceptance. No real production V2 migration from V1 until current V1 complete and explicit owner gates.

**PARALLEL:** Independently continue M5-to-native-H4 qualification: at least 30 exact 48xM5 completely closed H4 windows across at least seven real days including session/weekend gaps; do not replace native H4 before separate owner sign-off. D1 stays Australia/Sydney-native. Investigate prior M5 tail lag observation, >1024 M5 rooted checkpoint and retention rights, and B2/S2 0/36 source numeric owner approvals. HOT V3 and broker always OFF.

Cloud-only GitHub + Google Drive. NO Mac, MOCHI or local computation.
