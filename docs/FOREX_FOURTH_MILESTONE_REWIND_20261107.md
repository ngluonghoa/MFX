# Forex Trading 1.0 — additional one-milestone rewind to M2/P0.10, 2026-11-07

**POST-ROLLBACK AUDIT ADDENDUM:** Code M2/P0.10 correctly restored under PR #43. A subsequent deep audit found normative native 02 Master Spec still incorrectly at v0.12 §27; it has now been restored to **v0.11 §26, exact original 273 paragraphs / 63846 chars**. Handoff v0.38 §48 and [current audit](FOREX_ROLLBACK_DEEP_AUDIT_20261107.md) supersede earlier wording below that v0.12 remains current. Previous text preserved for provenance.


## Governance and user instruction

The user requested **one more milestone** of rollback after the previous three-milestone rewind had restored M2/P0.11. Interpret this as withdrawing **M2/P0.11 synthetic AES-GCM cache prototype** and restoring original **M2/P0.10 / Handoff v0.30** source/CI baseline. This is not a request to rewrite or delete Git or native Docs history, change prior functional design, or change Swing Trading / FX 2.0 / CK / Scanner.

## Reference points

- Previous current main before this additional rollback: `67e7b3a0d73fa1600c7c762827974bcc19ed07c2` (source M2/P0.11, Handoff v0.36 §46, QA v0.49 §64).
- Immutable archive branch: `archive/forex-before-extra-m2-p10-rewind-20261107` at that exact main commit.
- Restored target: **PR #28 merged commit `7f0904eefad9afe3da7bbaab522d8c59b6847c9e`**, last original M2/P0.10 full-docs source checkpoint, **original Handoff v0.30 §40**. PR #27 `32ad253ae8458e42776e11db48a20d9c1d8084b2` produced the actual 141B+439B synthetic Drive connector smoke.
- Withdrawn M2/P0.11 PR #29 (code) and PR #30 (docs) from the active working tree; historical Git commits and Docs text remain reachable.

## Implementation withdrawal

- Delete `src/forex_trading/synthetic_sealed_cache.py` and `tests/test_synthetic_sealed_cache.py`.
- Delete `docs/M2_P11_AEAD_SYNTHETIC_RECOVERY_AND_WITNESS.md` and `requirements-security-synthetic.txt` (the pinned `cryptography==50.0.2` requirement was added for M2/P0.11 only).
- Restore `.github/workflows/ci.yml` to original baseline commit blob `7af90b720a25802974d2fb02279eedc760d15626`, removing the installation of the withdrawn security dependency.
- Preserve M2/P0.10 original source, tests, CI, and all pre-M2/P0.11 smoke files without alteration.
- On the rollback branch, recursive GitHub tree comparison of `src/**`, `tests/**`, `.github/**`, and `requirements*` with the target baseline MUST have zero differences. Original code/test count **46 files**, restored M2/P0.10 suite **448** synthetic tests on Python 3.11/3.12. [Rollback PR #43](https://github.com/ngluonghoa/forex-trading-1-0/pull/43) merged at current source SHA `a68d9015781469156ac0339483bf4bc1d893ce84`; [PR CI 42375323936](https://github.com/ngluonghoa/forex-trading-1-0/actions/runs/42375323936) SUCCESS and independent [merged-main CI 42375384660](https://github.com/ngluonghoa/forex-trading-1-0/actions/runs/42375384660) SUCCESS, each Python 3.11 and 3.12 **Ran 448 tests OK**. Exact source/tests/.github/requirements 47/47 blob SHA identity established on both branch and main against M2/P0.10 commit 7f0904eefad9afe3da7bbaab522d8c59b6847c9e. Canonical Handoff v0.37 §47, original source-era Handoff v0.30 §40; QA v0.50 §65.
- Docs/README remain controlled current governance records, preserving later history and documenting withdrawn implementation; they are not expected to match old documents byte-for-byte. Master Spec v0.12 §27 remains design-only, not proof of currently implemented withdrawn modules.

## Google Drive scope

Previously quarantined PR #32 fabricated **753B encrypted TESTPAIR00 chunk** and **644B test manifest** remain quarantined (folder ID `1ihSmQHycUxeWgQc-Wh69EXT9HnkLb-G_`), unchanged. M2/P0.11 was entirely in-memory, so no separate encrypted Drive artifact is being removed from cloud. Earlier M2/P0.10 real connector synthetic **141B chunk** and **439B manifest** stay in active test-only staging. Never destroy historical proof, and do not claim that real market price caching exists.

## Resume policy

Stop implementation in all overlapping Forex chats. To resume later, read the latest native Handoff rollback section and QA, verify actual GitHub main/ref and tests, then proceed in a single conversation only with fresh user instruction. Source data usage rights, persistent production keys, concurrency/rollback witness, real 5-minute scan, historical Backtest/OOS, and broker trading remain BLOCKED.
