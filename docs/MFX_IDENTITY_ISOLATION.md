# MFX project identity and isolation — M1/P0.4a

Status: PR candidate. Source baseline already frozen; this file is **not** a production release.

## Immutable 1:1 source anchor

- Source project: `ngluonghoa/forex-trading-1-0`, commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`
- Independent MFX initial import: `6ee5e7c07baf4ea8f06a28889175808ea53c2316`
- Exact 102-file Git source/destination tree: `5df2058346f6dc96ed5bb02581b139fe2aa2d803`
- MFX independent source CI: https://github.com/ngluonghoa/MFX/actions/runs/42492455894 — Python 3.11: 556 tests PASS; Python 3.12: 556 tests PASS; cross-Python wheel parity PASS.
- Legacy Forex Trading Git history was **not** cloned: original 102-file HEAD snapshot only.

## Identity changes in this PR (M1/P0.4a)

1. Change only wheel **distribution** name to `mfx-forex-core` in `pyproject.toml`, preserving version, module implementations and import paths.
2. Change workflow **display name** and same-run upload/download wheel artifact names to `mfx-baseline-wheel-3.11` / `mfx-baseline-wheel-3.12`. GitHub job IDs and three required branch-protection check contexts remain unchanged.
3. Mark repository README as MFX and clearly separate historical source notes from independent MFX evidence.
4. Add this project identity/isolation policy.

**Intentionally unchanged for golden parity:** `src/forex_trading/**`, `tests/**`, `tools/**`, source contract functions, signals, TP/SL, API imports, market data/cache logic, catalog and all trading decisions. Thus core source byte-level parity can still be proven against frozen commit for those paths.

The `forex_trading` Python **import** namespace is retained as a compatibility holdover. A future MFX-only change must migrate or alias it, with a complete import/replay regression and an explicit rollback contract, before claiming Python runtime package namespace isolation. Never install both packages into the same Python environment merely because the wheel distribution names differ. Use separated Cloud runtime environments.

## Isolation requirements (future implementation gates)

- MFX repo, issues, protected branches, releases, artifacts, PRs and CI are independent. **Never write to Forex Trading 1.0**.
- MFX Google Drive documents, cache manifests, persistent chunk IDs and ACL/secret namespaces are independent of Forex Trading, MOCHIFX and all other projects.
- Preserve Google Drive as the **durable cache target**; any hot cache must be authorized Cloud-only and must never become a user-Mac/MOCHI local dependency.
- Do not provision broker credentials, send orders, activate a trading scheduler, claim real qualified FX data rights, or deploy live trading from this project.
- Preserve original 18-label catalog and source distinctions. New C-group changes require experimental branches, matching bid/ask/first-known reference inputs, after-cost OOS validation, and separate promotion.
- This repository is currently **Public** by user configuration. Never add credentials or real/proprietary market datasets to Git history.
- Protected `main`: ruleset `MFX-main-protection` (ID `26801788`), three required check contexts `python-unittest (3.11)`, `python-unittest (3.12)`, `Cross-Python wheel parity (3.11 / 3.12)`; PR-only writes, linear history, no force/deletion/bypass.
- The ruleset allows 0 approving reviews, so GitHub CI status is mandatory but does **not** provide independent human review. No automatic release or live trading.

## Acceptance checklist for M1/P0.4a

- [ ] Branch PR created on MFX only; original source repo and imported baseline SHA unchanged.
- [ ] PR diff limited to `README.md`, `pyproject.toml`, `.github/workflows/ci.yml`, and this policy file.
- [ ] 3/3 protected CI checks passed independently on PR SHA, 556 tests under each Python unless a documented test-only addition changes counts.
- [ ] Build wheel name/metadata MFX-scoped, same-run cross-Python artifact parity PASS.
- [ ] Zero changes to domain code and test files; API/signal parity follows identical source bytes for those unchanged paths.
- [ ] Safe rollback is the immutable MFX import commit `6ee5e7c07baf4ea8f06a28889175808ea53c2316`, not a released LKG.
- [ ] User/maintainer reviews PR status before merge. Do not assume required status checks imply authorization to release or trade.

The canonical decision/QA history is maintained in MFX Google Drive Handoff and Roadmap under owner decision DEC-MFX-001 (32 directions approved only).
