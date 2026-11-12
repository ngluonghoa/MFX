# A04/P0.85 — two Git-pinned checkpoints / complete bounded M5 SHA verification

## Current real evidence and missing proof

Source main at P0.84 cfdb4cda1424296d9c61d352512c147b1dc5e041. Existing full read-only H4 parity run GitHub Actions #43138482666 / job 130919438343 at 2026-11-12 02:02:08 UTC verified ALL 31 M5 Manifest+Chunk pairs, 372 closed M5 bars, last hour 2026-11-12T00:00:00+00:00, head SHA256 9e27346ebcef2d292f0ce519acffd46d7c01e45b1e31906e31bbda12f38fc629, full_bounded_chain_verified=true. It also verified 7 matched H4 windows and did NOT permit H4 cutover. P0.69 source-pinned genesis 2026-11-10T18:00:00+00:00 SHA256 47320a77ba8a615cd043dbba55b6bc2d4e02ad0f88adf4b229143aca5dde93c0.

Latest existing GitHub Actions read-only tail audit #43155201019 / job 130973426524 at 2026-11-12 04:30:19 UTC verified 3 recent pairs only. The receipt shows 33 M5 manifests, 396 closed M5 bars, last hour 2026-11-12T02:00:00+00:00, SHA 478840990e3a8bc4a745da5d694a98193aa5f614bd1abad92f487a530a213d76, last_hour_lag=1, full_history_audited=false. The independently inspected Drive manifest folder lists 33 M5, 7 native H4, 2 native D1. The 31-pair full audit PLUS later 3-pair tail audit are NOT the same as fresh complete SHA validation of all 33 raw M5 chunks at one time: older bytes were not re-read.

## Pure verifier scope

New tools/mfx_m5_full_sha_two_anchor_audit.py REUSES the existing strict P0.66 pure _m5_archive verifier, which checks every manifest/chunk SHA, parent pointers, exactly 12 closed UTC M5 candles per hour, cumulative counts and M15/M30/H1 derived-bar lineage while archive has at most 256 pairs. P0.85 adds two Git-reviewed immutable anchors (P0.69 genesis and P0.66 31-pair checkpoint), rejects removed or rewritten anchors and rollback behind the 31-pair checkpoint, and re-reads first/checkpoint/latest manifest plus before/after full object-name enumerations to detect changes during audit. No independent external monotonic witness is claimed; a deliberate rollback AFTER the 31-pair checkpoint cannot be ruled out without a newer externally pinned head.

21 hermetic positive/negative tests cover 31/33 records, tampered old/recent chunks, altered checkpoint/root, missing records, rollback to 30, orphan, bad UTC, mutated enumeration during scan, and >256 cap. The module has ZERO HTTP/Drive/vendor/broker IO; no production workflow/cache changes, no Forex source 102/blob or frozen Docs modification. Source H4 replacement, live V2, FX numeric signals, HOT and broker remain DENIED, as do license/session-calendar proofs.

## Next independent production qualification

The current pure proof is source+CI only: do NOT claim it has read the actual latest 33-pair private Drive archive. To produce same-time LIVE full bounded SHA proof, use the existing GitHub P0.66 read-only workflow via separately authorized workflow_dispatch, or the next daily scheduled read-only parity run, without changing cache writers. Reconcile latest root/head with signed GitHub evidence; no automatic merging of external witness or H4 source switch. H4 source reduction requires >=30 exact 48xM5 H4 windows over >=7 real days plus calendar/session and separate owner GO. Sydney D1 remains native. Cloud-only GitHub + Drive, no local/Mac/MOCHI.
