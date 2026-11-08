# M1/P0.2: Provider-declared Forex calendar, DST and temporal evidence

Design reference: canonical 02 Master Spec v0.8 (source quality, calendar, DST and first-known). The goal is **fail-closed REFERENCE / read-only acceptance tests**, not real broker-calendar authorization.

## Contract
- `SourceCalendarPolicy` records provider, immutable calendar/timezone policy IDs, IANA zone name, TZDB version **claim**, explicit daily rollover wall time, and when that policy was first known. The actual local `ZoneInfo` installation is **NOT** cryptographically pinned by this claim.
- `resolve_local_wall_time` resolves **naive source wall time** to UTC. Ambiguous DST fall-back overlap requires an explicit 0/1 fold. Nonexistent spring-gap time always fails. Zone alias typos fail, no implicit UTC fallback.
- `SessionEvidence` is a versioned explicit provider-announced UTC window with its own first-known timestamp and source revision. No generic "weekend closed" assumption, and absent quotes never proves currency market closure.
- `validate_session_ledger` rejects duplicate IDs and overlapping windows per provider/calendar revision.
- `assess_bar_source_calendar` validates whether the claimed policy, session, source and bar identity/time align and were known as of decision cutoff. A D1 bar checks that both endpoints respect a **source-configured** wall rollover; a 25-hour bar across New York DST fall-back is valid. **W1 remains BLOCKED** until its actual week-boundary policy is specified. Bar lifecycle/coverage/quality is an **independent additional** gate (evaluate_closed_bar must still pass).
- CalendarGate result `VERIFIED_CONTRACT_INPUT` means local internal consistency of **provided synthetic/claimed metadata**, not independent provider authenticity, data entitlement, market open time, signal confirmation, trade permission, or an active release.

## Synthetic regression cases (not full formal FX-DC acceptance)
DST overlap, fold 0/1 and malformed folds; spring-gap rejection; invalid zone; source/provenance and calendar revision mismatch; first-known future policy/session/bar exclusion; session ledger overlap; missing session vs no-trade; provider-defined 17:00 rollover D1 25h fall-back; rejection of unspecified W1 calendar; separate bar quality failure still blocks.

## Open production gates
Real broker/vendor documentation & legal rights to use historical BID/ASK; provider event time semantics and detected ingestion first-known; frozen tzdb dependency/rules version; explicit source session/holiday/rollover/week start and unannounced closures; session/source revision persistence; replay and fill/margin/TP/SL. No live market execution. Does not alter Forex 18 design zone labels, B2/S2 trading thresholds or research-only FX-B9.
