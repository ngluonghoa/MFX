# A04/P0.90 — SHA-pinned retrospective M5 evidence pack (OFFLINE ONLY)

Observed and source-reviewed 2026-11-12 UTC. This is an owner-directed, non-deploying historical evidence cross-check. It does **not** run another private Google Drive audit, call a vendor, edit the production workflow, change market-data cache, enable H4 replacement, unlock live V2, or issue BUY/SELL signals.

## Authoritative frozen evidence joined

- **P0.87:** 12 actual successful GitHub M5 scheduled runs, 14 consecutive observed closed-hour Drive manifest batches from 2026-11-11T14:00:00Z to 2026-11-12T03:00:00Z, two runs with bounded 2-hour catchup. The earliest eligible close+10 minute cron is a theoretical comparison baseline, not authenticated source of an event.
- **P0.88:** exact GH job stages: 2–3 seconds created-to-started (median 3 seconds), 17–39 seconds run time (median 22.5 seconds), all sampled Drive manifest creation timestamps within the corresponding writer step. No proof of pre-run concurrency contention or GH internal event dispatch.
- **P0.89 source:** the same 12 run IDs map to exactly seven immutable source commit HEADs. Historical workflow Git blob c506c0c7212e17d20ea22090e1887fd8aa7bf38b is identical on all seven. Its cron is `10 * * * *` UTC, group mfx-twelvedata-private-cache, cancel-in-progress=false; no source workflow modifications in that observed cohort.
- **P0.89 read-only full SHA:** existing P0.66 GitHub Actions https://github.com/ngluonghoa/MFX/actions/runs/43138482666 attempt **4**, job **131119847520**, PASS marker `MFX_A04_P66_READONLY_SOURCE_SHA_PARITY_AUDIT_PASS` at 2026-11-12T10:23:09.517Z. Entire then-current bounded Drive M5 archive verified **40/40** Manifest+Chunk SHA/parent/derived pairs, 480 CLOSED M5 bars to 09:00Z, head SHA256 `9354cbe797c69b40a7466218db8cc8018b2c454396c95c33a66146d4939ec91d`; native H4 8 archive pairs/126 bars and **9** exactly matched full 48xM5 windows, 0 mismatch. Audit: provider calls 0, Drive writes 0, broker orders 0. This was original historical P0.66 code, **not** the newer P0.85 two-anchor wrapper.

## P0.90 source-only code and QA

`tools/mfx_m5_retrospective_evidence_pack.py` composes existing P0.87–P0.89 pure validators, requires the exact independently reviewed 12 run-to-seven HEAD mapping and pins the **P0.89 historical SHA receipt** to run/attempt/job ID, UTC completion, exact 40/480 head, H4 counts and zero-write safe scope.

New `tests/test_a04_p90_retrospective_evidence_pack.py` provides **34 offline positive/negative checks**, including mismatched GitHub run identity/head/blob, stale/wrong SHA, false audit marker, incorrect temporal ordering, unauthorized production activity, timestamp/booleans, and future-as-of freshness misrepresentation.

These Python files make **zero GitHub/Drive/provider/broker calls** and cannot authenticate their own caller-supplied rows. The reviewed point-in-time 40/40 validation is an external *historical* audit, not a current archive head claim. The pure P0.90 code verifies only consistency with that pinned history. A new M5 manifest after 09:00Z requires a fresh independent full-SHA audit for a new head. It does not establish vendor legal storage rights or a licensed price/broker-side model.

## Explicit no-go and next

- 12-run sample does **not** reveal GitHub's authenticated original schedule event emission/dispatch timestamp or vendor first publication. Cause of large pre-run delay remains unproven; **no production cron or concurrency change**.
- H4 source remains **native**; only 9 complete exact matches, below >=30 matching windows across >=7 actual FX days and session-gap verification, plus explicit owner GO. Sydney D1 remains native.
- Live V2 external monotonic witness/CAS, third-party FX data rights/calendar, 36 B2/S2 numerical owner signoffs and market BUY/SELL/HOT permissions remain gated. Broker execution is forbidden.
- ChatGPT hourly engineering automation remains **disabled**, separate from existing GitHub data workflows.

**NEXT P0.91:** request/rerun only an already authorized read-only full-SHA archive audit to establish a newer *point-in-time* M5 head, then correlate it without promoting this P0.90 offline result to independent external attestation. For prospective source telemetry or production edits, first obtain separate owner approval, security review, rollback and release evidence. Cloud GitHub + Google Drive only; never Mac/MOCHI/local.
