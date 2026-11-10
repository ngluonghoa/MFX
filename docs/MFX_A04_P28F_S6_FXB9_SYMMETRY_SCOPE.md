# A04/P0.28F — S6 ↔ FX-B9 structural false-break symmetry audit

**Status: MFX design clarification / review only. Not a source numeric approval or executable SELL signal.**

## Audited source fact

The frozen Forex detector audit [SOURCE_LOCKED_03](https://docs.google.com/document/d/10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA/edit) defines original **S6 Bull Trap** at paragraphs 160–170. R0 (161) references an H1/H4 breakout pivot; R_C (162) says **"return to range"**, but this does not say whether "range" is a predeclared sideways H1/H4 range or the area below a known structural pivot. This is an *ambiguity*, not proof of S6 outside-range scope. R_E (163) refers to CLOSED M15 below the former pivot and R_F (164) refers to H1 below pivot and micro-support, still only hypotheses.

**S4** at paragraphs 138–148 explicitly covers the high side of an established H1/H4 sideways range; **B3** at 39–49 covers the low side. MFX-only **FX-B9** from [P0.28E](https://github.com/ngluonghoa/MFX/pull/47) covers proposed false downward breaks of predeclared structural support outside the sideways range. It is not an inherited Forex source label.

## Proposed MFX-only directional ownership table

| Context known before break | LONG / false break down | SHORT / false break up |
| --- | --- | --- |
| At an established sideways range boundary | **B3** (range lower edge) | **S4** (range upper edge) |
| Outside established sideways range at prior structural H1/H4 level | **FX-B9** (support bear trap, already MFX design approved) | **S6 proposed structural-outside variant** (resistance bull trap, review-only) |
| Context missing, conflicting, revised or future-known | UNKNOWN / NO_SIGNAL | UNKNOWN / NO_SIGNAL |

The existing S6 label remains the only proposed high-side structural false-break short; do **not** create a new SHORT label or rewrite the original Forex audit. Do **not** claim the original S6 already specifies this subtype conclusively. This is a **MFX-specific proposed scope clarification** requiring explicit versioned definition and original/parity differential review before numeric detectors are implemented.

Phase proposal for S6 within MFX only: **R0** causal prior H1/H4 resistance/pivot and upward-break event; **R_C** documented failure to hold and revisit below pivot; **R_E** CLOSED verified M15 below pre-known pivot; **R_F** higher-timeframe invalidation of upward break, prior-known micro-support loss, cost/spread/news/SL/TP and structural risks. All thresholds, lookbacks, pivot recognition, time windows, quote-side handling, anti-chase, risk economics and invalidation remain **PENDING**. Spot SELL candidate would later use **BID**, unlike FX-B9 BUY candidate **ASK**, but no execution fill is established.

## Why S6 cannot simply be called a numeric mirror of FX-B9

- SOURCE_LOCKED S6 says "return to range" and has no calibrated predicate for "outside range".
- There is no evidence of symmetric spread, stop placement, slippage, swaps, performance, sample sufficiency or untouched OOS.
- S4/S6 and B3/FX-B9 can overlap; deduplicate by original structural event and opportunity id, not matching rule count.
- If the prebreak sideways range / structural context is unclear, fail closed instead of promoting either variant.

## Immutable counts and hard gates

**Frozen Forex** 18 labels: 7 LONG candidates + 8 SHORT candidates + B7 WATCH + S3/S8 protection. **MFX overlay** 19 labels: 8 LONG (including FX-B9) + 8 SHORT (including S6, not a new label) + 3 watch/protective. These are design candidates, **0/16 numerically approved**. B2/S2 original 36/36 numerical requirements remain unsigned ([Issue #45](https://github.com/ngluonghoa/MFX/issues/45)). Licensed FX feed and raw Drive market quote retention remain blocked ([Issue #27](https://github.com/ngluonghoa/MFX/issues/27)). No source/src mutation, real quote ingestion, live alert, broker order or release.

Contract: [JSON reviewer matrix](MFX_A04_P28F_S6_FXB9_SYMMETRY_SCOPE.json). Review and test plan: [Issue #48](https://github.com/ngluonghoa/MFX/issues/48). This checkpoint must pass exact PR-head and independent new-main CI before being labeled complete.
