# MFX A04/P0.68 — Correct seven-day H4 parity qualification for partial archive edges

Date: 2026-11-11 ICT. Scope: P0.66 SOURCE READ-ONLY M5/H4 parity classification. This is a qualification logic correction only; NO changes to real M5 writer, H4/D1 source writer, authorized GitHub schedules, private Google Drive files, price provider usage, signals or broker.

## Actual evidence and the hidden permanent-veto bug

P0.66 first genuine authenticated GitHub Actions #43013931317 passed full source SHA and found 168 archived M5, 3 exact matching complete H4 shadow/native OHLC windows and one **partial initial H4 label 2026-11-10T16:00:00Z** because M5 archival root began at **18:00 UTC**, inside that earlier H4 block.

The P0.66 candidate threshold required `not shadow.skipped_incomplete_windows`, and status reported `INCOMPLETE_M5_WINDOWS_REVIEW_REQUIRED` once enough observed windows existed while ANY partial (even before the first fully observed H4) remained. Because that first partial window was immutable and permanently present in the full source archive, **a future 7-day span could never qualify**, even if every H4 *inside* the fully observed block matched native source. The unit test had started its synthetic M5 history at UTC midnight, missing this real boundary condition. This bug was found from the first real read-only source receipt rather than from speculation about provider behavior.

## Surgical correction

- Classify every H4 skipped because it lacked precisely 48 contiguous CLOSED M5 UTC bars as either:
  - **BOUNDARY_PARTIAL:** earlier than the first *complete* shadow H4 start or later than the last complete shadow H4 start; these excluded edge windows are **not fabricated** and are omitted from the candidate's comparison domain.
  - **INTERIOR_INCOMPLETE:** incomplete H4 on or between the first and last complete H4 starts; these are real source continuity holes that ALWAYS deny qualification. The existing strict consecutive 4h-grid check independently rejects gaps.
- Keep existing `m5_h4_incomplete_windows` reporting, add `m5_h4_boundary_partial_windows`, `m5_h4_interior_incomplete_windows`, bounded interior UTC samples; truthful metadata preserves visibility even if boundary partials are waived for the seven-day decision.
- Candidate `h4_parity_observation_threshold_met` requires at least 30 complete windows, **minimum 7 full days between the first and last observed complete H4 UTC starts**, all consecutive on four-hour UTC grid, 0 mismatches, 0 native-missing, **0 interior incomplete**. Boundary-only skipped windows no longer create a permanent veto.
- Any positive 7-day evidence remains OBSERVATIONAL ONLY. `may_replace_native_h4=false` and `may_reduce_native_h4_requests=false` ALWAYS; separate owner-approved PR and rollback require a later explicit decision.
- Preserve P0.66 app-owned Drive full SHA/parent checks, source-mid provenance, 48-M5 exact closed-bar computation, provider native H4 reference. No D1 Australia/Sydney synthesis or any numeric BUY/SELL approval.
- Tests: synthetic M5 archive root at UTC 02:00 and trailing partial at 192:00, but 47 complete 4h windows across >7 days must qualify observationally; subtract one interior M5 hour and qualification must fail; valid provenance with wrong native H4 high or missing native must fail; short boundary-only history is not sufficient. No raw OHLC leaks/writes.

## Acceptance

P0.68 changes only `tools/run_mfx_m5_h4_live_parity_audit.py` and adds one isolated test module and this runbook, pinned to the MFX approved delta SHA manifest. Require complete hosted Python3.11 and Python3.12 CI, frozen original 102 Forex source Git blob parity, cross-Python wheel, static/security and independently exact-main push CI; then a REAL P0.66 GitHub Actions read-only *push-triggered* rerun after the protected merge proving source SHA counts and new boundary/interior fields. Actual M5/H4 source 3/3 proof remains accepted historically but still not enough data. Current source native H4 hourly, native D1, existing M5 automated writer and P0.67 delayed-cron catchup unchanged. M5 full-chain initial 256-hour audit capacity and long-term retention-license proof remain separate unresolved engineering/owner conditions.
