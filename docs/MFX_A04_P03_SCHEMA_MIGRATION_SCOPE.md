# MFX A04/P0.3 — ABI/schema change review and reversible declaration proof

Base protected main `e13705cab30db4302c158158843bb7b68620a0f0`; MFX independent Cloud-only GitHub and
Google Drive, no Mac/MOCHI/local. Original Forex source remains frozen at
`7e1c1c012b1b189be5ad7b9d07756eac012a8309` and original MFX
102-blob tree import at `6ee5e7c07baf4ea8f06a28889175808ea53c2316`.
No source `src/` changes are allowed in this milestone.

## New artifacts
- `tools/a04_contract_migration.py`: five synthetic immutable schema
  declarations mirroring A04/P0.2 inert port identifiers, major/minor
  version, typed required/optional field shapes, and a clearly labelled
  *unverified* semantic SHA claim. No implementation methods.
- `tools/check_a04_schema_matrix.py`: read pinned P0.2 original-50-golden
  and 4-port graph SHA, execute deterministic 14-case static mismatch
  matrix, and canonical JSON encode/decode replay. Accept only EXACT
  unchanged declarations or optional-only +1 minor fields as
  **STRUCTURALLY REVIEWABLE, NOT AUTOMATICALLY APPROVED**. Fail closed
  on major drift, changed mandatory fields, semantic claim drift,
  removed optional fields, unversioned schema edits, skipped/downgraded
  minor versions, graph/ABI source drift and frozen golden drift.
- Exact declarative rollback preflight: compare canonical replay bytes
  to original snapshot after a synthetic proposal, reject wrong-target
  restore. No git revert, runtime rollback, real data or live state.
- Negative unit tests and 2-language GitHub Actions CI matrix
  (Python3.11/3.12), strict mypy, original frozen 50-golden and
  A01/A02/A03 mutation, coverage and wheel gates.

## No implicit authority
A static matching *shape* does NOT prove semantic or economic parity.
A04/P0.3 is NOT a schema transformation engine, runtime plugin loader,
data entitlement, historical native BID/ASK source, TP/SL fill simulator,
market OOS, release or trading authorization. The reference fields here
are deliberately synthetic design claims, not vendor API payload
definitions and not a claim that the original Forex core implements
these interfaces.

## QA gate
Compare observed matrix outcomes, 14 case labels, SHA, counts and both
Python runs. Pin hashes only after real verified CI observations.
Review exact non-src path changes; squash merge only with same PR head,
full 3/3 green, protected unchanged main, independent main 3/3 green.
Update Handoff, QA, Roadmap and immutable Source Traceability with the
observed evidence and limitations. A04 overall remains PARTIAL.
NEXT: A04/P0.4 can address contract-level backward compatibility and
canary/rollback protocol; actual source wiring needs an independent
authorized PR and strict source-delta gate.

## Initial PR CI red record
First run 42568122304: 739 unit methods per Python; one isolated
P0.3 assertion compared dataclass tuple ordering before/after canonical
JSON replay, which is not a valid schema identity test. Canonical
serializer deliberately sorts five schema records. Updated the synthetic
QA assertion to compare exact canonical encoded bytes and SHA256 digest
instead of Python tuple ordering. No source or actual adapter modified.
Retain this red record; require fresh exact-head CI.

## Second CI red record
Run 42568230247: 739/739 synthetic tests PASS on Python3.11.
Four-module mypy strict scope discovered two typing-only diagnostics in
the matrix summary guard: inferred `dict[str, object]` prevented comparison
with integer thresholds. Fixed by declaring the report as
`dict[str, Any]`; preserves all integer threshold checks and never
suppresses mypy. No change to `src/` or transaction semantics. Preserve
the red history and require fresh PR CI 3/3 before merge.

## GitHub CI observed A04/P0.3 evidence (2026-11-09 UTC)
First run 42568122304 RED: invalid dataclass tuple-order assertion (canonical
JSON intentionally sorts schema identities); corrected test to require
exact canonical bytes and identity digest. Second run 42568230247 RED:
739/739 tests passed but strict mypy found inferred object types in
numeric matrix budget assertion; fixed with explicit dict[str, Any]
typing, no noqa/ignore.

Measured third run 42568341516: Python3.11 job 128999717335 and
Python3.12 job 128999717065 each 739/739 unittest methods PASS,
four new A04 typed tools strict mypy PASS, 50 frozen Forex/MFX synthetic
golden and A04/P0.2 per-group SHA PASS, 17 mutation sentinels PASS,
source coverage 2546/2683 lines and 973/1112 branches preserved,
pinned 80-case feedback PASS, isolated wheel parity 3/3 PASS.
Cross-Python matrix receipts IDENTICAL: 14 scenarios, 11 blocked,
3 structurally reviewable (one exact no-op and two additive optional
minor proposals, NEVER approval), all five schema families covered.
Baseline schema identity SHA256
`bf3c98b939e6257fce3b8b8ddc9b32591d8baed87f05fd9d53ae683518df0c23`
and deterministic case matrix SHA256
`85e285640914e55a700417b88a6586052c214835a9d087235569312fabe33443`.
Synthetic exact declaration restore matches; wrong restore blocked;
NO actual Git rollback, source mutation, plugin execution or trade.

Now `docs/MFX_A04_P03_COMPAT_MATRIX_BASELINE.json` freezes actual
observed SHA/count/negative reason budget and a new fail-closed
verification gate rejects drift, false authority and mismatched
original source identity. Fresh exact-head PR CI 3/3 and independent
postmain CI 3/3 are required after this commit.
