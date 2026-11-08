# Forex Trading 1.0 — independent deep rollback audit (2026-11-07)

**Intent:** Verify exhaustive rollback to M2/P0.10 / original source-era Handoff v0.30 §40 after the user's concern about omitted changes. This is a **governance and source artifact audit**, not a Forex trading/backtest run.

## Findings

| Audit scope | Observation | Disposition |
| --- | --- | --- |
| Source and tests | Recursive Git blob SHA map `src/`, `tests/` on GitHub main `8adc7278cebe5244a725bcb277a3e75a963bf63b` matched original source-era commit `7f0904eefad9afe3da7bbaab522d8c59b6847c9e`: **46/46 identical files** | PASS, retained |
| CI, runtime/dependency manifests | `.github/workflows/ci.yml` and all `requirements*` paths matched old baseline exactly. Only standard CI workflow remains; removed pinned `cryptography==50.0.2`, no M2/P0.11 AES-GCM module | PASS, retained |
| GitHub Actions after merge | [run 42375920559](https://github.com/ngluonghoa/forex-trading-1-0/actions/runs/42375920559) SUCCESS, Python 3.11 and 3.12 each `Ran 448 tests`, `OK` | PASS — synthetic tests only |
| GitHub PRs and releases | No open PRs, no releases; historical feature/rollback branches and past merged commits remain as reversible audit records | No active PR/deployment; old branches not current code |
| Original synthetic cache staging | Only 141B original TEST-only chunk and 439B manifest from M2/P0.10 remain under active staging, with unchanged file IDs | PASS, retained |
| Post-baseline encrypted TEST artifacts | 753B/644B PR #32 files are in `02_AUDIT_AND_QUARANTINE__STAGING` and not in active manifests/chunks | PASS, isolated not destroyed |
| 01 decision ledger and business Docs | 01 v0.14 and 03–05, 07–10 predate original M2/P0.10 checkpoint; do not revert approved earlier decisions | PASS |
| **02 Master Spec** | **FAIL FOUND:** Native current v0.12 §27 had been left as editable active design even after source rolled back to original checkpoint with v0.11 §26 | **CORRECTED**: guarded native Docs rollback of two header strings and eight §27 paragraphs. Exactly matches original v0.11 text, 273 paragraphs / 63846 chars, original Git blob `024d1f2c0d0997230e0ae97bfcf60d3880c39832` |
| Handoff/QA, repo documentation | Later rollback histories remain intentionally. Some original audit docs said v0.35 'latest', #32/#37 'preserved', or current Spec v0.12; these statements were superseded but lacked explicit historical notices | CORRECTED current Handoff v0.38 §48, QA v0.52 §67, README/reference and historical document banners |
| Native ↔ GitHub snapshots | 00 current native v0.38 §48 / 02 current native v0.11 must match full GitHub snapshot files after docs PR merge | Require exact string parity and independent main CI before closing |

## Final state and constraints

**Active engineering checkpoint:** M2/P0.10 (original Handoff v0.30 §40; target source commit `7f0904eefad9afe3da7bbaab522d8c59b6847c9e`), **active normative design** Master Spec v0.11 §26, **current Handoff audit record** v0.38 §48. Original post-baseline v0.12 §27 preserved in historical Handoff §43 and old Git history only, NOT active. 01 DEC-FX-020/021/022 remains prior user-approved. Keep original Google Drive synthetic-only M2/P0.10 source evidence; do not claim real licensed price data.

Any future Forex development must be explicitly restarted in one conversation, with clean branch and tests. The following remain BLOCKED: provider account-specific historical BID/ASK rights, persistent production cache/KMS/independent antirollback witness, broker-side price/fill fidelity, real 5-minute scanner, strategy Backtest/OOS, production trading/release. No other financial trading project was edited.
