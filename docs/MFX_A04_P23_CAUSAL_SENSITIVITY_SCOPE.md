# A04/P0.23 — deterministic B2/S2 causal sensitivity QA (DRAFT / NO MERGE)

Pre-registered scope: https://github.com/ngluonghoa/MFX/issues/35#issuecomment-6744031508. Baseline protected P0.22 squash main 90219a02a49c6c710d4f3ee379a263b5e5602868. This is isolated test-only code, not runtime implementation, source-approved numeric threshold, broker integration or licensed real data.

## Exact test inventory

- tests/test_a04_p23_sensitivity_boundaries.py: **21 independently grouped unittest methods**, each with B2 and/or S2 subcases. Separate strict-neighbor OHLC oracle enumerates right-bar confirmed pivots with left/right 1..3; first known/retrieved clocks, future retrieval and incomplete candles are denied; tie and dual high/low ambiguity rejected; insufficient input and fake SIM policy fail closed.
- Decimal boundary tests cover near-zone equality vs epsilon outside, anti-chase threshold epsilon either side, latest M15 micro-level strict close break, opposite/UNKNOWN D1/H4 trend, explicit structural invalidation, and H1 true-range recalculation for changed ATR periods. Also denied: future/revised M15 micro seed, wrong quote side, pair and calendar. Deterministic event replay only; persistent duplicate suppression NOT implemented.
- tools/run_a04_p23_sensitivity_demo.py: CI-only exact 21-test inventory and explicit 36/36 pending source obligations, zero confirmed real BUY/SELL, no feed/cache/trade/release permissions. CI workflow retains original 50 Forex frozen source golden, 34 frozen wrapper parity, source coverage/mutation and all A04/P0.1-22 gates, strict Ruff/mypy, static/security and cross-wheel parity. New paths SHA locked by docs/MFX_ALLOWED_BASELINE_DELTAS.json. No src changes.

## Known limitations / STOP

- Existing P0.20 research receipt uses ClaimedStructuralContext default structure_invalidated=False; this test suite can deny an explicitly invalidated scenario, but **does not** independently establish real H1/H4 structural invalidation or source numeric Forex parity.
- origin_event_id is propagated but **no persisted idempotence/expiry** has been implemented. Synthetic replay equality must not be misrepresented as duplicate prevention.
- Synthetic 24-hour D1/H4/MID prices cannot validate broker FX DST/weekend/session/rollover, native BID/ASK+spread, ADR/news, net TP/SL R, out-of-sample data or licensed Google Drive price-cache rights. Vendor entitlement remains BLOCKED on Issue #27. MFX is informational BUY/SELL signals only, never broker orders.
- All 36 original B2/S2 numerical requirements remain not approved. No original source module, source-locked Doc, Forex Trading 1.0 or MOCHIFX edits; Cloud GitHub+Google Drive only.

## Gated delivery

P0.22 PR #34 exact-head run 42635338643 passed 3/3, but the **independent GitHub Actions push run for main commit 90219a02... has not been positively retrieved/verified** (GitHub connector commit-run method exposes pull-request runs only, public browser fetch unsuccessful). Therefore keep this P0.23 **DRAFT PR UNMERGED**, even if its PR CI passes. Once older checkpoint has verified post-main 3/3, independently review P0.23 exact-head 3/3; squash only with unchanged protected main and exact SHA; then verify its independent postmain 3/3 and update four canonical Drive Docs. No silent bypass.
