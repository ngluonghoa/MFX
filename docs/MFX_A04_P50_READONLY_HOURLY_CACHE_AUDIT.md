# MFX A04/P0.50 — Read-only hourly cache audit

Status: **STAGED — pending CI, merge and real GitHub Actions audit receipt.** No broker or numeric signal approvals. The original Forex Trading 1:1 source is unchanged.

## Verified live prerequisites

- OAuth bootstrap job #42877139410 attempt 2: PASS, folder IDs read back.
- B3B synthetic two-write same-file proof #42873128914: PASS.
- V2 live first-hour batch #42882112799: `BATCH_COMMITTED`, 12 closed EUR/USD M5 bars for **2026-11-10 18:00–18:55 UTC**, with derived M15×4, M30×2, H1×1.
- Google Drive independently yielded exactly one V2 chunk (ID `1TWCucH41VYmrbsLOiOMusQpfY8VqBZt9`) and one linked manifest (ID `15yyvo3r1larXtUnCXtbdVqQAsDjXVupg`).
- First manifest says `BOOTSTRAP_HISTORY_UNVERIFIED`, which is correct for the first recorded batch; this does **not** yet prove two consecutive committed hours.
- Vendor retention/caching rights are **not independently verified**. User-directed private caching does not change that fact.

## Hourly schedule

- V2 writer: UTC minute **10**, gated by both `MFX_REAL_CACHE_ENABLED=true` and `MFX_V2_BATCH_CACHE_ACCEPTED=true`.
- New audit: UTC minute **35**, same dual gate and the same single-writer GitHub Actions concurrency group. GitHub scheduled runs can be delayed.
- Audit authenticates with the same three OAuth GitHub Secrets and the app-created private Drive `CHUNK` and `MANIFEST` folder IDs.
- **No Twelve Data API key is passed**, no vendor call, no Drive mutation, no user signals and no broker orders.

## Verified properties and limits

- Enumerates immutable V2 chunk/manifest names and rejects duplicate manifest hours.
- Re-reads and validates up to the most recent **three** paired JSON objects and their exact canonical SHA256 names.
- Checks each manifest's referenced chunk SHA256, hour and parent reference.
- Checks adjacent manifest parent SHA and the continuity/gap declarations.
- Emits `MFX_A04_P50_READONLY_DRIVE_CACHE_AUDIT_PASS` plus a JSON receipt with last hour, lag, count, continuity and SHA.
- `FRESH_LAST_CLOSED_HOUR` means cached last hour equals the latest full UTC hour. `LAGGING_OR_MARKET_CLOSED_NEEDS_REVIEW` flags lag but is not proof of an error (weekends, provider closed sessions and GitHub schedule delays exist).
- If more than three manifests exist, `full_history_audited=false`: **the whole history is not certified**. This is only a rolling tail verification. In particular, it is not a Drive transactional compare-and-swap.
- Hash/parent corruption and missing objects cause a failed Actions job. The audit never repairs or deletes data.

## Acceptance and recovery

1. Require MFX PR CI on Python 3.11 and 3.12 and cross-Python parity.
2. Merge via governed protected `main`; confirm post-main CI.
3. Manually dispatch `MFX V2 Hourly READ-ONLY Cache Integrity Audit` on main or use its next scheduled run.
4. Check log marker `MFX_A04_P50_READONLY_DRIVE_CACHE_AUDIT_PASS`, `read_only=true`, `twelve_data_api_calls=0`, `broker_orders=0` and actual Drive counts.
5. Independently confirm a *second* B1 hourly writer manifest before claiming `CONTIGUOUS_WITH_PRIOR_BATCH` across two hours.
6. On failure, do not delete/change sealed files; disable V2 writer with either activation variable if integrity is compromised and examine the exact failed object.
