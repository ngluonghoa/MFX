# Forex Trading 1.0 — three-milestone rollback / HISTORICAL CHECKPOINT — 2026-11-07

**SUPERSEDED:** This records the prior M2/P0.11 stopping point, **not** active scope. Additional rollback PR #43 restores M2/P0.10 and the deep audit restores native Spec v0.11 §26; latest Handoff v0.38 §48. This earlier text and test count 472 are retained for chronology only. [Current audit](FOREX_ROLLBACK_DEEP_AUDIT_20261107.md).


## User instruction and interpretation

The user asked to roll back **three development milestones** and withdraw edits made in concurrent chats, to redo later. The three overlapping development stages **M2/P0.12**, **M2/P0.13** (independent DRIVE and EXEC lanes) and **M2/P0.14** are treated as the withdrawn scope. **M2/P0.11 / merged PR #30**, commit `aa411515d837e59664cf4a9fdfbe1a3caf7ab5e2`, is the selected *source/test baseline*, not an attempt to delete later historical records.

## Rollback evidence and preservation

- Protected snapshot branch `archive/forex-pre-three-milestone-rewind-20261107` preserves the last observed `main` SHA `b47bfd09936e252bc1b6b93b2ab401597d9f11d9` before this rollback. All earlier Git commits remain reachable and auditable; no force push or rewriting history.
- Existing overlapping-chat cleanup PR #39 already removed standalone #31 per-week in-memory module/test/doc and #33 synthetic fill/Backtest module/test/doc, preserving the independently authored #32 and #37. Do not undo #39 or accidentally resurrect #31/#33.
- This controlled rollback removes the *remaining active code* from #32 and #37: `synthetic_cloud_aead_receipt.py`, `synthetic_sealed_weekly_store.py` and their matching tests, plus their noncanonical milestone engineering documents. These are deliberate REVERTS of experimental code, not evidence that historical smoke checks never happened.
- Both real Google Drive synthetic encrypted TESTPAIR00 files from #32 (753 B ciphertext envelope and 644 B manifest, **PUBLIC TEST KEY**) have been MOVED, not deleted, from active staging chunks/manifests into `02_AUDIT_AND_QUARANTINE__STAGING` folder `1ihSmQHycUxeWgQc-Wh69EXT9HnkLb-G_`. Original IDs are unchanged: `1IfzBILWfo6dAPHBIdvPpY52QQ3XVsDaR`, `1Be06jBxGDpjeKHpzJdA0XMLHoY4I7lCF`. The older M2/P0.10 #27 harmless synthetic smoke remains intact.
- A **full recursive GitHub tree comparison of all files under `src/` and `tests/`** on this rollback branch against the exact #30 baseline produced **48 of 48 identical blob SHA values, zero additions/deletions/differences**. All previously approved older M1/M2/P0.1–P0.11 source code is preserved.
- No change to independent Swing Trading, CK, FX 2.0, Scanner or remote Mac/VPS. No external Forex data, broker account, key custody or real orders involved.

## Functional-design and docs boundary

Canonical `02_FOREX_MASTER_SPEC v0.12 §27` is left untouched as a **design-only document** reflecting earlier user-approved concepts, not currently implemented code. Historical §43 of Handoff and QA evidence remain as history. Their references to merged #31/#32/#33/#37 are historical and MUST NOT be interpreted as current modules after this rollback. A new final Handoff checkpoint supersedes previous NEXT/implementation claims and freezes development until the user explicitly resumes in a single conversation.

## Expected tests and controls

- After source/code removals, the full `src/` and `tests/` tree must **exactly match** #30 `aa411515d837e59664cf4a9fdfbe1a3caf7ab5e2`, with the **472 synthetic tests** on Python 3.11 and 3.12 restored. Only cite CI as PASS after the actual PR and independent main runs report PASS.
- Do not promote test results into real vendor-data entitlement, persistent encrypted production cache, real 5-min 5→20→1→20 performance, Backtest/OOS or broker trading eligibility. All production gates remain BLOCKED.
- Restore the withdrawn modules, cloud staging files or implementation lanes **only after explicit renewed instructions**, on a clean branch/PR with independent CI and source+version provenance checks.

## Rollback versus deletion

This is a safe and reversible *working-tree rollback* by new branch and PR, with archive and audit records. GitHub historical PRs/commits and the quarantined cloud smoke are not destroyed. This is intentional so the user can later reconstruct exactly what was changed and decide how to redo it.
