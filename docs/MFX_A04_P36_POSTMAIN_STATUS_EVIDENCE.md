# A04/P0.36 — Independently readable main-push CI evidence via GitHub commit status

**Purpose:** Close a recurring, *technical observability* blocker without changing Forex strategy/business scope. Existing `.github/workflows/ci.yml` runs for both PR and `push` to `main`, but the connected GitHub action `fetch_commit_workflow_runs` intentionally lists only PR-triggered runs. This prevented independent confirmation of GitHub-hosted CI **after** each protected squash merge, despite successful PR-head CI.

## New verifiable evidence path

A new job `postmain-status` in the **existing** CI workflow runs **only** when `github.event_name == push`, `github.ref == refs/heads/main`, `github.repository == ngluonghoa/MFX`, and the prerequisite jobs have succeeded:

- `python-unittest`: complete original-source parity/security/coverage and MFX tests on **both Python 3.11 and 3.12**.
- `cross-python-wheel-parity`: verified identical Python 3.11/3.12 build artifacts.

Only then does `tools/postmain_ci_commit_status.py` use standard-library HTTPS to write a GitHub *native commit status* for exactly `GITHUB_SHA`: `state=success`, `context=mfx/main-push-full-ci`, and a `target_url` pointing to that precise GitHub Actions run. HTTP 201 is required; a failed request makes the postmain job fail rather than claiming a status.

The extra job is skipped on PRs. It is restricted to job-scoped `contents: read` and `statuses: write`, uses an immutable pinned checkout action with `persist-credentials: false`, and receives only the ephemeral `GITHUB_TOKEN` for its status-publishing step. Repository/branch/event, full lowercase 40-character SHA, positive bounded run ID, official GitHub server/API URLs, and scoped token are strictly validated before any outbound request. The module does not log tokens.

### Independent readback procedure using the connected GitHub app

1. After protected squash merge, obtain the exact new `main` SHA from `search_commits`; confirm expected files/diff via `compare_commits`.
2. Fetch that SHA through `get_commit_combined_status` and require context `mfx/main-push-full-ci` equal to `success`, with expected exact repository run URL and SHA. **Never interpret a missing/pending status as PASS.**
3. Extract the original Actions run ID from the status `target_url` (do not invent an ID) and independently call `fetch_workflow_run_jobs` for that run, requiring Python 3.11, Python 3.12, cross-Python wheel **and** postmain-status jobs to report `completed/success`.
4. Read job logs/steps as needed; then make a **bounded statement**: latest current main SHA's push CI verified. This does *not* retroactively establish the original `push` CI evidence for older release SHAs; it verifies the cumulative latest source, unless separate prior run IDs can actually be recovered.

**Integrity distinction:** This is a native GitHub Actions job self-publishing a status **after its successful dependencies**, not a cryptographically independent external attestation or proof of tamper-resistant CI. Its value is that a separate GitHub read API can locate the exact run and validate all job conclusions. Commit status alone is insufficient: verify the target's actual job list.

## Required gates and business limits

[Issue #64](https://github.com/ngluonghoa/MFX/issues/64) preregisters 12 source/permissions/HTTP/negative tests. Host CI must run full inherited 1:1 parity tests on Python3.11 and 3.12, static analysis, source SHA checks and cross-Python wheel. The extra status job **only executes on main push**, so PR green alone does not prove it works; complete verification needs **one genuine merge** followed by observed exact-sha native status and exact `push` run jobs.

No original frozen Forex `src/` or source-locked documents change. This task cannot approve any trading formula, turn the 36 source-owner-pending B2/S2 quantitative items into approved values, acquire BID/ASK vendor data rights, write real Forex market prices to Google Drive, publish real BUY/SELL alerts or enable broker orders.

**Current MFX design:** 22 labels (8 LONG entry candidates, 8 SHORT entry candidates, 2 WATCH, 4 protective); 0/16 owner-approved entry numeric strategies, 36/36 B2/S2 source decisions pending ([#45](https://github.com/ngluonghoa/MFX/issues/45)), licensed real provider/Drive market data rights pending ([#27](https://github.com/ngluonghoa/MFX/issues/27)). Real user action remains `NO_SIGNAL`; MFX is informational signals-only and never an automated trading executor.

## P0.37 HTTP egress correction (2026-11-10 ICT)
The original P036 main-only writer used raw stdlib HTTPSConnection, which bypasses proxy-aware opener configuration on hosted runners. P037 read-only diagnostic confirmed an HTTP403 on the first GitHub branch metadata GET, **without GitHub's request-id, server identifier or JSON response**. This is consistent with a proxy/egress-layer denial, not proof that GitHub rejected a valid commit status. The amended P037 code switches both P036 writer and P037 read-only diagnostics to a standard-library HTTPS proxy-aware opener for an **exact validated https://api.github.com URL**, with HTTP redirects rejected and original GitHub branch/SHA/event checks preserved. This is an engineering remediation hypothesis until the proxied PR job actually contacts GitHub and an eventual main-push run publishes the native status. Never upgrade QA from a code change alone.
