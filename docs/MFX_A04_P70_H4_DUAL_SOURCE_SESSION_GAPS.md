# MFX A04/P0.70 — Dual-source H4 UTC session-gap research (no automatic weekend waiver)

Date: 2026-11-11 ICT. Owner-approved follow-through from P0.65–P0.69; new additive Cloud-only research diagnostics. Original 102 Forex Trading source files and source-locked Docs, trading rules, broker, M5 and H4/D1 source-native GitHub hourly writers remain unchanged.

## Background and observed facts

P0.69 live owner-OAuth SHA audit #43024328457 authenticated 17 M5 V2 Chunk+Manifest pairs/204 M5, H4 source-native 3 pairs/121 bars, exactly 3 M5(48) derived H4 OHLC matches against native H4 on labels 2026-11-10 20:00, 2026-11-11 00:00 and 04:00 UTC; M5 archive latest hour 10:00 UTC, thus the 08:00–12:00 H4 M5 candle is still incomplete. Native H4 08:00 was already independently committed in P0.64 #43018791501 and verified by native H4+D1 read-only #43021908812. D1 native latest exchange-local Sydney session date 2026-11-10, 119 bars/1 pair, no actual next child yet. Direct Drive inventory check in this continuation also showed no M5 11:00 UTC hourly pair and no D1 2026-11-11-local child at that exact inspection. **No new failed job inferred solely from data delay.**

P0.66/P0.68 threshold currently demands >=30 exact MATCH H4 and first-to-last H4 starts spanning >=7 calendar days with ALL fully observed H4 timestamps strictly on consecutive 4-hour UTC grid. This is conservative. Without separately proven session gaps, actual Forex market closures/weekends could prevent achieving the criterion despite no source tampering. Conversely, blindly waiving weekend grid gaps could hide missed vendor candles, an outage or incomplete source history. Source publisher calendar behavior MUST be supported by independently verified data, not a blanket 24/5 or 24/7 assumption.

Twelve Data's public timezone guidance says Forex exchange default is Australia/Sydney (https://support.twelvedata.com/en/articles/5745849-timezones); intraday API accepts explicit timezone=UTC while D1 ignores that and remains exchange-local (https://twelvedata.com/docs). Twelve Data's Forex exchange page publicly advertises its own published trading-hours information (https://twelvedata.com/exchanges/physical_currency?group=reference), which should not be treated as a proof that every UTC four-hour grid slot actually carries a provider-native candle. Empirical native-to-M5 source inventory is still necessary.

## P0.70 standalone research component

Add pure `tools/mfx_h4_source_coverage.py` and call it from existing P0.66 **read-only** authenticated Drive M5/H4 parity auditor. Inputs are already full-SHA-verified source-native H4 UTC-open labels and fully derived 48-M5 H4 UTC-open labels; no HTTP provider requests are added.

Inspect the bounded UTC grid between FIRST and LAST complete M5->H4 shadow candles, max 72 UTC 4h slots (~12 days), classifying each label into exactly one category:
- BOTH_PRESENT: source-native H4 and complete M5-derived H4 both exist; numeric OHLC equality is separately decided by existing P0.65 comparator
- NATIVE_ONLY: source-native H4 exists but M5 does not have a complete 48-M5 H4; potential missing source minutes or session edge, NEVER a source replacement approval
- M5_ONLY: 48-M5 H4 complete but matching native H4 absent; native-source lookup/label/availability gap, never a match
- BOTH_ABSENT: neither source has a candle; optionally mark UTC Saturday/Sunday as a **weekend candidate**, not evidence that the vendor, broker, Sydney-local session or market was actually closed

Report bounded counts, UTC label samples (max 8) and explicit flags `h4_weekend_session_policy_proven=false`, `h4_weekend_gaps_auto_waived=false`, `h4_coverage_diagnostics_research_only=true`. This flags source discrepancies without logging any raw OHLC, secrets or trade instructions. All labels must match the strict P0.65 UTC 00/04/08/12/16/20 grid and typed source requirements.

**Critical no-behavior-change invariant:** existing P0.68 `h4_consecutive_4h_grid`, `h4_span_at_least_7_days`, `h4_parity_observation_threshold_met` computation, 30+ H4 matching threshold, fail-closed source gaps and the unconditional `may_replace_native_h4=false`, `may_reduce_native_h4_requests=false` stay untouched. Native D1 Australia/Sydney is wholly outside scope. These are diagnostics for later separate owner-controlled calendar and vendor-source session parity policy, not a migration to a new trade signal mode.

## Acceptance and later work

Add 16 hermetic tests: UTC Friday-to-Monday both-absent classified as WEEKEND_CANDIDATE (never auto accepted), weekday both-absent, M5-only, native-only, duplicate/unsorted labels, non-UTC clocks, invalid grid, >72-span cap, empty data, intact existing 3/3 path and zero provider/Drive/broker calls. Full hosted Python3.11 &3.12 unit/staged source parity, unchanged exact source 102 blobs, SHA-pinned MFX-only delta manifest, security/static and identical wheel; independently reverify protected-main push CI.

After merge, push-triggered owner-OAuth **READ-ONLY** P0.66 auditor must verify the actual native vs M5 coverage report with 17+ M5 pairs and 3+ H4 native objects, and continue exact OHLC comparison; no claims of a weekend session hypothesis accepted until weekend source history is actually observed and independently reviewed.

Future separately approved proposal (NOT implemented P0.70): a tested and versioned Sydney/UTC provider session calendar and source-native-gap policy, with gap-specific fallback and explicit user acceptance gates. Do not alter provider-native H4 cadence before 30+ exact matching **meaningfully comparable** H4 bars across seven days and session/holiday evidence. No hidden data filling, no premature BUY/SELL production or broker. Continue extending P0.69 checkpoint raw-source proof before 1024 hourly archive pairs, and verify the first native D1 incremental append separately.

Rollback: revert only the pure P0.70 diagnostics file, integration lines, tests/runbook and exact two new MFX-only SHA pins / modified auditor pin. Current M5/H4/D1 source archive and automation unaffected.
