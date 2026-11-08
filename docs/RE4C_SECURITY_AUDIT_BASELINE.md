# Forex RE4c — bounded security and dependency gates (2026-11-08)

**Candidate only until CI evidence is verified.** Implement RE4c as an incremental CI/security milestone after RE4b main `af1fc42953aa786d0962cc77eb70ef573d9271af`, not a production qualification or release.

## Gate coverage

- **Committed-file secret patterns:** `tools/check_repo_secrets.py` uses the Git index to scan all currently tracked UTF-8 files including archived text snapshots. High-confidence signature classes: PEM private-key header, GitHub classic/fine-grained PAT, AWS access-key ID, Google API key, Slack token and Stripe live secret. It returns only file paths and signature IDs; it never logs candidate secret values. Missing, unreadable, symlinked or non-text tracked files fail closed. Positive/negative synthetic tests include redaction and tracked-only scope.
- **Python Bandit security lint:** pinned `bandit==1.9.4` scans `src tools` with medium-and-higher severity **and** medium-and-higher confidence as a blocking CI gate. Lower severity/confidence reports and independent manual security review remain outstanding.
- **Dependency advisory lookup:** pinned `pip-audit==2.10.1` audits the declared Python project dependencies via `pip-audit --progress-spinner off .` against public advisories. `pyproject.toml` currently declares `dependencies = []`; a clean audit therefore gives **little coverage of third-party runtime dependencies**. The build backend requirement `setuptools>=70,<80`, GitHub Actions, runner tooling, tool-transitive dependencies and cross-host locked provenance are NOT covered by this declared-runtime audit. Internet advisory availability is required; fail the workflow if lookup errors rather than claiming PASS.
- **CI scope:** preserve Python 3.11/3.12 528 baseline synthetic unit tests (plus the new scanner tests), prior Ruff critical and E4/E7 globally, strict Pyflakes/mypy of the five typed modules and repeated wheel parity. Tools install in CI only. `src/forex_trading`, package metadata, test logic unrelated to scanner and market specs remain unchanged.

## Explicit limits and safeguards

This is an incremental baseline, not complete SAST/DAST, general entropy or history-wide secret scanning, dependency pin/hash lock, SBOM/signature, branch protection enforcement, KMS or proven source entitlement. Future authorized scanner revisions must add full history/entropy/broader token formats, build/transitive dependencies and quality coverage. A scanner cannot prove that an arbitrary-looking credential is harmless.

No automatic security autofix, broker orders, Forex price fetching, cache migration, release tag, approved Last Known Good or restore action. One isolated PR and original historical M2/P0.10 rollback SHA `7f0904eefad9afe3da7bbaab522d8c59b6847c9e` stay separate. Failures require evidence and a focused remedy, never global suppressions.

## First negative CI finding — MD5 is Drive compatibility metadata, not an integrity proof

Initial PR Actions run 42445635433: existing unit tests including ten new scanner tests PASS (538 each Python). Tracked-file scan PASS (95 UTF-8 files). Bandit correctly flagged three HIGH-confidence HIGH-severity B324 findings: two in `google_drive_wire_contract.py` and one in `synthetic_drive_receipt_validation.py`, because MD5 was called without explicitly stating whether it is used for security. These SHA-256-backed synthetic Drive compatibility contracts need MD5 solely to compare Google Drive's existing `md5Checksum` metadata or the historical `chunk_md5` field; SHA-256 over readback bytes is separately required before acceptance. Narrowly mark exactly three existing MD5 invocations `usedforsecurity=False`, preserving the algorithm and digest bytes and leaving SHA-256 validation intact. This is not an ignore/suppression and does not rehabilitate MD5 as a security primitive. Verify follow-up CI before merge; no release/security clearance claimed.
