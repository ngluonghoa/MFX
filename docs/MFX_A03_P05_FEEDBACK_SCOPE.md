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

## Measured reproducible corpus baseline (GitHub Cloud 2026-11-09)
First PR run 42558478998: 681 tests per Python PASS, 80 candidate inputs
tested, 17 novel-arc interesting inputs and 118 observed execution arcs.
The first digest erroneously included Python-specific diagnostics, leading
to different cross-Python corpus hashes; retained as red evidence for QA
reproducibility (even though the ordinary three CI jobs were green).

Corrected audit run 42558710338: BOTH Python3.11 job 128970130935
and Python3.12 job 128970130815 produce exact same accepted-input-set
corpus SHA256
`2780e390be2d239c5042d6c8d9c691a3cc019601be1b977359704ddf67742df2`,
80/80 cases, 17 interesting, 118 executed arcs, 77 expected rejections.
The corpus key fingerprints only the accepted input payloads and excludes
interpreter-specific outcome text and arc annotations. New
`docs/MFX_A03_FEEDBACK_CORPUS_BASELINE.json` freezes those measured
counts and hash with a fail-closed runtime guard and negative tests.

This is reproducible bounded input corpus selection with real observed-arc
feedback, NOT full-system guided fuzz, source rights, per-input shrinking,
trading profitability, qualified BID/ASK, TP/SL fill or signed LKG.
Exact-head PR 3/3 CI and independent postmain 3/3 pending this commit.
