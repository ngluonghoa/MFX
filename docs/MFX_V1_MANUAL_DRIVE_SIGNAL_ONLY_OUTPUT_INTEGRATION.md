# MFX v1 — P0.150 owner-gated real Google Drive six-TF NO_SIGNAL output integration

Date: 13 Nov 2026 (ICT). Prerequisites: accepted PR #149 typed immutable six-frame `NO_SIGNAL` research renderer; existing dormant manual GET-only workflow introduced by PR #142 and authenticated historical read #43269657301. Governing release path: [Issue #138](https://github.com/ngluonghoa/MFX/issues/138); source-restatement HOLD: [Issue #147](https://github.com/ngluonghoa/MFX/issues/147).

## Why this is a real integration step

Previously, the P0.149 typed report was usable only by pure offline callers while the already existing manual authenticated Drive read tool emitted its older SHA / freshness summary. This PR connects them: **the same single already-authorized GET-only evidence receipt** is passed into `build_signal_only_research_response` after original audited M5/H4/D1 archive and source-time gap validation, without another network request.

The CLI now prepares and JSON-serializes the entire validated safe report **before** printing the technical PASS marker. CI initially caught the prior implementation printing PASS prematurely if report validation failed; it was fixed before merge. Failed validation/encoding prints only a redacted FAIL marker with nonzero exit.

The existing public-safe summary keeps its old schema and fields intact, and adds one nested `signal_only_output` with action, stage, six-frame coverage, missing/stale flags, deterministic fingerprint of source reference hashes, source-quality and authority reason codes. It exposes explicit null zone/entry/SL/TP/net-R:R/publisher-first-known fields. These values are **not** independently authenticated publisher receipts or proof of strategy profitability.

## Hard stop boundaries

- Current branch only touches the dormant `tools/run_mfx_v1_manual_drive_six_tf.py` report composition, a hermetic test file, this documentation and the exact SHA allowlist. It does **not** change the manual workflow YAML, its owner variable, existing writer approvals, GitHub secrets, Google Drive archive, cache cadence, Twelve Data polling, data rights, historical as-of, or broker execution.
- The workflow remains manual-only and **OFF** until the source owner separately sets the dedicated `MFX_V1_SIX_TF_MANUAL_READONLY_APPROVED=true` and explicitly chooses `READ_ONLY_NO_SIGNAL`. No new real probe is invoked by these changes. The accepted real historical #43269657301 is point-in-time only, not a claim the current feed is fresh.
- The view is `NO_SIGNAL / UNVERIFIED` even if all six technical windows are present. Original B2/S2 rule approvals remain **0/36**, other entry families are not numerically approved, account-specific licence/first-known not independently established, MID is not executable BID/ASK, and no net economic SL/TP/R:R or deterministic causal OOS has passed.
- Current live D1 2026-11-11 actual Decimal OHLC revision difference is still under the original strict `P059_SOURCE_NATIVE_REVISION_QUARANTINE`. Never change, normalize or append corrected historical source while Issue #147 remains owner HOLD.
- M5/M15 can be unavailable intra-hour on the existing hourly writer schedule; unavailable frame names and missing source slots remain explicit, never synthesized.

## Evidence and QA boundaries

Tests are hermetic and cover complete/partial six frames, stale M5/M15, null economic fields, signoff forgery, forged source digest and quote authority, no raw prices/secret/Drive IDs in log JSON, same one injected Drive probe receipt, disabled owner mode and clean fail-closed CLI error. These tests **cannot** prove a real new OAuth read, live vendor market timeliness or first-known custody. Accepted CI requires GitHub-hosted Python 3.11 / 3.12, frozen Forex source102 and 11 locked Docs preservation, exact SHA allowlist, full security and crosswheel, then independently green protected-main push status.

Rollback: only revert this MFX-only integration PR; retain #149 renderer, protected original source and all real Drive cache bytes. No Mac/MOCHI/local engineering compute or ChatGPT recurring automation.

Next: obtain independently verifiable original source owner numeric predicates and lawful market rights/first-known/cost evidence. Do not promote a simulated B2/S2 rule or publish BUY/SELL from this technical output.
