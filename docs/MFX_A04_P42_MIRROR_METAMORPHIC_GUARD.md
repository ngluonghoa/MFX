# MFX A04/P0.42 — 11-pair mirrored-role metamorphic safety contract

Status: IMPLEMENTED AS CLOUD-ONLY SIM REGRESSION / NO ORIGINAL STRATEGY APPROVAL.
Issue: https://github.com/ngluonghoa/MFX/issues/68

## Provenance and invariants

- Original Forex Trading 1.0 source freeze: commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`, 18 original zone labels unchanged.
- Qualitative P0.29 symmetry audit: `docs/MFX_A04_P29_ELEVEN_PAIR_SYMMETRY_AUDIT.json`, exact Git blob `08bc1896c2007f532367750f5f1eeb6be06d1ad6`; historically the 3 new nonentry counterparts were *proposals*.
- P0.30 subsequent explicit MFX-only design approval established effective 22 labels: 8 LONG candidates + 8 SHORT candidates + 2 WATCH + 4 EXIT warnings. It did **not** approve source numeric predicates.
- P0.31 SIM label router only classifies user-asserted closed-candle research labels, not independently detected market patterns.

The eight entry design pairs are `B1/S1`, `B2/S2`, `B3/S4`, `B4/S5`, `B5/S7`, `B6/FX-S9`, `B8/FX-S10`, `FX-B9/S6`. The three nonentry mirror pairs are `B7/FX-S11` (WATCH both), `S3/FX-B10` and `S8/FX-B11` (EXIT_LONG versus EXIT_SHORT warnings). Each of the 22 zone labels belongs to **exactly one** conceptual pair.

## Executable regression contract

New unittest `tests/test_a04_p42_mirror_metamorphic.py` pins the actual P0.29 Git blob and reads the approved P0.30 registry; it checks all 11 pairs against P0.31 runtime SIM research routing. Sixteen test methods cover source lineage, 8 explicit entry mirror roles, 3 nonentry roles, 22/22 coverage, independent BUY-only and SELL-only *research presentation*, pair collision => `CONFLICT_NO_SIGNAL`, input-order invariance, separate source-origin isolation, all 22 label grouping, provenance/duplicate/future-known fail closed, 0 live alerts/real cache/orders/release.

CI adds an explicit P0.42 suite check, in addition to normal full Python3.11/3.12 unittest discovery, source frozen guard, wheels and security/static analysis.

## Explicit negative claims

A mirror label **does not** prove numerical inverse predicates, equal stop/TP geometry, market-price signal detection, OOS/backtest quality, broker fills, source-owner authorization, or provider quote/Google Drive data rights. In particular `FX-B9/S6` are structural false-break counterparts but B9's outside-range ownership and S6's historical 'return to range' language cannot be homogenized as a single executable numeric rule.

- Source B2/S2 36 independent numeric owner obligations remain **unsigned** (Issue #45), approved source numerical entry rules **0/16**.
- Legal private Google Drive raw Forex quote retention and actual data/first-known/BIDASK economic quality are separate blocked gates (Issue #27).
- External actions remain `NO_SIGNAL`, with no cloud runtime, real market data call, raw quote cache write, production alert, auto-exit, broker order, or release.

Any future implementation of actual detector mirror inversion must start a separate milestone with signed qualitative/numeric source-policy decisions, causal OHLC first-known semantics, and independent quantitative/OOS/rights qualification. This P0.42 test merely protects already-approved MFX **design-role routing** from accidental regression.
