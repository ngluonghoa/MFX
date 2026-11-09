# MFX A03/P0.5b — true observed arc-feedback synthetic parser corpus

Base protected main: `c4e114abee8701161d49b5ae3c0217ac9031c15d`; stage 1 PR #11 merged and post-main 42557738111 3/3 PASS.
Decision DEC-MFX-001, A03 test-system adequacy, not a production market adapter.

This follow-on milestone adds a bounded candidate exploration campaign in GitHub Actions only.
Each candidate invokes the existing frozen-source synthetic OANDA-shaped parser under a
fresh `coverage.py==7.10.7` collector with `branch=True` and `data_file=None`.
Only inputs that create NOVEL ACTUALLY OBSERVED execution arcs can seed
mutated children. The loop is a deterministic grammar, maximum 80 cases,
maximum depth 2, and denies real source IO. The accepted corpus is fingerprinted.
This meets a narrowly scoped true feedback-directed candidate selection criterion;
it is NOT a generic high-throughput coverage-guided fuzzer, cross-module global
campaign, per-input shrinker, whole-program mutation score, TP/SL, OOS or broker fill.

Expected QA gate: full A01 SHA+50 golden, strict mypy30/30 and pinned legacy F401,
A03 17 targeted mutants/47 controls, P0.5 stage-1 2546 covered lines /
973 branch outcomes frozen thresholds, two Python runners and cross-Python wheel,
all 3 CI jobs. No domain `src/` edits, original Forex writes, provider secrets,
live Google Drive cache or order runtime. Stage-2 reported novel arc numbers and
corpus digest must come ONLY from actual CI and be pinned after twin-run
readback; do not fabricate or equate executed arcs with 30-module branch totals.

First red runs retained for QA. Do NOT merge until exact-head PR CI 3/3
and independently verify post-main CI 3/3. Cloud-only, zero broker/orders.

## Real first-run cross-Python audit (P0.5b)
PR first run 42558478998: 681 unit methods on both Python versions PASS,
80 candidates / 17 feedback-interesting corpus entries / 118 observed arcs.
The first `corpus_sha256` also included interpreter-specific exception
diagnostics and arc counts; it DIVERGED between Python3.11 and Python3.12.
This is not silently accepted as deterministic cross-version reproducibility.
The revised corpus identity hashes only the sorted set of accepted input payload
SHA256 digests. CI must verify that resulting digest is identical across both
Python versions before pinning any new baseline or merging.
