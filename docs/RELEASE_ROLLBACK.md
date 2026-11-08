# Versioning / rollback safety — M1 design and simulation only

Every future execution uses an immutable *complete* profile identity: code + dependencies + rules + parameters + provider + data revision + calendar + BID/ASK basis + cost/fill + risk + persistence schema + reporting schema.

Changing only a Git commit is NOT full rollback. Future release requires a previously approved LKG backed by PR/CI, source rights, data/replay, cost model, separate OOS and risk approval. No active or LKG release exists yet.

`assess_rollback()` currently evaluates limited read-only replay compatibility by checking source revision, provider adapter, BID/ASK basis and schema. The result is **never permission to deploy, switch versions, change database/cache state or touch broker positions**; external review remains required even if the synthetic preview is compatible.

Do not use a CI test label as an FX-VR acceptance receipt unless it maps to that formal case with exact run evidence. Provider entitlement, quote retention, backup, signature custody and broker safety require separate approved infrastructure.

Existing policy: [Google Drive 10_VERSIONING_RELEASE_ROLLBACK_STANDARD](https://docs.google.com/document/d/19z5m73GJgCu5AYCfio0JJGWHbcPJMwm___djxSq-GtA/edit).
