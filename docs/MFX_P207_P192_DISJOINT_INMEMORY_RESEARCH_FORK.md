# MFX P0.207 — Separate the revised 18-Nov D1 for **private, in-memory research only**

**Owner source policy is unchanged.** The selected active P192 EUR/USD daily source starts Australia/Sydney local **2026-11-18** and preserves the originally SHA-sealed 18-Nov native candle. Real subsequent Twelve Data D1 responses have returned one numerically changed OHLC overlap for that label. P0.200 classifies it; P0.204 produces a private SHA-bound nonauthorizing review. Neither is publisher first-known, a legal data entitlement, nor source-owner acceptance of revised D1.

## What this changes

New pure `mfx_cache/p207_p192_d1_disjoint_research_fork.py` consumes the SAME P204 private review and SAME already refetched `NativeFXBatch` currently rejected by P192, and the audited P192 `FreshEpochState` already in memory. No new source request, Drive GET or write, cache prefix, credential, workflow or schedule.

1. **Exact immutable parent custody:** require P204 reviewed original P192 SHA root, one original 18-Nov bar, SHA-root equality, one changed 18-Nov numeric source row, zero source authority flags.
2. **Strict closed D1:** require UTC runner observation and 2m15s post Sydney-local D1 close publication grace, no open/future D1, provider-native MID provenance, monotonically labelled **revised 18-Nov plus optional later closed dates only**. Do not splice pre-18-Nov P171/V1 price history, do not pretend calendar dates are known tradable sessions.
3. **In-memory variant chain:** retain private immutable `NativeFXBar` rows, original and revised source-row SHA references, and deterministic SHA-256-linked row identities for later **private scientific comparison**. Do not overwrite or write a revised P192 manifest, do not assign an approved source vintage or publisher first-known.
4. **Public-safe redaction:** on the **existing P204 diagnosed conflict path only**, log `MFX_P207_P192_REVISED_D1_FORK_INMEMORY_ONLY` with counts and explicit **`NO_SIGNAL` / no writes / no rights / no publisher first-known / no trading**, but never print original/revised SHA, raw OHLC, market dates, session timestamps, private row objects, or the runner clock. On any failure to construct the optional fork, log an unprivileged unavailable marker while the original P200/P192 exception continues unchanged.
5. **No live application:** research-only object exists in process RAM and is discarded with the job. P187 six-TF signal reader **still selects the original P192 epoch**, which remains precisely one SHA-sealed D1 bar and does not promote this variant. The H4-only safe writer path remains independent and its real H4 archive may still append when due. The combined native D1 job remains **RED** with original `P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE`.

## Negative/acceptance tests

Sixteen hermetic tests cover source SHA immutability; exact original-vs-revised source row identity; ban on V1/P171 pre-cutoff data; wrong root and forged permissions; changed/unchanged/metadata source; tampered in-memory hash-chain/replay; future Sydney-local D1; wrong UTC/clock; public log redaction; a real mocked scheduled writer that must still throw the same P192 quarantine, spend **one** existing vendor D1 call, make **no extra** Drive writes (the two existing objects are old P192 state), and retain original P204/P200 logs in order.

The title **does not mean a signed/approved revision fork**. The actual developer output is a nonpersisted capability to inspect candidate source versions in memory. Changing the canonical D1, writing a separate *persistent* research variant, qualifying historical-as-of source prices, or publishing BUY/SELL needs separate source-owner/versioned permission and vendor/publisher provenance (#180). Keep original source numerical 0/36 (#45), account BID/ASK retention/rights (#27), six-TF causality, economics, OOS and release-signoff (#138) as NO-GO.

## Merge and rollback

Review exact PR-head Python3.11 and 3.12 full hermetic QA, A01 frozen Forex original 102 Git blobs and golden, static/security, cross-Python wheel parity, protected squash merge, independently verified `mfx/main-push-full-ci`. Rollback touches only new P207 module, 16 tests, this doc, two narrow importer/marker hunks in the existing writer and corresponding SHA allowlist entries. Original P192 state and all other source code/workflows/cache data remain unchanged. **No broker client, account login, or position order.**
