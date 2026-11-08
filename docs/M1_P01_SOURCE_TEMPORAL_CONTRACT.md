# M1/P0.1 — Causal source/revision/closed-bar contract

**Scope: synthetic typed domain controls, no provider access.** Canonical functional contract: Google Drive 02 Master Spec v0.8 §§3–6, source and temporal requirements. This PR does NOT activate any approved Forex detector, broker execution or data acquisition.

## Invariants
- `Observation`: provider / stream / endpoint / source revision / raw SHA-256 / observed first-known UTC / retrieved UTC / source timezone-policy version / licence scope **CLAIM**. The digest proves identity for supplied bytes only, not independent authenticity, rights, accuracy or time semantics.
- `MarketBarKey`: pair/instrument version, timeframe, start/end UTC, calendar and aggregation policy versions, BID/ASK/MID side. The fixed M1/M5/M15/M30 duration is checked, but D1/W1/rollover/session/DST calendar is NOT invented.
- `MarketBar`: immutable positive finite Decimal OHLC, lifecycle OPEN/CLOSED, coverage COMPLETE/PARTIAL/SPARSE_UNVERIFIED/UNKNOWN/INVALID, source quality VERIFIED/WARN/UNVERIFIED/BLOCKED, revision number and separate first-known clock. CLOSED known before cutoff is rejected.
- `select_asof_revision()`: sees ONLY first-known-by-decision entries; rejects conflicting identity, duplicate revision and invalid chronology in the known prefix; future correction cannot alter a prior as-of decision. Does NOT certify completeness of a broker data revision ledger.
- `evaluate_closed_bar()`: fail-closed clock/lifecycle/coverage/quality checks. M15 complete CLOSED is base input; M5 requires explicit conditional arm plus preexisting HTF context. A verified MID bar can be used as reference but cannot be an executable quote-side. Nothing grants confirmation/ trade permission, even when read-only technical data is usable.

## Known future gates / exclusions
1. Real source/contract identity, BID/ASK historical access and license/retention/derived/replay entitlement verification;
2. Native provider timestamp semantics, first-known and revisions validated against independent ingestion receipts;
3. Source calendar/market sessions, DST, NY-close D1, Sunday candle, weekend rollover and no-quote vs no-trade semantics;
4. Causal pivot and policy-specific detector predicates and full-vs-incremental equivalence tests;
5. Spread/SL/TP/cost/position fill broker simulator and untouched OOS experiments;
6. Secured append-only storage, provenance custody and operational rollback drill.

**Meaning of tests:** synthetic contract/negative tests only. Status `UNIT_TESTED` may be assigned after actual GitHub Actions evidence but source licensing and `FX-DC-01..08` full formal acceptance are NOT passed merely by similarly named tests.

## Governance
Read-only GitHub M1 feature branch/PR/CI; no M15001 use, no MOCHI dependency, no actual Forex data persisted, no trade orders.
