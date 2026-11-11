# MFX A04/P0.78 — Fenced witness CAS and interrupted-write recovery contract (OFFLINE)

**Disposition: RESEARCH-ONLY / NO V2 PRODUCTION APPROVAL.** This adds no authenticated witness, digital signature, durable monotonic ledger, real lease or atomic CAS, no Google Drive write API and no background workflow. It cannot authorize actual H4/D1 V2 migration or any trading.

## Exact objective

A04/P0.74–P0.77 established a proposed V1→V2 root, SHA-linked native sharded Chunk/Manifest records, caller-pinned monotonic witness drafts and a GET-only Drive V2 reader verified with mocked HTTP. Neither a caller-controlled tip SHA nor a SHA-linked witness draft prevents a malicious party from replacing BOTH price history and its reference SHA. A04/P0.78 now models the *necessary preconditions* for an independently administered CAS+fencing authority and interrupted-write recovery. Its externally observed head remains **caller-supplied** and cannot be authenticated by this code.

## Test-only protocol

- `WitnessAuthorityHead`: domain/symbol/interval, numeric authority epoch, strictly increasing fencing token, monotonic witness generation and canonical P0.76 witness SHA. `draft_authority_genesis` creates an **untrusted** in-memory snapshot from a caller-provided fake V1 256/256 archive state. It does not publish an attestation.
- `prepare_fenced_v2_cas` accepts one candidate V2 pair only. It checks the *entire* committed history via `verify_witness_draft`, replays the complete proposed cross-shard SHA chain via `audit_v2_chain`, requires the exact expected head SHA/generation, advances one generation, validates the witness-parent digest and proposes a higher fence in the same epoch.
- `assert_conditional_cas_preconditions` checks an expected vs observed head, same epoch, token current, one generation advance, canonical next witness SHA, and no live authorization. It is **not atomic**; real concurrency safety would require a distinct, durable, independently authenticated service with server-side compare-and-swap and monotonic fence allocation. Caller-provided head/tokens can be forged.
- `assess_recovery_after_interruption` classifies no objects, one exact Chunk orphan, both exact Chunk+Manifest without a committed witness, and a complete pair with a matching advanced head. Unexpected/duplicated/forked objects, a Manifest without its Chunk, or an advanced head with missing data FAIL CLOSED. Every non-error outcome requires a new authenticated authority readback and manual decision; no automatic repair or witness advancement is performed.
- 26 hermetic fake-authority tests simulate competing writers sharing one predecessor, stale epoch and fence, two-step generation and shard rollover, crash after Chunk, crash after Manifest, crash after witness, replay, corrupted historical data, unknown objects and replacement of the entire fake authority. A test intentionally shows that **two separate fake authorities can each accept a conflicting source of truth**: a single external trust boundary is not optional.

## Critical missing trust guarantees

The mock authority is in-process and not an independently trusted service; there is no owner identity attestation, signer/key material, signature verification, trusted monotonic epoch, separately backed-up immutable append ledger, server-side CAS, distributed lease, witness freshness SLA, optimistic-concurrency-safe Google Drive writes, consistency snapshot, multiwriter durable fencing, owner-approved recovery runbook or production rollback drill.

Never store or treat a hash-only pin in the same mutable Google Drive folders as an authenticated anti-rollback witness. Google Drive's existence of a file or SHA-hashed filename does NOT by itself provide required CAS semantics. No owner OAuth secret/variable, GitHub cron, V1 Cache history, production numeric FX signal or broker action is changed.

## Review / QA

Acceptance is for an inert, pure Python research contract only: protected PR, exact-head Python 3.11/3.12 tests (26 new), pinned source SHA deltas, original Forex Trading 1.0 frozen 102 Git blob parity and 11 locked Docs, security/static/dependency checks, cross-Python wheel, protected-main independent CI and documentation CAS readback.

**Next separately gated tasks:** select a real independent trust provider and signer authority with key/epoch rotation; determine whether its actual API offers atomic compare-and-swap, strongly consistent read and durable retention; verify supported Google Drive OAuth and test-only read-only V2 namespace; design staging-only immutable 2-object writes with failure injection and a separately authorized recovery operator; prove session gap and 30+ matching M5-derived H4 windows over >=7 days before considering native H4 source reduction. D1 remains source-native Sydney. No automatic live V2 or source signal promotion.
