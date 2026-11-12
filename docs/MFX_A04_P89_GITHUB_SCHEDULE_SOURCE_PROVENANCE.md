# A04/P0.89 — Source-locked GitHub schedule provenance and real 40/40 M5 read-only audit

Evidence collected **2026-11-12 UTC**. This is a SOURCE-ONLY milestone. The ChatGPT hourly task remains DISABLED. No existing production GitHub workflow, cron, concurrency, secrets, variables, Cache writer, provider-credit quota, H4/D1 source, live V2 witness, trading, HOT or broker code is modified.

## 1. New point-in-time real M5 evidence (not simulated)

The already-authorized, pre-existing P0.66 M5-to-Native-H4 read-only full SHA parity workflow was rerun on GitHub: [Actions #43138482666, attempt #4](https://github.com/ngluonghoa/MFX/actions/runs/43138482666), job **131119847520**, result **SUCCESS**. The independent log records the marker MFX_A04_P66_READONLY_SOURCE_SHA_PARITY_AUDIT_PASS at **2026-11-12T10:23:09.517Z**.

The same-run Drive audit checked **40/40** immutable M5 Manifest+Chunk pairs and **480** fully CLOSED M5 bars, latest hour **2026-11-12T09:00:00Z**, latest manifest SHA256 **9354cbe797c69b40a7466218db8cc8018b2c454396c95c33a66146d4939ec91d**. The full bounded SHA/parent/derived chain passes. It also checked **8 native H4 Manifest+Chunk pairs**, 126 closed native H4 bars and **9 exact comparable 48xM5-derived H4 windows matched native**, 0 H4 OHLC mismatches. H4 qualification flag remains FALSE: insufficient >=30 windows spanning >=7 real days/session validation and explicit owner GO.

This was the **existing historical P0.66 auditor**, not the P0.85 source-only two-anchor wrapper. Its read-only run explicitly reported ZERO vendor requests, ZERO Drive writes and ZERO broker orders. The result is point-in-time SHA/structural integrity for these 40 M5 pairs, not a proof of price authenticity, market-calendar validity, source vendor license, history before root, future batches or an independent external monotonic witness.

## 2. Independently checked 12 actual GitHub run-source histories

P0.87 and P0.88 had independently correlated **12 successful scheduled M5 writer runs** (from #43053200735 to #43158866760), their GH REST run and job timestamps, writer log receipts and 14 corresponding Drive M5 hourly manifest creation timestamps. In P0.89 all 12 original GitHub run GET resources were checked again for **run ID, run_attempt, event, workflow_id, workflow path, run_created, run_started, head SHA and success conclusion**. Every observed run has run_attempt=1, event=schedule, workflow_id=413180668 and workflow path .github/workflows/twelve-data-cache.yml. GH REST run_started equals run_created in each checked run; importantly, that does NOT disclose actual GH internal cron event dispatch or verify which nominal hourly slot caused a run.

The 12 runs span **7 distinct historical HEAD commit SHAs**:
- d61fe9ecb7c4214699f3d027e17fabada42a3b63
- 9e9c76a47eaf769e4104600796c87c8dcd247621
- f19c78e0892c5bf4790762ccf1459f55f2cf5db8
- 4c60644d0a812eabee0e89519a29e1cce9731b61
- 627509cc4971b3222ccdfc97eba93d85b14fb44c
- 61cd36e04e0e2eb73de1e38fb2b42af71040310f
- 28dd1d617a7223196f85d612b221ea5cccea8563

**For ALL seven HEADs**, separately fetched the immutable Git blob of the existing scheduled writer .github/workflows/twelve-data-cache.yml. Its SHA is EXACTLY **c506c0c7212e17d20ea22090e1887fd8aa7bf38b** on each, and the same blob was checked on P0.88 main. The immutable source contains cron **10 * * * *** UTC, shared concurrency group **mfx-twelvedata-private-cache** with cancel-in-progress=false. Consequently, the observed variable run-creation times were **not caused by changes to the cron/workflow file across these seven checked source revisions**. The verified equality does NOT prove GH internal dispatch, account concurrency contention, schedule event loss, vendor first candle availability, or exact publisher root cause.

For the same observed cohort, GH job created→started was only 2–3s (median 3s), job started→completed 17–39s (median 22.5s), and manifest appeared inside the matched writer step. P0.87's first theoretically eligible close+10m to run creation median +48.12m is a **comparison baseline**, NOT an authentic mapping from scheduled tick to GH run. Neither shifting cron nor inserting a second writer is justified by these data.

## 3. New pure source provenance validator

tools/mfx_m5_schedule_source_provenance.py builds on the P0.87 12-run/14-manifest cohort and P0.88 exact job-stage join. It accepts ONLY caller-provided GH REST run-source metadata and enforces:
- Complete one-to-one matching of 12 historical run IDs to exact read-only GH job receipts; no duplicate/fake run IDs, non-schedule events, incorrect workflow ID/path/repository, source-blob mismatch, unsuccessful run or malformed 40-char Git SHA.
- Exact UTC clocks and source run.created matching GH job and P0.87 run records; run.started must lie between run creation and job start.
- The reviewed immutable workflow blob SHA is a **hard-coded expected fingerprint**; source control cron expression is distinguished from an authenticated event dispatch UTC timestamp.
- An attempt >1 or a missing observed M5 hour is reported as RECHECK, not promoted to scheduler-cause proof.
- All external event timing, source-first-publication, rights, real session calendar, modifying production cron/Cache/H4, live V2/CAS, numeric BUY/SELL/HOT or broker permissions remain DENIED, as do claims of external source/event attestation.

tests/test_a04_p89_schedule_source_provenance.py contains **34 hermetic tests** with the 12 real run IDs/7 historical HEAD fixture set and negative tampering/UTC/identity/attempt/gap cases. This pure code performs NO network call, provider request, Drive read/write or trading. Tests are NOT substitute for the independently fetched real GitHub metadata or 40/40 live SHA audit.

## 4. Prospective instrumentation acceptance decision — no deployment

A future optional read-only telemetry change to the existing live GitHub workflow would require separately explicit OWNER permission, a reviewed new PR with a security/privacy checklist and rollback. Safe candidate fields: GitHub run_id, run_attempt, event name, workflow path and SHA, run.created, job.created/started/completed, named writer step start/end, public GitHub cron expression and SHA-pinned Drive manifest creation time. Keep raw OHLC, secrets/tokens, OAuth IDs, broker/account details, provider raw responses out of logs.

Even if an approved workflow printed github.event.schedule (which contains an expression) and date -u, **that still would not expose an authoritative GH internal scheduler event emission UTC**. First-available provider candle time cannot be derived from a successful late fetch; a separate budgeted, authorized vendor-native observation would be required. A reporting-only/prospective design is approved here, NOT a new production workflow, schedule, concurrency change, telemetry dispatch, provider probe or publication claim.

## Next

P0.90 may focus on a **non-deploying read-only retrospective run-source audit pack** using existing GH REST/Drive metadata, or request distinct owner authorization for narrowly scoped prospective instrumentation. Full-M5-SHA qualification must follow every new head; H4 source still native until >=30 matching full 48xM5 windows spanning >=7 days with legitimate FX sessions plus owner GO; Australia/Sydney D1 native. Do not switch live V2 witness/CAS, release BUY/SELL signals, HOT live or broker on this evidence.
