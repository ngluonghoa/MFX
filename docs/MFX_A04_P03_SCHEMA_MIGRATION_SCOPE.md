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
