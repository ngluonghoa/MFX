# A03/P0.3 — systematic stateful fuzz replay, independently modeled safety properties

## Baseline and source integrity

MFX protected main before this PR: `81449357adbe9dd6aeb3d7480bdf8a918ef621a3`. Independent frozen Forex Trading 1.0 source commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309` remains untouched; initial MFX 102/102 exact import `6ee5e7c07baf4ea8f06a28889175808ea53c2316` is a rollback reference. Current MFX source still has 24 original Git source blobs byte-equal and six prior A02 typed-only SHA-pinned differences. **This A03/P0.3 PR makes ZERO modifications to `src/`**.

## Expanded deterministic fuzz corpus and independent oracles

`tests/test_a03_stateful_fuzz.py` adds **seven** unittest methods, of which six explore up to **8 fixed seeds × 16 stateful scenarios** each (128 per method). The seventh verifies a deterministic one-step counterexample reducer on a deliberately synthetic predicate. This is systematic bounded fuzz, **NOT** a coverage-guided or Hypothesis-based engine.

The tests challenge real read-only contract behavior with independent expected outcomes:

1. **Multi-revision causal as-of:** randomized 2–6 known versions per one candle, randomized arrival gaps and shuffled revision order; an independent model picks the latest revision whose first-known time is at or before each decision. Future corrections cannot contaminate historical output.
2. **Stateful candle cache:** append, revise and idempotent no-change operations over 16 successive decisions; an independent map by bar start is the oracle for sorted contents, changes/dirty indices, prior snapshot immutability and zero real-data persistence authorization.
3. **Mixed append + revision order:** shuffled 2-record batch must generate identical snapshot/result fingerprints and first-dirty timestamp, not order-sensitive behavior.
4. **Arbitrary noncyclic DAG:** for multiple independent pairs, randomly choose L1–L5 parents from earlier layers. A separate fixed-point reachability oracle is compared with production invalidation closure under shuffled input order and change order.
5. **Quote time-shift metamorphism:** translating event, first-known and decision clocks by the same random offset cannot change quote side/indicative BID/ASK price; only returned first-known shifts.
6. **Cache source isolation:** changing rights-policy reference must change partition/snapshot fingerprints; changing side/provider must fail identity checks even if the candle series itself is unchanged.
7. **Counterexample reduction:** a small deterministic set-reduction helper is tested for repeatability and 1-minimality on a synthetic failure predicate. It is **not automatically invoked for every fuzz failure** in this milestone.

`tools/check_a03_stateful_fuzz_budget.py` enforces exact eight-seed corpus, 16-step budget, seven-method discovery and `SYNTHETIC_ONLY=True`, producing `MFX_A03_STATEFUL_FUZZ_REPLAY_PASS`. CI executes all seven methods through its normal unittest discovery in both Python 3.11 and 3.12 jobs. Seed/case/subtest indices appear in failures for reproducibility; no provider access, trade, release or calendar inference.

Existing A03/P0.2 17/17 targeted mutation sentinels remain mandatory, and their clean A03 pre-mutation control-suite count increases from 29 to **36** (29 existing + 7 new). Neither source mutation targets nor their 17-item score are altered. The temporary mutation copy is still destroyed by GitHub Actions.

## Acceptance and quantitative limits

Expected `641 + 7 = 648` discovered unit-test methods on **each** Python version. Each required CI run must also prove:

- 8 seeds, 16 steps, seven new test methods discovered, and no new source code or new secret/API entitlement;
- A03 17/17 targeted sentinels killed; control A03 suite 36/36 green;
- A01 frozen original 102-file Git tree and SHA-pinned six A02 source deviations, plus 50 independently replayed Forex vs MFX synthetic golden contracts;
- A02 mypy strict 30/30, exact 24 known F401 legacy diagnostics and no new Pyflakes findings, security checks and isolated wheel provenance;
- all 3 required PR GitHub CI jobs PASS, then reviewed protected Squash merge and **independent post-main 3/3 PASS**.

This milestone does **not** claim source-wide line/branch coverage, coverage-guided fuzzing, systematic whole-program mutation score, real financial strategy/executable 18-zone detector behavior, TP/SL, tick-level broker fill simulation, live source/rights or untouched OOS. A03 remains PARTIAL after P0.3.

No Mac/MOCHI/local computation, no changes to original Forex Trading repo, no broker, no live trading. Twelve Data is the only currently available external market-data MCP candidate but is not queried or granted runner credentials here.
