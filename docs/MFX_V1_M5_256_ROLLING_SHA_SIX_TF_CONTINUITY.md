# MFX 1.0 — continuous M5 SHA custody for six-TF research after 256 hourly archives

Date: 2026-11-12 ICT. MFX signal-first Issue #138. This is a Cloud-only,
GET/list-only research input continuity fix, NOT H4 substitution research.

## Problem solved without Drive or provider mutation

The PR #141 six-TF reader hard-stopped at the 256th M5 hourly manifest.
A continuously operating hourly M5 Cache can therefore pass that threshold
well before MFX 1.0 signal-first release and cause its independent manual
probe to fail even if the writer legitimately continued appending.

This change reuses two existing MFX SHA protocols, never fabricates source
price candles and never increases Twelve Data request frequency or creates
new Google Drive objects.

## Exact acceptance modes

**M5 <= 256 manifest/chunk pairs: FULL_BOUNDED_ALL_RAW_SHA**

- Reuse P0.66 complete M5 manifest/raw-chunk SHA and parent-chain audit,
  original derived M15/M30/H1 per-hour proof and strict source-reviewed
  first root and 31-pair checkpoint pins.
- Every archived M5 raw chunk is SHA-read in this run.
- `all_three_bounded_sha_chains_verified=True` as before.
- `m5_full_historical_raw_sha_verified=True`,
  `m5_historical_raw_chunks_not_reread=0`.

**M5 257–1024 manifest/chunk pairs:
ROOT_PINNED_ALL_MANIFESTS_LATEST_256_CHUNKS**

- Reuse the original P0.69 root-pinned rolling SHA auditor without changing
  its source, schema, or historical evidence policy.
- Independently require the exact MFX GitHub-reviewed original root SHA,
  AND the 31-pair checkpoint SHA+index/content from P0.85.
- Verify every available manifest SHA, timestamp, ordered parent link,
  gap count, name, total pair count, immutable chunk reference and each
  of the **newest 256** M5 raw chunks plus 3/6/12 derived fingerprints.
- Older historical M5 raw chunks beyond the latest 256 are **NOT read
  again**. Their current contents are therefore **NOT newly SHA certified**.
  Manifest ancestry is proved, not old chunk byte preservation.
- `all_three_bounded_sha_chains_verified=False` (the original whole-archive
  historical wording must NEVER be silently promoted to true).
- `m5_full_historical_raw_sha_verified=False`,
  `m5_historical_raw_chunks_not_reread=total_manifests-256`,
  and `m5_total_manifest_parent_chain_verified=total_manifests`.
- Current latest 12 CLOSED M5 bars and native source H4/Sydney D1 still
  pass through the existing source six-TF context. Stale gaps, H4/D1
  mismatch, open candles and incomplete windows remain NO_SIGNAL.

**M5 >1024 pairs**: STOP/NO_GO pending separately reviewed archive scaling
and improved externally attested checkpoint; DO NOT automatically
truncate/delete original cache. Any root/checkpoint rollback, orphan
chunks, changed listing, wrong SHA, bad native H4/D1 or damaged recent raw
bar fails closed before a receipt.

## Manual-only integration output

The existing PR #142 optional `workflow_dispatch` remains off until
a separate explicit owner repository variable and exact manual choice.
Its GET-only Drive adapter now accepts both truthful SHA evidence modes,
printing `m5_sha_audit_mode`, total manifest SHA-parent count, raw M5
chunks SHA-verified this read, number of historical raw chunks not
re-read, a boolean for full historical raw SHA, and existing masked
tip digests/time/NO_SIGNAL. It does NOT claim that the rolling window
reverified old raw or that historical payload is independently
authenticated.

Manual workflow itself and GitHub Cache writer schedules, secrets,
vendor Twelve Data queries, Drive data, original frozen Forex 102 blobs
and 11 SOURCE_LOCKED Docs are NOT modified. No Mac/MOCHI/local.

## QA evidence and release

24 new hermetic adversarial tests include the exact 256-to-257 boundary,
source-reviewed fixture pins, old/new tamper distinction, M5
orphan/rollback and manifest SHA failures, mutation during multi-read,
real code 3/6/12 derivation, full versus rolling receipt claims,
masked manual output, denied fake proof/counts and the >1024 NO_GO.
The test injects **synthetic** source pins; they are explicitly NOT
source-authorized immutable GitHub root decisions or a live feed run.

A successful PR+independent main CI proves code correctness only.
No real OAuth workflow has yet been dispatched. Real license/retention,
publisher first-known, external anti-rollback, source-owner numeric
B2/S2 0/36, other 14 entry numeric rules, BID/ASK/SL/TP/net R:R
and out-of-sample signal validation remain open. BUY/SELL release NO_GO.

NEXT: owner-approved one-off manual GitHub GET-only workflow using
the real app-created Drive archive; record run ID and observed SHA
scope/number of unread historical M5 chunks, and do not confuse
a stale hourly source tip with actionable intraday M5 data.
