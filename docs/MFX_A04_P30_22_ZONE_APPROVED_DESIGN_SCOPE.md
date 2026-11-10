# A04/P0.30 — User-approved MFX 22-zone design taxonomy (NON-ENTRY mirrors)

**Approved by user on 2026-11-10 for MFX design only.** The previous [P0.29 source audit](MFX_A04_P29_ELEVEN_PAIR_SYMMETRY_AUDIT.md) identified three missing non-entry mirrors, and the user explicitly approved adding all three. This is not an approval of numerical strategy parameters, historical/real-market data rights, price-based detector execution or live BUY/SELL/EXIT alerts.

## Current effective MFX design count: 22 labels (11 qualitative mirror pairs)

| Category | Existing labels | New user-approved MFX-only labels | Total |
| --- | --- | --- | ---: |
| BUY/LONG entry design candidates | B1,B2,B3,B4,B5,B6,B8,FX-B9 | *None* | 8 |
| SELL/SHORT entry design candidates | S1,S2,S4,S5,S6,S7,FX-S9,FX-S10 | *None* | 8 |
| WATCH_ONLY | B7 | **FX-S11** (technical SHORT-side countertrend WATCH in uptrend) | 2 |
| EXIT_LONG_WARNING_ONLY | S3,S8 | *None* | 2 |
| EXIT_SHORT_WARNING_ONLY | *None* | **FX-B10**, **FX-B11** | 2 |
| **Total** | **19 prior MFX** | **3 newly approved, non-entry** | **22** |

The **eight** entry candidate families remain: B1↔S1, B2↔S2, B3↔S4, B4↔S5, B5↔S7, B6↔FX-S9, B8↔FX-S10, FX-B9↔S6. The additional non-entry families are B7↔FX-S11, S3↔FX-B10 and S8↔FX-B11. **11 conceptual mirror pairs ≠ 11 BUY entry +11 SELL entry.** There are still **16 entry design candidates**, and all **16 lack source-owner-approved numeric predicates**.

### Three new MFX-only design roles (no changes to inherited Forex)

| New label | Qualitative R0 and detection intent | Permitted future scope only | Explicit denial |
| --- | --- | --- | --- |
| **FX-S11** | D1/H4 causal uptrend, temporarily extended toward known resistance; potential down correction/rejection | WATCH_ONLY (B7's mirrored SHORT-side research), zero entry orders | May never transform into SHORT entry because of watch hypothesis |
| **FX-B10** | D1/H4 downtrend reaches predeclared trough/support/TP; M15 CLOSED recovery hypothesis | EXIT_SHORT_WARNING_ONLY to protect a **verified existing SHORT position**, no independent BUY | No open SHORT → WATCH_ONLY/NO_SIGNAL, never entry BUY |
| **FX-B11** | D1/H4 downside acceleration/failed low, potential exhaustion/capitulation, CLOSED causal M15 rebound evidence | EXIT_SHORT_WARNING_ONLY after verified SHORT and approved risk economics, no BUY | No open SHORT, no causal exhaustion proof or no signed rules → NO_SIGNAL |

Detailed **R0 / R_C / R_E / R_F hypotheses** and evidence/provenance are pinned to the [user-approved JSON design contract](MFX_A04_P30_22_ZONE_APPROVED_DESIGN_OVERLAY.json). Conditions such as pivot strength/right-bar count, price distance, time window, ATR, ADR, spread, swap, broker fill, market-session calendar, risk gates, TP/SL and closed-bar as-of timing all remain unsigned **PENDING NUMERIC CALIBRATION**. Do not copy thresholds from existing mirrored labels.

### Position, overlap and anti-double count rules

- The label prefix **B** or **S** here denotes historical naming, not permission to enter LONG/SHORT: FX-B10/FX-B11 are *only* prospective exit-SHORT warnings, not BUY entries; FX-S11 is only a SHORT countertrend WATCH, not SELL entry.
- A genuine verified SHORT position (position ID, symbol/side, lifecycle, source-first-known, authorized risk plan) is prerequisite to any later exit-SHORT warning. The current P0.30 module accepts an asserted SIM boolean **for design preview only**; this is not actual verification. It always returns **NO_SIGNAL** and `may_publish=false, may_auto_exit=false, may_open_position=false`.
- A stretched-down event may be considered by B7 WATCH and FX-B11 EXIT_SHORT; a stretched-up event may involve FX-S11 WATCH and S8 EXIT_LONG. One instrument/calendar/origin event creates one research opportunity, but ownership and position role remain distinct; never duplicate order/alert or infer that a watch is an exit or new opposite-side entry.
- An unproven as-of candle, unknown original event, future-known pivot, absent licensed native BID/ASK, unapproved source rules or unverified position fails closed. Even if a position claim is present, **no live warning or broker action is authorized**.

### What stays frozen and historically truthful

The original `ngluonghoa/forex-trading-1-0` at commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`, tree `5df2058346f6dc96ed5bb02581b139fe2aa2d803` remains **18 original source labels** and original 11 source-locked Docs unchanged. The earlier MFX [P0.28E design overlay](MFX_A04_P28E_FXB9_DESIGN_OVERLAY.json) remains the historical approved **19-label** version; the [P0.29 audit contract](MFX_A04_P29_ELEVEN_PAIR_SYMMETRY_AUDIT.json) remains a historical **proposal-only** snapshot. Neither is rewritten to pretend they always contained the new three labels. **P0.30 composes and supersedes them only for the current effective MFX DESIGN view: 22 labels.**

The SHA-sealed, separate `mfx_research/p030_approved_nonentry_design.py` defines `Mfx22DesignReceipt` and an entirely non-actionable review-only preview. It never mutates frozen `src/`, invokes a Forex provider, reads/writes real market data, generates alerts or enters/exits orders. CI pre-registered [Issue #52](https://github.com/ngluonghoa/MFX/issues/52) 24 positive/negative scope, provenance, type, role, anti-rollback and nonpromotion checks. Exact per-file Git blobs are SHA-pinned in `docs/MFX_ALLOWED_BASELINE_DELTAS.json`.

**Still blocked:** [Issue #45](https://github.com/ngluonghoa/MFX/issues/45) B2/S2 36/36 original numerical source owner obligations and 0/16 approved MFX entry numeric predicates; [Issue #27](https://github.com/ngluonghoa/MFX/issues/27) licensed historical native BID/ASK, vendor rights, real Drive market price cache, replay cost/OOS evidence. No live BUY/SELL signals, exit notices, broker orders, market data cache or release. Require exact PR-head hosted CI and independently verified postmain push CI before calling technical QA complete.
