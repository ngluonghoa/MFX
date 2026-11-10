# A04/P0.29 — Full symmetry audit: 8 entry pairs + 3 missing non-entry mirrors

**Status: MFX-only evidence review and unapproved design proposals (2026-11-10).** The user has approved comparing all pairs and finding counterparts for B7/S3/S8, **not** approved additional source-strategy numeric rules or an active 22-zone catalog. Do not reinterpret a `WATCH_ONLY` or `EXIT_*_WARNING_ONLY` as a fresh BUY/SELL signal.

## Audited source
Frozen original Forex Trading 1.0 commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`, tree `5df2058346f6dc96ed5bb02581b139fe2aa2d803`. [Source-locked detector audit](https://docs.google.com/document/d/10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA/edit) and [exact 18-row source evidence matrix](MFX_A04_P27_SOURCE_EVIDENCE_MATRIX.json); MFX-only [FX-B9 overlay](MFX_A04_P28E_FXB9_DESIGN_OVERLAY.json) and [S6 ambiguity review](MFX_A04_P28F_S6_FXB9_SYMMETRY_SCOPE.md). The JSON companion contains the **exact source text and paragraph anchors for every R0, R_C, R_E, R_F phase** in all eight pairs; no sampled, invented or copied numeric thresholds.

## Eight existing entry candidates — reviewed qualitative mirrors, not verified equality

| Pair | BUY | SELL | Current asymmetry / evidence question |
| --- | --- | --- | --- |
| E01 | **B1** | **S1** | B1 uses prior-downtrend/support and closed H4/D1 BOS_UP+HL; S1 uses prior-uptrend/resistance and closed BOS_DOWN+LH. Confirmed causal pivot rules, observation window and invalidation differ. |
| E02 | **B2** | **S2** | B2 M15 early HL or reclaim vs S2 rejection/LH/BOS_DOWN. H1 support/EMA/session-low vs resistance/EMA/session-high, spread/cost and 36 exact quantitative source obligations pending. |
| E03 | **B3** | **S4** | B3 false breakdown at lower predeclared H4/H1 range; S4 failed upper breakout/sweep. Source does not approve touch counts, lookback, range threshold, event overlap priority. |
| E04 | **B4** | **S5** | B4 source explicitly requires confirmed first HL with right bars; S5 says causal first LH complete but does not separately state identical right-bar algorithm. Verify causal confirmation each side. |
| E05 | **B5** | **S7** | B5 upside breakout/retest former resistance; S7 downside breakdown/retest former support. Compare pre-known origin, retest age/ATR, micro-high vs micro-low, false break/reclaim. |
| E06 | **B6** | **FX-S9** | B6 R_E allows M15 near upper boundary OR valid micro-break; FX-S9 R_E explicitly requires CLOSED+VERIFIED break below lower boundary. Their early stages are not literally symmetric. |
| E07 | **B8** | **FX-S10** | B8 includes confirmed M15 breakout quality/spread, ADR extension; FX-S10 requires closed verified M15 downside break and warns against defining momentum from one long candle. Additional quality gates not demonstrated equal. |
| E08 | **FX-B9** | **S6** | MFX-only FX-B9 outside sideways range and original S6 bullish trap pivot. S6 original R_C states 'return to range' ambiguously; outside-range subtype proposal in P0.28F is not inherited/approved numerical source. |

**No new entry label is justified solely by this review.** All eight pairs map to distinct, inherited/MFX-approved design families. None has owner-signed symmetry of numerical predicates, lookbacks, spread, cost, invalidation, TP/SL, expectancy or untouched OOS evidence. B2/S2 retain **36/36 unsigned source quantification obligations** in [Issue #45](https://github.com/ngluonghoa/MFX/issues/45). B3/S4 own inside-range failures; FX-B9/S6 is the outside-structural pair only as **MFX qualitative proposal** because original S6 R_C says ambiguously `return to range`.

## Three missing non-entry mirrors — candidate labels, NOT additions to approved catalog

| Existing original | Proposed MFX-only mirror | Position role / why not new entry |
| --- | --- | --- |
| **B7** — technical LONG rebound *watch* in D1/H4 downtrend | **FX-S11** — technical SHORT correction *watch* in D1/H4 uptrend | WATCH_ONLY on both; no entry SHORT |
| **S3** — protect/exit verified LONG at upswing peak or approved target | **FX-B10** — protect/exit verified SHORT at downswing trough or approved target | EXIT_SHORT_WARNING_ONLY; no entry LONG |
| **S8** — downside reversal warning after upside blow-off, exit LONG only | **FX-B11** — upside reversal warning after downside capitulation, exit SHORT only | EXIT_SHORT_WARNING_ONLY; no entry LONG |

Proposed four-phase behavior:
### FX-S11 mirrors B7 — WATCH_ONLY
- **R0:** Confirmed D1/H4 UPTREND with causal HH/HL; potential countertrend downward relief only; not a trend-reversal verdict.
- **R_C:** Price extension vs as-of ATR and/or known H1/H4 resistance; deterministic predeclared level and spread quality still PENDING.
- **R_E:** CLOSED M15 rejection/CHoCH_DOWN with event ID, own first-known and retrieved times; research/watch only.
- **R_F:** No trade by default; any later review requires separate owner numerical approval, OOS and countertrend risk policy; no short-entry promotion.

### FX-B10 mirrors S3 — EXIT_SHORT_WARNING_ONLY
- **R0:** H1/H4 downtrend, preknown target/support and verified OPEN_SHORT position required to issue exit advice; otherwise WATCH_ONLY.
- **R_C:** Approach approved TP/support with as-of ADR/exhaustion or risk invalidation check; no hindsight or price-side confusion.
- **R_E:** CLOSED M15 causal CHoCH_UP or source-verified approved TP trigger; no unsourced fill assertion.
- **R_F:** CLOSED H1/M15 break above known minor lower-high/micro-resistance or independently approved actual TP fill event; can only warn/exit verified SHORT, never enter LONG.

### FX-B11 mirrors S8 — EXIT_SHORT_WARNING_ONLY
- **R0:** Downside D1/H4 price acceleration vs historical as-of return/ATR distribution; not an assertion of final major bottom.
- **R_C:** Measure causal lower wick/failed downside extension and exhaustion without volume-climax requirement, with prior known quote lineage.
- **R_E:** CLOSED M15 failed low/micro CHoCH_UP with first-known event timestamp; no future-confirmation leak.
- **R_F:** CLOSED H1/H4 micro-resistance recovery provides warning/exit SHORT only with verified position/rights and risk policy; never entry LONG.

**Overlap and false-positive requirements:** Protect/exit requires independently verified open position and economic/trading rights; a watch does not infer a position. After a downtrend stretch, B7 WATCH and FX-B11 protective might fire on the same *observation*, but both refer to one source event and cannot double-count trade or convert to opposite entry. Likewise S8/FX-S11 on an upside stretch and S3/S8 or FX-B10/FX-B11 for one position event. Missing as-of range, pivot, origin event, closed candle, first-known/retrieved history, actual bid/ask, session/DST/cost or owner signoff -> UNKNOWN or NO_SIGNAL.

## Counts — two different states, never mix

| State | BUY entry | SELL entry | WATCH-only | Protective-only | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen original Forex | 7 | 8 | 1 (B7) | 2 (S3,S8) | **18** |
| **Currently approved MFX design** | **8** | **8** | **1** | **2** | **19** |
| **If owner later approves all 3 proposals** | **8** | **8** | **2** | **4** | **22** |

Approval would still be *design-only*, not signed numerical execution rules. The 11 conceptual pairs comprise 8 entry families and 3 watch/protection families, not 11 BUY and 11 SELL trade entry pairs.

## Preconditions for any future active catalog update
(1) Explicit owner approval of three names and scope including position-state semantics, (2) MFX-only versioned overlay (do not mutate immutable Forex source, original 18-row evidence audit, or source-locked Docs), (3) documented two-side exit/alert router avoiding new-position misinterpretation, (4) causal bid/ask/first-known event model, (5) covered R0/R_C/R_E/R_F and negative/no-position/replay/collision tests, (6) exact SHA and independent PR-main CI/QA. Existing numeric policy + licensed real-FX/Drive market cache gates remain **BLOCKED** ([Issue #45](https://github.com/ngluonghoa/MFX/issues/45), [Issue #27](https://github.com/ngluonghoa/MFX/issues/27)).

The issue [#50](https://github.com/ngluonghoa/MFX/issues/50) preregisters 22 audit tests. [JSON source-anchored contract](MFX_A04_P29_ELEVEN_PAIR_SYMMETRY_AUDIT.json). No broker orders, no true real-price signal, no production cache, no release from this audit.
