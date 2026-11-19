# MFX P0.197 — Independent GitHub Actions history of the existing hourly M5 cache writer

**Scope:** protected GitHub main, GH Actions-read-only metadata. No quote provider request, no Drive listing/write, no broker, no changes to the writer's existing cron.

## Why

P0.196 proved that the successful owner-triggered real manual six-TF GET-only audit #44429248928 had missing M5 17 bars at 2026-11-19T00:28:40Z: 12 bars from one eligible full UTC hour not sealed and five bars that an on-time hourly-only writer cannot seal. P0.196 separated these two classes without inventing a cause. The writer's own schedule is `.github/workflows/twelve-data-cache.yml` `10 * * * *`, using one full CLOSED UTC hour per batch, five-minute grace and at most four immutable catch-up batches.

Authenticated Google Drive metadata read on 19 Nov showed actual later batches, not a dead writer: 07:00Z and 08:00Z sealed manifests created about 09:10Z, 15:00Z and 16:00Z manifests created about 17:12Z. The 16:00Z completed source hour was the latest writer-eligible complete source hour at roughly 17:40Z. Therefore do not call this a persistent missing-hour backlog without more precise writer run evidence.

The existing connector can read a run/job when given its ID but cannot list past GitHub Action runs for this workflow. Do not infer skipped/failed jobs solely from Drive object timestamps. This PR makes the needed independent GitHub run IDs visible from a **cloud-only** read-only attestation.

## Atomic implementation

- New `tools/audit_mfx_m5_writer_runs.py` uses the existing, already tested GitHub-runner HTTPS proxy-safe `_get_json` utility to request exactly one GitHub Actions REST endpoint: `/repos/ngluonghoa/MFX/actions/workflows/twelve-data-cache.yml/runs?event=schedule&per_page=60`. It accepts only repository main, GitHub official API URL and real GitHub workflow triggers, with a scoped `actions: read` token. No GitHub-write permission.
- Sorts schedule runs, filters last 36 hours, records at most 24 recent *GitHub* run IDs, created/start UTC timestamps and known statuses/conclusions. It distinguishes observed creation→start delay from **unproven** planned cron event delivery timing. It does not infer missing slots, successful provider HTTP, quota headroom or Drive batch commits from success of a GitHub workflow.
- Adds a **separate**, nonblocking `github-m5-writer-history-readonly` job to the existing hourly native H4/D1 SHA audit workflow, retaining the **same existing** `:45 UTC` schedule and protected-main push path. The existing authenticated H4/D1 GET-only SHA audit job remains untouched; no extra cron or independent scheduled workflow, no Drive credentials passed to this new job. If GitHub metadata API fails, the independent native source audit is not falsely failed.
- Fourteen hermetic regression tests for spoofed GH metadata, date and run ID validity, correct redaction, queued/failed distinctions, missing run non-approval, event and branch scoping, sorting, 60-entry limit, clock anomalies and trusted env. Exact blob SHA baseline allowlist updated for modified/added MFX-only files.

## Intended real-GitHub evidence

After squash merge, the existing native H4/D1 SHA audit is triggered by the modification to its workflow file on protected main, and independently each hour at the existing `:45` cron. The separate GH-only job prints `MFX_P197_GITHUB_SCHEDULED_M5_WRITER_READONLY_AUDIT_PASS` **only** after actual GitHub API successful response. Its output may contain scheduled run IDs, then an authorized connector can read *those exact run job logs* to identify failure/skip/provider quota vs delayed schedule. A green CI test for this code is not a substitute for the actual GitHub API read.

## Guards

No source-algorithm numeric approval (B2/S2 still 0/36), no licenced BID/ASK execution economics, original publisher first-known event timestamp or historical untouched OOS verified. One P192 Sydney-local owner D1 from 18-Nov alone remains insufficient for confirmed trend/pivot. All signal output remains `NO_SIGNAL/UNVERIFIED`, broker orders=0. Preserve original frozen Forex 102 blobs and 11 source Docs.

**Verification:** require exact PR-head Python 3.11 and 3.12 full tests, source SHA golden/security + cross-Python wheel, squash-only merge, independent protected main CI, and actual new GH API schedule witness. **Rollback:** revert the new separate GitHub audit job and the new script/tests/doc/allowlist only; no existing native audit or M5 writer modification.
