# A04/P0.88 — Real 34/34 M5 full SHA + GitHub job-stage evidence, no production instrumentation

Evidence dated 2026-11-12 UTC. MFX remains cloud-only, with ChatGPT hourly development automation DISABLED. This milestone neither changes an existing production workflow/cron nor authorizes H4 source replacement, vendor calls or trading.

## 1. Real private Drive archive: repeat existing read-only SHA check

After P0.86 verified the 33/33 Manifest+Chunk archive at 04:52Z, the existing owner-approved P0.66 read-only workflow was run once more without modifying its source/workflow. GitHub Actions #43138482666 ATTEMPT #3, job 131006263544, completed SUCCESS; independent log marker MFX_A04_P66_READONLY_SOURCE_SHA_PARITY_AUDIT_PASS at 2026-11-12T06:04:44.684Z. Link: https://github.com/ngluonghoa/MFX/actions/runs/43138482666 .

Its same-run structural/cryptographic receipt:
- M5 34/34 immutable Manifest+Chunk SHA/linked/derived pairs; 408 fully closed M5 bars; last UTC hour 2026-11-12T03:00:00Z, latest SHA256 360460f00e50bc822b2401571773ce91cd6a0614bef84b89aa20a31c70f2fe97; m5_full_bounded_chain_verified=true.
- Native H4 archive 7 fully SHA-verified pairs; 8 M5-derived complete 4H windows matched native, zero mismatches, H4 qualification threshold FALSE, no permission to reduce/replace native H4. The increase from 7 to 8 matching windows is consistent with the 03:00Z M5 final hour completing a grid window.
- provider_api_calls=0, drive_writes=0, broker_orders=0; read-only. The P0.85 two-anchor wrapper was NOT executed: this is the existing full-bounded P0.66 reader on historical checkout SHA 4c60644d0a812eabee0e89519a29e1cce9731b61. Its critical read-only code/workflow blob identities were independently verified unchanged through P0.87 in P0.86.
- No external monotonic trust witness, price-provider licensing, exact session calendar, history before genesis or future SHA attestations. Real completeness applies to those 34 pairs at this exact audit time only.

## 2. P0.87 cohort expanded with original GitHub job lifecycle

P0.87 already cross-checked 12 actual scheduled run creations against 14 closed M5 batch manifest files (contiguous from 2026-11-11T14:00Z to 2026-11-12T03:00Z; two runs wrote two hours each). Its observed median manifest-after-hour-close is 58.44 minutes; run-created-to-manifest is 21.6 seconds. Median run creation after the batch's theoretical close+10m cron is 48.12 minutes; this does NOT prove which scheduled tick actually produced any given run.

For those SAME 12 IDs, independently fetched GitHub REST job subresources: each job's created_at, started_at, completed_at and the Sync verified CLOSED step start/end. Every job concluded SUCCESS.
- GitHub job created to started: 2–3 seconds, median 3 seconds.
- Job started to completed: 17–39 seconds, median 22.5 seconds.
- Writer sync-step duration: median 15 seconds (API timestamps have seconds precision).
- Every corresponding Drive manifest creation time fell WITHIN that run's writer sync step: temporal agreement, not authenticated price content.
- The 12 jobs collectively reported 12 vendor-price requests, but no NEW calls were made for this research audit.

Inference boundary: prolonged queueing AFTER job creation is not supported in this cohort. This does not prove GitHub's upstream scheduled-event creation/dispatch delay, a dropped cron event, pre-run concurrency queuing, or provider publication timing. GitHub run metadata lacks an independently authenticated emitted-event timestamp. Neither github.event.schedule (cron expression) nor job.created_at proves when the internal event fired.

## 3. New pure offline job-stage join

New tools/mfx_m5_job_lifecycle_evidence.py consumes existing P0.87 immutable schedule/manifest cohort PLUS caller-supplied independent GitHub REST job timestamp receipts, joined by exact run ID and created time. It checks:
- Strict complete per-run bijection, no duplicate run/job IDs, real schedule event and successful job receipt, UTC-only clocks.
- Run created <= job created <= job started <= sync started <= sync finished <= job completed.
- Every matching Drive manifest-creation timestamp must occur INSIDE the corresponding writer sync step.
- Bounded sample and explicit gap reporting via existing P0.87; numerical medians are stage observations only.
- All cause/authorization fields fail closed: no authenticated original cron event time, no scheduler/concurrency/vendor attribution, no provider-call/Drive-write/trading, no complete price SHA re-attestation by this module, no cron/H4/V2/live signals promotion.

tests/test_a04_p88_m5_job_lifecycle_evidence.py adds 28 hermetic positive/negative cases with actual observed 12 job-stage UTC timestamps plus intentionally fake/negative altered data. Tests are offline and never fetch live Drive or vendor prices. New code, docs and tests are SHA-pinned MFX-only deltas; no original Forex 102 frozen source change.

## 4. Prospective P0.89 instrumentation boundaries — NOT deployed

If the owner later approves a separate explicitly read-only telemetry change to an existing GH workflow, it could emit non-secret job/step timestamps and github.event.schedule expression/run_id/attempt, then correlate public GitHub REST run creation with existing private Drive manifest metadata. However GitHub does NOT expose an authoritative internal dispatch timestamp to that job. The proposal must NOT claim it can uniquely measure scheduled-event dispatch by printing github.event.schedule or date -u. To isolate source publication timing would require a separately approved, budgeted vendor availability probe or provider-native publishing timestamps, not guesses from successful late API fetches.

Any production cron, shared concurrency group, cache writer, repo variables/secrets, vendor quote requests, data retention permissions or source switch remains OWNER APPROVAL REQUIRED, with rollback and exact-head QA. Additional telemetry must avoid printing OHLC, credentials, account IDs, Drive raw identifiers, provider requests or trading signals. H4 source remains NO-GO until >=30 matched complete 48xM5 H4 windows over >=7 days with real FX session gaps and owner GO; Sydney D1 remains native.
