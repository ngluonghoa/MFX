# A04/P0.27 — source-locked Forex 18-zone BUY/SELL candidate evidence audit

**Decision: REVIEW-READY QUALITATIVE SOURCE MAPPING / NUMERIC SIGNAL NOT APPROVED.** This checkpoint brings original source evidence closer to the user's BUY/SELL objective. It does *not* fabricate a numeric detector or execute trading. Protected baseline MFX main `bb9e227d3a09830ffd3a48250e5d3e46af4cdabd` was CI verified [push 42670099570](https://github.com/ngluonghoa/MFX/actions/runs/42670099570) 3/3 with 1165/1165 unit tests each Python. Original Forex Trading 1.0 Git commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`, source tree `5df2058346f6dc96ed5bb02581b139fe2aa2d803`, 102 blobs and 11 frozen Google Docs untouched.

## Original source vs design candidates vs usable signals

Authoritative direct readback: [SOURCE_LOCKED_03_DETECTOR_AUDIT](https://docs.google.com/document/d/10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA/edit) (281 paragraphs, 0-based indexes), and original `src/forex_trading/catalog.py` with Git blob `dc0cd0d7eab7f8603071401aa51723f7e4b8ef20`, whose docstring explicitly says taxonomy is **NOT executable signal predicates**. `docs/MFX_A04_P27_SOURCE_EVIDENCE_MATRIX.json` captures verbatim original headings, R0 context, R_C/WATCH, R_E/EARLY, R_F/CONFIRM and status paragraphs with source indices for **every one of the 18 labels**. Its Git blob SHA is pinned as `d07f54e845e134c98b8bcbb5342a8f47df7c5f8a`; no original document was edited.

| Current original taxonomy | Label IDs | Actual status | Potential action if separately source-approved |
|---|---|---|---|
| 7 LONG entry candidates | B1 B2 B3 B4 B5 B6 B8 | Qualitative manifest only; numeric entry 0 approved | BUY at ASK, pending evidence |
| 8 SHORT entry candidates | S1 S2 S4 S5 S6 S7 FX-S9 FX-S10 | Qualitative manifest only; numeric entry 0 approved | SELL at BID, pending evidence |
| Watch only | B7 | Countertrend warning/watch, not entry | NONE |
| Exit-long protection only | S3 S8 | May warn of protected LONG/closing that LONG, NOT open SHORT | NONE (conditional separate EXIT_LONG at BID only with verified existing position) |

**Important:** These are 18 catalog **labels**, 15 **entry-candidate IDs** and 8 conceptual family patterns, NOT 18 or 16 independently executable numeric strategies. The two FX-S9/FX-S10 short entries are `APPROVED_DESIGN_SCOPE / FORMULA_PENDING`, not approved production formula or quantified signal. Other first 16 labels remain `MANIFEST_DRAFT / PREDICATES=SPEC_PENDING / ACTION_ELIGIBLE=FALSE`; every individual status quote reports action ineligible. MFX current default action for all 18 is `NO_SIGNAL`, stage `UNVERIFIED`.

## First priority source: B2 BUY, S2 SELL — explicit evidence and gaps

The [B2 original paragraph anchors 28,29–32,38](https://docs.google.com/document/d/10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA/edit) describe an **uptrend** on D1/H4, a WATCH near H1 support, an M15 closed early reclaim/HL, then confirmation above a previously known micro-high with valid higher trend and costs. Original S2 anchors **116,117–120,126** mirror downtrend D1/H4, WATCH near H1 resistance, M15 rejection/LH/BOS_DOWN, and confirmation below a known micro-low with valid spread/cost. Their separate invalidation/cost anchors are B2 33–37, S2 121–125. All quantitative thresholds, pivot lookback, ATR multipliers, news/session/DST, BID/ASK, SL/TP, cost-aware net-R, event expiry and untouched historical/OOS are still PENDING.

`docs/MFX_A04_P21_SOURCE_PARAMETER_REGISTER.json` is **strictly** a source review of 18 qualitative requirements × B2/S2 = **36 unapproved numeric obligations**, plus **14 SIM examples** used only for offline engineering. `mfx_research/source_parameter_review.py` already rejects fake source approval. For the remaining **13 entry candidate IDs**, source numerical verification is **not indexed**, not 'approved'. P0.27 explicitly labels those as `NUMERIC_SOURCE_CASE_NOT_INDEXED`, without inventing numeric requirements or treating design approval as a threshold.

## Gate and fault-injection QA

[Issue #43](https://github.com/ngluonghoa/MFX/issues/43) preregistered 20 standalone QA groups **before the code**: original Git blob/tree integrity and unique exact 18 catalog order; B7 watch vs S3/S8 protective; 7/8/3 counts; source paragraph anchors and phase text; draft/formula pending status; P0.21 36 pending and 14 SIM; action/quote-side mapping; 13 other unindexed numeric entries; tampered document/commit/tree/citation indexes; missing phases/forged approved statuses; duplicate and reordered matrix entries; fake `numeric_approved`, `CONFIRMED_SIGNAL`, inserted ATR number, forged real market/notification rights; source-origin P0.22 SIM BUY/SELL must remain UNVERIFIED.

Source matrix quotes are copied from authenticated Google Docs source readback; code pins **exact Git blob SHA** and checks phase/heading/status source indexes and the original catalog bytes against frozen Git manifest. A checksum is an integrity aid; it is **not** a trusted user/strategy owner approval signature. Any future source modification requires separate owner review, original source 1:1 compatibility governance, fresh evidence, and independent CI. No change to `src/forex_trading`, user source Docs, or Forex Trading/MOCHIFX repos.

GitHub-hosted full Python3.11/3.12 CI + strict Ruff/mypy, frozen 50 source golden + 34 A04 wrapper golden, A03 17 targeted mutants/80 feedback, all prior 1165 unit methods, security, rights and cross-wheel remain mandatory. PR exact-head 3/3 required before controlled squash; independent `main push` 3/3 required before QA/Handoff docs final. This is a **review/indexing milestone**, NOT source numeric parity or a real market data / OOS backtest.

## Real signal readiness remains BLOCKED

- **No approved BUY/SELL numeric detector:** 0/15 approved entry rules; 36/36 B2/S2 original source numeric clauses pending; other 13 candidates unindexed. Qualitative source text alone cannot determine BUY or SELL at a market timestamp.
- **Data rights [Issue #27](https://github.com/ngluonghoa/MFX/issues/27):** no independently qualified licensed native bid/ask quote source, rights to store raw prices on Drive, broker/session calendar, costs/SL/TP net-R or untouched historical OOS.
- **Event delivery:** prior simulated P0.25/P0.26 journal has no actual authorized persistent Google Docs journal, server CAS two-worker verified result or independently acknowledged receiver. No confirmed alerts, broker orders or production release.

**Next evidence request (NOT an approval inferred here):** strategy owner separately provides source-linked numeric B2/S2 definitions for each of the 18 listed requirements and clear after-cost quote conventions, then source owner/QA checks a controlled positive/negative fixture, chronological replay and licensed OOS. Only then may a future milestone propose an executable BUY/SELL detector. A separate read-only provider/rights review must be completed before live quote ingestion or Drive price cache writes. MFX Cloud GitHub+Google Drive only; no Mac/MOCHI/local.
