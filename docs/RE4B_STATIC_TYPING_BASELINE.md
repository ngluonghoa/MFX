# RE4b — Static quality and strict typing of stable Forex contracts

**Scope:** new additive CI gates and one **name-only source hygiene fix** in `provider_delta_contract.py` to address actual Ruff E741 from the first failed CI attempt, RE4b first slice. The local variable `l` (low price) becomes `low` in the OHLC tuple, JSON serialization and unchanged `StagedQuoteBar` argument position. No changes to output structure, numeric computations, indicators, cache migration, broker operation, release, LKG, vendor access or master business specs. Propose one small PR on top of RE4a Handoff-sync PR #63.

## Baseline and gate design

- Keep the same `python-unittest` job identity, Python 3.11/3.12 matrix, 528 existing synthetic tests and artifact parity smoke checks.
- Preserve prior pinned Ruff v0.13.0 critical checks `E9,F63,F7,F82` over `src tests tools`; add blocking `E4,E7` error classes on the same full tree.
- Apply complete Pyflakes `F` in strict blocking mode to five self-contained, already typed foundational contracts: `model.py`, `pipeline.py`, `scan_contract.py`, `versioning.py`, `release_readiness.py`.
- Run pinned mypy 1.18.2 `--strict` on exactly the five contracts above under Python 3.11 semantics. Includes static analysis of dependencies actually imported; never use `--ignore-missing-imports`, `--follow-imports=skip`, `--disable-error-code` or global `# type: ignore` in CI to manufacture passing evidence.
- Intentional legacy re-export and module shims (especially `synthetic_drive_cache_staging.py`) have not been migrated to full `F` or strict mypy yet. Broader full-project lint, type coverage, formatting, tests/tool typing and security scanning remain OPEN, not implicitly PASS.
- Pinned type/lint tools are installed in CI only; they are **not production dependencies**, do not change `pyproject.toml`, and cannot publish/activate Forex trades.

## Original negative CI finding and correction

- First PR #64 attempt Actions 42443744490 failed identically on Python 3.11/3.12 at `ruff check --select E4,E7 src tests tools`, detecting one pre-existing `E741` (ambiguous variable `l`) in `src/forex_trading/provider_delta_contract.py:228`. Earlier critical Ruff checks and existing synthetic tests succeeded.
- Correction is a mechanical three-site local name replacement only: `o, h, l, c` to `o, h, low, c`, JSON `str(l)` to `str(low)`, DTO constructor argument `l` to `low`. This preserves the exact same OHLC order and digest/DTO semantics.
- Do not ignore or globally suppress E741. Verify rerun and type checks before merge; any new diagnostics require separate investigation.

## Second negative CI finding and correction

- Second PR #64 attempt Actions 42443832566: all Ruff checks PASS on both Python versions after the E741 local-rename fix; strict mypy discovered two existing assignment type errors in `scan_contract.py:66,70`. Mypy inferred the `selected` local variable too narrowly from the `len(requested_pairs) == 1` SINGLE branch, conflicting with CUSTOM/ALL variable-length selections.
- Add `selected: tuple[str, ...]` before the unchanged mode branches. This constrains the static type without changing any runtime assignment, selected pair ordering, validation, scanning, cached data or business behavior. No mypy ignore or config relaxation.
- Rerun full existing synthetic tests, strict type checks, Ruff and wheel parity before merge.

## Evidence and failure handling

GitHub Actions PR and postmerge main logs must independently show the exact strict-type and Ruff commands PASS in each Python job, baseline unittests PASS and twice-built wheel SHA parity. If either job fails, do not merge; inspect source/CI diagnostics and make an isolated reviewed fix, never globally suppress errors or edit unrelated domain logic. For a clean revert, revert this PR's CI and this audit doc without touching stateful caches, broker state, previously merged RE4a, or historical M2/P0.10 rollback archive.

**STATUS: PROPOSED / CI NOT YET OBSERVED WHEN WRITTEN.** Google Drive 00 Handoff v0.45 §55, 06 QA v0.60 §75 and 10 Release Standard v1.5 §17 remain current until independently verified PR results and canonical document updates.
