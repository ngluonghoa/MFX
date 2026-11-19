# MFX P0.199 — Investigate fresh owner P192 Sydney D1 source-day lag

## Incident, independently observed

The protected-main OAuth GET-only native source audit #44581413611, job #135762746928, completed SUCCESS on 19 Nov 2026 at ~17:51 UTC. This is a SHA/read/custody success, **not** a D1 freshness success. Its redacted `d1_fresh_epoch_readonly` receipt says owner epoch `P192_D1_FRESH_20261118` is still one manifest/chunk and one closed candle, `last_native_open_label=2026-11-18`, but `latest_expected_closed_local_label=2026-11-19`, `active_d1_calendar_lag_not_market_sessions=1`. MFX must not splice old 11-Nov/earlier D1 values; do not falsify source or remove the immutable archive/quarantine.

The existing scheduled native H4/D1 writer in `.github/workflows/mfx-native-htf-incremental-commit.yml` uses `25 * * * *` UTC, a four-variable configuration gate, owner `MFX_D1_OWNER_CUTOFF_20261118=true` and provider quota checks. Its P192 epoch code is intended to append CLOSED Sydney-local sessions after the 18-Nov starting cutoff; new 19-Nov session is a valid candidate only after the proper close+2m15s publication guard. At 17:51Z 19 Nov that criterion is met, but source is still one bar. Whether the writer skipped/delayed, quota refused, vendor returned stale snapshot or the 18-Nov overlap SHA changed is **not proven** from read-only audit alone.

## P0.199 atomic diagnostic

- Generalize the already tested P197 bounded historical GitHub-run timestamp parser to accept exactly two approved fixed workflow names/cron minutes: existing M5 writer `twelve-data-cache.yml` (:10), and existing native H4/D1 writer `mfx-native-htf-incremental-commit.yml` (:25). No arbitrary URL/name may be passed.
- New `tools/read_mfx_native_writer_runs_from_pr.py` reuses the existing P037 PR-only official GitHub API/Actions-read token boundary and prints a non-authorizing, no-OHLC native schedule run ID/status/timestamp report. One added **best-effort read-only** step in the existing P037 CI job, no new cron, no quota/API usage, no producer/cache code change, no OAuth scope change. Five synthetic trust/masking tests, exact SHA allowlist.
- After exact-head PR CI, inspect **actual run IDs** from the new PR-only GH API receipt; use connected GitHub job-log readback on those specific native writer runs to diagnose P192 fresh D1 lag. Never infer source commit/readiness from GH workflow success alone; the writer may deliberately print NO_NEW_CLOSED_SLOT, a quota hold or changed-overlap quarantine without failing the job.

## Release STOP

MFX source P192 from 18-Nov remains immutable and strictly no-splice, 0/36 original B2/S2 numeric signoffs, BID/ASK account rights/SLTP net R, publisher first-known, and independent untouched chronological OOS not accepted. No automatic BUY/SELL/trade. The owner Nov22 target is conditional GO/NO-GO. Need actual D1 writer log before any source-price write or code repair.

**Required QA:** exact PR-head Python3.11/3.12, frozen Forex 102 SHA/golden/security/wheel parity, controlled squash-only merge, independent protected main-push CI, plus separate actual scheduled native writer log witness. Rollback only this metadata read-only observer + test/docs + blob SHA allowlist.
