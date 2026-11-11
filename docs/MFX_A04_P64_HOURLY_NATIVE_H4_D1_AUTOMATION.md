# MFX A04/P0.64 — Owner-approved hourly native EUR/USD H4+D1 Cache writer

Date: 2026-11-11 ICT. User decision: **"Vẫn âm thầm giám sát đi, nhưng 1 giờ 1 lần được không?"** in MFX6, then on this turn explicitly chose to continue activating the hourly writer after the difference between manual P0.59 and scheduled M5/P0.58 was clarified. The first REAL P0.59 manually dispatched H4 incremental append was accepted 2026-11-11 09:17Z GitHub Actions #42993880950; independent SHA-construction plus first post-append scheduled P0.58 full read-only audit #42996305344 both PASS. D1 *incremental append* had not yet been observed. Scope remains private EUR/USD composite MID native H4 UTC labels and D1 Australia/Sydney session dates; **not broker quotations, bid/ask, execution, strategy signal activation, or any automatic trading**.

## Scheduled production workflow (existing protected main workflow, not a second cache engine)

Change the existing `.github/workflows/mfx-native-htf-incremental-commit.yml` from manual-only to **BOTH**:
- `schedule: - cron: "25 * * * *"` — once per hour at UTC minute 25 (equivalent to **xx:25 Vietnam time**). GitHub may queue, delay or omit scheduled jobs under load; this is best-effort hourly scheduling, not guaranteed exact-minute delivery or market data SLA.
- `workflow_dispatch:` — retains owner's manual diagnostic/operational fallback.
- The same `mfx-twelvedata-private-cache` cross-workflow concurrency group, `cancel-in-progress: false`, and read-only repo permissions `contents: read`. Sharing the lock is essential because Google Drive Chunk/Manifest creation is **not atomic multi-object compare-and-swap**.
- Same pinned checkout/setup actions, Python 3.12, Google OAuth/requests pinned dependencies, repository Variables, and GitHub Actions Secrets as the previously real-accepted P0.59. **No new variable, credential, repository or workflow entitlement required.** The fourth owner opt-in `MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED=true` was observed in the real P0.59 run; job-level GitHub Variables require all four exact `'true'` values, and Python independently refuses any run when one gate is missing.
- No `broker_orders`, trade API, HOT V3 deployment, numeric BUY/SELL approvals, M5 writer rewrite, legacy initial H4/D1 root rewrite or changes to the frozen 102 Forex source blobs.

### Hourly schedule layout, all UTC minutes

| Minute | Workflow | Source calls |
| --- | --- | --- |
| :10 | M5 V2 hourly private-Drive writer | Only its existing M5 source logic |
| **:25** | **P0.64 H4+D1 incremental native writer** | 0/1/2 according to P0.59 pure close/overlap plans; never request still-open bars |
| :35 | M5 V2 read-only cache integrity audit | 0 provider price calls / 0 writes |
| :45 | P0.58 H4+D1 full bounded SHA parent-chain audit | 0 provider price calls / 0 writes |

All four workflows share the cooperative Drive lock; manual dispatches of the same resource share it too. Scheduled and manual runs may queue; cancel-in-progress stays false to avoid aborting a Chunk+Manifest pair between its writes. GitHub cron's real start clock may drift; all eligibility decisions are computed from the actual execution UTC time, never the nominal cron timestamp.

## Exact operational path and protections (no changes from P0.59/P0.61/P0.62/P0.63)

Every run independently audits BOTH H4 and D1 Drive archives and computes `plan_native_fetch` from the actual time, retaining the **2m15 conservative candle-publication buffer** after the true H4 UTC four-hour close and after Sydney-local D1 midnight (IANA DST-aware). A cached latest closed slot means **ZERO** provider usage API calls, **ZERO** vendor OHLC price calls and ZERO immutable writes; this is expected on most hourly runs. If only one interval needs new closed bars, only that TF is fetched. If both need an update, there are at most two selective price calls in this run and both vendor envelopes are source/SHA validated **before** the first Drive append.

A04/P0.63 protects bounded capacity: if any due native archive has reached the 256 object per bucket+TF limit, fail before any vendor calls/Drive writes. P0.59 first checks the actual available daily credit quota (including the upstream `api_usage` call) and rechecks before the second price call. The source must match strict EUR/USD source-native MID, timezone provenance, no open bars, H4 UTC 00/04/08/12/16/20 grid, D1 source Sydney-local dates and last-16 SHA overlap. Changed historical bars, missing overlap, orphan chunks, changed parent archive, quota exhaustion or incomplete Drive write **fail closed**. Writes always append immutable Chunk then Manifest and read back their SHA; no planned automatic retry beyond the next eligible hourly run, no destructive cleanup and no broker instructions.

### Truthful run receipts

The same Python writer `tools.run_mfx_native_htf_incremental_commit.py` branches on GitHub-provided `GITHUB_EVENT_NAME` for reporting only, not for bypassing gates. On a **scheduled** run:
- `execution_mode=hourly_schedule`, `automatic_native_schedule_activated=true`; if a native provider fetch occurred and was SHA-validated, marker `MFX_A04_P64_HOURLY_NATIVE_INCREMENTAL_SHA_READBACK_PASS`. Per-interval receipt `NATIVE_INCREMENTAL_NEW_BARS_COMMITTED` versus `NATIVE_INCREMENTAL_PROVIDER_STALE_NO_NEW_BAR` still distinguishes actual writes from a stale but valid vendor response.
- If no eligible new H4/D1 slot: original marker `MFX_A04_P59_NATIVE_NO_NEW_CLOSED_SLOTS_ZERO_VENDOR_CALLS` plus JSON `NO_NATIVE_CLOSED_SLOTS_DUE` and **0** actual price/usage requests and Drive writes; scheduled mode still explicitly reported. This is NOT a skipped GitHub job or a system failure.
- If quota is insufficient: `MFX_A04_P59_NATIVE_QUOTA_NO_PRICE_REQUESTS` with `NOT_EXECUTED_INSUFFICIENT_QUOTA_HEADROOM`; log also says scheduled mode and indicates zero price/Drive writes. Do not claim a new native candle was saved.
- A manually dispatched run retains the preexisting `MFX_A04_P59_NATIVE_INCREMENTAL_MANUAL_SHA_READBACK_PASS` marker and reports `execution_mode=manual`, `automatic_native_schedule_activated=false`. Existing first owner-run acceptance remains reproducible.

The `automatic_native_schedule_activated` field means the GitHub-triggered `schedule` execution *in that particular run*, not a claim that the entire scheduling service guarantees successful execution every hour.

### First scheduled runtime acceptance (NOT proved by PR CI alone)

Once protected main merge+independent CI are green, the GitHub Actions workflow becomes eligible to run on the next hourly GitHub cron tick; verify the first **real event=`schedule`** run ID, actual head SHA, GitHub job not `skipped`, run log `execution_mode=hourly_schedule`, `automatic_native_schedule_activated=true`, and either valid no-new/zero-vendor receipt or real due-slot SHA-verified source ingestion. Compare native Drive CHUNKS and MANIFESTS before/after, and use the scheduled P0.58 read-only full SHA audit after a real append. The first D1 newly closed source-native appending, parent-chain SHA, M5 non-interference and quota are individually accepted only after those operations have actually occurred, not because unit tests passed. A GitHub success but an untouched D1 (not yet due) is **not** D1 append proof.

At the point of the 2026-11-11 16:44 ICT checkpoint, actual private Drive archives were H4 2 Chunk+Manifest pairs / 120 H4 closed bars (last UTC open 04:00), D1 1 pair / 119 D1 closed bars (last Sydney 2026-11-10), and M5 14 pairs. The next eligible Sydney-local D1 date 2026-11-11 becomes due at **2026-11-11 13:02:15 UTC (20:02:15 ICT)**; the next scheduled attempt after that is **13:25 UTC (20:25 ICT)**, subject to GitHub scheduler execution, Twelve Data actual publication, plan limits and credential/quota status. No operator action is normally needed after the workflow is merged, and **no immediate extra price call is triggered by the code/PR merge itself**.

### Controls and rollback

To pause automatic H4/D1 source writing immediately, set `MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED=false` in GitHub Actions repository Variables (this also blocks manual P0.59 until re-enabled). For **manual-only while leaving owner manual gate on**, revert the P0.64 workflow change that introduced `schedule`, through a protected-main PR+green CI; do not disable M5 or P0.58 audit. Preserve last known-good main release/source blob and CI provenance. A paused scheduler does not modify or delete previously created Drive data.

The external Twelve Data plan's permission for raw FX OHLC retention on private Google Drive and any 3rd-party restriction remains **account-specific and unverified**; no unconditional perpetual cache license is asserted. This change uses the already owner-approved source writer and does not grant distribution or storage rights. No local Mac/MOCHI compute, all code/data/CI in GitHub+Google Drive.

## Verification plan

- Hermetic tests `tests/test_a04_p64_hourly_native_scheduler.py` cover scheduled UTC cron, same lock as M5 + SHA audits, exact four gates and no broker, no-due 0 source/Drive, manual compatibility, scheduled H4-only/D1-only/both-due provider paths, quota fail-closed, false gates, and stale provider truth.
- Existing P0.59, P0.62, P0.63 tests that asserted manual-only are updated to require the approved hourly schedule while keeping legacy P0.55 manual-only. No other source/native SHA/price logic or 102 frozen Forex baseline blobs changed.
- Require full hosted Python 3.11/3.12 CI test suite, strict source/golden parity, static/security checks, cross-wheel parity, independent exact-protected-main push status, then independent evidence from the first **actual** scheduled job and Drive before marking live hourly schedule PASS.
