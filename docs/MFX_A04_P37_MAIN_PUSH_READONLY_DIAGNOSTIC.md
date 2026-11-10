# A04/P0.37 — Hosted read-only diagnostic for main-push CI status

**Problem being investigated:** GitHub repo `ngluonghoa/MFX` has `on: push: branches: [main]` plus `pull_request` and, since P0.36, a main-only native commit status publisher. The connected GitHub action `fetch_commit_workflow_runs` filters to PR-triggered events and `get_commit_combined_status` repeatedly reported `statuses: []` for commit `74c210dabf83d670c0ce71964332218f57317a75`. A missing native status is **not a PASS** and by itself cannot distinguish a missing, running, failed or skipped push job.

## Actual diagnostic

A new, cheap `p037-read-main-push` workflow job runs ONLY for MFX-owned PRs, with `contents: read`, `actions: read`, and pinned noncredential-persisting checkout. It invokes `tools/read_main_push_ci_diagnostic.py` using an ephemeral GitHub-provided token. No write permission and no status mutation. The script uses fixed-host `HTTPSConnection('api.github.com')` and calls only these read-only REST endpoints:

1. Branch `main` metadata to learn exact head SHA, never reuse a guessed or PR merge SHA.
2. GitHub Actions run list filtered `event=push&branch=main`; select a run matching exact current main `head_sha`.
3. The selected run's actual job list (Python3.11, Python3.12, crosswheel, main-status publisher).
4. The exact main SHA native commit status records filtered for `mfx/main-push-full-ci`.

The output prints limited run/job IDs and status/conclusion fields, along with `push_jobs_and_native_status_verified` true only when the exact main push run and **all four jobs** succeeded and native SHA status is successful. The diagnostic does **not** attest old historical push runs. It **does not** print the request token and cannot read/write Forex provider data, Google Drive quote cache, broker accounts or original strategy owner signatures.

Eight network-free preregistered tests cover exact PR/repository authorization, safe API host, token handling, strict SHA, actual run/job/status cross-check, negative failed/missing cases, mock-only endpoint dispatch and original Forex 18/MFX 22 design + 36 pending source approvals. Full established CI on Python 3.11 and 3.12, Ruff/strict mypy/source freeze/security and crosswheel still runs unmodified.

**Interpretation after Cloud CI:** Use the `p037-read-main-push` job logs on its exact PR head to diagnose whether P0.36 publisher failed, was skipped or never had a `push` run. Do not merge a speculative fix until the evidence identifies the cause. Keep [Issue #64](https://github.com/ngluonghoa/MFX/issues/64) open until native status + push jobs prove cumulative current main QA, and [Issue #66](https://github.com/ngluonghoa/MFX/issues/66) as diagnostic evidence. Original source owner B2/S2 36/36 decisions [#45](https://github.com/ngluonghoa/MFX/issues/45) and real FX data/Drive quote rights [#27](https://github.com/ngluonghoa/MFX/issues/27) remain externally blocked; all real signals `NO_SIGNAL` and no broker execution.
