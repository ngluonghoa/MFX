# A02/P0.2 — Full strict mypy audit and six controlled type-only corrections

Scope: **full strict typing quality gate after a red inherited-defect audit**. The original Forex Trading GitHub repository and its immutable 102-file tree remain untouched. Six MFX-only source files receive strictly scoped type-annotation or `typing.cast` changes, each pinned by exact SHA and decision ID under A01 exception governance; all 50 original-vs-MFX golden scenarios remain mandatory.

Source is locked at `ngluonghoa/forex-trading-1-0` commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309` (102-file tree `5df2058346f6dc96ed5bb02581b139fe2aa2d803`). MFX protected main before this PR: `45e3a402f633147ee3f02f9815e18137cb3f9e7c`.

A02/P0.1 previously gated all 30 Python files for Pyflakes, allowing exactly 24 frozen legacy F401 diagnostics, and ran mypy strict successfully for only 12 files. This P0.2 audit invokes the same pinned mypy 1.18.2 on **every file under `src/forex_trading`** with `--strict --python-version 3.11 --show-error-codes --no-incremental`. An initial CI failure here is **diagnostic evidence**, not permission to weaken the rules.

Process:
1. Collect complete strict mypy diagnostics from both GitHub-hosted Python 3.11 and 3.12 workflow jobs, retaining exact code/path/line and category.
2. Evaluate compatibility, false-positive/type-only defects, and existing untyped code without changing source semantics or public import API.
3. Never add blanket `# type: ignore`, `--ignore-missing-imports`, `--follow-imports=skip`, or silently exclude modules.
4. The audit identified 13 inherited mypy errors in six source files (run 42502127538, both Python versions). Their corrections are narrowly staged on this same unmerged controlled PR for direct audit-to-fix traceability. A01 verifier is extended ONLY for an explicit six-file A02 allowlist with decision `DEC-MFX-001:A02/P0.2-STRICT-TYPING`, a per-file pinned Git blob SHA, and fail-closed tests. Existing other source paths remain forbidden, without wildcard exceptions. Runtime semantics of imported data remain as before; type annotations can change introspection metadata, so this is **compatibility engineering**, not a claim of byte-identical MFX source after upgrades.
5. No CI pass or release is claimed until 3/3 required checks pass on the PR and again on protected main.

No Twelve Data download, real market data, quote licence, broker connection, scheduler, Mac/MOCHI/local execution, release or live trade is permitted by this audit.

## Audited legacy mypy diagnostics (initial red CI run 42502127538)

All-30-module strict run on both Python 3.11 and 3.12 reported **13 identical type errors in six files**:

- `synthetic_drive_receipt_validation.py`: 3 (generic dict type parameters, nested hook annotation, Any return).
- `google_drive_wire_contract.py`: 5 (dict type parameters, untrusted file-id type).
- `cache_core.py`: 1 (optional last closed-bar timestamp).
- `synthetic_scan_workload.py`: 2 (empty tuple inference and optional delta start).
- `provider_delta_contract.py`: 1 (untrusted timestamp string type).
- `synthetic_drive_scan_orchestrator.py`: 1 (optional delta start).

Corrections change type hints, standard-library type imports and `typing.cast` only; they do not add provider requests, change indicator formulas, alter timezone rules, change candle selection logic or introduce order execution. `cast` is runtime identity and uses previously validated/checked domain values. **Ruff pinned 24 inherited F401 diagnostics must remain stable**. No blanket ignores or weakening of strict mode.

## QA and promotion gate

- Existing A01 immutable original source manifest remains unchanged. MFX records approved six typed source deviations explicitly; A01 verifier now exposes both exact unchanged original source count and approved typed delta count, never falsely claiming 30/30 byte equality.
- Nine new negative tests reject unknown source paths, wrong decision IDs, changed source SHAs, missing source blobs, and fake permission to trade.
- All 603+ synthetic tests, all 50 original-vs-MFX read-only golden cases across two Python versions, full 30-module Pyflakes, strict mypy 30 modules, wheel checks and package import ownership must PASS on PR and protected main.
- The pass would establish static quality and **tested synthetic contract parity**, not mathematical equivalence on all inputs, signed production release, broker-accurate TP/SL, licensed Twelve Data history, or economic trading efficacy.
- No merge if any job fails; protected `main` remains on pre-PR commit until full evidence supports reviewed Squash merge.
