# A04/P0.22 — reviewable B2/S2 quantitative proposal and causal synthetic truth table

## Source authority and design-only boundary

MFX is an informational Forex BUY/SELL signal product, never an automated broker. Its unmodified SOURCE_LOCKED_03_DETECTOR_AUDIT [frozen Google Doc](https://docs.google.com/document/d/10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA/edit) describes **qualitative** B2 (zero-based paragraphs 28–38), S2 (116–126) and universal controls (9). Those predicates are marked MANIFEST_DRAFT, CALIBRATION_NOT_RUN, SPEC_PENDING, OOS_NOT_RUN, ACTION_ELIGIBLE_FALSE. The original 18-label catalog maps 7 LONG entries, 8 SHORT entries, B7 watch and S3/S8 exit warnings; this change does not alter that catalog.

**Do not mistake a design proposal, SIM fixture success or hash fingerprint for source-approved Forex numerical rules, verified live signals or market profit.** The 36 P0.21 numeric obligations (18 each side) remain pending; this proposal contains 14 copied *SIM-only* experimental values, **zero** newly approved/default numeric parameters. Each of 36 rows also specifies what independent calibration evidence is missing. The P0.20 pivot LEFT1/RIGHT1, P0.19 H1 ATR/zone, P0.18 near/chase 0.5 are explicitly artificial. No owner parameter approval is asserted by CI.

## Executable, testable CI-only scope

- docs/MFX_A04_P22_SIM_POLICY_CASEBOOK.json: versioned per-field source lineage and evidence-needed review proposal, plus **14** pinned positive, no-signal and denial scenarios on fabricated SIM closed candles; no production policy file.
- mfx_research/p022_policy_casebook.py: validates exact source/phase/values against independently checked P0.21, rejects duplicated/unknown fields and fake authority, then runs actual P0.20 D1/H4 right-bar-confirmed causal B2/S2 route. Expected case order/results are independently code-pinned; cases cannot self-certify by editing JSON.
- tests/test_a04_p22_policy_casebook.py: change-forgery and negative-causality matrix (future right bar, retrieval time, open/partial bar, wrong pair/BIDASK side, forged provider/rights, fake numeric owner approval, unsupported source escalation).
- tools/run_a04_p22_casebook_demo.py: reproducible CI receipt; Python 3.11/3.12 plus cross-Python wheel checks and all original Forex source golden checks remain compulsory.

A result of research BUY or SELL in SIM data is always **UNVERIFIED**, with zero permission to send a verified signal, activate provider network calls, save licensed Google Drive market-price data, claim BID/ASK execution or TP/SL net profit, release an official build or place broker orders. Independent vendor account terms, native broker-aligned BID/ASK, first-known/calendar DST/rollover, structural SL/TP+cost, owner review and chronological real OOS remain unverified. See [MFX Issue #27](https://github.com/ngluonghoa/MFX/issues/27) for real data and storage rights.

## Merge / release gates and next checkpoint

One isolated protected branch; exact PR-head three-job CI pass; review file diff, no src/ changes, SHA-pinned manifest; squash-merge only if protected main is unchanged; independent post-main three-job CI pass; then update MFX 00 Handoff, 03 QA, 04 Traceability, 05 Roadmap. Keep all red CI receipts. No Forex Trading, MOCHIFX, Mac/MOCHI/local or automated broker changes.

Next: independent owner review of *proposed* B2/S2 numeric semantics and research thresholds, additional synthetic boundary/ablation cases, then separately qualified real-market rights and historical out-of-sample before any source-1:1 numerical claim. P0.22 is **NOT** full 15-entry detector or production signal completion.
