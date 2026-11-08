# M2/P0.7 — Single / custom / all Forex scope over existing synthetic Smart Cache

**User approval 2026-11-07:** Forex Trading 1.0 shall support scanning exactly one pair, a user-selected subset, and all 20 approved pairs, with one shared calculation/quality/cache core and no unselected data refresh.

## Executable SYNTHETIC reference only

`src/forex_trading/scan_selection.py` adds an explicit immutable `ScanMode` selector and `plan_scan_selection`:

| Mode | Selected instruments | Unselected instruments |
| --- | --- | --- |
| SINGLE | Exactly 1 from the caller-supplied canonical 20-pair catalog | 19 skipped |
| CUSTOM | Any 2–19 distinct catalog instruments, user order retained | Others skipped |
| ALL | All 20, canonical catalog order | None |

Invalid/unknown/duplicated pairs, malformed catalog/mode, or wrong cardinality fail closed. No actual market universe is fabricated here; all symbols used in tests are explicitly synthetic (`TESTPAIR00` etc.). The GUI/UX selector is an approved design, **not implemented**.

`run_selected_synthetic_scan` dispatches only selected fixtures to the pre-existing `run_synthetic_five_minute_sweep`; it does not replace the L1 cache delta planning or indicate that real provider API calls have been implemented. For a single pair, all 19 others can be completely absent from in-memory fixtures; no history has to be loaded for them. The in-memory oracle used for tests is not proof that a provider would avoid server-side full downloads.

## Deterministic example, not real speed/bytes

The existing M2/P0.4 fixture has 20 FAKE instrument IDs, BID+ASK sides and M5/M15/H1/H4/D1 synthetic UTC timeframes. With two-bar overlap, caller-supplied head claims and one M5 step:

| Scope | Streams | Naive full-history counterfactual rows | Planned delta windows | Fixture returned rows | Claim-only head skips |
| --- | ---: | ---: | ---: | ---: | ---: |
| Single | 10 | 82 | 2 | 6 | 8 |
| Three selected | 30 | 246 | 6 | 18 | 24 |
| All 20 | 200 | 1640 | 40 | 120 | 160 |

These are deterministic **fixture counters only**. Head claims are not independently authenticated; silent old corrections remain possible. Real HTTP calls, bytes and wall latency all remain unmeasured; no actual provider rights/connection/persistent cache/5-minute scheduler exist. No operational scanner, no detector/eligibility or broker order path exists.

## Cache and scope invariants

- Scope selection happens **before** per-pair refresh planning. No skipped pair enters its delta calculation or influences selected counters.
- All selected pair-timeframe groups require both BID and ASK; incomplete, absent or duplicated selected partitions fail closed.
- Cached candle snapshots are immutable; repeated synthetic scans produce the same report without rewriting old bars.
- A hidden correction in an **unselected** pair must not force invalidation of the requested pair; explicit dependencies remain governed by the existing L1–L5 dependency DAG.
- ALL retains identical behavior/counters to existing M2/P0.4 synthetic 20-pair sweep.
- No fallback to full market-data history if the source lacks a bounded window. All `may_*` real-data/trading capabilities remain FALSE.
- A future real provider adapter must enforce selection *before* network requests and account for downstream cross-pair market-wide dependencies if approved (not assumed independent). Any actual 20 pair symbols/product mapping must be source and user-qualified.

## Open implementation and acceptance gates

1. Native editable 02 Master Spec/00 Handoff and 06 QA record this approved scope without pretending a UI is shipped.
2. Provider account-specific historical BID/ASK entitlement and cache/derived-data retention, residency and legitimate replay/backtest rights require independent evidence.
3. Encrypted durable cache/storage host with verified generation witness and restart/recovery drill requires separate approval.
4. Real HTTP adapter must prove no per-request unselected symbol fetch, bounded delta/partial correction handling, real bytes/latency/call counts and cache reuse across scan modes.
5. Full L2–L5 indicator/detector/audit integration, UI and end-to-end single/custom/20 scans remain NOT IMPLEMENTED; no financial backtest/OOS or live trades.
