# A02/P0.2 — Full 30-module strict mypy audit before any source edits

Scope: **quality gate assessment only**. Original Forex source code stays byte-for-byte untouched; all A01 source SHA and 50 golden scenarios remain mandatory.

Source is locked at `ngluonghoa/forex-trading-1-0` commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309` (102-file tree `5df2058346f6dc96ed5bb02581b139fe2aa2d803`). MFX protected main before this PR: `45e3a402f633147ee3f02f9815e18137cb3f9e7c`.

A02/P0.1 previously gated all 30 Python files for Pyflakes, allowing exactly 24 frozen legacy F401 diagnostics, and ran mypy strict successfully for only 12 files. This P0.2 audit invokes the same pinned mypy 1.18.2 on **every file under `src/forex_trading`** with `--strict --python-version 3.11 --show-error-codes --no-incremental`. An initial CI failure here is **diagnostic evidence**, not permission to weaken the rules.

Process:
1. Collect complete strict mypy diagnostics from both GitHub-hosted Python 3.11 and 3.12 workflow jobs, retaining exact code/path/line and category.
2. Evaluate compatibility, false-positive/type-only defects, and existing untyped code without changing source semantics or public import API.
3. Never add blanket `# type: ignore`, `--ignore-missing-imports`, `--follow-imports=skip`, or silently exclude modules.
4. If full strict requires source changes, separate narrowly reviewed PR with A01 pinned source exception changes, expanded golden regression evidence and original Forex compatibility. If not yet safe, record explicit blocked source modules and preserve protected main unchanged.
5. No CI pass or release is claimed until 3/3 required checks pass on the PR and again on protected main.

No Twelve Data download, real market data, quote licence, broker connection, scheduler, Mac/MOCHI/local execution, release or live trade is permitted by this audit.
