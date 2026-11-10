# A04/P0.28E — MFX-only FX-B9 Bear Trap / False Breakdown design extension

## User design decision — 10 November 2026

The user explicitly approves **FX-B9: Bear Trap / False Breakdown**, a proposed additional LONG/BUY *design candidate*, distinct from the inherited B3 lower-range false break and a qualitative opposite family to S6 Bull Trap. **Approved design ≠ approved numerical Forex strategy ≠ verified BUY signal.** FX-B9 remains `APPROVED_DESIGN_SCOPE_FORMULA_PENDING / ACTION_ELIGIBLE=FALSE / UNVERIFIED / NO_SIGNAL`, not a trade recommendation or alert.

Original Forex Trading 1.0 Git source **remains 1:1 frozen** at commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`, tree `5df2058346f6dc96ed5bb02581b139fe2aa2d803`, catalog blob `dc0cd0d7eab7f8603071401aa51723f7e4b8ef20`, with exactly 18 original labels. Original `validate_catalog()` intentionally rejects `FX-B9` as an inherited label. The [source-locked original Forex 03 audit](https://docs.google.com/document/d/10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA/edit) paragraph **255** explicitly recorded FX-B9 as research-only/unapproved in the *original* catalog; do **not** silently rewrite or falsify that source. The user's new decision applies to an **additional, versioned MFX design overlay**, not Forex Trading or MOCHIFX.

## Two distinct counts must never be conflated

| Taxonomy | BUY/LONG entry design candidates | SELL/SHORT entry design candidates | Watch/protective only | Total labels |
|---|---:|---:|---:|---:|
| Frozen original Forex source + P0.27 evidence | 7 | 8 | 3 | **18** |
| MFX extended design overlay (adds FX-B9 only) | **8** | **8** | 3 | **19** |

Frozen original BUY labels: B1,B2,B3,B4,B5,B6,B8. MFX additionally considers **FX-B9** as the eighth potential BUY label. Existing SELL labels remain S1,S2,S4,S5,S6,S7,FX-S9,FX-S10. **B7 remains WATCH_ONLY**, and **S3/S8 remain EXIT_LONG_WARNING_ONLY**: neither becomes a SELL-to-open/SHORT. Therefore 8+8 refers to sixteen *entry setup design candidates*, not executable buy/sell detectors. All 16 numerical entry predicates remain unapproved (including FX-B9); source inherited 15 remain 0/15 approved and B2/S2 36/36 original numerical source obligations pending.

## FX-B9 qualitative four-phase outline (new MFX design, not inherited numeric rules)

- **R0 — Context:** prior H1/H4 support, origin event and first-known timestamps; intended break event is *outside* the previously defined sideways range. Price structure, lookback, support tolerance and definition of outside remain numerical **PENDING**.
- **R_C — Watch:** downside break fails to hold and returns toward known support; no future bars or revised levels. ATR, spread and window **PENDING**.
- **R_E — Early hypothesis:** CLOSED M15 price shows an evidenced reclaim at its own first-known/retrieved timestamp; no publishing or action. All numerical conditions **PENDING**.
- **R_F — Confirmation hypothesis:** independently verified higher-timeframe alignment and structural reclaim of a previously known micro-high with cost/risk checks. Lookback, anti-chase, invalidation, stop, TP, pip/ATR and net-R **PENDING**.

The B3 original [source audit paragraphs 39–49](https://docs.google.com/document/d/10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA/edit) instead specify false-break/reclaim around the **lower bound of an established H4/H1 range**. That context belongs to B3. If the range context is unknown or contradictory, **do not select FX-B9**. S6 [paragraphs 160–170](https://docs.google.com/document/d/10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA/edit) is the SHORT/Bull Trap high-side mirror conceptually; no assumption that B9 can copy S6's thresholds, risk, profitability or OOS performance.

## Data lineage, overlap and nonpromotion

The immutable design contract is [MFX_A04_P28E_FXB9_DESIGN_OVERLAY.json](https://github.com/ngluonghoa/MFX/blob/main/docs/MFX_A04_P28E_FXB9_DESIGN_OVERLAY.json), pinned by the overlay research module to an exact Git blob SHA. It references original Forex source commit, tree and B3/S6/FX-B9 paragraph anchors; it does not modify source docs or the P0.27 **18-row original-only** evidence matrix.

The pure SIM-only `mfx_research/p028e_fxb9_design_overlay.py` uses **caller-declared** context, NOT parsed forex candles or licensed quote data, to produce an *informational research classification* `B3_RESEARCH_ONLY`, `FXB9_RESEARCH_ONLY`, `UNKNOWN` or `NOT_FALSE_BREAK`, always `NO_SIGNAL`, `UNVERIFIED`, `may_publish=false`. It never verifies that a support line or market structure actually exists. Its research opportunity ID includes instrument, calendar, original event and known-support timestamp but excludes rule label/scope: if a caller has conflicting B3 and FX-B9 context for the same event, they share **one research opportunity**; neither creates a duplicate market alert. A real receiver-independent persistent idempotency mechanism is still unavailable.

Research inputs require explicitly `SIM:` names, UTC first-known and retrieved after closed candle, previously known support, no revised data, no claimed real price side/provider rights, and no preapproved numeric rules. Actual historical bid/ask, spread, DST, real market quote data, Google Drive quote cache, TP/SL, signed source numeric formulas and genuine execution-price/OOS evidence remain absent. No real provider calls, Drive quote-cache writes, user alerts, scheduler or broker orders.

## QA / release governance

[Issue #46](https://github.com/ngluonghoa/MFX/issues/46) preregistered **20** negative/scope/approval-isolation test groups **before coding**. The task uses only a new non-source manifest, a separate `mfx_research/` overlay, tests, hosted CI demo, this spec, `.github/workflows/ci.yml` and exact Git SHA allowlist. Original `src/`, 102 frozen source blobs, 30 modules, original Forex Trading/MOCHIFX repositories and 11 source-locked Docs stay untouched.

Hosted GitHub Actions MUST pass the full inherited Python3.11+3.12 1185 tests each **plus 20 new** P0.28E groups, strict Ruff/mypy, source golden50, wrapper34, 17 targeted mutants/80 feedback, historical P0.1–P0.27 gates, security/rights and crosswheel parity: exact PR-head 3/3 before protected squash, **independent event=push new-main 3/3** before canonical Handoff/QA/Roadmap/Trace checkpoint. All compute and artifact storage GitHub+Google Drive Cloud, no Mac/MOCHI/local.

**Outstanding independent blockers unchanged:** [Issue #45 P0.28](https://github.com/ngluonghoa/MFX/issues/45) original B2/S2 36 signed quantitative source requirements and [Issue #27](https://github.com/ngluonghoa/MFX/issues/27) licensed Forex native BID/ASK/history/Drive price storage rights. Owner design approval for FX-B9 does not resolve either. No source-approved verified BUY/SELL or production release permitted.
