# MFX P0.183 — Isolated native H4 incremental append with P171 fresh D1 SHA HOLD

**Real incident:** [#180](https://github.com/ngluonghoa/MFX/issues/180#issuecomment-6941204415) now proves CHANGED_OVERLAP_SHA on two natural hourly source calls: 1 of 5 P171 fresh D1 SHA labels changed, 4 unchanged, **zero missing**, source vendor correction cause not proven. Independent SHA audit [#44042645121](https://github.com/ngluonghoa/MFX/actions/runs/44042645121) PASS on **already saved** source and shows 4 closed H4 slots behind as of 2026-11-17 07:57 UTC.

## Operationally narrow scope

- Existing owner-authorized hourly Cloud H4/D1 writer and real provider requests remain unchanged; no new workflow, environment variable, quota, cron, source endpoint or Google Drive namespace.
- P183 permits H4 to append ONLY when the already-fetched D1 result from P180 is exactly **CHANGED_OVERLAP_SHA, changed 1, missing 0**, all other previous SHA labels identical and every source-right/approval flag false. This is **not** D1 source authorization.
- Existing strict H4 source overlap SHA and native sealed plan must PASS first. After both original H4 and legacy D1 complete SHA re-audit post-fetch, re-audit full immutable owner-approved 2026-11-11+ P171 fresh D1 epoch AGAIN. Any drift/orphan makes zero new writes.
- Recompute exact immutable H4 content-addressed chunk + manifest proposal and verify it; only original H4 store's original two-object atomic-ish readback path may append H4. It independently checks H4 archive parent and source SHA before its write. Never write old D1 V1, never write fresh P171 D1, never rebaseline/overwrite P171, never override D1 quarantine; no broker, output remains NO_SIGNAL/UNVERIFIED.
- Emit redacted H4-only receipt and **intentionally FAIL the scheduled job RED** with original P171 overlap quarantine. H4 can catch up from vendor rows within existing request and Drive quota, while D1 stays in hold; the job must NEVER be interpreted as source or product readiness.
- Additional Drive GETs required by full P171 SHA re-audit; no additional vendor price calls. No D1 source revision observation written in this PR. Source first-known still not independently proven. Data use/retention rights #27 remain a separate gate.

Negative proof: missing or multiple changed D1 labels, wrong incident, extra/forged diagnostic keys, stale/corrupt/changed source, failed H4 SHA, no H4 due, quota exhaustion, changing D1 parent before writing, and wrong quote/signal authorization cannot append H4; original D1 must remain SHA unchanged.

Code touches ONLY MFX runner outside original frozen `src/forex_trading`, plus one pure helper, offline test file, this doc, SHA-pinned delta allowlist. No change to 102 Forex source Git blobs or 11 SOURCE_LOCKED Docs. Source owner-approved B2/S2 numeric rules still 0/36; no real BUY/SELL or broker execution.

Rollback by reverting P183 code paths and allowlist rows; NEVER delete an already accepted immutable H4 chunk/manifest.
