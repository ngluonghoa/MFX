# Forex overlap rollback — HISTORICAL CHECKPOINT, superseded 2026-11-07

**IMPORTANT: RETIRED STATUS ONLY.** The #39 snapshot below reflects an earlier partial rollback; its claims that #32/#37 modules still exist or that Handoff v0.35 is latest are **NO LONGER TRUE**. Latest canonical Handoff v0.38 §48 restores active code to M2/P0.10 and active Spec to v0.11 §26, with 448/448 Python 3.11/3.12 tests. #32 fake cloud files are quarantined. Read [deep audit](FOREX_ROLLBACK_DEEP_AUDIT_20261107.md) and current [snapshot manifest](HANDOFF_SNAPSHOT_MANIFEST.md). Original text retained below for history.

---


**Scope:** This chat only. Keep OTHER CHAT's independent Forex development and any unrelated Swing Trading project commits. Roll back code through a new PR and unchanged Git history, not destructive reset.

- Withdrawn original code [#31](https://github.com/ngluonghoa/forex-trading-1-0/pull/31): `src/forex_trading/synthetic_weekly_chunks.py`, `tests/test_synthetic_weekly_chunks.py`, `docs/M2_P12_WEEKLY_SEGMENTED_CACHE.md`.
- Withdrawn original code [#33](https://github.com/ngluonghoa/forex-trading-1-0/pull/33): `src/forex_trading/fx_execution_scenarios.py`, `tests/test_fx_execution_scenarios.py`, `docs/M2_P13_FX_EXECUTION_BACKTEST_REFERENCE.md`.
- **Preserved:** independent #32 encrypted fake Drive smoke, #36 native snapshot normalization, #37 `synthetic_sealed_weekly_store.py`, #38 v0.34 Handoff, licensed data rights still blocked. Three minimal #37 required model contracts `FXWindowRef`, `FXWindowManifest`, `FXWindowSync` now live inside that unrelated module to avoid unresolved imports after removing #31.
- Revert [PR #39](https://github.com/ngluonghoa/forex-trading-1-0/pull/39) MERGED main `291e9942ae18587781fb7b0ae4d641be010df646`. Postmerge full [CI](https://github.com/ngluonghoa/forex-trading-1-0/actions/runs/42371889929) SUCCESS 513/513 each Python 3.11/3.12, down from 560 due exactly 47 removed tests (21 + 26); external #37 code tests remain.
- Canonical Google Docs [Handoff v0.35 §45](https://docs.google.com/document/d/1_F8yvAw5uBj25J5g7OUhhKyBgO2aO65qPtme4yHHgAE/edit) is the latest user-instruction boundary; older §42-§44 and Master Spec v0.12 §27 are historical. [QA v0.47 §62](https://docs.google.com/document/d/19CGNHVw1QqnTifmtf1Xu5bst0IAbEWLhQlgOoVzfYZg/edit) records the rollback and non-claims.
- **No future work in this chat** until the user explicitly selects one active development lane. No OS, MOCHI, M15001 or production source/cache actions involved.
