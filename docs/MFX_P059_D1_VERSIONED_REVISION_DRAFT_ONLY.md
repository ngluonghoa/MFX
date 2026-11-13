# MFX P0.59 — D1 numerical source revision **DRAFT ONLY** custody schema

Date: 13 November 2026 (Asia/Ho_Chi_Minh). Dedicated open HOLD:
[issue #147](https://github.com/ngluonghoa/MFX/issues/147).
Umbrella: [issue #138](https://github.com/ngluonghoa/MFX/issues/138).

## Actual observed incident versus planned policy

Two naturally scheduled native H4/D1 jobs, notably
[#43365063369](https://github.com/ngluonghoa/MFX/actions/runs/43365063369)
and [#43372028090](https://github.com/ngluonghoa/MFX/actions/runs/43372028090),
reported **ONE** stored-vs-refetched Decimal OHLC difference in the
Twelve Data composite-mid EUR/USD provider-native **D1 2026-11-11**
Australia/Sydney local session. Prior source index: 16 SHA-attested
bars, 15 unchanged, zero missing. Non-numeric/format-only discrepancy
count: zero. The ORIGINAL
`P059_SOURCE_NATIVE_REVISION_QUARANTINE` halted each writer before any
Drive commit, and prior stored native archive SHA audit passed.

This is **not** proof of a vendor-canonical correction date, the cause
of the difference, independently attested first-known time, source
rights, economic correctness or trade-readiness.

## Exact scope of the new offline code

`mfx_cache/native_htf_revision_candidate.py` is pure Python,
**not imported into production writer, cache reader, signal validator,
GitHub Actions or any app endpoint**. The module cannot touch an
online resource and does not create any Google Drive object.

`draft_d1_revision_candidate` accepts externally supplied, formerly
full-SHA-audited native D1 last-16 rows, the same original sealed
manifest, a typed already retrieved provider-native D1 batch and an
explicit UTC observation timestamp from the caller. It verifies the
entire passed prior SHA index against the typed original rows, requires
all 16 overlap labels, exact D1/source/zone/side, valid OHLC, **exactly
one** changed old SHA bar on **2026-11-11**, and a genuine **Decimal
numeric OHLC** difference. It refuses extra or missing overlap,
multi-session drift, H4/M5 substitution and text-only changes.

The resulting **DRAFT ONLY** receipt lists SHA256 for the original
immutable manifest and original/proposed D1 typed bars, which numeric
OHLC field names differ, which non-price metadata field names differ,
and a caller-supplied observation time explicitly labelled **NOT an
independently witnessed publisher first-known timestamp**. It never
contains raw OHLC values, provider API credentials, account keys, Drive
file IDs, or an implicit approved replacement date.

The record includes a self-digest and optional parent receipt SHA to
support **a bounded two-observation chain** during the same isolated
2026-11-11 incident. The second candidate must refer to the prior
SHA, be observed strictly later in UTC and propose a different bar
SHA while keeping the SAME original archive manifest and bar SHA.
A standalone second receipt without its parent is rejected by the
contract. Only two observations are intentionally supported, not an
unbounded rewrite or a system-wide price restatement ledger.
This is a **planning-format illustration**, not a deployed Drive
append log, signatures, remote CAS, or independent publisher witness.
Any future expansion would require separate design review.

Every receipt is fixed in
`DRAFT_REQUIRES_OWNER_SOURCE_REVIEW` with:
`publisher_revision_cause_verified=false`,
`provider_first_known_verified=false`,
`publisher_data_rights_verified=false`,
`owner_source_policy_approved=false`,
`may_mutate_canonical_archive=false`,
`may_publish_buy_sell=false`,
`approved_numeric_signals=false`,
`broker_orders=0`, `drive_writes_by_planner=0`,
`drive_reads_by_planner=0`, `provider_requests_by_planner=0`.
No new state/approval field is accepted. Even a forged owner approval
or trade flag is rejected after recomputing the receipt hash.

**Important limitation:** The receipt SHA proves local bit integrity
only. A malicious actor can forge SHA of an invented manifest and
new bar. The helper does not itself re-audit the entire remote
archive, validate independent source first-known or certify rights;
those remain mandatory external controls. This draft MUST NEVER
be consumed as market authority. No actual 2026-11-11 price values
are fetched or stored by this PR.

## Owner-controlled decision sequence (not yet approved)

1. Preserve entire original H4/D1 source objects, chain and Cache M5
   unchanged; leave `P059_SOURCE_NATIVE_REVISION_QUARANTINE` active.
2. Independently substantiate both previously observed vendor versions
   and their first-known times and account data retention license.
3. Review the numeric OHLC disagreement, broker-side economics, effect
   on historical as-of replay/OOS and version selection semantics.
4. If owner explicitly approves, design a *separate* append-only,
   remote source revision namespace, immutable parent receipts,
   conflict handling, independent signatures/first-known evidence,
   actual writer/readback and rollback. All of that is **OUT OF SCOPE**
   for the draft contract and needs a different approval/checkpoint.
5. Before any new release, independent signal owner numerical rules,
   6TF M5/M15 source freshness, price licensing, BID/ASK spread,
   SL/TP, net R:R and causal OOS must also meet GO criteria.

No cache update, provider quota change, GitHub schedule modification,
manual OAuth workflow activation, local machine use, broker execution,
or automatic BUY/SELL is permitted by this work. MFX remains
`NO_SIGNAL / UNVERIFIED`.

## Test boundary

38 synthetic/negative offline tests cover deterministic root SHA
proposal, unique changed D1 label, exact current source SHA-index
attestation, typed UTC, numeric-vs-string-vs-metadata isolation,
two-observation parent link/clock, anti-repeat, policy/approval
forgery (including rehashed receipts), immutable input and no HTTP.

Only hosted Python 3.11/3.12 PR + independently accepted protected-main
CI can mark **offline schema and tests** completed. It does NOT
mark issue #147 resolved or authorize source restatement.
