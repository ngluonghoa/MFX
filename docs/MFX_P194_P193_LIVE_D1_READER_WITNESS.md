# MFX P0.194 — Real P193 D1 source-reader witness inside existing SHA-only audit

**Owner intent:** Continue the technically safe 18-Nov source cutoff, with 22-Nov conditional GO/NO-GO and no unintended public signals or broker activity.

## Why this exists

P0.193 GitHub PR and main CI approved code-only integration of the P192 new D1 epoch into real GET-only six-TF reading, but no subsequent **real protected-main OAuth Drive execution of that exact P193 reader** had been observed. P0.192 was read back by the separate archive verifier. They are different interfaces and different trust checks.

## Narrow implementation

- Reuse **EXISTING** `MFX P0.58 Hourly READ-ONLY Native H4+D1 Full SHA Audit` at UTC :45 and existing post-main push-on-source-change trigger. No new cron, workflow permissions, OAuth secrets, Google Drive folder, Twelve Data API key, broker endpoint, provider polling or Drive write.
- After the independent P192 archive audit and only **if P192 is already seeded**, invoke `mfx_research.p193_owner_nov18_active_d1_reader.read_p192_owner_d1_epoch` against the actual private `PrivateD1Nov18Store` on the same authenticated GET-only Drive session, anchored to the already SHA-read-back immutable original V1 D1 source. **Do not read P171 prices or mix V1 pre-cutoff OHLC**. The P193 code uses a GitHub-reviewed **real** root SHA independently witnessed by writer 44316306054 and audit 44337203165, validates all manifests/chunks/parents, exact caller-as-of runner-observed timestamps and Sydney-local closed D1 dates.
- Require an **independent cross-check** that P193 reader and P192 archive auditor agree on root tip SHA, complete manifest count, total new bars, last D1 label, V1 original parent and strictly no earlier source bars. Divergence fails nonzero, never degrades to old epoch data.
- Public GitHub log contains **only** release-inert text marker `MFX_P194_LIVE_P193_D1_READER_ROOT_ASOF_SHA_PASS` and redacted bounded identity/count JSON status `P194_REAL_P193_GET_ONLY_SOURCE_ROOT_ASOF_ACCEPTED`, no quotes, raw OHLC, credentials, Drive file IDs, D1 pivot/market event values or B2/S2 directions.
- Before source bootstrap, redacted status `P194_WAITING_FOR_FIRST_P192_CLOSED_D1` is not presented as successful source acceptance; the entire job's historic archive audit may still pass without claiming P193. P192 source revises -> existing P192 SHA hold + P193 source reader both fail closed.
- The real manual **six-timeframe** workflow remains a separately operator-confirmed `workflow_dispatch` with required `READ_ONLY_NO_SIGNAL` and repository gate. The hourly source-only audit is explicitly **NOT** full M5/M15/M30/H1/H4/D1 integration, not strategy OOS, source-owner rule approval, licensed publisher first-known, or a release signature.

## Required QA

- Hermetic actual audit-job tests prove positive P193 reader call with SHA cross-check, unseeded WAIT, wrong independent root hard failure, zero extra price requests, Drive writes, broker orders and no false "manual six TF ran" claim.
- CI Python3.11/3.12, source-golden/security/wheel parity, exact Git blob allowlist; protected squash-only PR and separate post-main CI.
- Only a naturally executed **real** postmerge read-only auditor (using existing OAuth credentials) can prove the new live bridge; prior P193 CI alone is not sufficient.
- Original source 102 files and 11 source-locked Docs unchanged; old V1/P171/P169 Drive data not changed or deleted.
- Still no AUTHORIZED trading output: B2/S2 original numeric owner sign-offs 0/36 #45, account tier source retention + bidask quotes #27 and historical untouched OOS/net SL/TP R #138 are hard STOP. The first P192 D1 18-Nov bar alone cannot define right-confirmed D1 pivots.

## Independent evidence pointers

- Writer first P192 actual 18-Nov candle: https://github.com/ngluonghoa/MFX/actions/runs/44316306054
- Independent source archive original root SHA: https://github.com/ngluonghoa/MFX/actions/runs/44337203165
- Previous P193 reader code main CI: https://github.com/ngluonghoa/MFX/actions/runs/44344989098
