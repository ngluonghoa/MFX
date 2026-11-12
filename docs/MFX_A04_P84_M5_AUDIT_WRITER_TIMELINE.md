# A04/P0.84 — M5 audit / writer / Drive timeline reconciliation (OFFLINE ONLY)

## Observed UTC evidence — 12 November 2026

This research-only milestone is independent of native V2 witness/CAS authorization, H4 source reduction and the original Forex 102 frozen blobs.

1. Existing READ-ONLY M5 audit GitHub Actions #43147634815 / job #130949076226 at 03:21:30 UTC reported last_manifest_hour_utc=2026-11-12T01:00:00Z, last_hour_lag=1, manifest_count=32, full_history_audited=false, and status LAGGING_OR_MARKET_CLOSED_NEEDS_REVIEW. A prior run #43137338521 at 01:51 UTC reported last_hour_lag=0. This is NOT independently diagnostic of missing bars.
2. Existing M5 scheduled writer GitHub Actions #43151652891 / job #130962013389 was created at 03:58:01 UTC and completed approximately 03:58:29 UTC. Its log reported BATCH_COMMITTED for committed_hours_utc=[2026-11-12T02:00:00Z], twelve M5 bars, vendor_price_requests=1, broker_orders=0.
3. Independent Google Drive manifest-folder listing contains file MFX_TD_EURUSD_M5_V2_manifest_20261112T0200Z_478840990e3a8bc4a745da5d694a98193aa5f614bd1abad92f487a530a213d76.json created at 03:58:23 UTC. The earlier 01:00 slot name is present. No duplicate M5 hourly slot name was found in the bounded 33-manifest listing. A file NAME alone is not cryptographic file-content proof.
4. The existing GitHub M5 workflow cron is UTC :10. The theoretically eligible :10 tick for the closed 02:00–03:00 UTC batch is 03:10. The observed writer-run creation at 03:58:01 occurs 48 minutes 1 second after that tick. This is observed elapsed time ONLY: actual scheduling/queue delay cause, provider publication, concurrency queue, and potential catch-up semantics are unproven.

## New pure code and QA

tools/mfx_m5_schedule_reconciliation.py accepts immutable caller-supplied audit, writer, and Drive name/timestamp observations. A positive fail-closed receipt requires the audit before writer, BATCH_COMMITTED, next consecutive hour exactly, matching SHA-shaped Drive manifest filename identity, Drive creation inside the writer-run interval, and reported audit lag equal one. It returns LATE_NEXT_SLOT_MANIFEST_OBSERVED, not FULL_HISTORY_VERIFIED or OUTAGE_FIXED.

The targeted hermetic negative suite rejects off-grid/naive UTC, stale audit, fake full history, wrong hour, malformed filename, mismatched source/symbol, Boolean/negative lag, invented chronology, and suspicious writer state. The module does zero HTTP, Google Drive, vendor, broker operations and never changes a live schedule.

The existing P0.83 classifier remains independent. Even a positive receipt does not prove full historical SHA chain, verified weekend/market-session/holiday calendar, vendor retention rights, GitHub root cause, or a trusted external witness. Real historical SHA integrity is a separate read-only qualification. Source-native H4 must remain in service unless >=30 exact 48xM5 fully closed matching H4 windows over >=7 days incl true session gaps and separate owner approval. Live V2/witness, HOT, numeric FX source approvals and broker are gated.

## Next

Collect independently authenticated read-only M5 bounded SHA history and audit following the 02:00 manifest; investigate late GitHub run creation separately from vendor response and shared concurrency. Do not auto-change schedules, variables, secrets, production Cache, H4 source, or rights. Cloud GitHub + Drive only, never Mac/MOCHI/local.
