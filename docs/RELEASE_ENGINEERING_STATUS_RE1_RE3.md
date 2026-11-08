# Release Engineering status — Forex Trading 1.0 (RE1–RE3)

**Verified 2026-11-08 (Asia/Ho_Chi_Minh).** This is a read-only technical evidence register, not a release or a Forex trading entitlement. Current GitHub source/CI main after RE3: `917cff60c1e1100319d43d771971af5ebe27f1ab`.

## Canonical authorities

- [Google Drive 00 Master Handoff v0.44 §54](https://docs.google.com/document/d/1_F8yvAw5uBj25J5g7OUhhKyBgO2aO65qPtme4yHHgAE/edit) — current checkpoint and NEXT.
- [Google Drive 06 QA v0.59 §74](https://docs.google.com/document/d/19CGNHVw1QqnTifmtf1Xu5bst0IAbEWLhQlgOoVzfYZg/edit) — independent code/CI evidence.
- [Google Drive 10 Release / Rollback Standard v1.4 §16](https://docs.google.com/document/d/19z5m73GJgCu5AYCfio0JJGWHbcPJMwm___djxSq-GtA/edit) — release, LKG and rollback policy.
- [Google Drive 02 Master Spec v0.11 §26](https://docs.google.com/document/d/1k5vidJ5mPjCFCDYxuzJ29DSfOaBicZUzXLOX4jtscy4/edit) — unchanged business authority.
- Historical original user-approved rollback checkpoint M2/P0.10: `7f0904eefad9afe3da7bbaab522d8c59b6847c9e` (not the current source HEAD).

## Implemented evidence — one change per PR

| Checkpoint | Merged Git commit | Scope | Independently checked PR Actions |
| --- | --- | --- | --- |
| [RE1 PR #58](https://github.com/ngluonghoa/forex-trading-1-0/pull/58) | `b476112e71655e7de1297c957d55ee7b952a8c44` | Immutable read-only release candidate with 12-field profile, 9 declared gates, conservative rollback preview; two added paths, +16 tests | [42399051070](https://github.com/ngluonghoa/forex-trading-1-0/actions/runs/42399051070) — 518 tests PASS EACH Python 3.11 and 3.12 |
| [RE2 PR #59](https://github.com/ngluonghoa/forex-trading-1-0/pull/59) | `30bc7e2145f9a6fb04822e222b7cfd005931fcae` | CI pip check, Python wheel build smoke; SHA256, package identity/module content validation; four touched paths, +7 tests | [42399438805](https://github.com/ngluonghoa/forex-trading-1-0/actions/runs/42399438805) — 525 tests PASS EACH; 30 package source files verified |
| [RE3 PR #60](https://github.com/ngluonghoa/forex-trading-1-0/pull/60) | `917cff60c1e1100319d43d771971af5ebe27f1ab` | Build twice no-cache per Python under same `SOURCE_DATE_EPOCH`, reject differing SHA256; three modified RE2 paths, +3 tests | [42399783655](https://github.com/ngluonghoa/forex-trading-1-0/actions/runs/42399783655) — **528 tests PASS EACH**, two wheel builds per runtime, both Python matrix jobs same digest in this run |

**RE3 controlled-run wheel digest:** `d6b8e5e3dc45c31ad48290386f7817f21886f5c47e47e44d1aaef4c19a1869a6`. This is a same-run repeatability receipt, not signed or globally reproducible across independent hosts/build tools. RE2 before fixing `SOURCE_DATE_EPOCH` had different wheel SHA across Python environments. `pyproject.toml` project version `0.1.0` is only package metadata, not a released Forex application, and must not be promoted silently.

## Gate-state matrix

| Engineering capability | Current status | What is still missing |
| --- | --- | --- |
| Isolated module changes, PR/diff/Git SHA | **Implemented** | Only one Forex mutation lane; production runtime boundaries remain future |
| Python CI syntax/tests on 3.11 and 3.12 | **Verified per PR** | Independent postmerge-main *push* CI is not observable with the currently used PR-filtered connector |
| Package build/content/version/SHA receipts | **Verified in CI** | Signed release asset, published artifact/verified tag, lockfile and SBOM |
| Same-run repeated wheel hash parity | **Verified in RE3 CI** | Cross-host and frozen build environment, signed provenance |
| Full candidate profile + nine release gate *claims* | **Implemented read-only** | Independent verification of every gate, owner authorization; no ability to make a release through this contract |
| Rollback of code through reviewed revert PR | **Historically practiced** | Actual DB/cache/schema/positions reconciliation, approved LKG and restore drill |
| Ruff, strict typing, security/dependency/secret scanner | **Not fully implemented** | RE4 independent targeted checks, baseline exceptions and fail-closed checks |
| GitHub main protection/rulesets | **Not independently verified** | Explicit GitHub settings/ruleset assessment and protections |
| Production Forex source, Backtest, OOS, broker | **BLOCKED** | Provider rights/retention, BID/ASK identity, causal data quality, execution/risk and operational approval |

## Nine mandatory release checks (currently no permission to pass live)

1. `CODE_CI`; 2. `REPRODUCIBLE_BUILD`; 3. `SOURCE_ENTITLEMENT`;
4. `CAUSAL_HISTORICAL_DATA`; 5. `OOS_BACKTEST`; 6. `COST_AND_RISK`;
7. `SECURITY_AND_KEY_CUSTODY`; 8. `RESTORE_DRILL`; 9. `OWNER_SIGNOFF`.

A `CLAIMED_PASS` is a caller string, **not** independently verified evidence. The new `release_readiness.py` never returns `may_publish_release`, `may_assign_lkg`, `may_activate` or `may_trade` as true. A matching `ExecutionProfile` fingerprint does not make a running system restorable. Git revert cannot undo broker fills or recover encrypted/cloud state. No owner-approved operational release, actual LKG or real restore drill has been completed by RE1–RE3.

## Next sequence (independent and reversible)

- **RE4 — quality/security:** introduce baseline-safe lint/type checks, secret/dependency assessment and inspect GitHub branch protection/ruleset requirements. Isolate each as its own PR; do not mass-format unrelated source or weaken test gates to make CI green.
- **RE5 — release reproducibility/provenance:** freeze the toolchain, implement cross-host reproducibility checks, lock provenance, generate verifiable SBOM/signatures without uploading licensed FX data or secrets.
- **RE6 — restore proof:** read-only synthetic install and rollback rehearsal first, then only with approved real environments/rights/keys a bounded operational restore drill. Verify old/new schema/cache/permissions and broker-state reconciliation; never automatic deployment.
- **Separate Forex technical lane:** P2.2-C BID/ASK temporal/product identity, P2.2-D causal first-known and P2.2-E calendar/volume/recovery, without activating market data/trading.

**Release status: NO RELEASE APPROVED. NO EXECUTABLE LKG. NO REAL RESTORE. NO BROKER AUTHORITY.**
