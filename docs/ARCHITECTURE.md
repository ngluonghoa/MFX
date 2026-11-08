# M1: Dependency boundaries and design / code gap

**Design sources:** 02_MASTER_SPEC v0.8, 03_DETECTOR_AUDIT v0.7, 04_ZONE_TAXONOMY v0.5, 08_SIGNAL_LIFECYCLE, 09_TP_EXIT, 10_VERSIONING.

Future runtime layers are planned:

1. Source adapters / entitlement / revision / temporal data quality
2. Pure domain market features and market structure
3. Versioned rule manifest and eight-family zone predicates
4. Early/confirmed opportunity detection and de-dup by origin event
5. Risk and independent LONG/SHORT TP/ExitManager
6. Common-core causal replay with broker realistic cost/fill simulator
7. 8-stage audit & report DTO, independent locked UI presentation
8. Versioned cache, evidence, profile registry and rollback controls

M1 intentionally implements **only** read-only DTOs, the 18-label taxonomy, quote-side/as-of guards, pipeline stage identifiers, signal-stage vocabulary and full-profile identity.

Safety and evidence boundaries:
- No source access and no SELL/BUY signal predicate. A named catalog label is NOT an executable rule.
- Closed M15 verified candles are the design baseline; conditional closed M5 early logic and quantitative rules are NOT implemented.
- BID/ASK indicative side is NOT a fill. Trade eligibility requires source entitlement, spread/slippage/swap, exposure risk and broker position verification.
- At least one approved B2 LONG and S2 SHORT calibrated predicate and a licensed BID/ASK history with identical scan/replay logic are prerequisites for real Backtest.
- The new FX-B9 outside-range false-breakdown is a **research proposal** only; no catalog activation.
